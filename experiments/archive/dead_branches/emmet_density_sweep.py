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
BETA          = 3.0   # beta alto para maximizar el efecto
GAMMA         = 2.0

# Barrido de densidad — este es el experimento central
DENSITIES = [round(x * 0.05, 2) for x in range(1, 13)]  # 0.05 a 0.60

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
                e['loss'] += 1
                losses += 1
                packet_lost = True
                break
            total_latency += e['latency']
        if not packet_lost:
            delivered += 1
        for u, v in G.edges():
            G[u][v]['load'] *= 0.9
    lpp = total_latency / delivered if delivered > 0 else 0
    return {
        'lat_per_packet': round(lpp, 4),
        'losses':         losses,
        'delivered':      delivered,
        'dropped_dead':   dropped_dead,
        'dropped_ttl':    dropped_ttl,
        'dropped_nopath': dropped_nopath,
    }

def run_density_sweep():
    results = []
    print(f"Density sweep: {len(DENSITIES)} points x {N_RUNS} runs each")
    print(f"Config: {NUM_NODES} nodes | {TRAFFIC_STEPS} steps | "
          f"alpha={ALPHA} beta={BETA} gamma={GAMMA}\n")
    print(f"{'Density':>8} {'SP_lpp':>10} {'FX_lpp':>10} "
          f"{'SP_loss':>9} {'FX_loss':>9} {'Delta_lat':>10} {'Loss_saved':>11} "
          f"{'FX_ttl':>8} {'FX_dead':>8} {'Connected':>10}")
    print("-" * 100)

    for density in DENSITIES:
        sp_lpp, sp_loss, sp_del = [], [], []
        fx_lpp, fx_loss, fx_del = [], [], []
        fx_ttl, fx_dead, fx_nopath = [], [], []
        connected_count = 0

        for seed in range(N_RUNS):
            random.seed(seed)
            G = build_graph(NUM_NODES, density, seed=seed)

            # Medir conectividad
            if nx.is_connected(G):
                connected_count += 1

            reset_graph(G)
            sp = simulate(G, 'shortest', TRAFFIC_STEPS, ALPHA, BETA, GAMMA)
            reset_graph(G)
            fx = simulate(G, 'emmet',     TRAFFIC_STEPS, ALPHA, BETA, GAMMA)

            sp_lpp.append(sp['lat_per_packet'])
            sp_loss.append(sp['losses'])
            sp_del.append(sp['delivered'])
            fx_lpp.append(fx['lat_per_packet'])
            fx_loss.append(fx['losses'])
            fx_del.append(fx['delivered'])
            fx_ttl.append(fx['dropped_ttl'])
            fx_dead.append(fx['dropped_dead'])
            fx_nopath.append(fx['dropped_nopath'])

        sp_lpp_m  = statistics.mean(sp_lpp)
        fx_lpp_m  = statistics.mean(fx_lpp)
        sp_loss_m = statistics.mean(sp_loss)
        fx_loss_m = statistics.mean(fx_loss)
        delta     = (fx_lpp_m - sp_lpp_m) / sp_lpp_m * 100 if sp_lpp_m > 0 else 0
        saved     = sp_loss_m - fx_loss_m
        conn_pct  = connected_count / N_RUNS * 100

        print(f"{density:>8.2f} {sp_lpp_m:>10.3f} {fx_lpp_m:>10.3f} "
              f"{sp_loss_m:>9.2f} {fx_loss_m:>9.2f} {delta:>+10.1f}% {saved:>11.2f} "
              f"{statistics.mean(fx_ttl):>8.2f} {statistics.mean(fx_dead):>8.2f} "
              f"{conn_pct:>9.0f}%")

        results.append({
            'density':       density,
            'sp_lpp_mean':   sp_lpp_m,
            'sp_lpp_std':    statistics.stdev(sp_lpp),
            'fx_lpp_mean':   fx_lpp_m,
            'fx_lpp_std':    statistics.stdev(fx_lpp),
            'sp_loss_mean':  sp_loss_m,
            'sp_loss_std':   statistics.stdev(sp_loss),
            'fx_loss_mean':  fx_loss_m,
            'fx_loss_std':   statistics.stdev(fx_loss),
            'delta_lat':     delta,
            'losses_saved':  saved,
            'fx_ttl_mean':   statistics.mean(fx_ttl),
            'fx_dead_mean':  statistics.mean(fx_dead),
            'connected_pct': conn_pct,
        })

    # Guardar resultados para el notebook
    with open('data/density_sweep_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to data/density_sweep_results.json")
    return results

if __name__ == "__main__":
    results = run_density_sweep()

    # Encontrar el knee point — donde losses_saved cae por debajo del 50% del maximo
    max_saved = max(r['losses_saved'] for r in results)
    knee = None
    for r in results:
        if r['losses_saved'] >= max_saved * 0.5:
            knee = r['density']
    print(f"\nKnee point (50% of max losses_saved): density ~ {knee}")
    print(f"Max losses saved: {max_saved:.2f} at density "
          f"{max(results, key=lambda r: r['losses_saved'])['density']}")
