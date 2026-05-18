"""
EMMET v5 — thermal dynamics on the loss snapshot.

Two physical ingredients added on top of v4 warm-up:

  1) Refrigerant (snapshot decay):
     After every measurement step, the frozen loss snapshot is multiplied
     by DECAY (< 1). Edges that don't keep failing 'cool down' over time.
     Heat dissipates — exactly what a refrigerant does in a real engine.

  2) Antifreeze (exploration floor):
     A small EXPLORATION_FLOOR is added to every potential evaluation.
     This keeps the field 'warm' enough to stay responsive in cold
     topologies where the snapshot is nearly empty. Equivalent to
     thermal background agitation.

  3) Warm-up scaling:
     warmup_steps = max(20, num_nodes * 5)
     Avoids over-fitting on tiny topologies (Abilene) while still
     providing enough samples on larger ones (GEANT).

Comparison: SP, LASP, EMMET cold, EMMET warm (v4), EMMET thermal (v5).
"""
import random
import statistics
import json
import os
import networkx as nx

TRAFFIC_STEPS      = 200
TTL_FACTOR         = 2
N_RUNS             = 30
ALPHA              = 1.0
BETA               = 3.0
GAMMA              = 2.0

DECAY              = 0.95   # refrigerante: snapshot enfría 5% por step
EXPLORATION_FLOOR  = 0.05   # anticongelante: ruido térmico mínimo

TOPO_DIR = '/home/clopez/emmet/data/topologies'

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

def run_warmup(G, traffic_warmup, alpha, beta, gamma):
    """Warm-up phase. Build initial loss snapshot via EMMET routing."""
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

def simulate(G, mode, traffic, alpha, beta, gamma,
             loss_snapshot=None, decay=1.0, exploration_floor=0.0):
    num_nodes = G.number_of_nodes()
    total_latency = 0.0
    losses = delivered = dropped_dead = dropped_ttl = dropped_nopath = 0
    if loss_snapshot is None:
        loss_snapshot = {}
    # Make a mutable copy if we will decay it
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
                # Update snapshot live for thermal mode
                if decay < 1.0:
                    k = tuple(sorted([u, v]))
                    snapshot[k] = snapshot.get(k, 0) + 1
                break
            total_latency += e['latency']
        if not packet_lost:
            delivered += 1

        for u, v in G.edges():
            G[u][v]['load'] *= 0.9

        # Refrigerant: cool the snapshot every step
        if decay < 1.0:
            for k in list(snapshot.keys()):
                snapshot[k] *= decay

    lpp = total_latency / delivered if delivered > 0 else 0
    return {'lat_per_packet': round(lpp, 4), 'losses': losses,
            'delivered': delivered, 'dropped_dead': dropped_dead}

