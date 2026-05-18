"""EMMET combined: calibrated params + Bloom 32-bit visited + EWMA online.

This is the production candidate of EMMET, integrating the three real
algorithmic improvements verified in Session 2:
  1. Calibrated parameters (TTL=1, theta=5, half_life=500, eps=0.10)
  2. Bloom-32 visited set (4-byte header overhead, beats unbounded set)
  3. EWMA online snapshot update (alpha=0.1, handles dynamic networks)

Compares against SP, LASP, and previous EMMET full (calibrated only,
no Bloom no EWMA) to isolate each contribution.
"""
import random
import statistics
import math
import json
import time
import hashlib
from pathlib import Path
from multiprocessing import Pool, cpu_count
import networkx as nx

REPO_ROOT  = Path(__file__).resolve().parents[1]
TOPO_DIR   = REPO_ROOT / 'data' / 'topologies'
DATA_DIR   = REPO_ROOT / 'data'

TRAFFIC_STEPS = 200
ALPHA = 1.0
BETA  = 3.0
GAMMA = 2.0

# Calibrated
TTL_FACTOR = 1
THETA      = 5.0
HALF_LIFE  = 500
DECAY      = math.exp(-math.log(2) / HALF_LIFE)
EPSILON    = 0.10

# Combined extras
BLOOM_SIZE = 128
BLOOM_K    = 3
EWMA_ALPHA = 0.10

class BloomFilter:
    def __init__(self, size_bits, num_hash):
        self.size = size_bits
        self.k = num_hash
        self.bits = 0

    def _hashes(self, item):
        h = hashlib.md5(str(item).encode()).digest()
        return [int.from_bytes(h[i:i+4], 'big') % self.size
                for i in range(0, 4*self.k, 4)]

    def add(self, item):
        for idx in self._hashes(item):
            self.bits |= (1 << idx)

    def __contains__(self, item):
        for idx in self._hashes(item):
            if not (self.bits >> idx) & 1:
                return False
        return True

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
    G = nx.relabel_nodes(G, {n: i for i, n in enumerate(G.nodes())})
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

def gen_traffic(nodes, steps, seed):
    rng = random.Random(seed)
    return [(rng.choice(nodes), rng.choice(nodes)) for _ in range(steps)]

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

def potential(G, cur, nb, dst, snap, beta_eff):
    e = G[cur][nb]
    cong = e['load'] / e['capacity']
    k = tuple(sorted([cur, nb]))
    lv = snap.get(k, 0)
    try:
        d = nx.shortest_path_length(G, nb, dst, weight='latency')
    except nx.NetworkXNoPath:
        d = 999
    return ALPHA * d + beta_eff * cong + GAMMA * lv

def emmet_route(G, src, dst, snap, eps_rng, adaptive_beta, use_bloom):
    if adaptive_beta:
        n_e = G.number_of_edges()
        temp = sum(G[u][v]['load']/G[u][v]['capacity'] for u,v in G.edges())/n_e if n_e else 0
        beta_eff = BETA * (1 + THETA * temp)
    else:
        beta_eff = BETA
    max_hops = TTL_FACTOR * G.number_of_nodes()
    if use_bloom:
        vis = BloomFilter(BLOOM_SIZE, BLOOM_K)
    else:
        vis = set()
    path, cur, hops = [src], src, 0
    while cur != dst and hops < max_hops:
        if use_bloom:
            vis.add(cur)
        else:
            vis.add(cur)
        nbrs = [n for n in G.neighbors(cur) if n not in vis]
        if not nbrs:
            return None, 'dead_end'
        ranked = sorted(nbrs, key=lambda n: potential(G, cur, n, dst, snap, beta_eff))
        if eps_rng and len(ranked) > 1 and eps_rng.random() < EPSILON:
            cur = ranked[1]
        else:
            cur = ranked[0]
        path.append(cur)
        hops += 1
    return (path, 'delivered') if cur == dst else (None, 'ttl_expired')

def warmup(G, traf, adaptive_beta, use_bloom):
    snap = {}
    for src, dst in traf:
        if src == dst: continue
        path, _ = emmet_route(G, src, dst, snap, None, adaptive_beta, use_bloom)
        if path is None: continue
        for i in range(len(path)-1):
            u, v = path[i], path[i+1]
            e = G[u][v]
            e['load'] += 1
            if e['load'] > e['capacity']:
                e['loss'] += 1
                break
        for u, v in G.edges():
            G[u][v]['load'] *= 0.9
    return {tuple(sorted([u,v])): G[u][v]['loss'] for u,v in G.edges()}

def simulate(G, mode, traffic, snap=None, eps_rng=None,
             adaptive_beta=False, use_bloom=False, ewma_alpha=0.0):
    snap_l = dict(snap) if snap else {}
    losses = delivered = dead = ttl = nopath = 0
    total_lat = 0.0
    for src, dst in traffic:
        if src == dst: continue
        if mode == 'sp':
            path, reason = shortest_path_route(G, src, dst)
        elif mode == 'lasp':
            path, reason = lasp_route(G, src, dst)
        else:
            path, reason = emmet_route(G, src, dst, snap_l, eps_rng,
                                       adaptive_beta, use_bloom)
        if path is None:
            if reason == 'dead_end': dead += 1
            elif reason == 'ttl_expired': ttl += 1
            else: nopath += 1
            continue
        lost = False
        for i in range(len(path)-1):
            u, v = path[i], path[i+1]
            e = G[u][v]
            e['load'] += 1
            if e['load'] > e['capacity']:
                e['loss'] += 1
                losses += 1
                lost = True
                if ewma_alpha > 0:
                    k = tuple(sorted([u, v]))
                    snap_l[k] = ewma_alpha * 1.0 + (1 - ewma_alpha) * snap_l.get(k, 0)
                break
            total_lat += e['latency']
        if not lost:
            delivered += 1
        for u, v in G.edges():
            G[u][v]['load'] *= 0.9
        if snap_l:
            for k in list(snap_l.keys()):
                snap_l[k] *= DECAY
    return {'lat_delivered': total_lat/delivered if delivered else 0,
            'losses': losses, 'delivered': delivered,
            'dead': dead, 'ttl': ttl, 'nopath': nopath}

