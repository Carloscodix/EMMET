"""Verify combined effect of optimized parameters across all scenarios."""
import random
import statistics
import math
import json
import time
from pathlib import Path
from multiprocessing import Pool, cpu_count
import networkx as nx

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR  = REPO_ROOT / 'data'

TRAFFIC_STEPS = 200
ALPHA = 1.0
BETA  = 3.0
GAMMA = 2.0

PARAMS_OLD = dict(ttl_factor=2, theta=1.0, half_life=100, epsilon=0.10)
PARAMS_NEW = dict(ttl_factor=1, theta=5.0, half_life=500, epsilon=0.10)

TOPO_DIR = REPO_ROOT / 'data' / 'topologies'

def build_synthetic(n, p, seed):
    rng = random.Random(seed)
    G = nx.erdos_renyi_graph(n, p, seed=seed)
    for u, v in G.edges():
        G[u][v]['latency']  = rng.uniform(1, 5)
        G[u][v]['capacity'] = rng.randint(3, 6)
        G[u][v]['load']     = 0
        G[u][v]['loss']     = 0
    return G

def build_real(filename, seed):
    G = nx.read_graphml(str(TOPO_DIR / filename))
    G = nx.Graph(G)
    G = nx.relabel_nodes(G, {n: i for i, n in enumerate(G.nodes())})
    rng = random.Random(seed)
    for u, v in G.edges():
        G[u][v]['latency']  = rng.uniform(1, 5)
        G[u][v]['capacity'] = rng.randint(3, 6)
        G[u][v]['load']     = 0
        G[u][v]['loss']     = 0
    return G

def reset_g(G):
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

def emmet(G, src, dst, snap, params, eps_rng):
    n_e = G.number_of_edges()
    temp = sum(G[u][v]['load']/G[u][v]['capacity'] for u,v in G.edges())/n_e if n_e else 0
    beta_eff = BETA * (1 + params['theta'] * temp)
    max_hops = params['ttl_factor'] * G.number_of_nodes()
    path, cur, vis, hops = [src], src, set(), 0
    while cur != dst and hops < max_hops:
        vis.add(cur)
        nbrs = [n for n in G.neighbors(cur) if n not in vis]
        if not nbrs:
            return None
        ranked = sorted(nbrs, key=lambda n: potential(G, cur, n, dst, snap, beta_eff))
        if eps_rng and len(ranked) > 1 and eps_rng.random() < params['epsilon']:
            best = ranked[1]
        else:
            best = ranked[0]
        path.append(best)
        cur = best
        hops += 1
    return path if cur == dst else None

def warmup(G, traf, params):
    snap = {}
    for src, dst in traf:
        if src == dst: continue
        path = emmet(G, src, dst, snap, params, None)
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

def simulate(G, traffic, snap, params, eps_rng):
    decay = math.exp(-math.log(2)/params['half_life'])
    snap_l = dict(snap)
    losses = delivered = 0
    total_lat = 0.0
    for src, dst in traffic:
        if src == dst: continue
        path = emmet(G, src, dst, snap_l, params, eps_rng)
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
        for k in list(snap_l.keys()):
            snap_l[k] *= decay
    return {'losses': losses, 'delivered': delivered,
            'lat': total_lat/delivered if delivered else 0}

def run_one(args):
    label, builder, builder_args, seed, params = args
    G_meta = builder(*builder_args, seed=seed)
    n_meta = G_meta.number_of_nodes()
    warmup_steps = max(20, n_meta * 5)
    G = builder(*builder_args, seed=seed); reset_g(G)
    wt = gen_traffic(list(G.nodes()), warmup_steps, seed + 300000)
    snap = warmup(G, wt, params)
    G2 = builder(*builder_args, seed=seed); reset_g(G2)
    traf = gen_traffic(list(G2.nodes()), TRAFFIC_STEPS, seed + 100000)
    res = simulate(G2, traf, snap, params, random.Random(seed + 400000))
    return {'scenario': label, 'seed': seed, **res}

def run_battery(params, label, scenarios):
    print(f'\n--- {label} | params={params} ---')
    jobs = []
    for sname, builder, args, seeds in scenarios:
        for s in range(seeds):
            jobs.append((sname, builder, args, s, params))
    with Pool(max(1, cpu_count()-4)) as pool:
        results = pool.map(run_one, jobs)
    by_scen = {}
    for r in results:
        by_scen.setdefault(r['scenario'], []).append(r)
    summary = {}
    for sc, rs in by_scen.items():
        losses = [r['losses'] for r in rs]
        lats = [r['lat'] for r in rs if r['lat'] > 0]
        delivered = [r['delivered'] for r in rs]
        summary[sc] = {
            'losses_mean': statistics.mean(losses),
            'losses_std':  statistics.stdev(losses),
            'lat_mean':    statistics.mean(lats) if lats else 0,
            'delivered_mean': statistics.mean(delivered),
        }
    for sc, s in summary.items():
        print(f"  {sc:<22} losses={s['losses_mean']:6.2f} "
              f"lat={s['lat_mean']:.3f} delivered={s['delivered_mean']:.1f}")
    return summary

if __name__ == '__main__':
    scenarios = [
        ('ER_n20_p0.05', build_synthetic, (20, 0.05), 100),
        ('ER_n20_p0.10', build_synthetic, (20, 0.10), 100),
        ('ER_n50_p0.05', build_synthetic, (50, 0.05), 100),
        ('Abilene',      build_real, ('Abilene.graphml',), 100),
        ('GEANT',        build_real, ('Geant.graphml',),   100),
    ]

    t0 = time.time()
    old = run_battery(PARAMS_OLD, 'OLD (current paper)', scenarios)
    new = run_battery(PARAMS_NEW, 'NEW (calibrated)', scenarios)

    print(f'\n=== Comparison ===')
    print(f"{'Scenario':<22} {'OLD loss':>10} {'NEW loss':>10} {'Delta':>10}")
    for sc in old:
        delta = (new[sc]['losses_mean'] - old[sc]['losses_mean']) / old[sc]['losses_mean'] * 100 if old[sc]['losses_mean'] > 0 else 0
        print(f"{sc:<22} {old[sc]['losses_mean']:>10.2f} {new[sc]['losses_mean']:>10.2f} {delta:>+9.1f}%")

    print(f'\nTotal time: {(time.time()-t0)/60:.1f} min')

    with open(DATA_DIR / 'parameter_calibration.json', 'w') as f:
        json.dump({
            'params_old': PARAMS_OLD,
            'params_new': PARAMS_NEW,
            'old': old,
            'new': new,
        }, f, indent=2)
    print(f"Saved to data/parameter_calibration.json")
