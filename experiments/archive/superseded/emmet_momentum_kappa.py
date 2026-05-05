"""EMMET-momentum (kappa-only): per-packet mass that grows with thermal load.

ISOLATED MECHANISM: only the mass dynamics. No inertia, no energy budget.
Goal: see if mass-grows-with-heat ALONE provides improvement over
LASP-aug (Dijkstra with EMMET potential).

Key idea (from Carlos's brainstorm):
  A packet that has traversed congested edges acquires effective mass.
  This mass is a property OF THE PACKET, carried with it.
  At each subsequent hop, the packet's mass affects the routing cost:
    cost(u -> n) = potential(u, n) * m(packet)
  Heavier packets are routed through wider/cooler edges; light packets
  can take faster but more constrained paths.

This is something LASP-aug structurally CANNOT do, because LASP-aug
computes one shortest weighted path with a single global state — it has
no notion of per-packet history.
"""
import random, statistics, math, json, time
from pathlib import Path
from multiprocessing import Pool, cpu_count
import sys
sys.path.insert(0, '/home/clopez/emmet/experiments')
from emmet_budget import (
    build_syn, build_real, reset, gen_traf,
    edge_potential, warmup as warmup_budget,
    shortest_path_route, lasp_route,
    TRAFFIC_STEPS, BETA, THETA, DECAY
)
import networkx as nx

REPO = Path('/home/clopez/emmet')
DATA = REPO / 'data'

# Mass dynamics parameters
M_INITIAL = 1.0
M_MAX     = 5.0   # cap to prevent runaway
KAPPA     = 0.3   # mass growth rate per unit congestion

def emmet_momentum_route(G, src, dst, snap, kappa=KAPPA, m_max=M_MAX):
    """Per-packet routing with mass dynamics.

    The packet carries m(t). At each hop, choose the neighbor n that
    minimizes m * potential(u,n). Mass grows after traversing edges
    proportional to local congestion.
    """
    if src == dst:
        return [src], 0
    n_e = G.number_of_edges()
    if n_e:
        temp = sum(G[u][v]['load']/G[u][v]['capacity'] for u,v in G.edges()) / n_e
    else:
        temp = 0
    beta_eff = BETA * (1 + THETA * temp)

    # We use Dijkstra-like greedy descent with mass-aware cost
    # but mass evolves WITH the path, so this is path-dependent.
    # Solution: best-first search with state = (node, mass_so_far)
    # Bounded: we cap mass at m_max so state space is finite.

    # For tractability we use a simple greedy descent with the current
    # mass as a multiplier. This matches the local-decision philosophy
    # of EMMET and is what a real router would do (no global lookahead).

    visited = {src}
    path = [src]
    cur = src
    m = M_INITIAL
    max_hops = 2 * G.number_of_nodes()  # generous bound, no budget
    hops = 0

    while cur != dst and hops < max_hops:
        nbrs = [n for n in G.neighbors(cur) if n not in visited]
        if not nbrs:
            # Dead end — unlike EMMET-fb, we report this honestly
            return None, m

        # Cost of moving to each neighbor, scaled by current mass
        def cost(n):
            base = edge_potential(G, cur, n, snap, beta_eff)
            return m * base

        best = min(nbrs, key=cost)

        # Mass update: grows with the congestion of the edge we're about to cross
        e = G[cur][best]
        congestion = e['load'] / e['capacity']
        m = min(m * (1 + kappa * congestion), m_max)

        path.append(best)
        visited.add(best)
        cur = best
        hops += 1

    if cur == dst:
        return path, m
    return None, m


def warmup(G, traf, kappa, m_max):
    """Warmup snapshot using emmet_momentum itself."""
    snap = {}
    for src, dst in traf:
        if src == dst: continue
        path, _ = emmet_momentum_route(G, src, dst, snap, kappa, m_max)
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


def lasp_aug_route(G, src, dst, snap):
    """LASP using EMMET's potential function as edge weight (defense baseline)."""
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


def simulate_momentum(G, traffic, snap, kappa, m_max):
    snap_l = dict(snap)
    losses = delivered = nopath = dead = 0
    cap_consumed = 0
    for src, dst in traffic:
        if src == dst: continue
        path, final_m = emmet_momentum_route(G, src, dst, snap_l, kappa, m_max)
        if path is None or len(path) < 2:
            dead += 1
            continue
        lost = False
        path_caps = 0
        for i in range(len(path)-1):
            u, v = path[i], path[i+1]
            e = G[u][v]
            # Mass-aware capacity consumption: heavy packet takes more capacity
            # For now we keep load increment at 1 but ALL future routing decisions
            # will see the inflated congestion via the path the packet took.
            # Future extension: heavy packet adds m units of load, not 1.
            e['load'] += 1
            path_caps += 1
            if e['load'] > e['capacity']:
                e['loss'] += 1
                losses += 1
                lost = True
                break
        if not lost:
            delivered += 1
            cap_consumed += path_caps
        for u, v in G.edges():
            G[u][v]['load'] *= 0.9
        for k in list(snap_l.keys()):
            snap_l[k] *= DECAY
    attempted = delivered + losses + dead + nopath
    return {
        'delivered': delivered, 'losses': losses,
        'dead': dead, 'nopath': nopath,
        'delivery_rate': delivered/attempted*100 if attempted else 0,
        'cap_per_delivery': cap_consumed/delivered if delivered else 0,
    }


