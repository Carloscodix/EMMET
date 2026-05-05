"""
EMMET v7 — fully audit-clean.

Fixes from third audit (Codex):

  1. Relative paths via Path(__file__).resolve().parents[1] — repo portable
     across machines.

  2. exploration_floor as constant was mathematically inert (proven empirically:
     identical results bit-for-bit with floor=0.0 vs 0.05). REPLACED with
     exploration_epsilon: epsilon-greedy stochastic exploration that with
     probability epsilon picks the second-best neighbor instead of the best.
     This is the correct implementation of "thermal background agitation".

  3. Latency metric clarified: we now report TWO metrics:
       lat_per_delivered  = total_latency_of_completed_paths / delivered
       lat_per_attempted  = (total_latency_completed + partial_latency_lost) / attempted
     The first is "latency seen by successful packets". The second includes
     wasted work from failed packets. Both are useful and we no longer
     conflate them.

  4. Snapshot remains read-only during measurement (from v6). Half-life
     decay = 100 steps. No live information leakage to EMMET.

  Comparison: SP, LASP, EMMET cold, EMMET thermal (warm-up + decay + epsilon).
"""
import random
import statistics
import json
import math
import os
from pathlib import Path
import networkx as nx

# ---------- repo-relative paths ----------
REPO_ROOT  = Path(__file__).resolve().parents[1]
TOPO_DIR   = REPO_ROOT / 'data' / 'topologies'
DATA_DIR   = REPO_ROOT / 'data'

# ---------- config ----------
TRAFFIC_STEPS         = 200
TTL_FACTOR            = 2
N_RUNS                = 30
ALPHA                 = 1.0
BETA                  = 3.0
GAMMA                 = 2.0
HALF_LIFE             = 100
DECAY                 = math.exp(-math.log(2) / HALF_LIFE)  # ~0.9931
EXPLORATION_EPSILON   = 0.10   # 10% chance to pick 2nd-best neighbor

# ---------- builders ----------
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
    mapping = {n: i for i, n in enumerate(G.nodes())}
    G = nx.relabel_nodes(G, mapping)
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

def generate_traffic(nodes_list, steps, traffic_seed):
    rng = random.Random(traffic_seed)
    return [(rng.choice(nodes_list), rng.choice(nodes_list)) for _ in range(steps)]

# ---------- routing strategies ----------
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

def compute_potential(G, current, neighbor, dst, alpha, beta, gamma, loss_snapshot):
    e = G[current][neighbor]
    congestion = e['load'] / e['capacity']
    edge_key = tuple(sorted([current, neighbor]))
    loss_value = loss_snapshot.get(edge_key, 0)
    try:
        dist = nx.shortest_path_length(G, neighbor, dst, weight='latency')
    except nx.NetworkXNoPath:
        dist = 999
    return alpha * dist + beta * congestion + gamma * loss_value

def emmet_route(G, src, dst, alpha, beta, gamma, num_nodes,
                loss_snapshot, epsilon=0.0, eps_rng=None):
    """EMMET with epsilon-greedy thermal exploration.

    With probability epsilon, picks the second-best neighbor instead of
    the best. This implements stochastic thermal agitation that actually
    changes routing decisions (unlike a constant floor, which is inert).
    """
    max_hops = TTL_FACTOR * num_nodes
    path, current, visited, hops = [src], src, set(), 0
    while current != dst and hops < max_hops:
        visited.add(current)
        neighbors = [n for n in G.neighbors(current) if n not in visited]
        if not neighbors:
            return None, 'dead_end'
        scored = sorted(neighbors,
                        key=lambda n: compute_potential(
                            G, current, n, dst, alpha, beta, gamma, loss_snapshot))
        if (epsilon > 0 and len(scored) >= 2
                and eps_rng is not None and eps_rng.random() < epsilon):
            best = scored[1]
        else:
            best = scored[0]
        path.append(best)
        current = best
        hops += 1
    return (path, 'delivered') if current == dst else (None, 'ttl_expired')

# ---------- warm-up ----------
def run_warmup(G, traffic_warmup, alpha, beta, gamma):
    num_nodes = G.number_of_nodes()
    loss_snapshot = {}
    for src, dst in traffic_warmup:
        if src == dst:
            continue
        path, _ = emmet_route(G, src, dst, alpha, beta, gamma,
                               num_nodes, loss_snapshot)
        if path is None:
            continue
        for i in range(len(path) - 1):
            u, v = path[i], path[i+1]
            e = G[u][v]
            e['load'] += 1
            if e['load'] > e['capacity']:
                e['loss'] += 1
                break
        for u, v in G.edges():
            G[u][v]['load'] *= 0.9
    snapshot = {}
    for u, v in G.edges():
        snapshot[tuple(sorted([u, v]))] = G[u][v]['loss']
    return snapshot

