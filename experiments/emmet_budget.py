"""EMMET-budget: routing with explicit hop budget and integrated potential.

For each (src, dst) packet:
  1. Compute SP hop count h_sp from src to dst
  2. Set budget k = ceil(alpha * h_sp), with alpha >= 1
  3. Find path P from src to dst with len(P) <= k that minimizes
     sum over edges (u,v) in P of: latency(u,v) + beta_eff * load(u,v)/cap(u,v)
                                   + gamma * loss_snapshot(u,v)
  4. If no such path exists, take SP (cannot do worse than baseline)

The optimization in step 3 is solved via dynamic programming:
  f(v, h) = min potential to reach v using exactly h hops from src
  recurrence: f(v, h) = min over u in pred(v) of f(u, h-1) + edge_pot(u,v)
  base: f(src, 0) = 0; f(v, 0) = +inf for v != src

Complexity: O(k * |E|) per packet. For k=2*sqrt(N) and dense graphs, viable.

This algorithm has THREE properties EMMET-fb did not:
  - Cannot dead-end (always finds a feasible path if one exists within budget)
  - Has bounded capacity consumption (at most alpha times SP)
  - Single decision rule, not two stitched together
"""
import random, statistics, math, json, time, hashlib
from pathlib import Path
from multiprocessing import Pool, cpu_count
import networkx as nx

REPO = Path(__file__).resolve().parents[1]
TOPO = REPO / 'data' / 'topologies'
DATA = REPO / 'data'

TRAFFIC_STEPS = 200
ALPHA_LAT = 1.0       # weight on latency
BETA      = 3.0       # weight on congestion
GAMMA     = 2.0       # weight on loss memory
THETA     = 5.0       # adaptive beta sensitivity
HALF_LIFE = 500
DECAY     = math.exp(-math.log(2) / HALF_LIFE)

def build_syn(n, p, seed):
    rng = random.Random(seed)
    G = nx.erdos_renyi_graph(n, p, seed=seed)
    for u, v in G.edges():
        G[u][v]['latency']  = rng.uniform(1, 5)
        G[u][v]['capacity'] = rng.randint(3, 6)
        G[u][v]['load']     = 0
        G[u][v]['loss']     = 0
    return G

def build_real(fn, seed):
    G = nx.read_graphml(str(TOPO / fn))
    G = nx.Graph(G)
    G = nx.relabel_nodes(G, {n: i for i, n in enumerate(G.nodes())})
    rng = random.Random(seed)
    for u, v in G.edges():
        G[u][v]['latency']  = rng.uniform(1, 5)
        G[u][v]['capacity'] = rng.randint(3, 6)
        G[u][v]['load']     = 0
        G[u][v]['loss']     = 0
    return G

def reset(G):
    for u, v in G.edges():
        G[u][v]['load'] = 0
        G[u][v]['loss'] = 0

def gen_traf(nodes, steps, seed):
    rng = random.Random(seed)
    return [(rng.choice(nodes), rng.choice(nodes)) for _ in range(steps)]

def edge_potential(G, u, v, snap, beta_eff):
    """The cost we minimize per edge. Pure local quantities (no lookahead)."""
    e = G[u][v]
    cong = e['load'] / e['capacity']
    k = tuple(sorted([u, v]))
    lv = snap.get(k, 0)
    return ALPHA_LAT * e['latency'] + beta_eff * cong + GAMMA * lv

