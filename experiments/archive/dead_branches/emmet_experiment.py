import random
import statistics
import networkx as nx

# ----------------------------
# CONFIG
# ----------------------------
NUM_NODES = 20
TRAFFIC_STEPS = 200
TTL_FACTOR = 2
N_RUNS = 30  # runs por configuracion

# Escenarios a testear
SCENARIOS = [
    {'alpha': 1.0, 'beta': 1.5, 'gamma': 2.0, 'density': 0.30, 'label': 'baseline'},
    {'alpha': 1.0, 'beta': 3.0, 'gamma': 2.0, 'density': 0.30, 'label': 'high_beta'},
    {'alpha': 1.0, 'beta': 5.0, 'gamma': 2.0, 'density': 0.30, 'label': 'max_beta'},
    {'alpha': 1.0, 'beta': 3.0, 'gamma': 2.0, 'density': 0.15, 'label': 'sparse'},
    {'alpha': 1.0, 'beta': 3.0, 'gamma': 2.0, 'density': 0.50, 'label': 'dense'},
]

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
        path = nx.shortest_path(G, src, dst, weight='latency')
        return path, 'delivered'
    except nx.NetworkXNoPath:
        return None, 'no_path'

def compute_potential(G, current, neighbor, dst, alpha, beta, gamma):
    load       = G[current][neighbor]['load']
    capacity   = G[current][neighbor]['capacity']
    loss       = G[current][neighbor]['loss']
    congestion = load / capacity
    try:
        dist = nx.shortest_path_length(G, neighbor, dst, weight='latency')
    except nx.NetworkXNoPath:
        dist = 999
    return alpha * dist + beta * congestion + gamma * loss

def emmet_route(G, src, dst, alpha, beta, gamma):
    max_hops = TTL_FACTOR * NUM_NODES
    path     = [src]
    current  = src
    visited  = set()
    hops     = 0
    while current != dst and hops < max_hops:
        visited.add(current)
        neighbors = [n for n in G.neighbors(current) if n not in visited]
        if not neighbors:
            return None, 'dead_end'
        best = min(neighbors,
                   key=lambda n: compute_potential(G, current, n, dst, alpha, beta, gamma))
        path.append(best)
        current = best
        hops   += 1
    if current == dst:
        return path, 'delivered'
    return None, 'ttl_expired'

def simulate(G, mode, steps, alpha, beta, gamma):
    total_latency  = 0.0
    losses         = 0
    delivered      = 0
    dropped_dead   = 0
    dropped_ttl    = 0
    dropped_nopath = 0

    for _ in range(steps):
        src = random.randint(0, NUM_NODES - 1)
        dst = random.randint(0, NUM_NODES - 1)
        if src == dst:
            continue

        if mode == "shortest":
            path, reason = shortest_path_route(G, src, dst)
        else:
            path, reason = emmet_route(G, src, dst, alpha, beta, gamma)

        if path is None:
            if reason == 'dead_end':   dropped_dead   += 1
            elif reason == 'ttl_expired': dropped_ttl += 1
            else:                      dropped_nopath += 1
            continue

        packet_lost = False
        for i in range(len(path) - 1):
            u, v = path[i], path[i + 1]
            edge = G[u][v]
            edge['load'] += 1
            if edge['load'] > edge['capacity']:
                edge['loss'] += 1
                losses       += 1
                packet_lost   = True
                break
            total_latency += edge['latency']

        if not packet_lost:
            delivered += 1

        for u, v in G.edges():
            G[u][v]['load'] *= 0.9

    lpp = total_latency / delivered if delivered > 0 else 0
    return {
        'lat_per_packet': round(lpp, 4),
        'losses':         losses,
        'delivered':      delivered,
        'dropped':        dropped_dead + dropped_ttl + dropped_nopath,
        'dropped_dead':   dropped_dead,
        'dropped_ttl':    dropped_ttl,
    }

