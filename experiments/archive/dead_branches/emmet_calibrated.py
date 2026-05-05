"""Full battery with calibrated parameters (TTL=1, theta=5.0, half_life=500, eps=0.10)."""
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

def emmet(G, src, dst, snap, eps_rng=None, adaptive_beta=False):
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
            return None, 'dead_end'
        ranked = sorted(nbrs, key=lambda n: potential(G, cur, n, dst, snap, beta_eff))
        if eps_rng and len(ranked) > 1 and eps_rng.random() < EPSILON:
            best = ranked[1]
        else:
            best = ranked[0]
        path.append(best)
        cur = best
        hops += 1
    return (path, 'delivered') if cur == dst else (None, 'ttl_expired')

def warmup(G, traf, adaptive_beta=False):
    snap = {}
    for src, dst in traf:
        if src == dst: continue
        path, _ = emmet(G, src, dst, snap, adaptive_beta=adaptive_beta)
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

def simulate(G, mode, traffic, snap=None, decay=1.0, eps_rng=None, adaptive_beta=False):
    snap_l = dict(snap) if (snap and decay < 1.0) else (snap or {})
    losses = delivered = dead = ttl = nopath = 0
    total_lat = 0.0
    for src, dst in traffic:
        if src == dst: continue
        if mode == 'sp':
            path, reason = shortest_path_route(G, src, dst)
        elif mode == 'lasp':
            path, reason = lasp_route(G, src, dst)
        else:
            path, reason = emmet(G, src, dst, snap_l, eps_rng, adaptive_beta)
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
                break
            total_lat += e['latency']
        if not lost:
            delivered += 1
        for u, v in G.edges():
            G[u][v]['load'] *= 0.9
        if decay < 1.0:
            for k in list(snap_l.keys()):
                snap_l[k] *= decay
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

    G = builder(*builder_args, topo_seed=seed); reset_graph(G)
    traf = gen_traffic(list(G.nodes()), TRAFFIC_STEPS, traffic_seed)
    out['emmet_cold'] = simulate(G, 'emmet', traf, snap={})

    G = builder(*builder_args, topo_seed=seed); reset_graph(G)
    wt = gen_traffic(list(G.nodes()), warmup_steps, warmup_seed)
    snap = warmup(G, wt, adaptive_beta=False)
    G = builder(*builder_args, topo_seed=seed); reset_graph(G)
    traf = gen_traffic(list(G.nodes()), TRAFFIC_STEPS, traffic_seed)
    out['emmet_thermal'] = simulate(G, 'emmet', traf, snap=snap, decay=DECAY,
                                     eps_rng=random.Random(eps_seed))

    G = builder(*builder_args, topo_seed=seed); reset_graph(G)
    traf = gen_traffic(list(G.nodes()), TRAFFIC_STEPS, traffic_seed)
    out['emmet_adaptive'] = simulate(G, 'emmet', traf, snap={}, adaptive_beta=True)

    G = builder(*builder_args, topo_seed=seed); reset_graph(G)
    wt = gen_traffic(list(G.nodes()), warmup_steps, warmup_seed)
    snap = warmup(G, wt, adaptive_beta=True)
    G = builder(*builder_args, topo_seed=seed); reset_graph(G)
    traf = gen_traffic(list(G.nodes()), TRAFFIC_STEPS, traffic_seed)
    out['emmet_full'] = simulate(G, 'emmet', traf, snap=snap, decay=DECAY,
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
    strats = ['sp', 'lasp', 'emmet_cold', 'emmet_thermal', 'emmet_adaptive', 'emmet_full']
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
    print(f'Calibrated battery: {len(jobs)} jobs x 6 strategies')
    print(f'Params: TTL={TTL_FACTOR} theta={THETA} half_life={HALF_LIFE} eps={EPSILON}')
    workers = max(1, cpu_count() - 4)
    t0 = time.time()
    with Pool(workers) as pool:
        results = []
        for i, r in enumerate(pool.imap_unordered(run_one, jobs, chunksize=4)):
            results.append(r)
            if (i+1) % 200 == 0:
                elapsed = time.time() - t0
                rate = (i+1) / elapsed
                eta = (len(jobs) - (i+1)) / rate
                print(f'  {i+1}/{len(jobs)} | {rate:.1f}/s | ETA {eta/60:.1f}m')
    print(f'\nDone in {(time.time()-t0)/60:.1f} min')

    with open(DATA_DIR / 'calibrated_raw_results.json', 'w') as f:
        json.dump(results, f, indent=1)
    summary = aggregate(results)
    with open(DATA_DIR / 'calibrated_summary.json', 'w') as f:
        json.dump(summary, f, indent=2)

    print()
    print(f"{'Scenario':<22} {'N':>4} {'SP':>7} {'LASP':>7} {'COLD':>7} {'THERM':>7} {'ADAPT':>7} {'FULL':>7}")
    for s in summary:
        print(f"{s['scenario']:<22} {s['n_runs']:>4} "
              f"{s['sp_losses_mean']:>7.2f} {s['lasp_losses_mean']:>7.2f} "
              f"{s['emmet_cold_losses_mean']:>7.2f} {s['emmet_thermal_losses_mean']:>7.2f} "
              f"{s['emmet_adaptive_losses_mean']:>7.2f} {s['emmet_full_losses_mean']:>7.2f}")
