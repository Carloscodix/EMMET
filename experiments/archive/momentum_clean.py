"""Clean comparison: each algorithm with own warmup, 32 buckets."""
import random, statistics, math, json, time
from pathlib import Path
from multiprocessing import Pool, cpu_count
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'experiments'))
from emmet_budget import (
    build_syn, build_real, reset, gen_traf,
    edge_potential, BETA, THETA, DECAY, TRAFFIC_STEPS
)
from emmet_momentum_dp import (
    emmet_momentum_dp_route, lasp_aug_route,
    M_MAX, ALPHA_BUDGET
)
import networkx as nx

DATA = Path(__file__).resolve().parents[1] / 'data'
N_BUCKETS_CLEAN = 32

def warmup_lasp_aug(G, traf):
    """Warmup using LASP-aug routes only."""
    snap = {}
    for src, dst in traf:
        if src == dst: continue
        n_e = G.number_of_edges()
        temp = sum(G[u][v]['load']/G[u][v]['capacity'] for u,v in G.edges())/n_e if n_e else 0
        beta_eff = BETA * (1 + THETA * temp)
        def w(u, v, d):
            e = G[u][v]
            cong = e['load']/e['capacity']
            k = tuple(sorted([u,v]))
            return 1.0*e['latency'] + beta_eff*cong + 2.0*snap.get(k, 0)
        try: path = nx.shortest_path(G, src, dst, weight=w)
        except nx.NetworkXNoPath: continue
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


def warmup_momentum(G, traf, kappa, n_buckets):
    snap = {}
    for src, dst in traf:
        if src == dst: continue
        path, _ = emmet_momentum_dp_route(
            G, src, dst, snap, kappa=kappa, m_max=M_MAX,
            alpha_budget=ALPHA_BUDGET, n_buckets=n_buckets)
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


def simulate_lasp_aug(G, traffic, snap):
    snap_l = dict(snap)
    losses = delivered = nopath = 0
    cap_consumed_delivered = 0
    cap_consumed_lost = 0
    for src, dst in traffic:
        if src == dst: continue
        path, _ = lasp_aug_route(G, src, dst, snap_l)
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


def simulate_momentum(G, traffic, snap, kappa, n_buckets):
    snap_l = dict(snap)
    losses = delivered = nopath = 0
    cap_consumed_delivered = 0
    cap_consumed_lost = 0
    for src, dst in traffic:
        if src == dst: continue
        path, _ = emmet_momentum_dp_route(
            G, src, dst, snap_l, kappa=kappa, m_max=M_MAX,
            alpha_budget=ALPHA_BUDGET, n_buckets=n_buckets)
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
    n_buckets = N_BUCKETS_CLEAN
    G = builder(*bargs, seed=seed)
    n = G.number_of_nodes()
    ws = max(20, n*5)
    out = {'scenario': label, 'seed': seed, 'kappa': kappa}

    # LASP-aug with its OWN warmup
    G = builder(*bargs, seed=seed); reset(G)
    wt = gen_traf(list(G.nodes()), ws, seed + 300000)
    snap_la = warmup_lasp_aug(G, wt)
    G = builder(*bargs, seed=seed); reset(G)
    traf = gen_traf(list(G.nodes()), TRAFFIC_STEPS, seed + 100000)
    out['lasp_aug'] = simulate_lasp_aug(G, traf, snap_la)

    # Momentum with its OWN warmup, 32 buckets
    G = builder(*bargs, seed=seed); reset(G)
    wt = gen_traf(list(G.nodes()), ws, seed + 300000)
    snap_m = warmup_momentum(G, wt, kappa, n_buckets)
    G = builder(*bargs, seed=seed); reset(G)
    traf = gen_traf(list(G.nodes()), TRAFFIC_STEPS, seed + 100000)
    out['momentum_dp'] = simulate_momentum(G, traf, snap_m, kappa, n_buckets)

    return out


def aggregate(results):
    by = {}
    for r in results:
        by.setdefault(r['scenario'], []).append(r)
    summary = []
    for sc, runs in sorted(by.items()):
        row = {'scenario': sc, 'n_runs': len(runs)}
        # Carry num_nodes if present (topology-aware scenarios). Codex r4 #5.
        if 'num_nodes' in runs[0]:
            row['num_nodes_mean'] = statistics.mean([r['num_nodes'] for r in runs])
        for strat in ['lasp_aug', 'momentum_dp']:
            for key in ['delivered', 'losses', 'delivery_rate', 'cap_per_delivery', 'cap_per_attempt', 'cap_per_routed_attempt', 'cap_consumed_lost']:
                vals = [r[strat][key] for r in runs]
                row[f'{strat}_{key}_mean'] = statistics.mean(vals)
                if len(vals) > 1:
                    row[f'{strat}_{key}_std'] = statistics.stdev(vals)
        summary.append(row)
    return summary


if __name__ == '__main__':
    KAPPA = 1.0
    print(f'Clean comparison: own warmup, 32 buckets, kappa={KAPPA}')

    scenarios = [
        ('GEANT', build_real, ('Geant.graphml',), 100),
        ('Abilene', build_real, ('Abilene.graphml',), 100),
        ('ER_n50_p0.05', build_syn, (50, 0.05), 100),
        ('ER_n50_p0.10', build_syn, (50, 0.10), 100),
        ('ER_n20_p0.20', build_syn, (20, 0.20), 100),
        ('ER_n20_p0.25', build_syn, (20, 0.25), 100),
        ('ER_n20_p0.15', build_syn, (20, 0.15), 100),
    ]
    jobs = []
    for sn, b, ba, ns in scenarios:
        for s in range(ns):
            jobs.append((sn, b, ba, s, KAPPA))

    print(f'jobs: {len(jobs)}')
    workers = max(1, cpu_count() - 4)
    t0 = time.time()
    with Pool(workers) as pool:
        results = []
        for i, r in enumerate(pool.imap_unordered(run_one, jobs, chunksize=4)):
            results.append(r)
            if (i+1) % 100 == 0:
                elapsed = time.time() - t0
                print(f'  {i+1}/{len(jobs)} | {(i+1)/elapsed:.1f}/s | '
                      f'ETA {(len(jobs)-(i+1))/((i+1)/elapsed)/60:.1f}m')
    print(f'Done in {(time.time()-t0)/60:.1f} min')

    summary = aggregate(results)
    with open(DATA / 'momentum_clean.json', 'w') as f:
        json.dump(summary, f, indent=2)

    print()
    print(f"{'Scenario':<18} {'LASP+ dr':>10} {'MOMDP dr':>10} | "
          f"{'LASP+ loss':>11} {'MOMDP loss':>11} | {'Δ losses':>10} | {'cap diff':>9}")
    print('-' * 110)
    for s in summary:
        delta = ((s['lasp_aug_losses_mean'] - s['momentum_dp_losses_mean'])
                 / s['lasp_aug_losses_mean'] * 100
                 if s['lasp_aug_losses_mean'] > 0 else 0)
        cap_diff = (s['momentum_dp_cap_per_delivery_mean']
                    - s['lasp_aug_cap_per_delivery_mean'])
        print(f"{s['scenario']:<18} "
              f"{s['lasp_aug_delivery_rate_mean']:>9.1f}% "
              f"{s['momentum_dp_delivery_rate_mean']:>9.1f}% | "
              f"{s['lasp_aug_losses_mean']:>11.2f} "
              f"{s['momentum_dp_losses_mean']:>11.2f} | "
              f"{delta:>+9.1f}% | {cap_diff:>+8.2f}")
