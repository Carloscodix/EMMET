"""EMMET-momentum-DP: per-packet mass evolves along path, DP guarantees delivery.

State: f[v][h][m_bucket] = (best cumulative cost, predecessor info)
  - v: node
  - h: hops used so far
  - m_bucket: discretized mass at v after h hops

Transition: from (u, h-1, m_in_bucket) via edge (u,v):
  cost_step = m_in * potential(u, v)
  m_out = min(m_in * (1 + kappa * congestion(u,v)), m_max)
  f[v][h][m_out_bucket] = min over predecessors of (f[u][h-1][m_in_bucket] + cost_step)

Path reconstruction: among all (h <= k, m) reaching dst, pick min cost; trace back.

This is EMMET-budget extended with packet state. Delivery is guaranteed
(within budget) because the DP explores all reachable (node, hops) pairs.
"""
import random, statistics, math, json, time
from pathlib import Path
from multiprocessing import Pool, cpu_count
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[0]))
from emmet_budget import (
    build_syn, build_real, reset, gen_traf,
    edge_potential, shortest_path_route, lasp_route,
    TRAFFIC_STEPS, BETA, THETA, DECAY
)
import networkx as nx

REPO = Path(__file__).resolve().parents[1]
DATA = REPO / 'data'

# Mass dynamics
M_INITIAL = 1.0
M_MAX     = 3.0
M_BUCKETS = 8     # discretization of mass for DP state
KAPPA     = 0.3
ALPHA_BUDGET = 1.25  # hop budget multiplier (same as EMMET-budget)


def m_to_bucket(m, m_max=M_MAX, n_buckets=M_BUCKETS):
    """Discretize mass [1, m_max] into n_buckets indices [0, n_buckets-1].

    Uses round() to ensure idempotency: m_to_bucket(bucket_to_m(b)) == b.
    This guarantees that mass cannot decrease through discretization
    artifacts when traversing zero-congestion edges.
    """
    if m <= 1.0:
        return 0
    if m >= m_max:
        return n_buckets - 1
    # Linear discretization. Idempotent via half-up rounding
    # (avoids Python's banker's rounding bias on exact boundaries).
    x = (m - 1.0) / (m_max - 1.0) * (n_buckets - 1)
    idx = int(math.floor(x + 0.5))
    return max(0, min(n_buckets - 1, idx))


def bucket_to_m(b, m_max=M_MAX, n_buckets=M_BUCKETS):
    """Inverse: bucket index -> representative mass value."""
    if b == 0:
        return 1.0
    if b == n_buckets - 1:
        return m_max
    return 1.0 + (m_max - 1.0) * b / (n_buckets - 1)


def emmet_momentum_dp_route(G, src, dst, snap, kappa=KAPPA, m_max=M_MAX,
                              alpha_budget=ALPHA_BUDGET, n_buckets=M_BUCKETS):
    """DP with per-packet mass state. Returns path that minimizes mass-weighted
    cumulative potential subject to len <= alpha_budget * sp_hops."""
    if src == dst:
        return [src], 0
    try:
        sp_hops = nx.shortest_path_length(G, src, dst)
    except nx.NetworkXNoPath:
        return None, 0
    k = max(sp_hops, math.ceil(alpha_budget * sp_hops))

    # Effective beta from global thermostat
    n_e = G.number_of_edges()
    if n_e:
        temp = sum(G[u][v]['load']/G[u][v]['capacity'] for u,v in G.edges()) / n_e
    else:
        temp = 0
    beta_eff = BETA * (1 + THETA * temp)

    INF = float('inf')
    nodes = list(G.nodes())
    # f[h] and parent[h] are dicts keyed by node, each value a list of B buckets.
    # Using dicts (not lists indexed by node value) makes the DP work with
    # arbitrary node labels: strings, non-compact integers, tuples, etc.
    f      = [{n: [INF]*n_buckets  for n in nodes} for _ in range(k+1)]
    parent = [{n: [None]*n_buckets for n in nodes} for _ in range(k+1)]

    # Initial state: at src, 0 hops, mass=M_INITIAL (bucket 0)
    f[0][src][0] = 0.0

    for h in range(1, k+1):
        for v in nodes:
            for u in G.neighbors(v):
                # For each previous mass-bucket at u
                for b_in in range(n_buckets):
                    if f[h-1][u][b_in] == INF:
                        continue
                    m_in = bucket_to_m(b_in, m_max, n_buckets)
                    pot = edge_potential(G, u, v, snap, beta_eff)
                    cost_step = m_in * pot
                    new_cost = f[h-1][u][b_in] + cost_step
                    # Update mass after traversing (u,v)
                    cong = G[u][v]['load'] / G[u][v]['capacity']
                    m_out = min(m_in * (1 + kappa * cong), m_max)
                    b_out = m_to_bucket(m_out, m_max, n_buckets)
                    if new_cost < f[h][v][b_out]:
                        f[h][v][b_out] = new_cost
                        parent[h][v][b_out] = (u, b_in)

    # Find best (h, b) reaching dst (only over finite terminal states).
    # If no finite terminal state exists, return None.
    best_h, best_b, best_cost = None, None, INF
    for h in range(sp_hops, k+1):
        for b in range(n_buckets):
            if f[h][dst][b] < best_cost:
                best_cost = f[h][dst][b]
                best_h, best_b = h, b

    if best_h is None:
        return None, 0

    # Reconstruct path
    path = [dst]
    cur, h, b = dst, best_h, best_b
    while h > 0:
        prev = parent[h][cur][b]
        if prev is None:
            return None, 0  # shouldn't happen if f is finite
        cur, b = prev
        h -= 1
        path.append(cur)
    path.reverse()
    return path, bucket_to_m(best_b, m_max, n_buckets)


