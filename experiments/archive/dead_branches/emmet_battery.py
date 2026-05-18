"""
EMMET full battery — definitive experiment for the paper.

Sweeps:
  n=20   x densities [0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40, 0.50] x 100 seeds
  n=50   x densities [0.05, 0.10, 0.15, 0.20, 0.25, 0.30]             x 100 seeds
  n=100  x densities [0.05, 0.10, 0.15, 0.20]                         x  50 seeds
  Real:  Abilene + GEANT x 100 seeds

Strategies: SP, LASP, EMMET cold, EMMET thermal (warm-up + decay + epsilon).

Audit-clean implementation:
  - Read-only loss snapshot during measurement
  - Half-life decay = 100 steps
  - Epsilon-greedy real exploration (not inert)
  - Identical traffic across strategies (separate RNGs)
  - Lat per DELIVERED packet (not lat / total_latency mix)

Parallelized with multiprocessing across cores.
"""
import random
import statistics
import json
import math
import os
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

# ---------- routing ----------
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

def emmet_route(G, src, dst, num_nodes, snapshot, eps_rng=None):
    max_hops = TTL_FACTOR * num_nodes
    path, current, visited, hops = [src], src, set(), 0
    while current != dst and hops < max_hops:
        visited.add(current)
        neighbors = [n for n in G.neighbors(current) if n not in visited]
        if not neighbors:
            return None, 'dead_end'
        ranked = sorted(neighbors, key=lambda n: potential(G, current, n, dst, snapshot))
        # Epsilon-greedy: with prob EPSILON, pick 2nd-best if available
        if eps_rng is not None and len(ranked) > 1 and eps_rng.random() < EPSILON:
            best = ranked[1]
        else:
            best = ranked[0]
        path.append(best)
        current = best
        hops += 1
    return (path, 'delivered') if current == dst else (None, 'ttl_expired')

def run_warmup(G, traffic_warmup):
    num_nodes = G.number_of_nodes()
    snapshot = {}
    for src, dst in traffic_warmup:
        if src == dst: continue
        path, _ = emmet_route(G, src, dst, num_nodes, snapshot)
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
def simulate(G, mode, traffic, snapshot=None, decay=1.0, eps_rng=None):
    num_nodes = G.number_of_nodes()
    total_lat_delivered = 0.0
    total_lat_attempted = 0.0
    losses = delivered = dead = ttl = nopath = 0
    snap = dict(snapshot) if (snapshot and decay < 1.0) else (snapshot or {})

    for src, dst in traffic:
        if src == dst: continue
        if mode == 'sp':    path, reason = shortest_path_route(G, src, dst)
        elif mode == 'lasp':path, reason = lasp_route(G, src, dst)
        else:               path, reason = emmet_route(G, src, dst, num_nodes, snap, eps_rng)

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

        total_lat_attempted += path_lat
        if not packet_lost:
            delivered += 1
            total_lat_delivered += path_lat

        for u, v in G.edges():
            G[u][v]['load'] *= 0.9

        if decay < 1.0:
            for k in list(snap.keys()):
                snap[k] *= decay

    attempted = delivered + losses + dead + ttl + nopath
    lat_del = total_lat_delivered / delivered if delivered > 0 else 0
    lat_att = total_lat_attempted / attempted if attempted > 0 else 0
    return {
        'lat_delivered': lat_del,
        'lat_attempted': lat_att,
        'losses': losses,
        'delivered': delivered,
        'dead': dead,
        'ttl': ttl,
        'nopath': nopath,
        'attempted': attempted,
    }

# ---------- single (scenario, seed) job ----------
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
    r = simulate(G, 'sp', traffic)
    out['sp'] = r

    # LASP
    G = builder(*builder_args, topo_seed=seed); reset_graph(G)
    traffic = generate_traffic(list(G.nodes()), TRAFFIC_STEPS, traffic_seed)
    r = simulate(G, 'lasp', traffic)
    out['lasp'] = r

    # EMMET cold (greedy pure, no epsilon, no snapshot)
    G = builder(*builder_args, topo_seed=seed); reset_graph(G)
    traffic = generate_traffic(list(G.nodes()), TRAFFIC_STEPS, traffic_seed)
    r = simulate(G, 'emmet', traffic, snapshot={})
    out['emmet_cold'] = r

    # EMMET thermal (warmup + decay + epsilon)
    G = builder(*builder_args, topo_seed=seed); reset_graph(G)
    warmup_traffic = generate_traffic(list(G.nodes()), warmup_steps, warmup_seed)
    snap = run_warmup(G, warmup_traffic)
    G = builder(*builder_args, topo_seed=seed); reset_graph(G)
    traffic = generate_traffic(list(G.nodes()), TRAFFIC_STEPS, traffic_seed)
    r = simulate(G, 'emmet', traffic, snapshot=snap, decay=DECAY,
                 eps_rng=random.Random(eps_seed))
    out['emmet_thermal'] = r

    return out