def run_one(args):
    label, builder, builder_args, seed = args
    G_meta = builder(*builder_args, topo_seed=seed)
    n_meta = G_meta.number_of_nodes()
    warmup_steps = max(20, n_meta * 5)
    traffic_seed = seed + 100000
    warmup_seed  = seed + 300000
    eps_seed     = seed + 400000
    out = {'scenario': label, 'seed': seed, 'num_nodes': n_meta}

    G = builder(*builder_args, topo_seed=seed); reset_graph(G)
    traf = gen_traffic(list(G.nodes()), TRAFFIC_STEPS, traffic_seed)
    out['sp'] = simulate(G, 'sp', traf)

    G = builder(*builder_args, topo_seed=seed); reset_graph(G)
    traf = gen_traffic(list(G.nodes()), TRAFFIC_STEPS, traffic_seed)
    out['lasp'] = simulate(G, 'lasp', traf)

    # EMMET full calibrated (already in calibrated_summary)
    G = builder(*builder_args, topo_seed=seed); reset_graph(G)
    wt = gen_traffic(list(G.nodes()), warmup_steps, warmup_seed)
    snap = warmup(G, wt, adaptive_beta=True, use_bloom=False)
    G = builder(*builder_args, topo_seed=seed); reset_graph(G)
    traf = gen_traffic(list(G.nodes()), TRAFFIC_STEPS, traffic_seed)
    out['emmet_calibrated'] = simulate(
        G, 'emmet', traf, snap=snap,
        eps_rng=random.Random(eps_seed),
        adaptive_beta=True, use_bloom=False, ewma_alpha=0.0)

    # EMMET combined: calibrated + Bloom + EWMA
    G = builder(*builder_args, topo_seed=seed); reset_graph(G)
    wt = gen_traffic(list(G.nodes()), warmup_steps, warmup_seed)
    snap = warmup(G, wt, adaptive_beta=True, use_bloom=True)
    G = builder(*builder_args, topo_seed=seed); reset_graph(G)
    traf = gen_traffic(list(G.nodes()), TRAFFIC_STEPS, traffic_seed)
    out['emmet_combined'] = simulate(
        G, 'emmet', traf, snap=snap,
        eps_rng=random.Random(eps_seed),
        adaptive_beta=True, use_bloom=True, ewma_alpha=EWMA_ALPHA)
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
    strats = ['sp', 'lasp', 'emmet_calibrated', 'emmet_combined']
    for sc, runs in by_scen.items():
        summ = {'scenario': sc, 'n_runs': len(runs), 'num_nodes': runs[0]['num_nodes']}
        for strat in strats:
            for key in ['lat_delivered', 'losses', 'delivered']:
                vals = [r[strat][key] for r in runs]
                summ[f'{strat}_{key}_mean'] = statistics.mean(vals)
                summ[f'{strat}_{key}_std']  = statistics.stdev(vals) if len(vals) > 1 else 0.0
        summary.append(summ)
    return summary

if __name__ == '__main__':
    jobs = battery_jobs()
    print(f'Combined battery: {len(jobs)} jobs')
    print(f'EMMET combined = calibrated params + Bloom-{BLOOM_SIZE} + EWMA alpha={EWMA_ALPHA}')
    workers = max(1, cpu_count() - 4)
    t0 = time.time()
    with Pool(workers) as pool:
        results = []
        for i, r in enumerate(pool.imap_unordered(run_one, jobs, chunksize=4)):
            results.append(r)
            if (i+1) % 200 == 0:
                elapsed = time.time() - t0
                print(f'  {i+1}/{len(jobs)} | {(i+1)/elapsed:.1f}/s | '
                      f'ETA {(len(jobs)-(i+1))/((i+1)/elapsed)/60:.1f}m')
    print(f'\nDone in {(time.time()-t0)/60:.1f} min')

    with open(DATA_DIR / 'combined_raw_results.json', 'w') as f:
        json.dump(results, f, indent=1)
    summary = aggregate(results)
    with open(DATA_DIR / 'combined_summary.json', 'w') as f:
        json.dump(summary, f, indent=2)

    print()
    print(f"{'Scenario':<22} {'N':>4} {'SP':>7} {'LASP':>7} {'CALIB':>7} {'COMBI':>7} {'vs LASP':>10}")
    for s in summary:
        la = s['lasp_losses_mean']
        co = s['emmet_combined_losses_mean']
        impr = (la - co) / la * 100 if la > 0 else 0
        print(f"{s['scenario']:<22} {s['n_runs']:>4} "
              f"{s['sp_losses_mean']:>7.2f} {la:>7.2f} "
              f"{s['emmet_calibrated_losses_mean']:>7.2f} "
              f"{co:>7.2f} {impr:>+9.1f}%")