def lasp_aug_route(G, src, dst, snap):
    n_e = G.number_of_edges()
    if n_e:
        temp = sum(G[u][v]['load']/G[u][v]['capacity'] for u,v in G.edges()) / n_e
    else:
        temp = 0
    beta_eff = BETA * (1 + THETA * temp)
    snap_local = snap
    def w(u, v, d):
        return edge_potential(G, u, v, snap_local, beta_eff)
    try:
        return nx.shortest_path(G, src, dst, weight=w), 'delivered'
    except nx.NetworkXNoPath:
        return None, 'no_path'


def warmup(G, traf, kappa, m_max, alpha_budget):
    snap = {}
    for src, dst in traf:
        if src == dst: continue
        path, _ = emmet_momentum_dp_route(G, src, dst, snap, kappa, m_max, alpha_budget)
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


def simulate(G, mode, traffic, snap, kappa, m_max, alpha_budget):
    snap_l = dict(snap)
    losses = delivered = nopath = 0
    cap_consumed_delivered = 0
    cap_consumed_lost = 0
    for src, dst in traffic:
        if src == dst: continue
        if mode == 'lasp_aug':
            path, _ = lasp_aug_route(G, src, dst, snap_l)
        else:
            path, _ = emmet_momentum_dp_route(G, src, dst, snap_l, kappa, m_max, alpha_budget)
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
        if not lost:
            delivered += 1
            cap_consumed_delivered += path_caps
        else:
            cap_consumed_lost += path_caps
        for u, v in G.edges():
            G[u][v]['load'] *= 0.9
        for k in list(snap_l.keys()):
            snap_l[k] *= DECAY
    attempted = delivered + losses + nopath
    routed = delivered + losses  # demand actually routed (excl. unroutable)
    total_cap = cap_consumed_delivered + cap_consumed_lost
    return {
        'delivered': delivered, 'losses': losses, 'nopath': nopath,
        'delivery_rate': delivered/attempted*100 if attempted else 0,
        'cap_per_delivery': cap_consumed_delivered/delivered if delivered else 0,
        'cap_per_attempt': total_cap/attempted if attempted else 0,
        'cap_per_routed_attempt': total_cap/routed if routed else 0,
        'cap_consumed_lost': cap_consumed_lost,
    }


