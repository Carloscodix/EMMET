"""
EMMET v4 with warm-up phase.

Physical justification: a particle in a real potential field moves through
a pre-existing field, not an empty one. Similarly, EMMET should make
routing decisions on a field that has already accumulated information
about where the network fails.

Warm-up phase: 50 packets are routed before measurement begins. The
'loss' values accumulated during warm-up are frozen and become the
loss_snapshot used during measurement. No future information leakage.

Comparison: SP, ECMP, LASP, EMMET (cold), EMMET (warmed up).
"""
import random
import statistics
import json
import os
import networkx as nx

TRAFFIC_STEPS = 200
WARMUP_STEPS  = 50
TTL_FACTOR    = 2
N_RUNS        = 30
ALPHA         = 1.0
BETA          = 3.0
GAMMA         = 2.0

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

def ecmp_route(G, src, dst, ecmp_rng):
    try:
        paths = list(nx.all_shortest_paths(G, src, dst, weight='latency'))
        return ecmp_rng.choice(paths), 'delivered'
    except nx.NetworkXNoPath:
        return None, 'no_path'

def lasp_route(G, src, dst):
    def weight_fn(u, v, data):
        return data['latency'] * (1 + data['load'] / data['capacity'])
    try:
        return nx.shortest_path(G, src, dst, weight=weight_fn), 'delivered'
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

def emmet_route(G, src, dst, alpha, beta, gamma, num_nodes, loss_snapshot):
    max_hops = TTL_FACTOR * num_nodes
    path, current, visited, hops = [src], src, set(), 0
    while current != dst and hops < max_hops:
        visited.add(current)
        neighbors = [n for n in G.neighbors(current) if n not in visited]
        if not neighbors:
            return None, 'dead_end'
        best = min(neighbors,
                   key=lambda n: compute_potential(
                       G, current, n, dst, alpha, beta, gamma, loss_snapshot))
        path.append(best)
        current = best
        hops += 1
    return (path, 'delivered') if current == dst else (None, 'ttl_expired')

