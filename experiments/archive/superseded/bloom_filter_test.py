"""Bloom Filter alternative for the visited set.

Real-world concern (Gemini 1): in a deployed network, the visited set
must travel in the packet header. A literal list of N node IDs grows
linearly with hop count and is unviable at scale.

Alternative: a fixed-size Bloom filter. The filter is set into the
packet header and updated at each hop. It produces false positives
(a node may be reported as 'visited' when it wasn't) but no false
negatives. False positives reduce routing flexibility but never break
loop-freedom.

This script measures: does EMMET full retain its loss-reduction
performance when the visited set is replaced by a Bloom filter of
fixed size in BITS?

We test bloom sizes: 32, 64, 128, 256 bits with 2-3 hash functions.
The 32-bit version is router-friendly (fits in a single IPv6 extension
header byte sequence). 256 bits is generous.
"""
import random
import statistics
import math
import json
import time
from pathlib import Path
from multiprocessing import Pool, cpu_count
import networkx as nx
import hashlib

REPO_ROOT  = Path(__file__).resolve().parents[1]
TOPO_DIR   = REPO_ROOT / 'data' / 'topologies'
DATA_DIR   = REPO_ROOT / 'data'

TRAFFIC_STEPS = 200
ALPHA = 1.0
BETA  = 3.0
GAMMA = 2.0
TTL_FACTOR = 1
THETA      = 5.0
HALF_LIFE  = 500
DECAY      = math.exp(-math.log(2) / HALF_LIFE)
EPSILON    = 0.10

class BloomFilter:
    """Minimal Bloom filter over node IDs."""
    def __init__(self, size_bits, num_hash):
        self.size = size_bits
        self.k = num_hash
        self.bits = 0  # represented as an int

    def _hashes(self, item):
        # Use multiple hashes derived from md5 for determinism
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

    def copy(self):
        c = BloomFilter(self.size, self.k)
        c.bits = self.bits
        return c

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

def emmet_set(G, src, dst, snap, eps_rng=None, adaptive_beta=False):
    """Original EMMET with a Python set as visited."""
    if adaptive_beta:
        n_e = G.number_of_edges()
        temp = sum(G[u][v]['load']/G[u][v]['capacity'] for u,v in G.edges())/n_e if n_e else 0
        beta_eff = BETA * (1 + THETA * temp)
    else:
        beta_eff = BETA
    max_hops = TTL_FACTOR * G.number_of_nodes()
    cur, vis, hops = src, set(), 0
    while cur != dst and hops < max_hops:
        vis.add(cur)
        nbrs = [n for n in G.neighbors(cur) if n not in vis]
        if not nbrs:
            return None, 'dead_end'
        ranked = sorted(nbrs, key=lambda n: potential(G, cur, n, dst, snap, beta_eff))
        if eps_rng and len(ranked) > 1 and eps_rng.random() < EPSILON:
            cur = ranked[1]
        else:
            cur = ranked[0]
        hops += 1
    return ([cur] if cur == dst else None), ('delivered' if cur == dst else 'ttl_expired')

def emmet_bloom(G, src, dst, snap, bloom_size, bloom_k, eps_rng=None, adaptive_beta=False):
    """EMMET with a Bloom filter as the visited set."""
    if adaptive_beta:
        n_e = G.number_of_edges()
        temp = sum(G[u][v]['load']/G[u][v]['capacity'] for u,v in G.edges())/n_e if n_e else 0
        beta_eff = BETA * (1 + THETA * temp)
    else:
        beta_eff = BETA
    max_hops = TTL_FACTOR * G.number_of_nodes()
    bf = BloomFilter(bloom_size, bloom_k)
    cur, hops = src, 0
    while cur != dst and hops < max_hops:
        bf.add(cur)
        nbrs = [n for n in G.neighbors(cur) if n not in bf]
        if not nbrs:
            return None, 'dead_end'
        ranked = sorted(nbrs, key=lambda n: potential(G, cur, n, dst, snap, beta_eff))
        if eps_rng and len(ranked) > 1 and eps_rng.random() < EPSILON:
            cur = ranked[1]
        else:
            cur = ranked[0]
        hops += 1
    return ([cur] if cur == dst else None), ('delivered' if cur == dst else 'ttl_expired')

