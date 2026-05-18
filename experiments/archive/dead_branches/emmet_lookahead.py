"""EMMET lookahead — physically-motivated 2-step horizon.

Physics: a particle with inertia 'sees' beyond the immediate next step.
A purely local gradient minimum may lead to a topological cul-de-sac
two hops ahead. EMMET-lookahead evaluates the aggregated potential
of (current -> n) + min over (n -> nn) for one extra step.

This is NOT a snapshot mechanism — it's an algorithmic refinement
to the routing rule itself. Compatible with both cold and thermal modes.

Tested combinations:
  - SP                              (baseline)
  - LASP                            (load-aware baseline)
  - EMMET cold     (greedy, h=1)    (current canonical cold)
  - EMMET cold-LA  (greedy, h=2)    (cold + lookahead 2)
  - EMMET thermal  (greedy, h=1, snapshot+decay+epsilon)
  - EMMET thermal-LA (greedy, h=2, snapshot+decay+epsilon)
"""
import random
import statistics
import json
import math
import time
from pathlib import Path
from multiprocessing import Pool, cpu_count
import networkx as nx

REPO_ROOT  = Path(__file__).resolve().parents[1]
TOPO_DIR   = REPO_ROOT / 'data' / 'topologies'
DATA_DIR   = REPO_ROOT / 'data'

TRAFFIC_STEPS = 200
TTL_FACTOR    = 2
ALPHA         = 1.0
BETA          = 3.0
GAMMA         = 2.0
HALF_LIFE     = 100
DECAY         = math.exp(-math.log(2) / HALF_LIFE)
EPSILON       = 0.10

# ---------- builders ----------
def build_synthetic(num_nodes, density, topo_seed):
    rng = random.Random(topo_seed)
    G = nx.erdos_renyi_graph(num_nodes, density, seed=topo_seed)
    for u, v in G.edges():
        G[u][v]['latency']  = rng.uniform(1, 5)
        G[u][v]['capacity'] = rng.randint(3, 6)
        G[u][v]['load']     = 0
        G[u][v]['loss']     = 0
    return G

def build_real(filename, topo_seed):
    G = nx.read_graphml(str(TOPO_DIR / filename))
    G = nx.Graph(G)
    mapping = {n: i for i, n in enumerate(G.nodes())}
    G = nx.relabel_nodes(G, mapping)
    rng = random.Random(topo_seed)
    for u, v in G.edges():
        G[u][v]['latency']  = rng.uniform(1, 5)
        G[u][v]['capacity'] = rng.randint(3, 6)
        G[u][v]['load']     = 0
        G[u][v]['loss']     = 0
    return G

def reset_graph(G):
    for u, v in G.edges():
        G[u][v]['load'] = 0
        G[u][v]['loss'] = 0

def generate_traffic(nodes_list, steps, traffic_seed):
    rng = random.Random(traffic_seed)
    return [(rng.choice(nodes_list), rng.choice(nodes_list)) for _ in range(steps)]

# ---------- routing primitives ----------
def shortest_path_route(G, src, dst):
    try:
        return nx.shortest_path(G, src, dst, weight='latency'), 'delivered'
    except nx.NetworkXNoPath:
        return None, 'no_path'

def lasp_route(G, src, dst):
    def w(u, v, d):
        return d['latency'] * (1 + d['load'] / d['capacity'])
    try:
        return nx.shortest_path(G, src, dst, weight=w), 'delivered'
    except nx.NetworkXNoPath:
        return None, 'no_path'

def potential(G, current, neighbor, dst, snapshot):
    e = G[current][neighbor]
    congestion = e['load'] / e['capacity']
    edge_key = tuple(sorted([current, neighbor]))
    loss_value = snapshot.get(edge_key, 0)
    try:
        dist = nx.shortest_path_length(G, neighbor, dst, weight='latency')
    except nx.NetworkXNoPath:
        dist = 999
    return ALPHA * dist + BETA * congestion + GAMMA * loss_value

def potential_lookahead(G, current, neighbor, dst, snapshot, visited, horizon=2):
    """Aggregate potential over `horizon` steps ahead, taking min over each step."""
    if neighbor == dst:
        return potential(G, current, neighbor, dst, snapshot)
    p1 = potential(G, current, neighbor, dst, snapshot)
    if horizon <= 1:
        return p1
    # Look one more step from neighbor — exclude visited nodes and current
    blocked = set(visited) | {current}
    next_neighbors = [nn for nn in G.neighbors(neighbor) if nn not in blocked]
    if not next_neighbors:
        # No exit from this neighbor; penalize it heavily
        return p1 + 999
    p2 = min(potential(G, neighbor, nn, dst, snapshot) for nn in next_neighbors)
    return p1 + p2

