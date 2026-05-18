"""EMMET beta adaptive — global congestion thermostat.

Physical motivation: a fixed beta assumes uniform congestion. Real networks
have stressed and relaxed zones. Beta should respond to the global thermal
state — more congestion-averse when the network is hot, less when cold.

Implementation:
    beta_eff = beta_base * (1 + theta * mean_normalized_load)
    where mean_normalized_load = avg(load/capacity) over all edges, in [0, 1+]

When theta=0, this reduces to fixed beta. When theta>0, beta scales up with
network load. This is a simple feedback mechanism, no learning required.

Strategies tested in this battery:
    - SP
    - LASP
    - EMMET cold        (fixed beta=3.0, no snapshot)
    - EMMET thermal     (fixed beta=3.0, warm-up snapshot + decay + epsilon)
    - EMMET adaptive    (adaptive beta, no snapshot)
    - EMMET full        (adaptive beta + warm-up snapshot + decay + epsilon)
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
THETA         = 1.0    # adaptive beta sensitivity (0 = fixed)
HALF_LIFE     = 100
DECAY         = math.exp(-math.log(2) / HALF_LIFE)
EPSILON       = 0.10

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

def global_temperature(G):
    """Mean normalized load = avg(load/capacity) over all edges."""
    total = 0.0
    n = 0
    for u, v in G.edges():
        total += G[u][v]['load'] / G[u][v]['capacity']
        n += 1
    return total / n if n > 0 else 0.0

def potential(G, current, neighbor, dst, snapshot, beta_eff):
    e = G[current][neighbor]
    congestion = e['load'] / e['capacity']
    edge_key = tuple(sorted([current, neighbor]))
    loss_value = snapshot.get(edge_key, 0)
    try:
        dist = nx.shortest_path_length(G, neighbor, dst, weight='latency')
    except nx.NetworkXNoPath:
        dist = 999
    return ALPHA * dist + beta_eff * congestion + GAMMA * loss_value

def emmet_route(G, src, dst, num_nodes, snapshot, eps_rng=None, adaptive_beta=False):
    max_hops = TTL_FACTOR * num_nodes
    if adaptive_beta:
        temp = global_temperature(G)
        beta_eff = BETA * (1 + THETA * temp)
    else:
        beta_eff = BETA
    path, current, visited, hops = [src], src, set(), 0
    while current != dst and hops < max_hops:
        visited.add(current)
        neighbors = [n for n in G.neighbors(current) if n not in visited]
        if not neighbors:
            return None, 'dead_end'
        ranked = sorted(neighbors,
                        key=lambda n: potential(G, current, n, dst, snapshot, beta_eff))
        if eps_rng is not None and len(ranked) > 1 and eps_rng.random() < EPSILON:
            best = ranked[1]
        else:
            best = ranked[0]
        path.append(best)
        current = best
        hops += 1
    return (path, 'delivered') if current == dst else (None, 'ttl_expired')

def run_warmup(G, traffic_warmup, adaptive_beta=False):
    num_nodes = G.number_of_nodes()
    snapshot = {}
    for src, dst in traffic_warmup:
        if src == dst: continue
        path, _ = emmet_route(G, src, dst, num_nodes, snapshot,
                              adaptive_beta=adaptive_beta)
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

def simulate(G, mode, traffic, snapshot=None, decay=1.0,
             eps_rng=None, adaptive_beta=False):
    num_nodes = G.number_of_nodes()
    total_lat_delivered = 0.0
    losses = delivered = dead = ttl = nopath = 0
    snap = dict(snapshot) if (snapshot and decay < 1.0) else (snapshot or {})

    for src, dst in traffic:
        if src == dst: continue
        if mode == 'sp':
            path, reason = shortest_path_route(G, src, dst)
        elif mode == 'lasp':
            path, reason = lasp_route(G, src, dst)
        else:
            path, reason = emmet_route(G, src, dst, num_nodes, snap,
                                        eps_rng, adaptive_beta=adaptive_beta)

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
    return {'lat_delivered': lat_del, 'losses': losses, 'delivered': delivered,
            'dead': dead, 'ttl': ttl}

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

    # EMMET cold (greedy pure)
    G = builder(*builder_args, topo_seed=seed); reset_graph(G)
    traffic = generate_traffic(list(G.nodes()), TRAFFIC_STEPS, traffic_seed)
    out['emmet_cold'] = simulate(G, 'emmet', traffic, snapshot={})

    # EMMET thermal (snapshot + decay + epsilon, fixed beta)
    G = builder(*builder_args, topo_seed=seed); reset_graph(G)
    warmup_traffic = generate_traffic(list(G.nodes()), warmup_steps, warmup_seed)
    snap = run_warmup(G, warmup_traffic)
    G = builder(*builder_args, topo_seed=seed); reset_graph(G)
    traffic = generate_traffic(list(G.nodes()), TRAFFIC_STEPS, traffic_seed)
    out['emmet_thermal'] = simulate(G, 'emmet', traffic, snapshot=snap,
                                     decay=DECAY,
                                     eps_rng=random.Random(eps_seed))

    # EMMET adaptive (adaptive beta, no snapshot)
    G = builder(*builder_args, topo_seed=seed); reset_graph(G)
    traffic = generate_traffic(list(G.nodes()), TRAFFIC_STEPS, traffic_seed)
    out['emmet_adaptive'] = simulate(G, 'emmet', traffic, snapshot={},
                                      adaptive_beta=True)

    # EMMET full (adaptive beta + thermal)
    G = builder(*builder_args, topo_seed=seed); reset_graph(G)
    warmup_traffic = generate_traffic(list(G.nodes()), warmup_steps, warmup_seed)
    snap = run_warmup(G, warmup_traffic, adaptive_beta=True)
    G = builder(*builder_args, topo_seed=seed); reset_graph(G)
    traffic = generate_traffic(list(G.nodes()), TRAFFIC_STEPS, traffic_seed)
    out['emmet_full'] = simulate(G, 'emmet', traffic, snapshot=snap,
                                  decay=DECAY,
                                  eps_rng=random.Random(eps_seed),
                                  adaptive_beta=True)

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
        jobs.append(('GEANT', build_real, ('Geant.graphml',), s))
    return jobs

def aggregate(results):
    by_scen = {}
    for r in results:
        by_scen.setdefault(r['scenario'], []).append(r)
    summary = []
    strats = ['sp', 'lasp', 'emmet_cold', 'emmet_thermal',
              'emmet_adaptive', 'emmet_full']
    for sc, runs in by_scen.items():
        summ = {'scenario': sc, 'n_runs': len(runs),
                'num_nodes': runs[0]['num_nodes']}
        for strat in strats:
            for key in ['lat_delivered', 'losses', 'delivered']:
                vals = [r[strat][key] for r in runs]
                summ[f'{strat}_{key}_mean'] = statistics.mean(vals)
                summ[f'{strat}_{key}_std']  = statistics.stdev(vals) if len(vals) > 1 else 0.0
        summary.append(summ)
    return summary

if __name__ == '__main__':
    jobs = battery_jobs()
    print(f"Adaptive battery: {len(jobs)} jobs x 6 strategies = {len(jobs)*6} sims")
    workers = max(1, cpu_count() - 4)
    print(f"Using {workers} workers")

    t0 = time.time()
    with Pool(workers) as pool:
        results = []
        for i, r in enumerate(pool.imap_unordered(run_one, jobs, chunksize=4)):
            results.append(r)
            if (i+1) % 100 == 0:
                elapsed = time.time() - t0
                rate = (i+1) / elapsed
                eta = (len(jobs) - (i+1)) / rate
                print(f"  {i+1}/{len(jobs)} | {rate:.1f} jobs/s | ETA {eta/60:.1f} min")
    print(f"\nCompleted in {(time.time()-t0)/60:.1f} min")

    with open(DATA_DIR / 'adaptive_raw_results.json', 'w') as f:
        json.dump(results, f, indent=1)
    summary = aggregate(results)
    with open(DATA_DIR / 'adaptive_summary.json', 'w') as f:
        json.dump(summary, f, indent=2)

    print("\n=== SUMMARY (mean losses) ===")
    print(f"{'Scenario':<20} {'N':>4} {'SP':>7} {'LASP':>7} "
          f"{'COLD':>7} {'THERM':>7} {'ADAPT':>7} {'FULL':>7}")
    for s in summary:
        print(f"{s['scenario']:<20} {s['n_runs']:>4} "
              f"{s['sp_losses_mean']:>7.2f} {s['lasp_losses_mean']:>7.2f} "
              f"{s['emmet_cold_losses_mean']:>7.2f} "
              f"{s['emmet_thermal_losses_mean']:>7.2f} "
              f"{s['emmet_adaptive_losses_mean']:>7.2f} "
              f"{s['emmet_full_losses_mean']:>7.2f}")
