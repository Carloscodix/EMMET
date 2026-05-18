"""
ECMP (Equal-Cost Multi-Path) baseline vs EMMET.

ECMP is the industry standard for load balancing in datacenters and IP networks.
When multiple shortest paths exist between src and dst, ECMP picks one at random
(simulating hash-based flow distribution).

This experiment compares:
- Shortest Path (single deterministic route)
- ECMP            (random choice among shortest paths)
- EMMET           (gradient descent on composite potential)

across both synthetic Erdos-Renyi graphs and real topologies (Abilene, GEANT).
"""
import random
import statistics
import json
import os
import networkx as nx

TRAFFIC_STEPS = 200
TTL_FACTOR    = 2
N_RUNS        = 30
ALPHA         = 1.0
BETA          = 3.0
GAMMA         = 2.0

TOPO_DIR = '/home/clopez/emmet/data/topologies'

# ----------------------------
# Graph builders
# ----------------------------
def build_synthetic(num_nodes, density, seed):
    rng = random.Random(seed)
    G = nx.erdos_renyi_graph(num_nodes, density, seed=seed)
    for u, v in G.edges():
        G[u][v]['latency']  = rng.uniform(1, 5)
        G[u][v]['capacity'] = rng.randint(3, 6)
        G[u][v]['load']     = 0
        G[u][v]['loss']     = 0
    return G

def build_real(filename, seed):
    G = nx.read_graphml(os.path.join(TOPO_DIR, filename))
    G = nx.Graph(G)
    mapping = {n: i for i, n in enumerate(G.nodes())}
    G = nx.relabel_nodes(G, mapping)
    rng = random.Random(seed)
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

# ----------------------------
# Routing strategies
# ----------------------------
def shortest_path_route(G, src, dst):
    try:
        return nx.shortest_path(G, src, dst, weight='latency'), 'delivered'
    except nx.NetworkXNoPath:
        return None, 'no_path'

def ecmp_route(G, src, dst, rng):
    """ECMP: pick uniformly at random from all shortest paths.

    Real ECMP hashes the flow tuple to a path index. We simulate this with
    uniform random choice among equal-cost paths — same statistical effect
    over a large packet population.
    """
    try:
        paths = list(nx.all_shortest_paths(G, src, dst, weight='latency'))
        return rng.choice(paths), 'delivered'
    except nx.NetworkXNoPath:
        return None, 'no_path'

def compute_potential(G, current, neighbor, dst, alpha, beta, gamma):
    e = G[current][neighbor]
    congestion = e['load'] / e['capacity']
    try:
        dist = nx.shortest_path_length(G, neighbor, dst, weight='latency')
    except nx.NetworkXNoPath:
        dist = 999
    return alpha * dist + beta * congestion + gamma * e['loss']

def emmet_route(G, src, dst, alpha, beta, gamma, num_nodes):
    max_hops = TTL_FACTOR * num_nodes
    path, current, visited, hops = [src], src, set(), 0
    while current != dst and hops < max_hops:
        visited.add(current)
        neighbors = [n for n in G.neighbors(current) if n not in visited]
        if not neighbors:
            return None, 'dead_end'
        best = min(neighbors,
                   key=lambda n: compute_potential(G, current, n, dst, alpha, beta, gamma))
        path.append(best)
        current = best
        hops += 1
    return (path, 'delivered') if current == dst else (None, 'ttl_expired')

# ----------------------------
# Simulator
# ----------------------------
def simulate(G, mode, steps, alpha, beta, gamma, rng):
    num_nodes = G.number_of_nodes()
    nodes_list = list(G.nodes())
    total_latency = 0.0
    losses = delivered = dropped_dead = dropped_ttl = dropped_nopath = 0
    for _ in range(steps):
        src = rng.choice(nodes_list)
        dst = rng.choice(nodes_list)
        if src == dst:
            continue
        if mode == 'shortest':
            path, reason = shortest_path_route(G, src, dst)
        elif mode == 'ecmp':
            path, reason = ecmp_route(G, src, dst, rng)
        else:
            path, reason = emmet_route(G, src, dst, alpha, beta, gamma, num_nodes)
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
            'delivered': delivered}

