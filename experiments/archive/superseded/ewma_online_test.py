"""EWMA online snapshot — does live update beat the frozen snapshot?

Gemini 1 concern: in real networks, link state changes after warmup. A
frozen snapshot becomes stale. EWMA online updates per loss event.

To stay audit-clean, we propose a fair comparison:
  - EMMET frozen: snapshot from warmup, decays only
  - EMMET online: snapshot from warmup, decays AND receives EWMA update
                  on each observed loss during measurement

The EWMA rule: when a packet is dropped on edge (u,v), update
  snapshot[(u,v)] <- alpha_ewma * 1.0 + (1 - alpha_ewma) * snapshot[(u,v)]
where alpha_ewma controls how much new info weighs against old info.

Since the snapshot influences EMMET's routing decisions, this gives
EMMET more recent information. To keep the comparison fair, we report
this as an algorithmic upgrade (real-world deployment scenario), not as
a strict comparison vs frozen — both are versions of EMMET, and the
question is which performs better.

We test alpha_ewma in {0.0, 0.05, 0.1, 0.3} where 0.0 = frozen (control).
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

def emmet(G, src, dst, snap, eps_rng, adaptive_beta):
    if adaptive_beta:
        n_e = G.number_of_edges()
        temp = sum(G[u][v]['load']/G[u][v]['capacity'] for u,v in G.edges())/n_e if n_e else 0
        beta_eff = BETA * (1 + THETA * temp)
    else:
        beta_eff = BETA
    max_hops = TTL_FACTOR * G.number_of_nodes()
    path, cur, vis, hops = [src], src, set(), 0
    while cur != dst and hops < max_hops:
        vis.add(cur)
        nbrs = [n for n in G.neighbors(cur) if n not in vis]
        if not nbrs:
            return None
        ranked = sorted(nbrs, key=lambda n: potential(G, cur, n, dst, snap, beta_eff))
        if eps_rng and len(ranked) > 1 and eps_rng.random() < EPSILON:
            cur = ranked[1]
        else:
            cur = ranked[0]
        path.append(cur)
        hops += 1
    return path if cur == dst else None

def warmup(G, traf):
    snap = {}
    for src, dst in traf:
        if src == dst: continue
        path = emmet(G, src, dst, snap, None, adaptive_beta=True)
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

def simulate_with_ewma(G, traffic, snap, eps_rng, alpha_ewma):
    """alpha_ewma=0.0 means frozen (no online update)."""
    snap_l = dict(snap)
    losses = delivered = 0
    total_lat = 0.0
    for src, dst in traffic:
        if src == dst: continue
        path = emmet(G, src, dst, snap_l, eps_rng, adaptive_beta=True)
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
                # EWMA update: if this loss happens, push the snapshot up
                if alpha_ewma > 0:
                    k = tuple(sorted([u, v]))
                    snap_l[k] = alpha_ewma * 1.0 + (1 - alpha_ewma) * snap_l.get(k, 0)
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

def run_one(args):
    label, builder, builder_args, seed, alpha_ewma = args
    G_meta = builder(*builder_args, topo_seed=seed)
    n = G_meta.number_of_nodes()
    warmup_steps = max(20, n*5)
    G = builder(*builder_args, topo_seed=seed); reset_graph(G)
    wt = gen_traffic(list(G.nodes()), warmup_steps, seed + 300000)
    snap = warmup(G, wt)
    G2 = builder(*builder_args, topo_seed=seed); reset_graph(G2)
    traf = gen_traffic(list(G2.nodes()), TRAFFIC_STEPS, seed + 100000)
    eps_rng = random.Random(seed + 400000)
    res = simulate_with_ewma(G2, traf, snap, eps_rng, alpha_ewma)
    return {'scenario': label, 'seed': seed, 'alpha_ewma': alpha_ewma, **res}

if __name__ == '__main__':
    scenarios = [
        ('ER_n20_p0.05', build_synthetic, (20, 0.05), 100),
        ('ER_n20_p0.10', build_synthetic, (20, 0.10), 100),
        ('ER_n50_p0.05', build_synthetic, (50, 0.05), 100),
        ('Abilene',      build_real, ('Abilene.graphml',), 100),
        ('GEANT',        build_real, ('Geant.graphml',),   100),
    ]
    alphas = [0.0, 0.05, 0.1, 0.3]
    print(f'EWMA online battery: {len(scenarios)} x {len(alphas)} alphas')

    jobs = []
    for sname, builder, args, seeds in scenarios:
        for a in alphas:
            for s in range(seeds):
                jobs.append((sname, builder, args, s, a))
    workers = max(1, cpu_count() - 4)
    print(f'Total jobs: {len(jobs)} | workers: {workers}')

    t0 = time.time()
    with Pool(workers) as pool:
        results = pool.map(run_one, jobs)
    print(f'Done in {(time.time()-t0)/60:.1f} min')

    by = {}
    for r in results:
        key = (r['scenario'], r['alpha_ewma'])
        by.setdefault(key, []).append(r)

    print()
    print(f"{'Scenario':<18} {'alpha_ewma':>12} {'Loss mean':>12} {'Loss std':>10} {'Delivered':>10}")
    summary = []
    for key, runs in sorted(by.items()):
        sc, alpha = key
        losses = [r['losses'] for r in runs]
        delivered = [r['delivered'] for r in runs]
        mode_str = 'frozen' if alpha == 0.0 else f'online a={alpha}'
        print(f"{sc:<18} {mode_str:>12} "
              f"{statistics.mean(losses):>12.2f} {statistics.stdev(losses):>10.2f} "
              f"{statistics.mean(delivered):>10.1f}")
        summary.append({
            'scenario': sc, 'alpha_ewma': alpha,
            'losses_mean': statistics.mean(losses),
            'losses_std':  statistics.stdev(losses),
            'delivered_mean': statistics.mean(delivered),
        })

    with open(DATA_DIR / 'ewma_online_summary.json', 'w') as f:
        json.dump(summary, f, indent=2)
    print(f"\nSaved to data/ewma_online_summary.json")
