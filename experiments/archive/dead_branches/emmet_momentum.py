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
ALPHA = 1.0
BETA  = 3.0
GAMMA = 2.0
DELTA = 2.0   # peso del termino de inercia (momentum)

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

def compute_potential(G, current, neighbor, dst, alpha, beta, gamma,
                      delta=0.0, prev_node=None):
    """
    Potencial compuesto con termino de inercia (momentum).

    P = alpha*dist + beta*congestion + gamma*loss + delta*momentum

    El termino de inercia penaliza volver al nodo anterior.
    Una particula en movimiento resiste el cambio de direccion de 180 grados.
    delta=0 equivale a emmet_v3 sin inercia.
    """
    e = G[current][neighbor]
    congestion = e['load'] / e['capacity']
    try:
        dist = nx.shortest_path_length(G, neighbor, dst, weight='latency')
    except nx.NetworkXNoPath:
        dist = 999

    # Termino de inercia: penaliza giro de 180 grados
    momentum = 1.0 if (prev_node is not None and neighbor == prev_node) else 0.0

    return alpha * dist + beta * congestion + gamma * e['loss'] + delta * momentum

def emmet_route_v4(G, src, dst, alpha, beta, gamma, delta=DELTA,
                  ttl_factor=TTL_FACTOR):
    """
    EMMET v4 con momentum (inercia fisica).

    El paquete recuerda de donde viene y penaliza volver atras.
    Esto evita el efecto ping-pong en redes con congestión dinamica.

    Causas de fallo:
      - dead_end   : callejon topologico
      - ttl_expired: disipacion termica
    """
    max_hops = ttl_factor * NUM_NODES
    path     = [src]
    current  = src
    prev     = None   # nodo anterior — memoria de inercia
    visited  = set()
    hops     = 0

    while current != dst and hops < max_hops:
        visited.add(current)
        neighbors = [n for n in G.neighbors(current) if n not in visited]

        if not neighbors:
            return None, 'dead_end'

        best = min(
            neighbors,
            key=lambda n: compute_potential(
                G, current, n, dst, alpha, beta, gamma, delta, prev_node=prev)
        )
        prev    = current   # actualizar memoria de inercia
        path.append(best)
        current = best
        hops   += 1

    if current == dst:
        return path, 'delivered'
    return None, 'ttl_expired'

def emmet_route_v3(G, src, dst, alpha, beta, gamma, ttl_factor=TTL_FACTOR):
    """EMMET v3 sin momentum — baseline para comparar."""
    max_hops = ttl_factor * NUM_NODES
    path, current, visited, hops = [src], src, set(), 0
    while current != dst and hops < max_hops:
        visited.add(current)
        neighbors = [n for n in G.neighbors(current) if n not in visited]
        if not neighbors:
            return None, 'dead_end'
        best = min(neighbors,
                   key=lambda n: compute_potential(G, current, n, dst,
                                                   alpha, beta, gamma, delta=0.0))
        path.append(best)
        current = best
        hops += 1
    return (path, 'delivered') if current == dst else (None, 'ttl_expired')

def shortest_path_route(G, src, dst):
    try:
        return nx.shortest_path(G, src, dst, weight='latency'), 'delivered'
    except nx.NetworkXNoPath:
        return None, 'no_path'

def simulate(G, mode, steps, alpha, beta, gamma, delta=DELTA):
    total_latency  = 0.0
    losses = delivered = dropped_dead = dropped_ttl = dropped_nopath = 0

    for _ in range(steps):
        src = random.randint(0, NUM_NODES - 1)
        dst = random.randint(0, NUM_NODES - 1)
        if src == dst:
            continue

        if mode == 'shortest':
            path, reason = shortest_path_route(G, src, dst)
        elif mode == 'emmet_v3':
            path, reason = emmet_route_v3(G, src, dst, alpha, beta, gamma)
        else:  # emmet_v4 con momentum
            path, reason = emmet_route_v4(G, src, dst, alpha, beta, gamma, delta)

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
    return {
        'lat_per_packet': round(lpp, 4),
        'losses':         losses,
        'delivered':      delivered,
        'dropped_dead':   dropped_dead,
        'dropped_ttl':    dropped_ttl,
    }