# ----------------------------
# Experiment runner
# ----------------------------
def run_scenario(name, builder_fn, builder_args):
    sp_lpp, sp_loss = [], []
    ec_lpp, ec_loss = [], []
    em_lpp, em_loss = [], []

    for seed in range(N_RUNS):
        # Same topology and traffic seed across all three strategies
        G = builder_fn(*builder_args, seed=seed)
        rng = random.Random(seed + 10000)
        reset_graph(G)
        sp = simulate(G, 'shortest', TRAFFIC_STEPS, ALPHA, BETA, GAMMA, rng)

        G = builder_fn(*builder_args, seed=seed)
        rng = random.Random(seed + 10000)
        reset_graph(G)
        ec = simulate(G, 'ecmp',     TRAFFIC_STEPS, ALPHA, BETA, GAMMA, rng)

        G = builder_fn(*builder_args, seed=seed)
        rng = random.Random(seed + 10000)
        reset_graph(G)
        em = simulate(G, 'emmet',    TRAFFIC_STEPS, ALPHA, BETA, GAMMA, rng)

        sp_lpp.append(sp['lat_per_packet']); sp_loss.append(sp['losses'])
        ec_lpp.append(ec['lat_per_packet']); ec_loss.append(ec['losses'])
        em_lpp.append(em['lat_per_packet']); em_loss.append(em['losses'])

    sp_m_lat, ec_m_lat, em_m_lat = map(statistics.mean, [sp_lpp, ec_lpp, em_lpp])
    sp_m_loss, ec_m_loss, em_m_loss = map(statistics.mean, [sp_loss, ec_loss, em_loss])

    print(f"\n=== {name} ===")
    print(f"  {'Strategy':<10} {'Lat/pkt':>14} {'Losses':>14}")
    print(f"  {'-'*42}")
    print(f"  {'SP':<10} {sp_m_lat:>8.3f}+/-{statistics.stdev(sp_lpp):.3f}  "
          f"{sp_m_loss:>6.2f}+/-{statistics.stdev(sp_loss):.2f}")
    print(f"  {'ECMP':<10} {ec_m_lat:>8.3f}+/-{statistics.stdev(ec_lpp):.3f}  "
          f"{ec_m_loss:>6.2f}+/-{statistics.stdev(ec_loss):.2f}")
    print(f"  {'EMMET':<10} {em_m_lat:>8.3f}+/-{statistics.stdev(em_lpp):.3f}  "
          f"{em_m_loss:>6.2f}+/-{statistics.stdev(em_loss):.2f}")

    # Comparisons
    if sp_m_loss > 0:
        ec_loss_red = (sp_m_loss - ec_m_loss) / sp_m_loss * 100
        em_loss_red = (sp_m_loss - em_m_loss) / sp_m_loss * 100
        print(f"  Loss reduction vs SP:  ECMP {ec_loss_red:+.1f}%   EMMET {em_loss_red:+.1f}%")
    if ec_m_loss > 0:
        em_vs_ecmp = (ec_m_loss - em_m_loss) / ec_m_loss * 100
        print(f"  EMMET vs ECMP loss:    {em_vs_ecmp:+.1f}%")
    if sp_m_lat > 0:
        ec_lat_d = (ec_m_lat - sp_m_lat) / sp_m_lat * 100
        em_lat_d = (em_m_lat - sp_m_lat) / sp_m_lat * 100
        print(f"  Delta lat vs SP:       ECMP {ec_lat_d:+.1f}%   EMMET {em_lat_d:+.1f}%")

    return {
        'scenario': name,
        'sp_lpp_mean': sp_m_lat, 'sp_loss_mean': sp_m_loss,
        'ec_lpp_mean': ec_m_lat, 'ec_loss_mean': ec_m_loss,
        'em_lpp_mean': em_m_lat, 'em_loss_mean': em_m_loss,
        'sp_lpp_std': statistics.stdev(sp_lpp), 'sp_loss_std': statistics.stdev(sp_loss),
        'ec_lpp_std': statistics.stdev(ec_lpp), 'ec_loss_std': statistics.stdev(ec_loss),
        'em_lpp_std': statistics.stdev(em_lpp), 'em_loss_std': statistics.stdev(em_loss),
    }

if __name__ == '__main__':
    print(f"ECMP baseline experiment | {N_RUNS} runs | alpha={ALPHA} beta={BETA} gamma={GAMMA}")

    results = []
    # Synthetic scenarios
    for density, label in [(0.15, 'ER_sparse_p0.15'),
                           (0.30, 'ER_baseline_p0.30'),
                           (0.50, 'ER_dense_p0.50')]:
        results.append(run_scenario(label, build_synthetic, (20, density)))

    # Real topologies
    results.append(run_scenario('Abilene', build_real, ('Abilene.graphml',)))
    results.append(run_scenario('GEANT',   build_real, ('Geant.graphml',)))

    with open('/home/clopez/emmet/data/ecmp_baseline_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    print("\nResults saved to data/ecmp_baseline_results.json")
