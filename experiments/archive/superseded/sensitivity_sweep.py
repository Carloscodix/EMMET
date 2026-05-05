"""T2.5 — Real parameter sensitivity sweep.

Sweeps over TTL_FACTOR, theta, epsilon, half_life one at a time on a
representative scenario (ER n=20 p=0.10 — sparse regime where EMMET's
contribution is largest). 100 seeds each.

Output: data/sensitivity_summary.json
"""
import random
import statistics
import math
import json
import time
from pathlib import Path
from multiprocessing import Pool, cpu_count
import networkx as nx

REPO_ROOT  = Path(__file__).resolve().parents[1]
DATA_DIR   = REPO_ROOT / 'data'

TRAFFIC_STEPS = 200
ALPHA         = 1.0
BETA          = 3.0
GAMMA         = 2.0

# Defaults — vary one at a time
DEF_TTL_FACTOR = 2
DEF_THETA      = 1.0
DEF_EPSILON    = 0.10
DEF_HALF_LIFE  = 100

# Sweeps
SWEEP_TTL      = [1, 2, 3, 5]
SWEEP_THETA    = [0.0, 0.5, 1.0, 2.0, 5.0]
SWEEP_EPSILON  = [0.0, 0.05, 0.10, 0.20, 0.30]
SWEEP_HALF     = [25, 50, 100, 200, 500]

N_NODES        = 20
DENSITY        = 0.10
N_SEEDS        = 100

def build_graph(seed):
    rng = random.Random(seed)
    G = nx.erdos_renyi_graph(N_NODES, DENSITY, seed=seed)
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

def potential(G, current, neighbor, dst, snapshot, beta_eff):
    e = G[current][neighbor]
    cong = e['load'] / e['capacity']
    edge_key = tuple(sorted([current, neighbor]))
    loss_v = snapshot.get(edge_key, 0)
    try:
        d = nx.shortest_path_length(G, neighbor, dst, weight='latency')
    except nx.NetworkXNoPath:
        d = 999
    return ALPHA * d + beta_eff * cong + GAMMA * loss_v

def emmet(G, src, dst, snap, ttl_factor, theta, eps, eps_rng):
    n_e = G.number_of_edges()
    temp = sum(G[u][v]['load']/G[u][v]['capacity'] for u,v in G.edges())/n_e if n_e else 0
    beta_eff = BETA * (1 + theta * temp)
    max_hops = ttl_factor * G.number_of_nodes()
    cur, vis, hops = src, set(), 0
    while cur != dst and hops < max_hops:
        vis.add(cur)
        nbrs = [n for n in G.neighbors(cur) if n not in vis]
        if not nbrs:
            return None
        ranked = sorted(nbrs, key=lambda n: potential(G, cur, n, dst, snap, beta_eff))
        if eps_rng and len(ranked) > 1 and eps_rng.random() < eps:
            cur = ranked[1]
        else:
            cur = ranked[0]
        hops += 1
    return [cur] if cur == dst else None

def warmup(G, traf, ttl_factor, theta, eps):
    snap = {}
    rng = random.Random(0)  # deterministic for warmup
    for src, dst in traf:
        if src == dst: continue
        path = emmet(G, src, dst, snap, ttl_factor, theta, eps, rng)
        if path is None: continue
        # simplified: use SP path for load update during warmup
        try:
            full_path = nx.shortest_path(G, src, dst, weight='latency')
        except nx.NetworkXNoPath:
            continue
        for i in range(len(full_path)-1):
            u, v = full_path[i], full_path[i+1]
            e = G[u][v]
            e['load'] += 1
            if e['load'] > e['capacity']:
                e['loss'] += 1
                break
        for u, v in G.edges():
            G[u][v]['load'] *= 0.9
    return {tuple(sorted([u,v])): G[u][v]['loss'] for u,v in G.edges()}