def run_warmup(G, traffic_warmup, alpha, beta, gamma):
    """Run warmup packets with EMMET and freeze the loss snapshot."""
    num_nodes = G.number_of_nodes()
    loss_snapshot = {}  # empty during warmup itself
    for src, dst in traffic_warmup:
        if src == dst:
            continue
        path, reason = emmet_route(G, src, dst, alpha, beta, gamma,
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
    # Freeze the loss values into the snapshot
    snapshot = {}
    for u, v in G.edges():
        snapshot[tuple(sorted([u, v]))] = G[u][v]['loss']
    return snapshot

def simulate(G, mode, traffic, alpha, beta, gamma,
             ecmp_rng=None, loss_snapshot=None):
    num_nodes = G.number_of_nodes()
    total_latency = 0.0
    losses = delivered = dropped_dead = dropped_ttl = dropped_nopath = 0
    if loss_snapshot is None:
        loss_snapshot = {}
    for src, dst in traffic:
        if src == dst:
            continue
        if mode == 'shortest':
            path, reason = shortest_path_route(G, src, dst)
        elif mode == 'ecmp':
            path, reason = ecmp_route(G, src, dst, ecmp_rng)
        elif mode == 'lasp':
            path, reason = lasp_route(G, src, dst)
        else:
            path, reason = emmet_route(G, src, dst, alpha, beta, gamma,
                                        num_nodes, loss_snapshot)
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
                e['loss'] += 1; losses += 1; packet_lost = True; break
            total_latency += e['latency']
        if not packet_lost:
            delivered += 1
        for u, v in G.edges():
            G[u][v]['load'] *= 0.9
    lpp = total_latency / delivered if delivered > 0 else 0
    return {'lat_per_packet': round(lpp, 4), 'losses': losses,
            'delivered': delivered, 'dropped_dead': dropped_dead}

def run_scenario(name, builder_fn, builder_args):
    sp_lpp,  sp_loss  = [], []
    la_lpp,  la_loss  = [], []
    em_lpp,  em_loss  = [], []  # cold EMMET
    ew_lpp,  ew_loss  = [], []  # warmed-up EMMET

    for seed in range(N_RUNS):
        traffic_seed = seed + 100000
        warmup_seed  = seed + 300000

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

        # EMMET warmed up
        G = builder_fn(*builder_args, topo_seed=seed)
        warmup_traffic = generate_traffic(list(G.nodes()), WARMUP_STEPS, warmup_seed)
        reset_graph(G)
        snapshot = run_warmup(G, warmup_traffic, ALPHA, BETA, GAMMA)
        # Reset and run measurement traffic with the frozen snapshot
        reset_graph(G)
        traffic = generate_traffic(list(G.nodes()), TRAFFIC_STEPS, traffic_seed)
        ew = simulate(G, 'emmet', traffic, ALPHA, BETA, GAMMA, loss_snapshot=snapshot)
        ew_lpp.append(ew['lat_per_packet']); ew_loss.append(ew['losses'])

    def stats(xs):
        return statistics.mean(xs), statistics.stdev(xs)

    sp_m, sp_s = stats(sp_lpp); sp_lm, sp_ls = stats(sp_loss)
    la_m, la_s = stats(la_lpp); la_lm, la_ls = stats(la_loss)
    em_m, em_s = stats(em_lpp); em_lm, em_ls = stats(em_loss)
    ew_m, ew_s = stats(ew_lpp); ew_lm, ew_ls = stats(ew_loss)

    print(f"\n=== {name} ===")
    print(f"  {'Strategy':<14} {'Lat/pkt':>16} {'Losses':>16}")
    print(f"  {'-'*50}")
    print(f"  {'SP':<14} {sp_m:>9.3f}+/-{sp_s:.3f}   {sp_lm:>6.2f}+/-{sp_ls:.2f}")
    print(f"  {'LASP':<14} {la_m:>9.3f}+/-{la_s:.3f}   {la_lm:>6.2f}+/-{la_ls:.2f}")
    print(f"  {'EMMET cold':<14} {em_m:>9.3f}+/-{em_s:.3f}   {em_lm:>6.2f}+/-{em_ls:.2f}")
    print(f"  {'EMMET warm':<14} {ew_m:>9.3f}+/-{ew_s:.3f}   {ew_lm:>6.2f}+/-{ew_ls:.2f}")

    if la_lm > 0:
        em_vs_la = (la_lm - em_lm) / la_lm * 100
        ew_vs_la = (la_lm - ew_lm) / la_lm * 100
        print(f"  Warm gain over LASP:  cold {em_vs_la:+.1f}%  -> warm {ew_vs_la:+.1f}%")
    if em_lm > 0:
        warm_gain = (em_lm - ew_lm) / em_lm * 100
        print(f"  Warm-up gain over cold EMMET: {warm_gain:+.1f}%")

    return {
        'scenario': name,
        'sp_lpp_mean':  sp_m, 'sp_loss_mean': sp_lm,
        'la_lpp_mean':  la_m, 'la_loss_mean': la_lm,
        'em_lpp_mean':  em_m, 'em_loss_mean': em_lm,
        'ew_lpp_mean':  ew_m, 'ew_loss_mean': ew_lm,
        'sp_lpp_std':  sp_s, 'sp_loss_std': sp_ls,
        'la_lpp_std':  la_s, 'la_loss_std': la_ls,
        'em_lpp_std':  em_s, 'em_loss_std': em_ls,
        'ew_lpp_std':  ew_s, 'ew_loss_std': ew_ls,
    }

if __name__ == '__main__':
    print(f"EMMET v4 with warm-up phase ({WARMUP_STEPS} packets) | "
          f"{N_RUNS} runs | alpha={ALPHA} beta={BETA} gamma={GAMMA}")
    results = []
    for density, label in [(0.15, 'ER_sparse_p0.15'),
                           (0.30, 'ER_baseline_p0.30'),
                           (0.50, 'ER_dense_p0.50')]:
        results.append(run_scenario(label, build_synthetic, (20, density)))
    results.append(run_scenario('Abilene', build_real, ('Abilene.graphml',)))
    results.append(run_scenario('GEANT',   build_real, ('Geant.graphml',)))
    with open('/home/clopez/emmet/data/warmup_v4_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    print("\nResults saved to data/warmup_v4_results.json")