def run_one(args):
    label, builder, bargs, seed, kappa = args
    m_max = M_MAX
    ab = ALPHA_BUDGET
    G = builder(*bargs, seed=seed)
    n = G.number_of_nodes()
    ws = max(20, n*5)
    out = {'scenario': label, 'seed': seed, 'kappa': kappa}

    # Warmup with the actual algorithm being measured
    G = builder(*bargs, seed=seed); reset(G)
    wt = gen_traf(list(G.nodes()), ws, seed + 300000)
    snap = warmup(G, wt, kappa, m_max, ab)

    G = builder(*bargs, seed=seed); reset(G)
    traf = gen_traf(list(G.nodes()), TRAFFIC_STEPS, seed + 100000)
    out['lasp_aug'] = simulate(G, 'lasp_aug', traf, snap, kappa, m_max, ab)

    G = builder(*bargs, seed=seed); reset(G)
    traf = gen_traf(list(G.nodes()), TRAFFIC_STEPS, seed + 100000)
    out['momentum_dp'] = simulate(G, 'momentum_dp', traf, snap, kappa, m_max, ab)

    return out


def aggregate(results):
    """Aggregate prototype run_one results, reporting the same metrics as
    momentum_clean.aggregate."""
    by = {}
    for r in results:
        by.setdefault((r['scenario'], r['kappa']), []).append(r)
    summary = []
    for (sc, k), runs in sorted(by.items()):
        row = {'scenario': sc, 'kappa': k, 'n_runs': len(runs)}
        for strat in ['lasp_aug', 'momentum_dp']:
            for key in ['delivered', 'losses', 'delivery_rate',
                        'cap_per_delivery', 'cap_per_attempt',
                        'cap_per_routed_attempt', 'cap_consumed_lost']:
                vals = [r[strat].get(key, 0) for r in runs]
                row[f'{strat}_{key}_mean'] = statistics.mean(vals)
                if len(vals) > 1:
                    row[f'{strat}_{key}_std'] = statistics.stdev(vals)
        summary.append(row)
    return summary


if __name__ == '__main__':
    print('=== EMMET-momentum-DP prototype (LEGACY) ===')
    print('NOTE: this prototype script uses shared warmup. The headline')
    print('battery is generated by momentum_clean_full.py with own warmup.')
    print('Mechanism: per-packet mass dynamics + DP-budget delivery guarantee.')
    print()

    scenarios = [
        ('GEANT', build_real, ('Geant.graphml',), 30),
        ('Abilene', build_real, ('Abilene.graphml',), 30),
        ('ER_n50_p0.05', build_syn, (50, 0.05), 30),
        ('ER_n50_p0.10', build_syn, (50, 0.10), 30),
        ('ER_n20_p0.20', build_syn, (20, 0.20), 30),
    ]
    kappa_values = [0.0, 0.1, 0.3, 0.5, 1.0]

    jobs = []
    for sn, b, ba, ns in scenarios:
        for k in kappa_values:
            for s in range(ns):
                jobs.append((sn, b, ba, s, k))

    print(f'Sweep jobs: {len(jobs)} (5 scenarios x {len(kappa_values)} kappa x 30 seeds)')
    workers = max(1, cpu_count() - 4)
    t0 = time.time()
    with Pool(workers) as pool:
        results = pool.map(run_one, jobs)
    print(f'Done in {(time.time()-t0)/60:.1f} min')

    summary = aggregate(results)
    with open(DATA / 'momentum_dp_kappa_sweep.json', 'w') as f:
        json.dump(summary, f, indent=2)

    print()
    print(f"{'Scenario':<18} {'kappa':>6} {'LASP+ dr':>10} {'MOMDP dr':>10} | "
          f"{'LASP+ loss':>11} {'MOMDP loss':>11} | {'Δ losses':>10} | {'cap diff':>9}")
    print('-' * 110)
    for s in summary:
        delta = ((s['lasp_aug_losses_mean'] - s['momentum_dp_losses_mean'])
                 / s['lasp_aug_losses_mean'] * 100
                 if s['lasp_aug_losses_mean'] > 0 else 0)
        cap_diff = (s['momentum_dp_cap_per_delivery_mean']
                    - s['lasp_aug_cap_per_delivery_mean'])
        print(f"{s['scenario']:<18} {s['kappa']:>6.2f} "
              f"{s['lasp_aug_delivery_rate_mean']:>9.1f}% "
              f"{s['momentum_dp_delivery_rate_mean']:>9.1f}% | "
              f"{s['lasp_aug_losses_mean']:>11.2f} "
              f"{s['momentum_dp_losses_mean']:>11.2f} | "
              f"{delta:>+9.1f}% | {cap_diff:>+8.2f}")
    print()
    print('Saved momentum_dp_kappa_sweep.json')
