"""T1.2 — Verify selection bias in lat_delivered metric.

DeepSeek hypothesis: if EMMET delivers fewer packets than SP, its mean
latency over delivered packets may be biased downward because the
delivered subset is non-random — easy (src,dst) pairs with short paths.

This script:
1. Reloads the raw battery results
2. For each (scenario, seed), identifies the subset of (src,dst) pairs
   delivered by ALL strategies (the 'common delivery set')
3. Recomputes mean latency conditioned on this common subset
4. Compares against the original lat_delivered metric
5. Reports whether Finding 2 (dual-superiority at low density) holds
   under the unbiased metric

NOTE: this requires access to per-packet detail, which the current
raw_results.json does NOT include — only summaries per (seed, strategy).
We need to re-run a small experiment that records per-packet outcomes
for representative scenarios to do this verification properly.

This file implements the re-run with per-packet logging on the scenarios
that motivated Finding 2: ER_n20 with p in [0.05, 0.10, 0.15].
"""
import random
import statistics
import math
import json
from pathlib import Path
from multiprocessing import Pool, cpu_count
import networkx as nx

REPO_ROOT  = Path(__file__).resolve().parents[1]
DATA_DIR   = REPO_ROOT / 'data'

TRAFFIC_STEPS = 200
TTL_FACTOR    = 2
ALPHA         = 1.0
BETA          = 3.0
GAMMA         = 2.0
HALF_LIFE     = 100
DECAY         = math.exp(-math.log(2) / HALF_LIFE)
EPSILON       = 0.10

def build_synthetic(num_nodes, density, topo_seed):
    rng = random.Random(topo_seed)
    G = nx.erdos_renyi_graph(num_nodes, density, seed=topo_seed)
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

def generate_traffic(nodes_list, steps, traffic_seed):
    rng = random.Random(traffic_seed)
    return [(rng.choice(nodes_list), rng.choice(nodes_list)) for _ in range(steps)]

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

def potential(G, current, neighbor, dst, snapshot, beta_eff):
    e = G[current][neighbor]
    congestion = e['load'] / e['capacity']
    edge_key = tuple(sorted([current, neighbor]))
    loss_value = snapshot.get(edge_key, 0)
    try:
        dist = nx.shortest_path_length(G, neighbor, dst, weight='latency')
    except nx.NetworkXNoPath:
        dist = 999
    return ALPHA * dist + beta_eff * congestion + GAMMA * loss_value

def emmet_route(G, src, dst, num_nodes, snapshot, eps_rng=None,
                adaptive_beta=False):
    max_hops = TTL_FACTOR * num_nodes
    if adaptive_beta:
        n_e = G.number_of_edges()
        temp = sum(G[u][v]['load']/G[u][v]['capacity']
                   for u,v in G.edges()) / n_e if n_e > 0 else 0
        beta_eff = BETA * (1 + 1.0 * temp)
    else:
        beta_eff = BETA
    path, current, visited, hops = [src], src, set(), 0
    while current != dst and hops < max_hops:
        visited.add(current)
        neighbors = [n for n in G.neighbors(current) if n not in visited]
        if not neighbors:
            return None, 'dead_end'
        ranked = sorted(neighbors,
                        key=lambda n: potential(G, current, n, dst, snapshot, beta_eff))
        if eps_rng is not None and len(ranked) > 1 and eps_rng.random() < EPSILON:
            best = ranked[1]
        else:
            best = ranked[0]
        path.append(best)
        current = best
        hops += 1
    return (path, 'delivered') if current == dst else (None, 'ttl_expired')

def run_warmup(G, traffic_warmup, adaptive_beta=False):
    num_nodes = G.number_of_nodes()
    snapshot = {}
    for src, dst in traffic_warmup:
        if src == dst: continue
        path, _ = emmet_route(G, src, dst, num_nodes, snapshot,
                              adaptive_beta=adaptive_beta)
        if path is None: continue
        for i in range(len(path) - 1):
            u, v = path[i], path[i+1]
            e = G[u][v]
            e['load'] += 1
            if e['load'] > e['capacity']:
                e['loss'] += 1
                break
        for u, v in G.edges():
            G[u][v]['load'] *= 0.9
    out = {tuple(sorted([u, v])): G[u][v]['loss'] for u, v in G.edges()}
    return out