def run_scenario(name, builder_fn, builder_args):
    sp_lpp,  sp_loss  = [], []
    la_lpp,  la_loss  = [], []
    em_lpp,  em_loss  = [], []  # cold
    ew_lpp,  ew_loss  = [], []  # warm (v4)
    et_lpp,  et_loss  = [], []  # thermal (v5)

    for seed in range(N_RUNS):
        traffic_seed = seed + 100000
        warmup_seed  = seed + 300000

        # Probe topology size to scale warm-up
        G_meta = builder_fn(*builder_args, topo_seed=seed)
        num_nodes = G_meta.number_of_nodes()
        warmup_steps = max(20, num_nodes * 5)

        # SP
        G = builder_fn(*builder_args, topo_seed=seed)
        traffic = generate_traffic(list(G.nodes()), TRAFFIC_STEPS, traffic_seed)
        reset_graph(G)
        sp = simulate(G, 'shortest', traffic, ALPHA, BETA, GAMMA)
        sp_lpp.append(sp['lat_per_packet']); sp_loss.append(sp['losses'])

        # LASP
        G = builder_fn(*builder_args, topo_seed=seed)
        traffic = generate_traffic(list(G.nodes()), TRAFFIC_STEPS, traffic_seed)
        reset_graph(G)
        la = simulate(G, 'lasp', traffic, ALPHA, BETA, GAMMA)
        la_lpp.append(la['lat_per_packet']); la_loss.append(la['losses'])

        # EMMET cold
        G = builder_fn(*builder_args, topo_seed=seed)
        traffic = generate_traffic(list(G.nodes()), TRAFFIC_STEPS, traffic_seed)
        reset_graph(G)
        em = simulate(G, 'emmet', traffic, ALPHA, BETA, GAMMA, loss_snapshot={})
        em_lpp.append(em['lat_per_packet']); em_loss.append(em['losses'])

        # EMMET warm (v4 — frozen snapshot)
        G = builder_fn(*builder_args, topo_seed=seed)
        warmup_traffic = generate_traffic(list(G.nodes()), warmup_steps, warmup_seed)
        reset_graph(G)
        snapshot = run_warmup(G, warmup_traffic, ALPHA, BETA, GAMMA)
        reset_graph(G)
        traffic = generate_traffic(list(G.nodes()), TRAFFIC_STEPS, traffic_seed)
        ew = simulate(G, 'emmet', traffic, ALPHA, BETA, GAMMA, loss_snapshot=snapshot)
        ew_lpp.append(ew['lat_per_packet']); ew_loss.append(ew['losses'])

        # EMMET thermal (v5 — warm + decay + floor)
        G = builder_fn(*builder_args, topo_seed=seed)
        warmup_traffic = generate_traffic(list(G.nodes()), warmup_steps, warmup_seed)
        reset_graph(G)
        snapshot = run_warmup(G, warmup_traffic, ALPHA, BETA, GAMMA)
        reset_graph(G)
        traffic = generate_traffic(list(G.nodes()), TRAFFIC_STEPS, traffic_seed)
        et = simulate(G, 'emmet', traffic, ALPHA, BETA, GAMMA,
                      loss_snapshot=snapshot,
                      decay=DECAY,
                      exploration_floor=EXPLORATION_FLOOR)
        et_lpp.append(et['lat_per_packet']); et_loss.append(et['losses'])

    def stats(xs):
        return statistics.mean(xs), statistics.stdev(xs)

    sp_m, sp_s = stats(sp_lpp); sp_lm, sp_ls = stats(sp_loss)
    la_m, la_s = stats(la_lpp); la_lm, la_ls = stats(la_loss)
    em_m, em_s = stats(em_lpp); em_lm, em_ls = stats(em_loss)
    ew_m, ew_s = stats(ew_lpp); ew_lm, ew_ls = stats(ew_loss)
    et_m, et_s = stats(et_lpp); et_lm, et_ls = stats(et_loss)

    print(f"\n=== {name} ===   (warmup_steps = {warmup_steps})")
    print(f"  {'Strategy':<16} {'Lat/pkt':>16} {'Losses':>16}")
    print(f"  {'-'*52}")
    print(f"  {'SP':<16} {sp_m:>9.3f}+/-{sp_s:.3f}   {sp_lm:>6.2f}+/-{sp_ls:.2f}")
    print(f"  {'LASP':<16} {la_m:>9.3f}+/-{la_s:.3f}   {la_lm:>6.2f}+/-{la_ls:.2f}")
    print(f"  {'EMMET cold':<16} {em_m:>9.3f}+/-{em_s:.3f}   {em_lm:>6.2f}+/-{em_ls:.2f}")
    print(f"  {'EMMET warm':<16} {ew_m:>9.3f}+/-{ew_s:.3f}   {ew_lm:>6.2f}+/-{ew_ls:.2f}")
    print(f"  {'EMMET thermal':<16} {et_m:>9.3f}+/-{et_s:.3f}   {et_lm:>6.2f}+/-{et_ls:.2f}")

    if la_lm > 0:
        print(f"  Loss vs LASP:   cold {(la_lm-em_lm)/la_lm*100:+.1f}%  "
              f"warm {(la_lm-ew_lm)/la_lm*100:+.1f}%  "
              f"thermal {(la_lm-et_lm)/la_lm*100:+.1f}%")
    if em_lm > 0:
        print(f"  Thermal vs cold EMMET: {(em_lm-et_lm)/em_lm*100:+.1f}%")

    return {
        'scenario': name,
        'warmup_steps': warmup_steps,
        'sp_lpp_mean':  sp_m, 'sp_loss_mean': sp_lm,
        'la_lpp_mean':  la_m, 'la_loss_mean': la_lm,
        'em_lpp_mean':  em_m, 'em_loss_mean': em_lm,
        'ew_lpp_mean':  ew_m, 'ew_loss_mean': ew_lm,
        'et_lpp_mean':  et_m, 'et_loss_mean': et_lm,
        'sp_lpp_std':  sp_s, 'sp_loss_std': sp_ls,
        'la_lpp_std':  la_s, 'la_loss_std': la_ls,
        'em_lpp_std':  em_s, 'em_loss_std': em_ls,
        'ew_lpp_std':  ew_s, 'ew_loss_std': ew_ls,
        'et_lpp_std':  et_s, 'et_loss_std': et_ls,
    }

if __name__ == '__main__':
    print(f"EMMET v5 thermal | DECAY={DECAY} FLOOR={EXPLORATION_FLOOR} | "
          f"{N_RUNS} runs | alpha={ALPHA} beta={BETA} gamma={GAMMA}")
    results = []
    for density, label in [(0.15, 'ER_sparse_p0.15'),
                           (0.30, 'ER_baseline_p0.30'),
                           (0.50, 'ER_dense_p0.50')]:
        results.append(run_scenario(label, build_synthetic, (20, density)))
    results.append(run_scenario('Abilene', build_real, ('Abilene.graphml',)))
    results.append(run_scenario('GEANT',   build_real, ('Geant.graphml',)))
    with open('/home/clopez/emmet/data/thermal_v5_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    print("\nResults saved to data/thermal_v5_results.json")
