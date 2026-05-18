"""Pre-Codex defense: compare EMMET-budget(alpha=1.25) against
LASP-augmented (same potential function, no budget — i.e., shortest
weighted path with EMMET's potential as edge weight).

This isolates the contribution of the BUDGET CONSTRAINT from the
contribution of the POTENTIAL DEFINITION.

Three strategies:
  - LASP (vanilla): weight = latency * (1 + load/cap)
  - LASP-aug:       weight = EMMET potential (latency + beta_eff*cong + gamma*loss_snap)
  - EMMET-budget:   minimize sum of EMMET potential subject to len <= alpha*sp_hops

If EMMET-budget beats LASP-aug, the budget constraint matters.
If they tie, EMMET-budget = "fancy LASP" and the paper has to pivot.
"""
import random, statistics, math, json, time
from pathlib import Path
from multiprocessing import Pool, cpu_count
import sys
sys.path.insert(0, '/home/clopez/emmet/experiments')
from emmet_budget import (
    build_syn, build_real, reset, gen_traf,
    edge_potential, emmet_budget_route, warmup,
    shortest_path_route, lasp_route,
    TRAFFIC_STEPS, BETA, THETA, DECAY
)
import networkx as nx

DATA = Path('/home/clopez/emmet/data')

def lasp_aug_route(G, src, dst, snap):
    """LASP using EMMET's potential function as edge weight."""
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

def simulate_route(G, traffic, route_fn, snap=None):
    snap_l = dict(snap) if snap else {}
    losses = delivered = nopath = 0
    cap_consumed = 0
    for src, dst in traffic:
        if src == dst: continue
        path, reason = route_fn(G, src, dst, snap_l) if snap_l else route_fn(G, src, dst)
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
        if snap_l:
            for k in list(snap_l.keys()):
                snap_l[k] *= DECAY
    attempted = delivered + losses + nopath
    return {
        'delivered': delivered, 'losses': losses, 'nopath': nopath,
        'delivery_rate': delivered/attempted*100 if attempted else 0,
        'cap_per_delivery': cap_consumed/delivered if delivered else 0,
    }

def simulate_emmet_budget(G, traffic, snap, alpha_budget):
    snap_l = dict(snap)
    losses = delivered = nopath = 0
    cap_consumed = 0
    for src, dst in traffic:
        if src == dst: continue
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
        if not lost:
            delivered += 1
            cap_consumed += path_caps
        for u, v in G.edges():
            G[u][v]['load'] *= 0.9
        for k in list(snap_l.keys()):
            snap_l[k] *= DECAY
    attempted = delivered + losses + nopath
    return {
        'delivered': delivered, 'losses': losses, 'nopath': nopath,
        'delivery_rate': delivered/attempted*100 if attempted else 0,
        'cap_per_delivery': cap_consumed/delivered if delivered else 0,
    }

def run_one(args):
    label, builder, bargs, seed, alpha_budget = args
    G = builder(*bargs, seed=seed)
    n = G.number_of_nodes()
    ws = max(20, n*5)
    out = {'scenario': label, 'seed': seed, 'num_nodes': n}

    G = builder(*bargs, seed=seed); reset(G)
    traf = gen_traf(list(G.nodes()), TRAFFIC_STEPS, seed + 100000)
    out['sp'] = simulate_route(G, traf, shortest_path_route)

    G = builder(*bargs, seed=seed); reset(G)
    traf = gen_traf(list(G.nodes()), TRAFFIC_STEPS, seed + 100000)
    out['lasp'] = simulate_route(G, traf, lasp_route)

    # Warmup using emmet_budget itself (so snap is built consistently)
    G = builder(*bargs, seed=seed); reset(G)
    wt = gen_traf(list(G.nodes()), ws, seed + 300000)
    snap = warmup(G, wt, alpha_budget)

    # LASP-aug uses the same snap as EMMET-budget (fair info)
    G = builder(*bargs, seed=seed); reset(G)
    traf = gen_traf(list(G.nodes()), TRAFFIC_STEPS, seed + 100000)
    out['lasp_aug'] = simulate_route(G, traf, lasp_aug_route, snap=snap)

    G = builder(*bargs, seed=seed); reset(G)
    traf = gen_traf(list(G.nodes()), TRAFFIC_STEPS, seed + 100000)
    out['emmet_budget'] = simulate_emmet_budget(G, traf, snap, alpha_budget)
    return out

def aggregate(results):
    by = {}
    for r in results:
        by.setdefault(r['scenario'], []).append(r)
    summary = []
    for sc, runs in sorted(by.items()):
        n = runs[0]['num_nodes']
        row = {'scenario': sc, 'n_runs': len(runs), 'num_nodes': n}
        for strat in ['sp', 'lasp', 'lasp_aug', 'emmet_budget']:
            for key in ['delivered', 'losses', 'delivery_rate', 'cap_per_delivery']:
                vals = [r[strat][key] for r in runs]
                row[f'{strat}_{key}_mean'] = statistics.mean(vals)
                if len(vals) > 1:
                    row[f'{strat}_{key}_std'] = statistics.stdev(vals)
        summary.append(row)
    return summary

if __name__ == '__main__':
    scenarios = [
        ('GEANT', build_real, ('Geant.graphml',), 100),
        ('Abilene', build_real, ('Abilene.graphml',), 100),
        ('ER_n20_p0.10', build_syn, (20, 0.10), 100),
        ('ER_n20_p0.20', build_syn, (20, 0.20), 100),
        ('ER_n50_p0.05', build_syn, (50, 0.05), 100),
        ('ER_n50_p0.10', build_syn, (50, 0.10), 100),
    ]
    ALPHA = 1.25
    jobs = []
    for sn, b, ba, ns in scenarios:
        for s in range(ns):
            jobs.append((sn, b, ba, s, ALPHA))
    print(f'LASP-aug vs EMMET-budget defense: {len(jobs)} jobs')
    with Pool(max(1, cpu_count()-4)) as pool:
        results = pool.map(run_one, jobs)
    summary = aggregate(results)

    print()
    print(f"{'Scenario':<18} {'SP_dr':>6} {'LASP_dr':>8} {'LASP+_dr':>9} {'EM_dr':>6} | "
          f"{'LASP_loss':>10} {'LASP+_loss':>11} {'EM_loss':>8} | "
          f"{'EM-LASP+ Δlosses':>18}")
    print('-' * 130)
    for s in summary:
        delta = ((s['lasp_aug_losses_mean'] - s['emmet_budget_losses_mean'])
                 / s['lasp_aug_losses_mean'] * 100 if s['lasp_aug_losses_mean'] > 0 else 0)
        print(f"{s['scenario']:<18} "
              f"{s['sp_delivery_rate_mean']:>5.1f}% "
              f"{s['lasp_delivery_rate_mean']:>7.1f}% "
              f"{s['lasp_aug_delivery_rate_mean']:>8.1f}% "
              f"{s['emmet_budget_delivery_rate_mean']:>5.1f}% | "
              f"{s['lasp_losses_mean']:>10.2f} "
              f"{s['lasp_aug_losses_mean']:>11.2f} "
              f"{s['emmet_budget_losses_mean']:>8.2f} | "
              f"{delta:>+15.1f}%")
    with open(DATA / 'budget_vs_laspaug.json', 'w') as f:
        json.dump(summary, f, indent=2)
    print(f"\nSaved budget_vs_laspaug.json")
