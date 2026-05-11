"""EMMET-core - the two-term physical router.

EMMET reduced to the two mechanisms an ablation showed are the only ones that
earn their keep. Effective mass, thermostat, temporal ripple and Archimedes
buoyancy were decoration and have been removed.

A packet is a particle descending a potential field. Per-edge cost:

    phi(u,v) = ALPHA*latency + BETA*(load/capacity) + GAMMA*scar(u,v)

Two physical ideas, nothing else:
  1. GRADIENT DESCENT: the packet follows phi downhill under a hop budget
     (up to alpha_budget x shortest path). Solved by a small exact DP.
  2. NEWTON III (the "scar"): a packet that dies on an edge pushes back -
     the edge scar increments so later packets are steered away. Scars fade
     (DECAY) when not refreshed, so there is no scar at rest.

No per-packet state, no mass, no knobs beyond the 3 potential weights and the
hop-budget factor. Matches CONGA/DRILL on most topologies; tube/sp predicts
the exceptions.
"""
import math
import networkx as nx

# --- the only parameters ---
ALPHA = 1.0          # weight on latency (distance)
BETA  = 3.0          # weight on congestion
GAMMA = 2.0          # weight on the Newton-III scar (loss memory)
HALF_LIFE = 500      # scar half-life, in steps
DECAY = math.exp(-math.log(2) / HALF_LIFE)
ALPHA_BUDGET = 1.25  # may wander up to 1.25x the shortest-path hop count


def edge_potential(G, u, v, scars):
    """phi(u,v): latency + congestion + Newton-III scar. Pure local quantities."""
    e = G[u][v]
    congestion = e['load'] / e['capacity']
    scar = scars.get(tuple(sorted((u, v))), 0.0)
    return ALPHA * e['latency'] + BETA * congestion + GAMMA * scar


def route(G, src, dst, scars, alpha_budget=ALPHA_BUDGET):
    """Gradient-descent routing under a hop budget.

    Returns the path from src to dst (length <= ceil(alpha_budget * sp_hops))
    that minimizes the sum of edge potentials, or None if disconnected.
    Exact dynamic program over (hops_used, node); complexity O(k * |E|).
    """
    if src == dst:
        return [src]
    try:
        sp_hops = nx.shortest_path_length(G, src, dst)
    except nx.NetworkXNoPath:
        return None

    k = max(sp_hops, math.ceil(alpha_budget * sp_hops))
    INF = float('inf')
    nodes = list(G.nodes())
    # f[h][v] = min potential to reach v in exactly h hops; parent for backtrack
    f = [{u: INF for u in nodes} for _ in range(k + 1)]
    parent = [{u: None for u in nodes} for _ in range(k + 1)]
    f[0][src] = 0.0

    for h in range(1, k + 1):
        for v in nodes:
            best, best_u = INF, None
            for u in G.neighbors(v):
                if f[h-1][u] == INF:
                    continue
                cost = f[h-1][u] + edge_potential(G, u, v, scars)
                if cost < best:
                    best, best_u = cost, u
            f[h][v] = best
            parent[h][v] = best_u

    # pick the best achievable length between sp_hops and the budget k
    best_h, best_cost = None, INF
    for h in range(sp_hops, k + 1):
        if f[h][dst] < best_cost:
            best_cost, best_h = f[h][dst], h
    if best_h is None:
        return None

    path = [dst]
    cur, h = dst, best_h
    while h > 0:
        cur = parent[h][cur]
        if cur is None:
            return None
        path.append(cur)
        h -= 1
    path.reverse()
    return path


def deposit_scar(scars, u, v, amount=1.0):
    """Newton's third law: a packet dying on edge (u,v) pushes back, leaving a
    scar that steers later packets away."""
    k = tuple(sorted((u, v)))
    scars[k] = scars.get(k, 0.0) + amount


def decay_scars(scars):
    """Scars fade when not refreshed (call once per simulation step).
    A corridor that stops failing reopens on its own -> no scar at rest."""
    for k in list(scars.keys()):
        scars[k] *= DECAY
        if scars[k] < 1e-6:
            del scars[k]