def simulate_lasp_aug(G, traffic, snap):
    snap_l = dict(snap)
    losses = delivered = nopath = 0
    cap_consumed = 0
    for src, dst in traffic:
        if src == dst: continue
        path, reason = lasp_aug_route(G, src, dst, snap_l)
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
            cap_consumed += path_caps
        for u, v in G.edges():
            G[u][v]['load'] *= 0.9
        for k in list(snap_l.keys()):
            snap_l[k] *= DECAY
    attempted = delivered + losses + nopath
    return {
        'delivered': delivered, 'losses': losses,
        'dead': 0, 'nopath': nopath,
        'delivery_rate': delivered/attempted*100 if attempted else 0,
        'cap_per_delivery': cap_consumed/delivered if delivered else 0,
    }


def run_one(args):
    label, builder, bargs, seed, kappa, m_max = args
    G = builder(*bargs, seed=seed)
    n = G.number_of_nodes()
    ws = max(20, n*5)
    out = {'scenario': label, 'seed': seed, 'kappa': kappa, 'm_max': m_max}

    # Warmup (use momentum routing for fairness)
    G = builder(*bargs, seed=seed); reset(G)
    wt = gen_traf(list(G.nodes()), ws, seed + 300000)
    snap = warmup(G, wt, kappa, m_max)

    # LASP-aug uses same snap (fair info)
    G = builder(*bargs, seed=seed); reset(G)
    traf = gen_traf(list(G.nodes()), TRAFFIC_STEPS, seed + 100000)
    out['lasp_aug'] = simulate_lasp_aug(G, traf, snap)

    G = builder(*bargs, seed=seed); reset(G)
    traf = gen_traf(list(G.nodes()), TRAFFIC_STEPS, seed + 100000)
    out['momentum'] = simulate_momentum(G, traf, snap, kappa, m_max)

    return out


def aggregate(results):
    by = {}
    for r in results:
        by.setdefault((r['scenario'], r['kappa']), []).append(r)
    summary = []
    for (sc, k), runs in sorted(by.items()):
        row = {'scenario': sc, 'kappa': k, 'n_runs': len(runs)}
        for strat in ['lasp_aug', 'momentum']:
            for key in ['delivered', 'losses', 'dead', 'delivery_rate', 'cap_per_delivery']:
                vals = [r[strat].get(key, 0) for r in runs]
                row[f'{strat}_{key}_mean'] = statistics.mean(vals)
                if len(vals) > 1:
                    row[f'{strat}_{key}_std'] = statistics.stdev(vals)
        summary.append(row)
    return summary


if __name__ == '__main__':
    print('=== EMMET-momentum (kappa only) prototype ===')
    print('Mechanism: mass-grows-with-heat. Per-packet state.')
    print('Baseline: LASP-aug (same potential, no per-packet state).')
    print()

    scenarios = [
        ('GEANT', build_real, ('Geant.graphml',), 50),
        ('Abilene', build_real, ('Abilene.graphml',), 50),
        ('ER_n50_p0.05', build_syn, (50, 0.05), 50),
        ('ER_n50_p0.10', build_syn, (50, 0.10), 50),
        ('ER_n20_p0.20', build_syn, (20, 0.20), 50),
    ]
    kappa_values = [0.0, 0.1, 0.3, 0.5, 1.0]
    m_max = 5.0

    jobs = []
    for sn, b, ba, ns in scenarios:
        for k in kappa_values:
            for s in range(ns):
                jobs.append((sn, b, ba, s, k, m_max))

    print(f'Sweep jobs: {len(jobs)} (5 scenarios x {len(kappa_values)} kappa x 50 seeds)')
    workers = max(1, cpu_count() - 4)
    print(f'workers: {workers}')

    t0 = time.time()
    with Pool(workers) as pool:
        results = pool.map(run_one, jobs)
    print(f'Done in {(time.time()-t0)/60:.1f} min')

    summary = aggregate(results)
    with open(DATA / 'momentum_kappa_sweep.json', 'w') as f:
        json.dump(summary, f, indent=2)

    print()
    print(f"{'Scenario':<18} {'kappa':>6} {'LASP+ dr':>10} {'MOM dr':>8} | "
          f"{'LASP+ loss':>11} {'MOM loss':>9} | {'Δ losses':>10}")
    print('-' * 90)
    for s in summary:
        delta = ((s['lasp_aug_losses_mean'] - s['momentum_losses_mean'])
                 / s['lasp_aug_losses_mean'] * 100
                 if s['lasp_aug_losses_mean'] > 0 else 0)
        print(f"{s['scenario']:<18} {s['kappa']:>6.2f} "
              f"{s['lasp_aug_delivery_rate_mean']:>9.1f}% "
              f"{s['momentum_delivery_rate_mean']:>7.1f}% | "
              f"{s['lasp_aug_losses_mean']:>11.2f} "
              f"{s['momentum_losses_mean']:>9.2f} | "
              f"{delta:>+9.1f}%")

    print()
    print('Saved momentum_kappa_sweep.json')
