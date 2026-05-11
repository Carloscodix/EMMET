"""
physics_cores.py - a battery of classical-physics routing cores.

Each core shares the SAME gradient-descent search engine (an exact hop-budget
DP, identical to emmet_core) and differs ONLY in the per-edge potential it
descends. This makes the comparison fair by construction: any performance
difference comes from the physics, not the search.

The thesis under test: several different classical-physics laws, each used
alone as the routing potential, independently reach the operating point of
engineered load balancers (CONGA, DRILL).

Cores implemented:
  - newton  : reactive loss-memory scar (Newton III). The proven baseline.
  - archimedes : anticipatory non-linear buoyancy with a flotation threshold.
                 Repels from edges whose density exceeds rho_0, BEFORE a drop.
  - pascal  : pressure transmitted to graph neighbours (spatial diffusion).
  - hooke   : elastic restoring force, linear in displacement above slack.

All potentials also include the shared distance + linear-congestion base, which
is the irreducible substrate (without it there is no router). The point of each
core is the ADDED physical term and whether it alone suffices.
"""
import math
import networkx as nx

# shared base weights (same as emmet_core)
ALPHA = 1.0          # latency / distance
BETA  = 3.0          # linear congestion (the irreducible substrate)
ALPHA_BUDGET = 1.25  # hop budget over shortest path


# --------------------------------------------------------------------------
# Per-edge potential terms. Each returns the ADDED cost for traversing (u,v),
# on top of the shared distance+congestion base. state holds any memory.
# --------------------------------------------------------------------------

def _base(G, u, v):
    e = G[u][v]
    return ALPHA * e['latency'] + BETA * (e['load'] / e['capacity'])


def term_newton(G, u, v, state):
    """Newton III: reactive scar deposited on loss, decaying over time."""
    scars = state.get('scars', {})
    return 2.0 * scars.get(tuple(sorted((u, v))), 0.0)


def term_archimedes(G, u, v, state, rho0=0.6, g_arq=8.0):
    """Archimedes: anticipatory buoyancy. A packet entering an edge whose
    congestion density rho exceeds the flotation threshold rho0 feels an
    upward (repulsive) push growing with the SQUARE of the excess density.
    Below rho0 it floats freely (zero added cost); above, it is expelled.
    Purely a function of the edge's present state - no memory, no mass,
    no waiting for a drop. This is the key difference from Newton (reactive)
    and from the linear beta term (no threshold, no curvature)."""
    e = G[u][v]
    rho = e['load'] / e['capacity']
    excess = rho - rho0
    if excess <= 0.0:
        return 0.0
    return g_arq * excess * excess


def term_pascal(G, u, v, state, g_pas=3.0):
    """Pascal: pressure applied to a congested edge transmits undiminished to
    its graph neighbours. The added cost is the mean congestion of the edges
    adjacent to (u,v), so a packet avoids not just congested edges but their
    neighbourhoods - spatial diffusion of pressure."""
    nbr = []
    for x in (u, v):
        for w in G.neighbors(x):
            if (w == v and x == u) or (w == u and x == v):
                continue
            nbr.append(G[x][w]['load'] / G[x][w]['capacity'])
    if not nbr:
        return 0.0
    return g_pas * (sum(nbr) / len(nbr))


def term_hooke(G, u, v, state, slack=0.5, k_spring=5.0):
    """Hooke: an edge loaded beyond a slack fraction behaves like a compressed
    spring, pushing back with a force linear in the displacement (rho - slack).
    Like Archimedes but linear rather than quadratic above threshold - a
    different curvature, to test whether the threshold or the curvature matters."""
    rho = G[u][v]['load'] / G[u][v]['capacity']
    disp = rho - slack
    return k_spring * disp if disp > 0.0 else 0.0


# registry: name -> added-term function
TERMS = {
    'newton': term_newton,
    'archimedes': term_archimedes,
    'pascal': term_pascal,
    'hooke': term_hooke,
}


# --------------------------------------------------------------------------
# Shared gradient-descent DP, parameterised by the added physical term.
# --------------------------------------------------------------------------

def route_with_term(G, src, dst, state, term_fn, alpha_budget=ALPHA_BUDGET):
    """Min-potential path under a hop budget, where per-edge cost is
    base(distance+congestion) + term_fn(added physics). Exact DP, O(k|E|)."""
    if src == dst:
        return [src]
    try:
        sp = nx.shortest_path_length(G, src, dst)
    except nx.NetworkXNoPath:
        return None
    k = max(sp, math.ceil(alpha_budget * sp))
    INF = float('inf')
    nodes = list(G.nodes())
    f = [{n: INF for n in nodes} for _ in range(k + 1)]
    par = [{n: None for n in nodes} for _ in range(k + 1)]
    f[0][src] = 0.0
    for h in range(1, k + 1):
        for v in nodes:
            best, bu = INF, None
            for u in G.neighbors(v):
                if f[h-1][u] == INF:
                    continue
                cost = f[h-1][u] + _base(G, u, v) + term_fn(G, u, v, state)
                if cost < best:
                    best, bu = cost, u
            f[h][v] = best
            par[h][v] = bu
    bh, bc = None, INF
    for h in range(sp, k + 1):
        if f[h][dst] < bc:
            bc, bh = f[h][dst], h
    if bh is None:
        return None
    path = [dst]; cur, h = dst, bh
    while h > 0:
        cur = par[h][cur]
        if cur is None:
            return None
        path.append(cur); h -= 1
    path.reverse()
    return path


def make_physics_policy(name):
    """Return a flowsim route_fn for the named classical-physics core.
    Newton additionally needs its scar field fed on drops (handled by the
    flowsim wrapper); the other cores are stateless functions of the graph."""
    term_fn = TERMS[name]
    def route_fn(G, src, dst, state):
        return route_with_term(G, src, dst, state, term_fn)
    return route_fn