def run_scenario(scenario, n_runs=N_RUNS):
    alpha   = scenario['alpha']
    beta    = scenario['beta']
    gamma   = scenario['gamma']
    density = scenario['density']
    label   = scenario['label']

    sp_lpp, sp_losses, sp_delivered = [], [], []
    fx_lpp, fx_losses, fx_delivered = [], [], []
    fx_dropped_ttl, fx_dropped_dead = [], []

    for seed in range(n_runs):
        random.seed(seed)
        G = build_graph(NUM_NODES, density, seed=seed)

        reset_graph(G)
        sp = simulate(G, "shortest", TRAFFIC_STEPS, alpha, beta, gamma)
        reset_graph(G)
        fx = simulate(G, "emmet",     TRAFFIC_STEPS, alpha, beta, gamma)

        sp_lpp.append(sp['lat_per_packet'])
        sp_losses.append(sp['losses'])
        sp_delivered.append(sp['delivered'])
        fx_lpp.append(fx['lat_per_packet'])
        fx_losses.append(fx['losses'])
        fx_delivered.append(fx['delivered'])
        fx_dropped_ttl.append(fx['dropped_ttl'])
        fx_dropped_dead.append(fx['dropped_dead'])

    def fmt(vals):
        return f"{statistics.mean(vals):.3f} +/- {statistics.stdev(vals):.3f}"

    print(f"\n{'='*60}")
    print(f"SCENARIO: {label}")
    print(f"  alpha={alpha} beta={beta} gamma={gamma} density={density}")
    print(f"  runs={n_runs} | nodes={NUM_NODES} | steps={TRAFFIC_STEPS}")
    print(f"{'-'*60}")
    print(f"  {'Metric':<28} {'SP':>14} {'EMMET':>14}")
    print(f"  {'-'*56}")
    print(f"  {'Lat/packet (mean+/-std)':<28} {fmt(sp_lpp):>14} {fmt(fx_lpp):>14}")
    print(f"  {'Losses (mean+/-std)':<28} {fmt(sp_losses):>14} {fmt(fx_losses):>14}")
    print(f"  {'Delivered (mean+/-std)':<28} {fmt(sp_delivered):>14} {fmt(fx_delivered):>14}")

    sp_lpp_mean = statistics.mean(sp_lpp)
    fx_lpp_mean = statistics.mean(fx_lpp)
    if sp_lpp_mean > 0:
        delta = (fx_lpp_mean - sp_lpp_mean) / sp_lpp_mean * 100
        print(f"\n  Delta lat/packet:    {delta:+.1f}%")

    losses_saved = statistics.mean(sp_losses) - statistics.mean(fx_losses)
    print(f"  Losses saved (avg):  {losses_saved:.2f}")
    print(f"  TTL expired (avg):   {statistics.mean(fx_dropped_ttl):.2f}")
    print(f"  Dead ends (avg):     {statistics.mean(fx_dropped_dead):.2f}")

    return {
        'label':        label,
        'delta_lat':    delta if sp_lpp_mean > 0 else None,
        'losses_saved': losses_saved,
        'sp_losses':    statistics.mean(sp_losses),
        'fx_losses':    statistics.mean(fx_losses),
    }

if __name__ == "__main__":
    print(f"EMMET Experiment: {N_RUNS} runs per scenario | {NUM_NODES} nodes | {TRAFFIC_STEPS} steps")
    print(f"TTL factor: {TTL_FACTOR}x")

    results = []
    for scenario in SCENARIOS:
        r = run_scenario(scenario)
        results.append(r)

    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    print(f"  {'Scenario':<15} {'Delta lat':>10} {'Losses saved':>14} {'SP losses':>10} {'FX losses':>10}")
    print(f"  {'-'*59}")
    for r in results:
        dl = f"{r['delta_lat']:+.1f}%" if r['delta_lat'] else "N/A"
        print(f"  {r['label']:<15} {dl:>10} {r['losses_saved']:>14.2f} {r['sp_losses']:>10.2f} {r['fx_losses']:>10.2f}")