def emmet_budget_route(G, src, dst, snap, alpha_budget):
    """DP-based routing under hop budget.

    Returns the path that minimizes sum of edge potentials subject to
    length <= ceil(alpha_budget * sp_hops).
    Falls back to SP if budget is infeasible (disconnected).
    """
    if src == dst:
        return [src], 'trivial', 0
    try:
        sp_hops = nx.shortest_path_length(G, src, dst)
    except nx.NetworkXNoPath:
        return None, 'no_path', 0

    k = max(sp_hops, math.ceil(alpha_budget * sp_hops))

    # Adaptive beta — global thermostat as before
    n_e = G.number_of_edges()
    if n_e:
        temp = sum(G[u][v]['load']/G[u][v]['capacity'] for u,v in G.edges()) / n_e
    else:
        temp = 0
    beta_eff = BETA * (1 + THETA * temp)

    # DP table: f[h][v] = min potential to reach v in exactly h hops
    # parent[h][v] = predecessor of v in optimal h-hop path
    INF = float('inf')
    nodes = list(G.nodes())
    f = [{u: INF for u in nodes} for _ in range(k + 1)]
    parent = [{u: None for u in nodes} for _ in range(k + 1)]
    f[0][src] = 0

    for h in range(1, k + 1):
        for v in nodes:
            best = INF
            best_u = None
            for u in G.neighbors(v):
                if f[h-1][u] == INF:
                    continue
                cost = f[h-1][u] + edge_potential(G, u, v, snap, beta_eff)
                if cost < best:
                    best = cost
                    best_u = u
            f[h][v] = best
            parent[h][v] = best_u

    # Find best length to reach dst (any h between sp_hops and k)
    best_h = None
    best_cost = INF
    for h in range(sp_hops, k + 1):
        if f[h][dst] < best_cost:
            best_cost = f[h][dst]
            best_h = h

    if best_h is None:
        # Should not happen if SP exists, but guard anyway
        try:
            sp_path = nx.shortest_path(G, src, dst, weight='latency')
            return sp_path, 'sp_fallback_unreachable', sp_hops
        except nx.NetworkXNoPath:
            return None, 'no_path', 0

    # Reconstruct path
    path = [dst]
    cur, h = dst, best_h
    while h > 0:
        cur = parent[h][cur]
        path.append(cur)
        h -= 1
    path.reverse()
    return path, 'delivered', sp_hops

def warmup(G, traf, alpha_budget):
    snap = {}
    for src, dst in traf:
        if src == dst: continue
        path, reason, _ = emmet_budget_route(G, src, dst, snap, alpha_budget)
        if path is None or len(path) < 2: continue
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

def shortest_path_route(G, src, dst):
    try:
        return nx.shortest_path(G, src, dst, weight='latency'), 'delivered'
    except nx.NetworkXNoPath:
        return None, 'no_path'

def lasp_route(G, src, dst):
    def w(u, v, d): return d['latency'] * (1 + d['load']/d['capacity'])
    try:
        return nx.shortest_path(G, src, dst, weight=w), 'delivered'
    except nx.NetworkXNoPath:
        return None, 'no_path'

def simulate(G, mode, traffic, snap=None, alpha_budget=1.5):
    snap_l = dict(snap) if snap else {}
    losses = delivered = nopath = 0
    cap_consumed_delivered = 0
    cap_consumed_lost = 0
    hop_count_delivered = 0
    sp_hops_delivered = 0  # for ratio computation

    for src, dst in traffic:
        if src == dst: continue
        if mode == 'sp':
            path, reason = shortest_path_route(G, src, dst)
            sp_h = len(path) - 1 if path else 0
        elif mode == 'lasp':
            path, reason = lasp_route(G, src, dst)
            try: sp_h = nx.shortest_path_length(G, src, dst)
            except nx.NetworkXNoPath: sp_h = 0
        else:  # emmet_budget
            path, reason, sp_h = emmet_budget_route(G, src, dst, snap_l, alpha_budget)

        if path is None or len(path) < 2:
            nopath += 1
            continue

        lost = False
        path_caps = 0
        for i in range(len(path)-1):
            u, v = path[i], path[i+1]
            e = G[u][v]
            e['load'] += 1
            path_caps += 1
            if e['load'] > e['capacity']:
                e['loss'] += 1
                losses += 1
                lost = True
                break
        if lost:
            cap_consumed_lost += path_caps
        else:
            delivered += 1
            cap_consumed_delivered += path_caps
            hop_count_delivered += len(path) - 1
            sp_hops_delivered += sp_h
        for u, v in G.edges():
            G[u][v]['load'] *= 0.9
        if snap_l:
            for k in list(snap_l.keys()):
                snap_l[k] *= DECAY

    attempted = delivered + losses + nopath
    return {
        'delivered': delivered,
        'losses': losses,
        'nopath': nopath,
        'delivery_rate': delivered / attempted * 100 if attempted else 0,
        'cap_per_delivery': cap_consumed_delivered / delivered if delivered else 0,
        'hop_per_delivery': hop_count_delivered / delivered if delivered else 0,
        'sp_hop_per_delivery': sp_hops_delivered / delivered if delivered else 0,
    }