def warmup(G, traf, adaptive_beta=False):
    snap = {}
    for src, dst in traf:
        if src == dst: continue
        path, _ = emmet_set(G, src, dst, snap, adaptive_beta=adaptive_beta)
        if path is None: continue
        # Use SP-style update for warmup (same in all variants for fairness)
        try:
            full = nx.shortest_path(G, src, dst, weight='latency')
        except nx.NetworkXNoPath:
            continue
        for i in range(len(full)-1):
            u, v = full[i], full[i+1]
            e = G[u][v]
            e['load'] += 1
            if e['load'] > e['capacity']:
                e['loss'] += 1
                break
        for u, v in G.edges():
            G[u][v]['load'] *= 0.9
    return {tuple(sorted([u,v])): G[u][v]['loss'] for u,v in G.edges()}

def simulate_set(G, traffic, snap, eps_rng):
    snap_l = dict(snap)
    losses = delivered = 0
    total_lat = 0.0
    for src, dst in traffic:
        if src == dst: continue
        if adaptive_beta_global:
            n_e = G.number_of_edges()
            temp = sum(G[u][v]['load']/G[u][v]['capacity'] for u,v in G.edges())/n_e if n_e else 0
            beta_eff = BETA * (1 + THETA * temp)
        else:
            beta_eff = BETA
        # Inline EMMET routing for full path tracking
        max_hops = TTL_FACTOR * G.number_of_nodes()
        path, cur, vis, hops = [src], src, set(), 0
        while cur != dst and hops < max_hops:
            vis.add(cur)
            nbrs = [n for n in G.neighbors(cur) if n not in vis]
            if not nbrs: break
            ranked = sorted(nbrs, key=lambda n: potential(G, cur, n, dst, snap_l, beta_eff))
            if eps_rng and len(ranked) > 1 and eps_rng.random() < EPSILON:
                cur = ranked[1]
            else:
                cur = ranked[0]
            path.append(cur)
            hops += 1
        if cur != dst:
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
                break
            total_lat += e['latency']
        if not lost:
            delivered += 1
        for u, v in G.edges():
            G[u][v]['load'] *= 0.9
        for k in list(snap_l.keys()):
            snap_l[k] *= DECAY
    return {'losses': losses, 'delivered': delivered,
            'lat': total_lat/delivered if delivered else 0}

def simulate_bloom(G, traffic, snap, eps_rng, bloom_size, bloom_k):
    snap_l = dict(snap)
    losses = delivered = 0
    total_lat = 0.0
    for src, dst in traffic:
        if src == dst: continue
        if adaptive_beta_global:
            n_e = G.number_of_edges()
            temp = sum(G[u][v]['load']/G[u][v]['capacity'] for u,v in G.edges())/n_e if n_e else 0
            beta_eff = BETA * (1 + THETA * temp)
        else:
            beta_eff = BETA
        max_hops = TTL_FACTOR * G.number_of_nodes()
        bf = BloomFilter(bloom_size, bloom_k)
        path, cur, hops = [src], src, 0
        while cur != dst and hops < max_hops:
            bf.add(cur)
            nbrs = [n for n in G.neighbors(cur) if n not in bf]
            if not nbrs: break
            ranked = sorted(nbrs, key=lambda n: potential(G, cur, n, dst, snap_l, beta_eff))
            if eps_rng and len(ranked) > 1 and eps_rng.random() < EPSILON:
                cur = ranked[1]
            else:
                cur = ranked[0]
            path.append(cur)
            hops += 1
        if cur != dst:
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
                break
            total_lat += e['latency']
        if not lost:
            delivered += 1
        for u, v in G.edges():
            G[u][v]['load'] *= 0.9
        for k in list(snap_l.keys()):
            snap_l[k] *= DECAY
    return {'losses': losses, 'delivered': delivered,
            'lat': total_lat/delivered if delivered else 0}