def simulate_with_per_packet(G, mode, traffic, snapshot=None, decay=1.0,
                              eps_rng=None, adaptive_beta=False):
    """Returns per-packet outcomes for selection-bias analysis."""
    num_nodes = G.number_of_nodes()
    snap = dict(snapshot) if (snapshot and decay < 1.0) else (snapshot or {})
    per_packet = []  # list of dicts: {src, dst, delivered, latency_if_delivered}

    for pkt_idx, (src, dst) in enumerate(traffic):
        if src == dst:
            continue
        if mode == 'sp':
            path, reason = shortest_path_route(G, src, dst)
        elif mode == 'lasp':
            path, reason = lasp_route(G, src, dst)
        else:
            path, reason = emmet_route(G, src, dst, num_nodes, snap,
                                        eps_rng, adaptive_beta=adaptive_beta)

        if path is None:
            per_packet.append({'pkt_idx': pkt_idx, 'src': src, 'dst': dst,
                               'delivered': False, 'latency': None,
                               'reason': reason})
            continue

        packet_lost = False
        path_lat = 0.0
        for i in range(len(path) - 1):
            u, v = path[i], path[i+1]
            e = G[u][v]
            e['load'] += 1
            if e['load'] > e['capacity']:
                e['loss'] += 1
                packet_lost = True
                break
            path_lat += e['latency']

        per_packet.append({
            'pkt_idx': pkt_idx, 'src': src, 'dst': dst,
            'delivered': not packet_lost,
            'latency': path_lat if not packet_lost else None,
            'reason': 'delivered' if not packet_lost else 'congestion_loss'
        })

        for u, v in G.edges():
            G[u][v]['load'] *= 0.9
        if decay < 1.0:
            for k in list(snap.keys()):
                snap[k] *= decay

    return per_packet

def run_one_with_logging(args):
    scenario_label, num_nodes, density, seed = args
    traffic_seed = seed + 100000
    warmup_seed  = seed + 300000
    eps_seed     = seed + 400000
    warmup_steps = max(20, num_nodes * 5)

    out = {'scenario': scenario_label, 'seed': seed}

    # SP
    G = build_synthetic(num_nodes, density, seed); reset_graph(G)
    traffic = generate_traffic(list(G.nodes()), TRAFFIC_STEPS, traffic_seed)
    out['sp'] = simulate_with_per_packet(G, 'sp', traffic)

    # LASP
    G = build_synthetic(num_nodes, density, seed); reset_graph(G)
    traffic = generate_traffic(list(G.nodes()), TRAFFIC_STEPS, traffic_seed)
    out['lasp'] = simulate_with_per_packet(G, 'lasp', traffic)

    # EMMET full
    G = build_synthetic(num_nodes, density, seed); reset_graph(G)
    warmup_traffic = generate_traffic(list(G.nodes()), warmup_steps, warmup_seed)
    snap = run_warmup(G, warmup_traffic, adaptive_beta=True)
    G = build_synthetic(num_nodes, density, seed); reset_graph(G)
    traffic = generate_traffic(list(G.nodes()), TRAFFIC_STEPS, traffic_seed)
    out['emmet_full'] = simulate_with_per_packet(
        G, 'emmet', traffic, snapshot=snap, decay=DECAY,
        eps_rng=random.Random(eps_seed), adaptive_beta=True)

    return out