# ----------------------------
# EXPERIMENTO: SP vs EMMET v3 vs EMMET v4 (momentum)
# ----------------------------
if __name__ == "__main__":
    N_RUNS   = 30
    DENSITY  = 0.30
    DELTAS   = [0.0, 0.5, 1.0, 2.0, 3.0, 5.0]  # barrido de inercia

    print(f"Momentum experiment | density={DENSITY} | {N_RUNS} runs | "
          f"alpha={ALPHA} beta={BETA} gamma={GAMMA}\n")

    # --- Baseline: SP y EMMET v3 ---
    sp_lpp, sp_loss = [], []
    v3_lpp, v3_loss = [], []

    for seed in range(N_RUNS):
        random.seed(seed)
        G = build_graph(NUM_NODES, DENSITY, seed=seed)
        reset_graph(G)
        sp = simulate(G, 'shortest', TRAFFIC_STEPS, ALPHA, BETA, GAMMA)
        reset_graph(G)
        v3 = simulate(G, 'emmet_v3',  TRAFFIC_STEPS, ALPHA, BETA, GAMMA)
        sp_lpp.append(sp['lat_per_packet'])
        sp_loss.append(sp['losses'])
        v3_lpp.append(v3['lat_per_packet'])
        v3_loss.append(v3['losses'])

    print(f"{'Mode':<20} {'Lat/pkt':>10} {'Losses':>8} {'Delta_lat':>10}")
    print("-" * 52)
    sp_m = statistics.mean(sp_lpp)
    print(f"{'Shortest Path':<20} {sp_m:>10.3f} "
          f"{statistics.mean(sp_loss):>8.2f}       ---")
    v3_m = statistics.mean(v3_lpp)
    d = (v3_m - sp_m) / sp_m * 100
    print(f"{'EMMET v3 (no momentum)':<20} {v3_m:>10.3f} "
          f"{statistics.mean(v3_loss):>8.2f} {d:>+10.1f}%")

    # --- Barrido de delta (inercia) ---
    print(f"\n--- Momentum sweep (EMMET v4) ---")
    results = []
    for delta in DELTAS:
        v4_lpp, v4_loss, v4_dead, v4_ttl = [], [], [], []
        for seed in range(N_RUNS):
            random.seed(seed)
            G = build_graph(NUM_NODES, DENSITY, seed=seed)
            reset_graph(G)
            v4 = simulate(G, 'emmet_v4', TRAFFIC_STEPS, ALPHA, BETA, GAMMA, delta)
            v4_lpp.append(v4['lat_per_packet'])
            v4_loss.append(v4['losses'])
            v4_dead.append(v4['dropped_dead'])
            v4_ttl.append(v4['dropped_ttl'])

        v4_m = statistics.mean(v4_lpp)
        d    = (v4_m - sp_m) / sp_m * 100
        saved = statistics.mean(sp_loss) - statistics.mean(v4_loss)
        print(f"  delta={delta:.1f}  lat={v4_m:.3f}  loss={statistics.mean(v4_loss):.2f}  "
              f"saved={saved:.2f}  dead={statistics.mean(v4_dead):.2f}  "
              f"ttl={statistics.mean(v4_ttl):.2f}  delta_lat={d:+.1f}%")
        results.append({
            'delta': delta, 'lpp': v4_m, 'loss': statistics.mean(v4_loss),
            'saved': saved, 'dead': statistics.mean(v4_dead),
            'ttl': statistics.mean(v4_ttl), 'delta_lat': d
        })

    with open('/home/clopez/emmet/data/momentum_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to data/momentum_results.json")
