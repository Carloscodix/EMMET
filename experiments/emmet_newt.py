"""EMMET-Newt: Newton-III extensions of EMMET-DP.

Contains two distinct mechanisms (see notes/blood_live_session.md):

  pressure_bonus / edge_potential_pressure / simulate_pressure:
    Collective-pressure extension. Neighbours of overpressured edges
    receive a discount. Empirically marginal in tested regimes; kept
    as theoretical sibling.

  simulate_momentum_live:
    Reaction-memory mechanism (BLOOD LIVE). When a packet dies on
    edge e, snap[e] is incremented at runtime so subsequent packets
    avoid the bloodstained edge. Empirically dominant; v2.0+ headline.

Both degenerate bit-for-bit to EMMET-DP v1 when their control
parameter (eta or blood_rate) is zero.
"""
import sys
sys.path.insert(0, '/home/clopez/emmet/experiments')
from emmet_budget import edge_potential, BETA, THETA

def overpressure(G, u, v):
    """delta(e) = max(0, load(e) - capacity(e))."""
    e = G[u][v]
    return max(0.0, e['load'] - e['capacity'])

def pressure_bonus(G, u, v, eta):
    """Total collective-pressure discount that neighbours of (u,v) confer.

    Returns positive value to subtract from edge potential.
    If eta=0 or no neighbours overpressured: returns 0.0.
    """
    if eta == 0.0:
        return 0.0
    total = 0.0
    for endpoint in (u, v):
        other = v if endpoint == u else u
        for neighbour in G.neighbors(endpoint):
            if neighbour == other:
                continue
            e_prime = G[endpoint][neighbour]
            d = max(0.0, e_prime['load'] - e_prime['capacity'])
            if d > 0:
                total += eta * d / e_prime['capacity']
    return total



def bleeding(snap, u, v):
    """blood(e) = snap[(u,v)] -- persistent loss memory on edge."""
    k = tuple(sorted([u, v]))
    return snap.get(k, 0.0)

def blood_penalty(G, u, v, snap, eta):
    if eta == 0.0:
        return 0.0
    total = 0.0
    for endpoint in (u, v):
        other = v if endpoint == u else u
        for neighbour in G.neighbors(endpoint):
            if neighbour == other:
                continue
            blood = bleeding(snap, endpoint, neighbour)
            if blood > 0:
                cap = G[endpoint][neighbour]['capacity']
                total += eta * blood / cap
    return total


def edge_potential_pressure(G, u, v, snap, beta_eff, eta=0.0):
    """Phi_C(e) = Phi(e) - bonus_carlos(e).
    
    When eta = 0, this is bit-for-bit Phi(e) from emmet_budget.
    """
    base = edge_potential(G, u, v, snap, beta_eff)
    penalty = blood_penalty(G, u, v, snap, eta)
    return base + penalty


import math
import networkx as nx
from emmet_momentum_dp import bucket_to_m, m_to_bucket, M_INITIAL, KAPPA, M_MAX, ALPHA_BUDGET, M_BUCKETS


def emmet_pressure_route(G, src, dst, snap, eta=0.0, kappa=KAPPA, m_max=M_MAX,
                       alpha_budget=ALPHA_BUDGET, n_buckets=M_BUCKETS):
    """EMMET-DP with CARLOS collective-pressure extension.

    Identical to emmet_momentum_dp_route when eta=0. When eta>0, the edge
    potential includes the Newton-III collective bonus from neighbouring
    overpressured edges (see notes/newton3_design.md formulation CARLOS).
    """
    if src == dst:
        return [src], 0
    try:
        sp_hops = nx.shortest_path_length(G, src, dst)
    except nx.NetworkXNoPath:
        return None, 0
    k = max(sp_hops, math.ceil(alpha_budget * sp_hops))

    n_e = G.number_of_edges()
    if n_e:
        temp = sum(G[u][v]['load']/G[u][v]['capacity'] for u,v in G.edges()) / n_e
    else:
        temp = 0
    beta_eff = BETA * (1 + THETA * temp)

    INF = float('inf')
    nodes = list(G.nodes())
    f      = [{n: [INF]*n_buckets  for n in nodes} for _ in range(k+1)]
    parent = [{n: [None]*n_buckets for n in nodes} for _ in range(k+1)]
    f[0][src][0] = 0.0

    for h in range(1, k+1):
        for v in nodes:
            for u in G.neighbors(v):
                for b_in in range(n_buckets):
                    if f[h-1][u][b_in] == INF:
                        continue
                    m_in = bucket_to_m(b_in, m_max, n_buckets)
                    pot = edge_potential_pressure(G, u, v, snap, beta_eff, eta=eta)
                    cost_step = m_in * pot
                    new_cost = f[h-1][u][b_in] + cost_step
                    cong = G[u][v]['load'] / G[u][v]['capacity']
                    m_out = min(m_in * (1 + kappa * cong), m_max)
                    b_out = m_to_bucket(m_out, m_max, n_buckets)
                    if new_cost < f[h][v][b_out]:
                        f[h][v][b_out] = new_cost
                        parent[h][v][b_out] = (u, b_in)

    best_h, best_b, best_cost = None, None, INF
    for h in range(sp_hops, k+1):
        for b in range(n_buckets):
            if f[h][dst][b] < best_cost:
                best_cost = f[h][dst][b]
                best_h, best_b = h, b

    if best_h is None:
        return None, 0

    path = [dst]
    cur, h, b = dst, best_h, best_b
    while h > 0:
        prev = parent[h][cur][b]
        if prev is None:
            return None, 0
        cur, b = prev
        h -= 1
        path.append(cur)
    path.reverse()
    return path, bucket_to_m(best_b, m_max, n_buckets)