def analyze_selection_bias(results):
    """For each scenario, compute:
    - Original lat_delivered (mean over each strategy's own delivered set)
    - Conditional lat_delivered (mean over packets delivered by ALL three)
    - Selection bias = original - conditional
    """
    by_scen = {}
    for r in results:
        by_scen.setdefault(r['scenario'], []).append(r)

    summary = []
    for scen, runs in by_scen.items():
        # Aggregate across seeds
        sp_orig_lat, sp_cond_lat = [], []
        la_orig_lat, la_cond_lat = [], []
        em_orig_lat, em_cond_lat = [], []
        sp_loss, la_loss, em_loss = [], [], []

        for r in runs:
            sp_pkts = r['sp']
            la_pkts = r['lasp']
            em_pkts = r['emmet_full']

            # Original metrics (per strategy's own delivered set)
            def avg_delivered(pkts):
                lats = [p['latency'] for p in pkts if p['delivered']]
                return sum(lats)/len(lats) if lats else 0, sum(1 for p in pkts if not p['delivered'] and p['reason']=='congestion_loss')

            sp_o, sp_l = avg_delivered(sp_pkts)
            la_o, la_l = avg_delivered(la_pkts)
            em_o, em_l = avg_delivered(em_pkts)
            sp_orig_lat.append(sp_o); sp_loss.append(sp_l)
            la_orig_lat.append(la_o); la_loss.append(la_l)
            em_orig_lat.append(em_o); em_loss.append(em_l)

            # Conditional metric (packets delivered by ALL three)
            common_idx = set()
            sp_delivered = {p['pkt_idx'] for p in sp_pkts if p['delivered']}
            la_delivered = {p['pkt_idx'] for p in la_pkts if p['delivered']}
            em_delivered = {p['pkt_idx'] for p in em_pkts if p['delivered']}
            common_idx = sp_delivered & la_delivered & em_delivered

            def cond_avg(pkts, common):
                lats = [p['latency'] for p in pkts
                        if p['delivered'] and p['pkt_idx'] in common]
                return sum(lats)/len(lats) if lats else 0

            sp_cond_lat.append(cond_avg(sp_pkts, common_idx))
            la_cond_lat.append(cond_avg(la_pkts, common_idx))
            em_cond_lat.append(cond_avg(em_pkts, common_idx))

        summary.append({
            'scenario': scen,
            'n_seeds': len(runs),
            'sp_lat_orig':  statistics.mean(sp_orig_lat),
            'sp_lat_cond':  statistics.mean(sp_cond_lat),
            'la_lat_orig':  statistics.mean(la_orig_lat),
            'la_lat_cond':  statistics.mean(la_cond_lat),
            'em_lat_orig':  statistics.mean(em_orig_lat),
            'em_lat_cond':  statistics.mean(em_cond_lat),
            'sp_losses':    statistics.mean(sp_loss),
            'la_losses':    statistics.mean(la_loss),
            'em_losses':    statistics.mean(em_loss),
        })
    return summary

if __name__ == '__main__':
    # Focus on the regime where Finding 2 (dual-superiority) was claimed
    jobs = []
    for d in [0.05, 0.10, 0.15, 0.20, 0.25, 0.30]:
        for seed in range(50):  # 50 seeds enough to detect the bias
            jobs.append((f'ER_n20_p{d:.2f}', 20, d, seed))

    print(f'Selection bias verification: {len(jobs)} jobs')
    workers = max(1, cpu_count() - 4)
    print(f'Using {workers} workers')

    with Pool(workers) as pool:
        results = pool.map(run_one_with_logging, jobs)

    summary = analyze_selection_bias(results)

    print()
    print(f"{'Scenario':<18} {'SP orig':>8} {'SP cond':>8} | "
          f"{'LASP orig':>10} {'LASP cond':>10} | "
          f"{'EM orig':>8} {'EM cond':>8} | "
          f"{'SP loss':>8} {'EM loss':>8}")
    print('-' * 110)
    for s in summary:
        print(f"{s['scenario']:<18} "
              f"{s['sp_lat_orig']:>8.3f} {s['sp_lat_cond']:>8.3f} | "
              f"{s['la_lat_orig']:>10.3f} {s['la_lat_cond']:>10.3f} | "
              f"{s['em_lat_orig']:>8.3f} {s['em_lat_cond']:>8.3f} | "
              f"{s['sp_losses']:>8.2f} {s['em_losses']:>8.2f}")

    # Save analysis
    with open(DATA_DIR / 'selection_bias_analysis.json', 'w') as f:
        json.dump(summary, f, indent=2)
    print(f"\nSaved to {DATA_DIR / 'selection_bias_analysis.json'}")

    # Verdict: does Finding 2 hold under the unbiased metric?
    print()
    print('=== FINDING 2 VERIFICATION (dual-superiority at low density) ===')
    print('Original claim: at p<0.15, EMMET has LOWER latency than SP.')
    print('Test: under the unbiased (conditional) metric, does this still hold?')
    print()
    for s in summary:
        if 'p0.05' in s['scenario'] or 'p0.10' in s['scenario'] or 'p0.15' in s['scenario']:
            sp_wins_orig = s['sp_lat_orig'] < s['em_lat_orig']
            sp_wins_cond = s['sp_lat_cond'] < s['em_lat_cond']
            verdict_orig = 'EMMET faster' if not sp_wins_orig else 'SP faster'
            verdict_cond = 'EMMET faster' if not sp_wins_cond else 'SP faster'
            consistent = '✓' if sp_wins_orig == sp_wins_cond else '⚠ DIFFERS'
            print(f"  {s['scenario']:<18}  orig: {verdict_orig:<14}  "
                  f"cond: {verdict_cond:<14}  {consistent}")