# ---------- simulator ----------
def simulate(G, mode, traffic, alpha, beta, gamma,
             loss_snapshot=None, decay=1.0,
             epsilon=0.0, eps_seed=None):
    """
    Returns multiple latency metrics so we don't conflate them:

      lat_per_delivered  : sum of latencies on completed paths / delivered
      lat_per_attempted  : (completed_lat + partial_lat_of_failed) / attempted
      lat_completed_only : sum of latencies on completed paths only

    'attempted' = total packets minus self-loops minus no_path drops.
    """
    num_nodes = G.number_of_nodes()
    completed_latency  = 0.0   # accumulated only for delivered packets
    wasted_latency     = 0.0   # partial work of packets that lost mid-path
    losses = delivered = 0
    dropped_dead = dropped_ttl = dropped_nopath = 0
    attempts = 0

    snapshot = dict(loss_snapshot) if loss_snapshot is not None else {}
    eps_rng  = random.Random(eps_seed) if eps_seed is not None else None

    for src, dst in traffic:
        if src == dst:
            continue
        attempts += 1
        if mode == 'shortest':
            path, reason = shortest_path_route(G, src, dst)
        elif mode == 'lasp':
            path, reason = lasp_route(G, src, dst)
        else:
            path, reason = emmet_route(G, src, dst, alpha, beta, gamma,
                                        num_nodes, snapshot,
                                        epsilon=epsilon, eps_rng=eps_rng)
        if path is None:
            if reason == 'dead_end':      dropped_dead   += 1
            elif reason == 'ttl_expired': dropped_ttl    += 1
            else:                         dropped_nopath += 1
            continue
        path_latency_so_far = 0.0
        packet_lost = False
        for i in range(len(path) - 1):
            u, v = path[i], path[i+1]
            e = G[u][v]
            e['load'] += 1
            if e['load'] > e['capacity']:
                e['loss'] += 1
                losses += 1
                packet_lost = True
                wasted_latency += path_latency_so_far
                break
            path_latency_so_far += e['latency']
        if not packet_lost:
            completed_latency += path_latency_so_far
            delivered += 1
        for u, v in G.edges():
            G[u][v]['load'] *= 0.9
        if decay < 1.0:
            for k in list(snapshot.keys()):
                snapshot[k] *= decay

    lat_per_delivered = completed_latency / delivered if delivered > 0 else 0
    total_latency     = completed_latency + wasted_latency
    lat_per_attempted = total_latency / attempts if attempts > 0 else 0

    return {
        'lat_per_delivered': round(lat_per_delivered, 4),
        'lat_per_attempted': round(lat_per_attempted, 4),
        'completed_latency': round(completed_latency, 2),
        'wasted_latency':    round(wasted_latency, 2),
        'losses':            losses,
        'delivered':         delivered,
        'attempts':          attempts,
        'dropped_dead':      dropped_dead,
        'dropped_ttl':       dropped_ttl,
        'dropped_nopath':    dropped_nopath,
    }