def run_one(args):
    label, builder, bargs, seed, alpha_budget = args
    G_meta = builder(*bargs, seed=seed)
    n = G_meta.number_of_nodes()
    ws = max(20, n * 5)
    out = {'scenario': label, 'seed': seed, 'alpha_budget': alpha_budget, 'num_nodes': n}

    G = builder(*bargs, seed=seed); reset(G)
    traf = gen_traf(list(G.nodes()), TRAFFIC_STEPS, seed + 100000)
    out['sp'] = simulate(G, 'sp', traf)

    G = builder(*bargs, seed=seed); reset(G)
    traf = gen_traf(list(G.nodes()), TRAFFIC_STEPS, seed + 100000)
    out['lasp'] = simulate(G, 'lasp', traf)

    G = builder(*bargs, seed=seed); reset(G)
    wt = gen_traf(list(G.nodes()), ws, seed + 300000)
    snap = warmup(G, wt, alpha_budget)
    G = builder(*bargs, seed=seed); reset(G)
    traf = gen_traf(list(G.nodes()), TRAFFIC_STEPS, seed + 100000)
    out['emmet_budget'] = simulate(G, 'emmet_budget', traf,
                                    snap=snap, alpha_budget=alpha_budget)
    return out

def aggregate(results):
    by = {}
    for r in results:
        key = (r['scenario'], r['alpha_budget'])
        by.setdefault(key, []).append(r)
    summary = []
    for (sc, ab), runs in sorted(by.items()):
        n = runs[0]['num_nodes']
        row = {'scenario': sc, 'alpha_budget': ab, 'n_runs': len(runs), 'num_nodes': n}
        for strat in ['sp', 'lasp', 'emmet_budget']:
            for key in ['delivered', 'losses', 'delivery_rate',
                        'cap_per_delivery', 'hop_per_delivery', 'sp_hop_per_delivery']:
                vals = [r[strat][key] for r in runs]
                row[f'{strat}_{key}_mean'] = statistics.mean(vals)
                if len(vals) > 1:
                    row[f'{strat}_{key}_std'] = statistics.stdev(vals)
        summary.append(row)
    return summary

if __name__ == '__main__':
    # First: quick sweep on one representative scenario to find good alpha_budget
    # Run just GEANT first across multiple alpha values to see the Pareto curve.
    print("=== Phase 1: alpha_budget sweep on representative scenarios ===")
    print()

    sweep_jobs = []
    sweep_scenarios = [
        ('GEANT', build_real, ('Geant.graphml',), 50),
        ('Abilene', build_real, ('Abilene.graphml',), 50),
        ('ER_n50_p0.05', build_syn, (50, 0.05), 50),
        ('ER_n20_p0.20', build_syn, (20, 0.20), 50),
    ]
    alphas = [1.0, 1.25, 1.5, 1.75, 2.0, 2.5, 3.0]

    for sn, b, ba, ns in sweep_scenarios:
        for a in alphas:
            for s in range(ns):
                sweep_jobs.append((sn, b, ba, s, a))

    print(f"Sweep jobs: {len(sweep_jobs)} | workers: {max(1, cpu_count()-4)}")
    t0 = time.time()
    with Pool(max(1, cpu_count()-4)) as pool:
        sweep_results = pool.map(run_one, sweep_jobs)
    print(f"Sweep done in {(time.time()-t0)/60:.1f} min")

    sweep_summary = aggregate(sweep_results)
    with open(DATA / 'budget_sweep_summary.json', 'w') as f:
        json.dump(sweep_summary, f, indent=2)

    print()
    print(f"{'Scenario':<18} {'alpha':>6} {'EM_dr':>7} {'LASP_dr':>8} {'SP_dr':>7} | "
          f"{'EM_loss':>8} {'LASP_loss':>10} | {'EM_cap/del':>11} {'LASP_cap':>9}")
    print('-' * 110)
    for s in sweep_summary:
        print(f"{s['scenario']:<18} {s['alpha_budget']:>6.2f} "
              f"{s['emmet_budget_delivery_rate_mean']:>6.1f}% "
              f"{s['lasp_delivery_rate_mean']:>7.1f}% "
              f"{s['sp_delivery_rate_mean']:>6.1f}% | "
              f"{s['emmet_budget_losses_mean']:>8.2f} "
              f"{s['lasp_losses_mean']:>10.2f} | "
              f"{s['emmet_budget_cap_per_delivery_mean']:>11.2f} "
              f"{s['lasp_cap_per_delivery_mean']:>9.2f}")
    print()
    print(f"Saved budget_sweep_summary.json")