def emmet_route(G, src, dst, num_nodes, snapshot, eps_rng=None, horizon=1):
    max_hops = TTL_FACTOR * num_nodes
    path, current, visited, hops = [src], src, set(), 0
    while current != dst and hops < max_hops:
        visited.add(current)
        neighbors = [n for n in G.neighbors(current) if n not in visited]
        if not neighbors:
            return None, 'dead_end'
        if horizon > 1:
            ranked = sorted(neighbors, key=lambda n: potential_lookahead(
                G, current, n, dst, snapshot, visited, horizon=horizon))
        else:
            ranked = sorted(neighbors, key=lambda n: potential(
                G, current, n, dst, snapshot))
        if eps_rng is not None and len(ranked) > 1 and eps_rng.random() < EPSILON:
            best = ranked[1]
        else:
            best = ranked[0]
        path.append(best)
        current = best
        hops += 1
    return (path, 'delivered') if current == dst else (None, 'ttl_expired')

def run_warmup(G, traffic_warmup, horizon=1):
    num_nodes = G.number_of_nodes()
    snapshot = {}
    for src, dst in traffic_warmup:
        if src == dst: continue
        path, _ = emmet_route(G, src, dst, num_nodes, snapshot, horizon=horizon)
        if path is None: continue
        for i in range(len(path) - 1):
            u, v = path[i], path[i+1]
            e = G[u][v]
            e['load'] += 1
            if e['load'] > e['capacity']:
                e['loss'] += 1
                break
        for u, v in G.edges():
            G[u][v]['load'] *= 0.9
    out = {}
    for u, v in G.edges():
        out[tuple(sorted([u, v]))] = G[u][v]['loss']
    return out

# ---------- simulator ----------
def simulate(G, mode, traffic, snapshot=None, decay=1.0, eps_rng=None, horizon=1):
    num_nodes = G.number_of_nodes()
    total_lat_delivered = 0.0
    losses = delivered = dead = ttl = nopath = 0
    snap = dict(snapshot) if (snapshot and decay < 1.0) else (snapshot or {})

    for src, dst in traffic:
        if src == dst: continue
        if mode == 'sp':    path, reason = shortest_path_route(G, src, dst)
        elif mode == 'lasp':path, reason = lasp_route(G, src, dst)
        else:               path, reason = emmet_route(G, src, dst, num_nodes,
                                                        snap, eps_rng, horizon=horizon)
        if path is None:
            if reason == 'dead_end': dead += 1
            elif reason == 'ttl_expired': ttl += 1
            else: nopath += 1
            continue

        packet_lost = False
        path_lat = 0.0
        for i in range(len(path) - 1):
            u, v = path[i], path[i+1]
            e = G[u][v]
            e['load'] += 1
            if e['load'] > e['capacity']:
                e['loss'] += 1; losses += 1; packet_lost = True; break
            path_lat += e['latency']

        if not packet_lost:
            delivered += 1
            total_lat_delivered += path_lat

        for u, v in G.edges():
            G[u][v]['load'] *= 0.9

        if decay < 1.0:
            for k in list(snap.keys()):
                snap[k] *= decay

    lat_del = total_lat_delivered / delivered if delivered > 0 else 0
    return {
        'lat_delivered': lat_del,
        'losses': losses,
        'delivered': delivered,
        'dead': dead,
        'ttl': ttl,
        'nopath': nopath,
    }

# ---------- single-job ----------
def run_one(args):
    scenario_label, builder, builder_args, seed = args
    G = builder(*builder_args, topo_seed=seed)
    num_nodes = G.number_of_nodes()
    warmup_steps = max(20, num_nodes * 5)
    traffic_seed = seed + 100000
    warmup_seed  = seed + 300000
    eps_seed     = seed + 400000

    out = {'scenario': scenario_label, 'seed': seed, 'num_nodes': num_nodes}

    # SP
    G = builder(*builder_args, topo_seed=seed); reset_graph(G)
    traffic = generate_traffic(list(G.nodes()), TRAFFIC_STEPS, traffic_seed)
    out['sp'] = simulate(G, 'sp', traffic)

    # LASP
    G = builder(*builder_args, topo_seed=seed); reset_graph(G)
    traffic = generate_traffic(list(G.nodes()), TRAFFIC_STEPS, traffic_seed)
    out['lasp'] = simulate(G, 'lasp', traffic)

    # EMMET cold (h=1, no eps)
    G = builder(*builder_args, topo_seed=seed); reset_graph(G)
    traffic = generate_traffic(list(G.nodes()), TRAFFIC_STEPS, traffic_seed)
    out['emmet_cold'] = simulate(G, 'emmet', traffic, snapshot={}, horizon=1)

    # EMMET cold + lookahead h=2 (no eps)
    G = builder(*builder_args, topo_seed=seed); reset_graph(G)
    traffic = generate_traffic(list(G.nodes()), TRAFFIC_STEPS, traffic_seed)
    out['emmet_cold_la2'] = simulate(G, 'emmet', traffic, snapshot={}, horizon=2)

    # EMMET thermal (h=1)
    G = builder(*builder_args, topo_seed=seed); reset_graph(G)
    warmup_traffic = generate_traffic(list(G.nodes()), warmup_steps, warmup_seed)
    snap = run_warmup(G, warmup_traffic, horizon=1)
    G = builder(*builder_args, topo_seed=seed); reset_graph(G)
    traffic = generate_traffic(list(G.nodes()), TRAFFIC_STEPS, traffic_seed)
    out['emmet_thermal'] = simulate(G, 'emmet', traffic, snapshot=snap,
                                     decay=DECAY,
                                     eps_rng=random.Random(eps_seed),
                                     horizon=1)

    # EMMET thermal + lookahead h=2
    G = builder(*builder_args, topo_seed=seed); reset_graph(G)
    warmup_traffic = generate_traffic(list(G.nodes()), warmup_steps, warmup_seed)
    snap = run_warmup(G, warmup_traffic, horizon=2)
    G = builder(*builder_args, topo_seed=seed); reset_graph(G)
    traffic = generate_traffic(list(G.nodes()), TRAFFIC_STEPS, traffic_seed)
    out['emmet_thermal_la2'] = simulate(G, 'emmet', traffic, snapshot=snap,
                                         decay=DECAY,
                                         eps_rng=random.Random(eps_seed),
                                         horizon=2)
    return out