from emmet_budget import DECAY

def simulate_pressure(G, traffic, snap, kappa, n_buckets, eta=0.0):
    snap_l = dict(snap)
    losses = delivered = nopath = 0
    cap_d = cap_l = 0
    for src, dst in traffic:
        if src == dst:
            continue
        path, _ = emmet_pressure_route(
            G, src, dst, snap_l, eta=eta, kappa=kappa, m_max=M_MAX,
            alpha_budget=ALPHA_BUDGET, n_buckets=n_buckets)
        if path is None or len(path) < 2:
            nopath += 1; continue
        lost = False; pc = 0
        for i in range(len(path)-1):
            u, v = path[i], path[i+1]
            e = G[u][v]
            e['load'] += 1; pc += 1
            if e['load'] > e['capacity']:
                e['loss'] += 1; losses += 1; lost = True; break
        if not lost:
            delivered += 1; cap_d += pc
        else:
            cap_l += pc
        for u, v in G.edges():
            G[u][v]['load'] *= 0.9
        for k in list(snap_l.keys()):
            snap_l[k] *= DECAY
    attempted = delivered + losses + nopath
    routed = delivered + losses
    total_cap = cap_d + cap_l
    return dict(
        delivered=delivered, losses=losses, nopath=nopath,
        delivery_rate=delivered/attempted*100 if attempted else 0,
        cap_per_delivery=cap_d/delivered if delivered else 0,
        cap_per_attempt=total_cap/attempted if attempted else 0,
        cap_per_routed_attempt=total_cap/routed if routed else 0,
        cap_consumed_lost=cap_l,
    )


def simulate_momentum_live(G, traffic, snap, kappa, n_buckets, blood_rate=1.0):
    """EMMET-DP with BLOOD LIVE for Poisson traffic (no GAP_SENTINEL)."""
    from emmet_momentum_dp import emmet_momentum_dp_route
    from emmet_budget import DECAY as DECAY_SNAP
    snap_l = dict(snap)
    losses = delivered = nopath = 0
    cap_d = cap_l = 0
    for src, dst in traffic:
        if src == dst:
            continue
        path, _ = emmet_momentum_dp_route(
            G, src, dst, snap_l, kappa=kappa, m_max=M_MAX,
            alpha_budget=ALPHA_BUDGET, n_buckets=n_buckets)
        if path is None or len(path) < 2:
            nopath += 1; continue
        lost = False; pc = 0; bleed_k = None
        for i in range(len(path)-1):
            u, v = path[i], path[i+1]
            e = G[u][v]
            e['load'] += 1; pc += 1
            if e['load'] > e['capacity']:
                e['loss'] += 1; losses += 1; lost = True
                bleed_k = tuple(sorted([u, v]))
                break
        if not lost:
            delivered += 1; cap_d += pc
        else:
            cap_l += pc
            snap_l[bleed_k] = snap_l.get(bleed_k, 0) + blood_rate
        for u, v in G.edges():
            G[u][v]['load'] *= 0.9
        for k in list(snap_l.keys()):
            snap_l[k] *= DECAY_SNAP
    attempted = delivered + losses + nopath
    routed = delivered + losses
    total_cap = cap_d + cap_l
    return dict(
        delivered=delivered, losses=losses, nopath=nopath,
        delivery_rate=delivered/attempted*100 if attempted else 0,
        cap_per_delivery=cap_d/delivered if delivered else 0,
        cap_per_attempt=total_cap/attempted if attempted else 0,
        cap_per_routed_attempt=total_cap/routed if routed else 0,
        cap_consumed_lost=cap_l,
    )