def emmet_route_full(G, src, dst, snap, ttl_factor, theta, eps, eps_rng):
    n_e = G.number_of_edges()
    temp = sum(G[u][v]['load']/G[u][v]['capacity'] for u,v in G.edges())/n_e if n_e else 0
    beta_eff = BETA * (1 + theta * temp)
    max_hops = ttl_factor * G.number_of_nodes()
    path, cur, vis, hops = [src], src, set(), 0
    while cur != dst and hops < max_hops:
        vis.add(cur)
        nbrs = [n for n in G.neighbors(cur) if n not in vis]
        if not nbrs:
            return None
        ranked = sorted(nbrs, key=lambda n: potential(G, cur, n, dst, snap, beta_eff))
        if eps_rng and len(ranked) > 1 and eps_rng.random() < eps:
            best = ranked[1]
        else:
            best = ranked[0]
        path.append(best)
        cur = best
        hops += 1
    return path if cur == dst else None

def simulate(G, traffic, snap, ttl_factor, theta, eps, half_life, eps_rng):
    decay = math.exp(-math.log(2)/half_life)
    snap_live = dict(snap)
    losses = delivered = 0
    total_lat = 0.0
    for src, dst in traffic:
        if src == dst: continue
        path = emmet_route_full(G, src, dst, snap_live, ttl_factor, theta, eps, eps_rng)
        if path is None:
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
        for k in list(snap_live.keys()):
            snap_live[k] *= decay
    return {'losses': losses, 'delivered': delivered,
            'lat': total_lat/delivered if delivered else 0}

def run_one(args):
    seed, ttl_factor, theta, eps, half_life = args
    G = build_graph(seed)
    nodes = list(G.nodes())
    warmup_traf = gen_traffic(nodes, max(20, N_NODES*5), seed + 300000)
    reset_graph(G)
    snap = warmup(G, warmup_traf, ttl_factor, theta, eps)
    G2 = build_graph(seed)
    reset_graph(G2)
    traf = gen_traffic(list(G2.nodes()), TRAFFIC_STEPS, seed + 100000)
    eps_rng = random.Random(seed + 400000)
    return simulate(G2, traf, snap, ttl_factor, theta, eps, half_life, eps_rng)

def sweep(name, values, ttl_factor=DEF_TTL_FACTOR, theta=DEF_THETA,
          eps=DEF_EPSILON, half_life=DEF_HALF_LIFE):
    print(f'\n=== Sweep: {name} ===')
    rows = []
    for v in values:
        kw = {'ttl_factor': ttl_factor, 'theta': theta, 'eps': eps,
              'half_life': half_life}
        kw[name] = v
        jobs = [(seed, kw['ttl_factor'], kw['theta'], kw['eps'],
                 kw['half_life']) for seed in range(N_SEEDS)]
        with Pool(max(1, cpu_count()-4)) as pool:
            results = pool.map(run_one, jobs)
        losses = [r['losses'] for r in results]
        lats = [r['lat'] for r in results if r['lat'] > 0]
        delivered = [r['delivered'] for r in results]
        row = {
            f'{name}': v,
            'losses_mean': statistics.mean(losses),
            'losses_std':  statistics.stdev(losses),
            'lat_mean':    statistics.mean(lats) if lats else 0,
            'delivered_mean': statistics.mean(delivered),
        }
        rows.append(row)
        print(f"  {name}={v:<7} losses={row['losses_mean']:.2f}+/-{row['losses_std']:.2f} "
              f"lat={row['lat_mean']:.3f} delivered={row['delivered_mean']:.1f}")
    return rows

if __name__ == '__main__':
    print(f'Sensitivity sweep on ER(n={N_NODES}, p={DENSITY}), {N_SEEDS} seeds')
    t0 = time.time()

    out = {
        'scenario': f'ER_n{N_NODES}_p{DENSITY}',
        'n_seeds': N_SEEDS,
        'defaults': {
            'ttl_factor': DEF_TTL_FACTOR, 'theta': DEF_THETA,
            'epsilon': DEF_EPSILON, 'half_life': DEF_HALF_LIFE,
        },
        'sweeps': {
            'ttl_factor': sweep('ttl_factor', SWEEP_TTL),
            'theta':      sweep('theta',      SWEEP_THETA),
            'eps':        sweep('eps',        SWEEP_EPSILON),
            'half_life':  sweep('half_life',  SWEEP_HALF),
        },
    }

    print(f'\nTotal time: {(time.time()-t0)/60:.1f} min')

    with open(DATA_DIR / 'sensitivity_summary.json', 'w') as f:
        json.dump(out, f, indent=2)
    print(f"Saved to {DATA_DIR / 'sensitivity_summary.json'}")
