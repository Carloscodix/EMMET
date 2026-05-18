"""
EMMET on real Internet topologies (Abilene, GEANT).

Validates the synthetic findings from Erdos-Renyi sweeps against
real backbone topologies from the Internet Topology Zoo.

Key insight: GEANT (density~0.08) sits BELOW our identified knee point
(rho_c ~ 0.15-0.30), placing real Internet research backbones in the
subcritical regime. Abilene (density~0.25) sits AT the transition zone.
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
TOPOLOGIES = [
    ('Abilene', 'Abilene.graphml'),
    ('GEANT',   'Geant.graphml'),
]

def load_topology(filename, seed):
    """Load a real topology and seed it with random link attributes.
    The topology stays fixed; only latency/capacity/load/loss vary per seed."""
    G = nx.read_graphml(os.path.join(TOPO_DIR, filename))
    G = nx.Graph(G)  # force undirected
    # Relabel to integers for consistency with synthetic experiments
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

def shortest_path_route(G, src, dst):
    try:
        return nx.shortest_path(G, src, dst, weight='latency'), 'delivered'
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
        path, reason = (shortest_path_route(G, src, dst) if mode == 'shortest'
                        else emmet_route(G, src, dst, alpha, beta, gamma, num_nodes))
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
            'delivered': delivered, 'dropped_dead': dropped_dead,
            'dropped_ttl': dropped_ttl}

if __name__ == '__main__':
    print(f"EMMET on real topologies | {N_RUNS} runs | alpha={ALPHA} beta={BETA} gamma={GAMMA}\n")

    all_results = []
    for name, filename in TOPOLOGIES:
        # Load once to print metadata
        G_meta = load_topology(filename, seed=0)
        density = nx.density(G_meta)
        print(f"--- {name} ---")
        print(f"  Nodes: {G_meta.number_of_nodes()}  Edges: {G_meta.number_of_edges()}  Density: {density:.4f}")

        sp_lpp, sp_loss = [], []
        em_lpp, em_loss, em_dead, em_ttl = [], [], [], []

        for seed in range(N_RUNS):
            G = load_topology(filename, seed=seed)
            rng = random.Random(seed)
            reset_graph(G)
            sp = simulate(G, 'shortest', TRAFFIC_STEPS, ALPHA, BETA, GAMMA, rng)
            rng = random.Random(seed)  # reset RNG for fair traffic comparison
            reset_graph(G)
            em = simulate(G, 'emmet', TRAFFIC_STEPS, ALPHA, BETA, GAMMA, rng)
            sp_lpp.append(sp['lat_per_packet'])
            sp_loss.append(sp['losses'])
            em_lpp.append(em['lat_per_packet'])
            em_loss.append(em['losses'])
            em_dead.append(em['dropped_dead'])
            em_ttl.append(em['dropped_ttl'])

        sp_lpp_m  = statistics.mean(sp_lpp)
        em_lpp_m  = statistics.mean(em_lpp)
        delta     = (em_lpp_m - sp_lpp_m) / sp_lpp_m * 100 if sp_lpp_m > 0 else 0
        saved     = statistics.mean(sp_loss) - statistics.mean(em_loss)

        print(f"  SP    : lat={sp_lpp_m:.3f}+/-{statistics.stdev(sp_lpp):.3f}  "
              f"loss={statistics.mean(sp_loss):.2f}+/-{statistics.stdev(sp_loss):.2f}")
        print(f"  EMMET : lat={em_lpp_m:.3f}+/-{statistics.stdev(em_lpp):.3f}  "
              f"loss={statistics.mean(em_loss):.2f}+/-{statistics.stdev(em_loss):.2f}")
        print(f"  Delta_lat: {delta:+.1f}%   Loss_saved: {saved:.2f}")
        print(f"  EMMET dead_ends: {statistics.mean(em_dead):.2f}   "
              f"ttl_expired: {statistics.mean(em_ttl):.2f}\n")

        all_results.append({
            'topology':      name,
            'nodes':         G_meta.number_of_nodes(),
            'edges':         G_meta.number_of_edges(),
            'density':       density,
            'sp_lpp_mean':   sp_lpp_m,
            'sp_lpp_std':    statistics.stdev(sp_lpp),
            'sp_loss_mean':  statistics.mean(sp_loss),
            'sp_loss_std':   statistics.stdev(sp_loss),
            'em_lpp_mean':   em_lpp_m,
            'em_lpp_std':    statistics.stdev(em_lpp),
            'em_loss_mean':  statistics.mean(em_loss),
            'em_loss_std':   statistics.stdev(em_loss),
            'em_dead_mean':  statistics.mean(em_dead),
            'em_ttl_mean':   statistics.mean(em_ttl),
            'delta_lat':     delta,
            'losses_saved':  saved,
        })

    with open('/home/clopez/emmet/data/real_topology_results.json', 'w') as f:
        json.dump(all_results, f, indent=2)
    print("Results saved to data/real_topology_results.json")