# Need adaptive_beta as a module-level toggle for the simulate fn
adaptive_beta_global = True

def run_one(args):
    label, builder, builder_args, seed, mode, bloom_size, bloom_k = args
    G = builder(*builder_args, topo_seed=seed)
    n = G.number_of_nodes()
    warmup_steps = max(20, n*5)
    G = builder(*builder_args, topo_seed=seed); reset_graph(G)
    wt = gen_traffic(list(G.nodes()), warmup_steps, seed + 300000)
    snap = warmup(G, wt, adaptive_beta=True)
    G2 = builder(*builder_args, topo_seed=seed); reset_graph(G2)
    traf = gen_traffic(list(G2.nodes()), TRAFFIC_STEPS, seed + 100000)
    eps_rng = random.Random(seed + 400000)
    if mode == 'set':
        res = simulate_set(G2, traf, snap, eps_rng)
    else:
        res = simulate_bloom(G2, traf, snap, eps_rng, bloom_size, bloom_k)
    return {'scenario': label, 'seed': seed, 'mode': mode,
            'bloom_size': bloom_size, 'bloom_k': bloom_k, **res}

if __name__ == '__main__':
    scenarios = [
        ('ER_n20_p0.10', build_synthetic, (20, 0.10), 100),
        ('ER_n50_p0.05', build_synthetic, (50, 0.05), 100),
        ('Abilene',      build_real, ('Abilene.graphml',), 100),
        ('GEANT',        build_real, ('Geant.graphml',),   100),
    ]

    variants = [
        ('set',   None, None),
        ('bloom', 32,  2),
        ('bloom', 64,  2),
        ('bloom', 128, 3),
        ('bloom', 256, 3),
    ]

    print(f'Bloom filter battery: {len(scenarios)} scenarios x {len(variants)} variants')
    jobs = []
    for sname, builder, args, seeds in scenarios:
        for v in variants:
            for s in range(seeds):
                jobs.append((sname, builder, args, s, v[0], v[1], v[2]))

    workers = max(1, cpu_count() - 4)
    print(f'Total jobs: {len(jobs)} | workers: {workers}')

    t0 = time.time()
    with Pool(workers) as pool:
        results = pool.map(run_one, jobs)
    print(f'Done in {(time.time()-t0)/60:.1f} min')

    by = {}
    for r in results:
        key = (r['scenario'], r['mode'], r['bloom_size'])
        by.setdefault(key, []).append(r)

    print()
    print(f"{'Scenario':<18} {'Mode':<10} {'Size':>6} {'Loss mean':>12} {'Loss std':>10} {'Delivered':>10}")
    summary = []
    for key, runs in sorted(by.items()):
        sc, mode, sz = key
        losses = [r['losses'] for r in runs]
        delivered = [r['delivered'] for r in runs]
        size_str = str(sz) if sz else 'unbounded'
        print(f"{sc:<18} {mode:<10} {size_str:>6} "
              f"{statistics.mean(losses):>12.2f} {statistics.stdev(losses):>10.2f} "
              f"{statistics.mean(delivered):>10.1f}")
        summary.append({
            'scenario': sc, 'mode': mode, 'bloom_size': sz,
            'losses_mean': statistics.mean(losses),
            'losses_std':  statistics.stdev(losses),
            'delivered_mean': statistics.mean(delivered),
        })

    with open(DATA_DIR / 'bloom_filter_summary.json', 'w') as f:
        json.dump(summary, f, indent=2)
    print(f"\nSaved to data/bloom_filter_summary.json")
