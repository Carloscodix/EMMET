import random
import statistics
import networkx as nx
import json

# ----------------------------
# CONFIG
# ----------------------------
NUM_NODES     = 20
TRAFFIC_STEPS = 200
TTL_FACTOR    = 2
N_RUNS        = 30
ALPHA         = 1.0
GAMMA         = 2.0
DENSITY       = 0.30

# Barrido de beta — el parametro fisico central
BETAS = [0.1, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0]

def build_graph(num_nodes, density, seed):
    G = nx.erdos_renyi_graph(num_nodes, density, seed=seed)
    for u, v in G.edges():
        G[u][v]['latency']  = random.uniform(1, 5)
        G[u][v]['capacity'] = random.randint(3, 6)
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

def emmet_route(G, src, dst, alpha, beta, gamma):
    max_hops = TTL_FACTOR * NUM_NODES
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

def simulate(G, mode, steps, alpha, beta, gamma):
    total_latency = 0.0
    losses = delivered = dropped_dead = dropped_ttl = dropped_nopath = 0
    for _ in range(steps):
        src = random.randint(0, NUM_NODES - 1)
        dst = random.randint(0, NUM_NODES - 1)
        if src == dst:
            continue
        if mode == 'shortest':
            path, reason = shortest_path_route(G, src, dst)
        else:
            path, reason = emmet_route(G, src, dst, alpha, beta, gamma)
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

if __name__ == "__main__":
    print(f"Beta sweep | density={DENSITY} | {N_RUNS} runs | "
          f"alpha={ALPHA} gamma={GAMMA}\n")

    # Baseline SP (independiente de beta)
    sp_lpp_all, sp_loss_all = [], []
    for seed in range(N_RUNS):
        random.seed(seed)
        G = build_graph(NUM_NODES, DENSITY, seed=seed)
        reset_graph(G)
        sp = simulate(G, 'shortest', TRAFFIC_STEPS, ALPHA, 1.0, GAMMA)
        sp_lpp_all.append(sp['lat_per_packet'])
        sp_loss_all.append(sp['losses'])

    sp_lpp_mean  = statistics.mean(sp_lpp_all)
    sp_loss_mean = statistics.mean(sp_loss_all)

    print(f"Shortest Path (baseline): lat={sp_lpp_mean:.3f} loss={sp_loss_mean:.2f}\n")
    print(f"{'Beta':>6} {'FX_lat':>8} {'FX_loss':>8} {'Delta_lat':>10} "
          f"{'Loss_saved':>11} {'Std_lat':>8} {'Std_loss':>9}")
    print("-" * 65)

    results = []
    for beta in BETAS:
        fx_lpp, fx_loss = [], []
        for seed in range(N_RUNS):
            random.seed(seed)
            G = build_graph(NUM_NODES, DENSITY, seed=seed)
            reset_graph(G)
            fx = simulate(G, 'emmet', TRAFFIC_STEPS, ALPHA, beta, GAMMA)
            fx_lpp.append(fx['lat_per_packet'])
            fx_loss.append(fx['losses'])

        fx_lpp_mean  = statistics.mean(fx_lpp)
        fx_loss_mean = statistics.mean(fx_loss)
        fx_lpp_std   = statistics.stdev(fx_lpp)
        fx_loss_std  = statistics.stdev(fx_loss)
        delta        = (fx_lpp_mean - sp_lpp_mean) / sp_lpp_mean * 100
        saved        = sp_loss_mean - fx_loss_mean

        print(f"{beta:>6.1f} {fx_lpp_mean:>8.3f} {fx_loss_mean:>8.2f} "
              f"{delta:>+10.1f}% {saved:>11.2f} {fx_lpp_std:>8.3f} {fx_loss_std:>9.3f}")

        results.append({
            'beta':          beta,
            'fx_lpp_mean':   fx_lpp_mean,
            'fx_lpp_std':    fx_lpp_std,
            'fx_loss_mean':  fx_loss_mean,
            'fx_loss_std':   fx_loss_std,
            'sp_lpp_mean':   sp_lpp_mean,
            'sp_loss_mean':  sp_loss_mean,
            'delta_lat':     delta,
            'losses_saved':  saved,
        })

    with open('/home/clopez/emmet/data/beta_sweep_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to data/beta_sweep_results.json")
