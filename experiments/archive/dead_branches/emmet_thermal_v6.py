"""
EMMET v6 — thermal dynamics, audit-clean version.

Fixes from second hostile review:

  BUG FIX (asymmetric information):
    v5 updated the loss snapshot LIVE during measurement when packets
    failed. This gave EMMET thermal real-time information that SP, LASP
    and EMMET cold did not have.
    FIX: snapshot is built ONLY during warm-up phase. During measurement,
    the snapshot is read-only. Decay still applies (heat dissipates) but
    no new information is added.

  BUG FIX (decay scale mismatch):
    v5 applied multiplicative decay every step (0.95^200 = 3.5e-5)
    annihilating any snapshot value within ~50 steps. The cooling was
    far too aggressive given that loss values are integers from warm-up.
    FIX: switched to a per-step half-life formulation. HALF_LIFE = 100
    means the snapshot loses 50% of its value every 100 steps. This
    matches the timescale of the simulation.

  Compared strategies (all see identical real-time network state):
    - SP             : Dijkstra(latency)
    - LASP           : Dijkstra(latency * (1 + load/cap))
    - EMMET cold     : potential field with empty snapshot
    - EMMET thermal  : potential field with warm-up snapshot + decay
"""
import random
import statistics
import json
import os
import math
import networkx as nx

TRAFFIC_STEPS      = 200
TTL_FACTOR         = 2
N_RUNS             = 30
ALPHA              = 1.0
BETA               = 3.0
GAMMA              = 2.0

HALF_LIFE          = 100   # steps for snapshot to lose 50% of value
DECAY              = math.exp(-math.log(2) / HALF_LIFE)  # ~0.9931
EXPLORATION_FLOOR  = 0.05

TOPO_DIR = '/home/clopez/emmet/data/topologies'

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
    G = nx.read_graphml(os.path.join(TOPO_DIR, filename))
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

def compute_potential(G, current, neighbor, dst, alpha, beta, gamma,
                      loss_snapshot, exploration_floor=0.0):
    e = G[current][neighbor]
    congestion = e['load'] / e['capacity']
    edge_key = tuple(sorted([current, neighbor]))
    loss_value = loss_snapshot.get(edge_key, 0)
    try:
        dist = nx.shortest_path_length(G, neighbor, dst, weight='latency')
    except nx.NetworkXNoPath:
        dist = 999
    return (alpha * dist
            + beta * congestion
            + gamma * loss_value
            + exploration_floor)

def emmet_route(G, src, dst, alpha, beta, gamma, num_nodes,
                loss_snapshot, exploration_floor=0.0):
    max_hops = TTL_FACTOR * num_nodes
    path, current, visited, hops = [src], src, set(), 0
    while current != dst and hops < max_hops:
        visited.add(current)
        neighbors = [n for n in G.neighbors(current) if n not in visited]
        if not neighbors:
            return None, 'dead_end'
        best = min(neighbors,
                   key=lambda n: compute_potential(
                       G, current, n, dst, alpha, beta, gamma,
                       loss_snapshot, exploration_floor))
        path.append(best)
        current = best
        hops += 1
    return (path, 'delivered') if current == dst else (None, 'ttl_expired')

# ---------- warm-up ----------
def run_warmup(G, traffic_warmup, alpha, beta, gamma):
    """Build the loss snapshot. EMMET routes warm-up packets and accumulates
    real loss observations. Snapshot is then frozen for the measurement."""
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
             loss_snapshot=None, decay=1.0, exploration_floor=0.0):
    """
    AUDIT-CLEAN: snapshot is READ-ONLY during measurement.
    Decay applies (heat dissipates) but no new information is added.
    All strategies see identical real-time network state (load).
    Only EMMET thermal carries the warm-up memory, and only that.
    """
    num_nodes = G.number_of_nodes()
    total_latency = 0.0
    losses = delivered = dropped_dead = dropped_ttl = dropped_nopath = 0
    if loss_snapshot is None:
        loss_snapshot = {}
    snapshot = dict(loss_snapshot) if decay < 1.0 else loss_snapshot

    for src, dst in traffic:
        if src == dst:
            continue
        if mode == 'shortest':
            path, reason = shortest_path_route(G, src, dst)
        elif mode == 'lasp':
            path, reason = lasp_route(G, src, dst)
        else:
            path, reason = emmet_route(G, src, dst, alpha, beta, gamma,
                                        num_nodes, snapshot, exploration_floor)
        if path is None:
            if reason == 'dead_end':      dropped_dead   += 1
            elif reason == 'ttl_expired': dropped_ttl    += 1
            else:                         dropped_nopath += 1
            continue
        packet_lost = False
        for i in range(len(path) - 1):
            u, v = path[i], path[i+1]
            e = G[u][v]
            e['load'] += 1
            if e['load'] > e['capacity']:
                e['loss'] += 1
                losses += 1
                packet_lost = True
                # NO snapshot update — read-only during measurement
                break
            total_latency += e['latency']
        if not packet_lost:
            delivered += 1

        for u, v in G.edges():
            G[u][v]['load'] *= 0.9

        # Snapshot decay only — heat dissipates, no new heat added
        if decay < 1.0:
            for k in list(snapshot.keys()):
                snapshot[k] *= decay

    lpp = total_latency / delivered if delivered > 0 else 0
    return {'lat_per_packet': round(lpp, 4), 'losses': losses,
            'delivered': delivered, 'dropped_dead': dropped_dead}