def battery_jobs():
    jobs = []
    for d in [0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40, 0.50]:
        for s in range(100):
            jobs.append((f'ER_n20_p{d:.2f}', build_synthetic, (20, d), s))
    for d in [0.05, 0.10, 0.15, 0.20, 0.25, 0.30]:
        for s in range(100):
            jobs.append((f'ER_n50_p{d:.2f}', build_synthetic, (50, d), s))
    for d in [0.05, 0.10, 0.15, 0.20]:
        for s in range(50):
            jobs.append((f'ER_n100_p{d:.2f}', build_synthetic, (100, d), s))
    for s in range(100):
        jobs.append(('Abilene', build_real, ('Abilene.graphml',), s))
    for s in range(100):
        jobs.append(('GEANT',   build_real, ('Geant.graphml',),   s))
    return jobs

STRATS = ['sp', 'lasp', 'emmet_cold', 'emmet_cold_la2',
          'emmet_thermal', 'emmet_thermal_la2']

def aggregate(results):
    by_scen = {}
    for r in results:
        by_scen.setdefault(r['scenario'], []).append(r)
    summary = []
    for sc, runs in by_scen.items():
        summ = {'scenario': sc, 'n_runs': len(runs),
                'num_nodes': runs[0]['num_nodes']}
        for strat in STRATS:
            for key in ['lat_delivered', 'losses', 'delivered', 'dead', 'ttl']:
                vals = [r[strat][key] for r in runs]
                summ[f'{strat}_{key}_mean'] = statistics.mean(vals)
                summ[f'{strat}_{key}_std']  = statistics.stdev(vals) if len(vals) > 1 else 0.0
        summary.append(summ)
    return summary

if __name__ == '__main__':
    jobs = battery_jobs()
    workers = max(1, cpu_count() - 4)
    print(f"Lookahead battery: {len(jobs)} jobs x 6 strategies = {len(jobs)*6} sims")
    print(f"Using {workers} workers")

    t0 = time.time()
    results = []
    with Pool(workers) as pool:
        for i, r in enumerate(pool.imap_unordered(run_one, jobs, chunksize=4)):
            results.append(r)
            if (i+1) % 100 == 0:
                rate = (i+1) / (time.time() - t0)
                eta = (len(jobs) - (i+1)) / rate / 60
                print(f"  {i+1}/{len(jobs)} | {rate:.1f} jobs/s | ETA {eta:.1f} min")
    print(f"Battery done in {(time.time() - t0)/60:.1f} min")

    with open(DATA_DIR / 'lookahead_raw_results.json', 'w') as f:
        json.dump(results, f, indent=1)
    summary = aggregate(results)
    with open(DATA_DIR / 'lookahead_summary.json', 'w') as f:
        json.dump(summary, f, indent=2)

    print(f"\n{'Scenario':<22} {'N':>4} {'cold':>7} {'cold-LA':>8} {'therm':>7} {'therm-LA':>9}")
    for s in summary:
        print(f"{s['scenario']:<22} {s['n_runs']:>4} "
              f"{s['emmet_cold_losses_mean']:>7.2f} "
              f"{s['emmet_cold_la2_losses_mean']:>8.2f} "
              f"{s['emmet_thermal_losses_mean']:>7.2f} "
              f"{s['emmet_thermal_la2_losses_mean']:>9.2f}")