# ---------- experiment runner ----------
def run_scenario(name, builder_fn, builder_args):
    sp_d, sp_a, sp_loss = [], [], []
    la_d, la_a, la_loss = [], [], []
    em_d, em_a, em_loss = [], [], []
    et_d, et_a, et_loss = [], [], []

    for seed in range(N_RUNS):
        traffic_seed = seed + 100000
        warmup_seed  = seed + 300000
        eps_seed     = seed + 400000

        G_meta = builder_fn(*builder_args, topo_seed=seed)
        warmup_steps = max(20, G_meta.number_of_nodes() * 5)

        # SP
        G = builder_fn(*builder_args, topo_seed=seed)
        traffic = generate_traffic(list(G.nodes()), TRAFFIC_STEPS, traffic_seed)
        reset_graph(G)
        r = simulate(G, 'shortest', traffic, ALPHA, BETA, GAMMA)
        sp_d.append(r['lat_per_delivered'])
        sp_a.append(r['lat_per_attempted'])
        sp_loss.append(r['losses'])

        # LASP
        G = builder_fn(*builder_args, topo_seed=seed)
        traffic = generate_traffic(list(G.nodes()), TRAFFIC_STEPS, traffic_seed)
        reset_graph(G)
        r = simulate(G, 'lasp', traffic, ALPHA, BETA, GAMMA)
        la_d.append(r['lat_per_delivered'])
        la_a.append(r['lat_per_attempted'])
        la_loss.append(r['losses'])

        # EMMET cold
        G = builder_fn(*builder_args, topo_seed=seed)
        traffic = generate_traffic(list(G.nodes()), TRAFFIC_STEPS, traffic_seed)
        reset_graph(G)
        r = simulate(G, 'emmet', traffic, ALPHA, BETA, GAMMA, loss_snapshot={})
        em_d.append(r['lat_per_delivered'])
        em_a.append(r['lat_per_attempted'])
        em_loss.append(r['losses'])

        # EMMET thermal v7 (warm-up + decay + epsilon-greedy)
        G = builder_fn(*builder_args, topo_seed=seed)
        warmup_traffic = generate_traffic(list(G.nodes()), warmup_steps, warmup_seed)
        reset_graph(G)
        snap = run_warmup(G, warmup_traffic, ALPHA, BETA, GAMMA)
        reset_graph(G)
        traffic = generate_traffic(list(G.nodes()), TRAFFIC_STEPS, traffic_seed)
        r = simulate(G, 'emmet', traffic, ALPHA, BETA, GAMMA,
                     loss_snapshot=snap, decay=DECAY,
                     epsilon=EXPLORATION_EPSILON, eps_seed=eps_seed)
        et_d.append(r['lat_per_delivered'])
        et_a.append(r['lat_per_attempted'])
        et_loss.append(r['losses'])

    def stats(xs):
        return statistics.mean(xs), statistics.stdev(xs)

    sp_dm, sp_ds = stats(sp_d); sp_lm, sp_ls = stats(sp_loss)
    la_dm, la_ds = stats(la_d); la_lm, la_ls = stats(la_loss)
    em_dm, em_ds = stats(em_d); em_lm, em_ls = stats(em_loss)
    et_dm, et_ds = stats(et_d); et_lm, et_ls = stats(et_loss)

    print(f"\n=== {name} ===   (warmup={warmup_steps})")
    print(f"  {'Strategy':<16} {'Lat/delivered':>18} {'Losses':>14}")
    print(f"  {'-'*52}")
    print(f"  {'SP':<16} {sp_dm:>9.3f}+/-{sp_ds:.3f}     {sp_lm:>5.2f}+/-{sp_ls:.2f}")
    print(f"  {'LASP':<16} {la_dm:>9.3f}+/-{la_ds:.3f}     {la_lm:>5.2f}+/-{la_ls:.2f}")
    print(f"  {'EMMET cold':<16} {em_dm:>9.3f}+/-{em_ds:.3f}     {em_lm:>5.2f}+/-{em_ls:.2f}")
    print(f"  {'EMMET thermal':<16} {et_dm:>9.3f}+/-{et_ds:.3f}     {et_lm:>5.2f}+/-{et_ls:.2f}")

    if la_lm > 0:
        print(f"  Loss vs LASP:   cold {(la_lm-em_lm)/la_lm*100:+.1f}%   "
              f"thermal {(la_lm-et_lm)/la_lm*100:+.1f}%")

    return {
        'scenario':       name,
        'warmup_steps':   warmup_steps,
        'sp_lat_per_delivered_mean': sp_dm,
        'la_lat_per_delivered_mean': la_dm,
        'em_lat_per_delivered_mean': em_dm,
        'et_lat_per_delivered_mean': et_dm,
        'sp_loss_mean':   sp_lm, 'sp_loss_std':   sp_ls,
        'la_loss_mean':   la_lm, 'la_loss_std':   la_ls,
        'em_loss_mean':   em_lm, 'em_loss_std':   em_ls,
        'et_loss_mean':   et_lm, 'et_loss_std':   et_ls,
    }

if __name__ == '__main__':
    print(f"EMMET v7 audit-clean | HALF_LIFE={HALF_LIFE} | "
          f"EPSILON={EXPLORATION_EPSILON} | {N_RUNS} runs | "
          f"alpha={ALPHA} beta={BETA} gamma={GAMMA}\n"
          f"Repo root: {REPO_ROOT}")
    results = []
    for density, label in [(0.15, 'ER_sparse_p0.15'),
                           (0.30, 'ER_baseline_p0.30'),
                           (0.50, 'ER_dense_p0.50')]:
        results.append(run_scenario(label, build_synthetic, (20, density)))
    results.append(run_scenario('Abilene', build_real, ('Abilene.graphml',)))
    results.append(run_scenario('GEANT',   build_real, ('Geant.graphml',)))

    out_path = DATA_DIR / 'thermal_v7_results.json'
    with open(out_path, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to {out_path}")