# ---------- experiment runner ----------
def run_scenario(name, builder_fn, builder_args):
    sp_lpp,  sp_loss  = [], []
    la_lpp,  la_loss  = [], []
    em_lpp,  em_loss  = [], []
    et_lpp,  et_loss  = [], []

    for seed in range(N_RUNS):
        traffic_seed = seed + 100000
        warmup_seed  = seed + 300000

        G_meta = builder_fn(*builder_args, topo_seed=seed)
        num_nodes = G_meta.number_of_nodes()
        warmup_steps = max(20, num_nodes * 5)

        # SP
        G = builder_fn(*builder_args, topo_seed=seed)
        traffic = generate_traffic(list(G.nodes()), TRAFFIC_STEPS, traffic_seed)
        reset_graph(G)
        r = simulate(G, 'shortest', traffic, ALPHA, BETA, GAMMA)
        sp_lpp.append(r['lat_per_packet']); sp_loss.append(r['losses'])

        # LASP
        G = builder_fn(*builder_args, topo_seed=seed)
        traffic = generate_traffic(list(G.nodes()), TRAFFIC_STEPS, traffic_seed)
        reset_graph(G)
        r = simulate(G, 'lasp', traffic, ALPHA, BETA, GAMMA)
        la_lpp.append(r['lat_per_packet']); la_loss.append(r['losses'])

        # EMMET cold
        G = builder_fn(*builder_args, topo_seed=seed)
        traffic = generate_traffic(list(G.nodes()), TRAFFIC_STEPS, traffic_seed)
        reset_graph(G)
        r = simulate(G, 'emmet', traffic, ALPHA, BETA, GAMMA, loss_snapshot={})
        em_lpp.append(r['lat_per_packet']); em_loss.append(r['losses'])

        # EMMET thermal — warm-up + decay, READ-ONLY during measurement
        G = builder_fn(*builder_args, topo_seed=seed)
        warmup_traffic = generate_traffic(list(G.nodes()), warmup_steps, warmup_seed)
        reset_graph(G)
        snapshot = run_warmup(G, warmup_traffic, ALPHA, BETA, GAMMA)
        reset_graph(G)
        traffic = generate_traffic(list(G.nodes()), TRAFFIC_STEPS, traffic_seed)
        r = simulate(G, 'emmet', traffic, ALPHA, BETA, GAMMA,
                     loss_snapshot=snapshot,
                     decay=DECAY,
                     exploration_floor=EXPLORATION_FLOOR)
        et_lpp.append(r['lat_per_packet']); et_loss.append(r['losses'])

    def stats(xs):
        return statistics.mean(xs), statistics.stdev(xs)
    sp_m, sp_s = stats(sp_lpp); sp_lm, sp_ls = stats(sp_loss)
    la_m, la_s = stats(la_lpp); la_lm, la_ls = stats(la_loss)
    em_m, em_s = stats(em_lpp); em_lm, em_ls = stats(em_loss)
    et_m, et_s = stats(et_lpp); et_lm, et_ls = stats(et_loss)

    print(f"\n=== {name} ===   (warmup_steps = {warmup_steps})")
    print(f"  {'Strategy':<16} {'Lat/pkt':>16} {'Losses':>16}")
    print(f"  {'-'*52}")
    print(f"  {'SP':<16} {sp_m:>9.3f}+/-{sp_s:.3f}   {sp_lm:>6.2f}+/-{sp_ls:.2f}")
    print(f"  {'LASP':<16} {la_m:>9.3f}+/-{la_s:.3f}   {la_lm:>6.2f}+/-{la_ls:.2f}")
    print(f"  {'EMMET cold':<16} {em_m:>9.3f}+/-{em_s:.3f}   {em_lm:>6.2f}+/-{em_ls:.2f}")
    print(f"  {'EMMET thermal':<16} {et_m:>9.3f}+/-{et_s:.3f}   {et_lm:>6.2f}+/-{et_ls:.2f}")

    if la_lm > 0:
        print(f"  Loss vs LASP:   cold {(la_lm-em_lm)/la_lm*100:+.1f}%  "
              f"thermal {(la_lm-et_lm)/la_lm*100:+.1f}%")
    if em_lm > 0:
        print(f"  Thermal vs cold: {(em_lm-et_lm)/em_lm*100:+.1f}%")

    return {
        'scenario': name,
        'warmup_steps': warmup_steps,
        'sp_lpp_mean':  sp_m, 'sp_loss_mean': sp_lm,
        'la_lpp_mean':  la_m, 'la_loss_mean': la_lm,
        'em_lpp_mean':  em_m, 'em_loss_mean': em_lm,
        'et_lpp_mean':  et_m, 'et_loss_mean': et_lm,
        'sp_lpp_std':  sp_s, 'sp_loss_std': sp_ls,
        'la_lpp_std':  la_s, 'la_loss_std': la_ls,
        'em_lpp_std':  em_s, 'em_loss_std': em_ls,
        'et_lpp_std':  et_s, 'et_loss_std': et_ls,
    }

if __name__ == '__main__':
    print(f"EMMET v6 audit-clean | HALF_LIFE={HALF_LIFE} (decay={DECAY:.4f}) "
          f"FLOOR={EXPLORATION_FLOOR} | {N_RUNS} runs | "
          f"alpha={ALPHA} beta={BETA} gamma={GAMMA}")
    results = []
    for density, label in [(0.15, 'ER_sparse_p0.15'),
                           (0.30, 'ER_baseline_p0.30'),
                           (0.50, 'ER_dense_p0.50')]:
        results.append(run_scenario(label, build_synthetic, (20, density)))
    results.append(run_scenario('Abilene', build_real, ('Abilene.graphml',)))
    results.append(run_scenario('GEANT',   build_real, ('Geant.graphml',)))
    with open('/home/clopez/emmet/data/thermal_v6_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    print("\nResults saved to data/thermal_v6_results.json")