# ---------- battery plan ----------
def battery_jobs():
    jobs = []
    # n=20 sweep
    for d in [0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40, 0.50]:
        for s in range(100):
            jobs.append((f'ER_n20_p{d:.2f}', build_synthetic, (20, d), s))
    # n=50 sweep
    for d in [0.05, 0.10, 0.15, 0.20, 0.25, 0.30]:
        for s in range(100):
            jobs.append((f'ER_n50_p{d:.2f}', build_synthetic, (50, d), s))
    # n=100 sweep (fewer seeds, only sparse range — most interesting)
    for d in [0.05, 0.10, 0.15, 0.20]:
        for s in range(50):
            jobs.append((f'ER_n100_p{d:.2f}', build_synthetic, (100, d), s))
    # real topologies
    for s in range(100):
        jobs.append(('Abilene', build_real, ('Abilene.graphml',), s))
    for s in range(100):
        jobs.append(('GEANT',   build_real, ('Geant.graphml',),   s))
    return jobs

def aggregate(results):
    """Group results by scenario and compute summary stats."""
    by_scen = {}
    for r in results:
        sc = r['scenario']
        by_scen.setdefault(sc, []).append(r)
    summary = []
    for sc, runs in by_scen.items():
        def col(strategy, key):
            return [r[strategy][key] for r in runs]
        summ = {
            'scenario': sc,
            'n_runs': len(runs),
            'num_nodes': runs[0]['num_nodes'],
        }
        for strat in ['sp', 'lasp', 'emmet_cold', 'emmet_thermal']:
            for key in ['lat_delivered', 'losses', 'delivered', 'dead', 'ttl']:
                vals = col(strat, key)
                summ[f'{strat}_{key}_mean'] = statistics.mean(vals)
                summ[f'{strat}_{key}_std']  = statistics.stdev(vals) if len(vals) > 1 else 0.0
        summary.append(summ)
    return summary

if __name__ == '__main__':
    jobs = battery_jobs()
    print(f"Battery: {len(jobs)} jobs across {cpu_count()} cores")
    print(f"Strategies per job: 4 (SP, LASP, EMMET cold, EMMET thermal)")
    print(f"Total simulations: {len(jobs) * 4}")

    workers = max(1, cpu_count() - 4)
    print(f"Using {workers} workers (4 cores reserved)")

    t0 = time.time()
    with Pool(workers) as pool:
        results = []
        for i, r in enumerate(pool.imap_unordered(run_one, jobs, chunksize=4)):
            results.append(r)
            if (i+1) % 100 == 0:
                elapsed = time.time() - t0
                rate = (i+1) / elapsed
                eta = (len(jobs) - (i+1)) / rate
                print(f"  {i+1}/{len(jobs)} done | {rate:.1f} jobs/s | "
                      f"ETA {eta/60:.1f} min")
    elapsed = time.time() - t0
    print(f"\nBattery completed in {elapsed/60:.1f} minutes")

    # Save raw results
    raw_path = DATA_DIR / 'battery_raw_results.json'
    with open(raw_path, 'w') as f:
        json.dump(results, f, indent=1)
    print(f"Raw results: {raw_path}")

    # Aggregate
    summary = aggregate(results)
    summary_path = DATA_DIR / 'battery_summary.json'
    with open(summary_path, 'w') as f:
        json.dump(summary, f, indent=2)
    print(f"Summary: {summary_path}")

    # Print summary table
    print("\n=== SUMMARY (mean losses) ===")
    print(f"{'Scenario':<20} {'N':>4} {'SP':>8} {'LASP':>8} {'EMMET-c':>8} {'EMMET-t':>8}")
    for s in summary:
        print(f"{s['scenario']:<20} {s['n_runs']:>4} "
              f"{s['sp_losses_mean']:>8.2f} {s['lasp_losses_mean']:>8.2f} "
              f"{s['emmet_cold_losses_mean']:>8.2f} {s['emmet_thermal_losses_mean']:>8.2f}")
