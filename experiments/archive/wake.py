"""ESTELA (wake) v2 — directional flow memory, TWO magnitudes (no cancel).

Two boats crossing leave two wakes, not a subtraction. So each edge keeps
wake_fwd (flow min->max) and wake_bwd (flow max->min), both POSITIVE.
Travelling ALONG a strong wake -> discount; AGAINST -> surcharge.

Carlos' insight: wake is fed by traffic and closes when flow ceases
(self-regulating); at rest no wakes -> no self-harm.
"""
import sys, math
sys.path.insert(0, '/home/clopez/emmet/experiments')
import networkx as nx
from emmet_budget import BETA, GAMMA, ALPHA_LAT, THETA, DECAY
from emmet_momentum_dp import bucket_to_m, m_to_bucket, M_MAX, ALPHA_BUDGET, M_BUCKETS


def wake_edge_potential(G, u, v, snap, wfwd, wbwd, beta_eff, wake_gain):
    e = G[u][v]
    cong = e['load'] / e['capacity']
    k = tuple(sorted([u, v]))
    lv = snap.get(k, 0)
    base = ALPHA_LAT * e['latency'] + beta_eff * cong + GAMMA * lv
    pos = (u < v)
    along  = wfwd.get(k, 0.0) if pos else wbwd.get(k, 0.0)
    against = wbwd.get(k, 0.0) if pos else wfwd.get(k, 0.0)
    return base - wake_gain * along + wake_gain * against


def wake_dp_route(G, src, dst, snap, wfwd, wbwd, wake_gain, kappa,
                  m_max=M_MAX, alpha_budget=ALPHA_BUDGET, n_buckets=M_BUCKETS):
    if src == dst:
        return [src], 0
    try:
        sp_hops = nx.shortest_path_length(G, src, dst)
    except nx.NetworkXNoPath:
        return None, 0
    k = max(sp_hops, math.ceil(alpha_budget * sp_hops))
    n_e = G.number_of_edges()
    temp = (sum(G[u][v]['load']/G[u][v]['capacity'] for u,v in G.edges())/n_e) if n_e else 0
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
                    if f[h-1][u][b_in] == INF: continue
                    m_in = bucket_to_m(b_in, m_max, n_buckets)
                    pot = wake_edge_potential(G, u, v, snap, wfwd, wbwd, beta_eff, wake_gain)
                    new_cost = f[h-1][u][b_in] + m_in * pot
                    cong = G[u][v]['load'] / G[u][v]['capacity']
                    m_out = min(m_in * (1 + kappa * cong), m_max)
                    b_out = m_to_bucket(m_out, m_max, n_buckets)
                    if new_cost < f[h][v][b_out]:
                        f[h][v][b_out] = new_cost
                        parent[h][v][b_out] = (u, b_in)
    best_h=best_b=None; best_cost=INF
    for h in range(sp_hops, k+1):
        for b in range(n_buckets):
            if f[h][dst][b] < best_cost:
                best_cost=f[h][dst][b]; best_h,best_b=h,b
    if best_h is None: return None, 0
    path=[dst]; cur,h,b=dst,best_h,best_b
    while h>0:
        prev=parent[h][cur][b]
        if prev is None: return None,0
        cur,b=prev; h-=1; path.append(cur)
    path.reverse()
    return path, bucket_to_m(best_b, m_max, n_buckets)


def _reinforce(wfwd, wbwd, path, deposit):
    """Each traversed edge feeds the wake IN ITS direction (positive only).
    fwd if u<v (min->max), bwd otherwise. No cancellation."""
    for i in range(len(path) - 1):
        u, v = path[i], path[i+1]
        k = tuple(sorted([u, v]))
        if u < v:
            wfwd[k] = wfwd.get(k, 0.0) + deposit
        else:
            wbwd[k] = wbwd.get(k, 0.0) + deposit


def run_wake(G, traf, snap, kappa, n_buckets, blood_rate=2.0,
             wake_gain=0.0, wake_deposit=1.0, wake_decay=0.85):
    """EMMET gradient+blood core + directional WAKE (two magnitudes).
    wake_gain=0 recovers pure gradient+blood (control)."""
    from bursty_runner import _walk_packet_archimedes, _decay, _decay_snap, _summary
    from bursty_traffic import GAP_SENTINEL
    snap_l = dict(snap)
    wfwd = {}; wbwd = {}
    losses = delivered = nopath = 0
    cap_d = cap_l = 0

    def erode():
        for d in (wfwd, wbwd):
            for k in list(d.keys()):
                d[k] *= wake_decay

    for step in traf:
        if step == GAP_SENTINEL or (step[0] == step[1]):
            _decay(G); _decay_snap(snap_l, DECAY); erode(); continue
        src, dst = step
        path, _ = wake_dp_route(G, src, dst, snap_l, wfwd, wbwd, wake_gain, kappa, n_buckets=n_buckets)
        if path is None or len(path) < 2:
            nopath += 1; _decay(G); _decay_snap(snap_l, DECAY); erode(); continue
        ok, hops, bk, m_eff, rho = _walk_packet_archimedes(G, path, kappa)
        if ok:
            delivered += 1; cap_d += hops
            _reinforce(wfwd, wbwd, path, wake_deposit)
        else:
            losses += 1; cap_l += hops
            snap_l[bk] = snap_l.get(bk, 0) + blood_rate * m_eff * rho
            cut = path.index(bk[0]) + 1 if bk[0] in path else len(path)
            _reinforce(wfwd, wbwd, path[:cut], wake_deposit)
        _decay(G)
        for k in list(snap_l.keys()): snap_l[k] *= DECAY
        erode()
    return _summary(delivered, losses, nopath, cap_d, cap_l)


ESCAPE_LO = 0.5

def _walk_escape(G, path, kappa):
    from emmet_momentum_dp import M_MAX
    hops = 0; m_eff = 1.0; escaped = []
    for i in range(len(path) - 1):
        u, v = path[i], path[i+1]
        e = G[u][v]
        rho_before = e['load'] / e['capacity']
        e['load'] += 1; hops += 1
        if e['load'] > e['capacity']:
            e['loss'] += 1
            return False, hops, tuple(sorted([u, v])), m_eff, rho_before, escaped
        if rho_before >= ESCAPE_LO:
            escaped.append(i)
        m_eff = min(m_eff * (1 + kappa * rho_before), M_MAX)
    return True, hops, None, m_eff, 0.0, escaped


def _reinforce_escape(wfwd, wbwd, path, escaped, deposit):
    """Deposit wake ONLY on hot edges that were successfully crossed
    (the escape route), in the direction of travel."""
    for i in escaped:
        u, v = path[i], path[i+1]
        k = tuple(sorted([u, v]))
        if u < v:
            wfwd[k] = wfwd.get(k, 0.0) + deposit
        else:
            wbwd[k] = wbwd.get(k, 0.0) + deposit


def run_wake_escape(G, traf, snap, kappa, n_buckets, blood_rate=2.0,
                    wake_gain=0.0, wake_deposit=1.0, wake_decay=0.85):
    """EMMET gradient+blood + ESCAPE wake (evacuation direction, not popularity).
    wake_gain=0 recovers pure gradient+blood (control)."""
    from bursty_runner import _decay, _decay_snap, _summary
    from bursty_traffic import GAP_SENTINEL
    snap_l = dict(snap)
    wfwd = {}; wbwd = {}
    losses = delivered = nopath = 0
    cap_d = cap_l = 0
    def erode():
        for d in (wfwd, wbwd):
            for k in list(d.keys()): d[k] *= wake_decay

    for step in traf:
        if step == GAP_SENTINEL or (step[0] == step[1]):
            _decay(G); _decay_snap(snap_l, DECAY); erode(); continue
        src, dst = step
        path, _ = wake_dp_route(G, src, dst, snap_l, wfwd, wbwd, wake_gain, kappa, n_buckets=n_buckets)
        if path is None or len(path) < 2:
            nopath += 1; _decay(G); _decay_snap(snap_l, DECAY); erode(); continue
        ok, hops, bk, m_eff, rho, escaped = _walk_escape(G, path, kappa)
        if ok:
            delivered += 1; cap_d += hops
            _reinforce_escape(wfwd, wbwd, path, escaped, wake_deposit)
        else:
            losses += 1; cap_l += hops
            snap_l[bk] = snap_l.get(bk, 0) + blood_rate * m_eff * rho
            _reinforce_escape(wfwd, wbwd, path, escaped, wake_deposit)
        _decay(G)
        for k in list(snap_l.keys()): snap_l[k] *= DECAY
        erode()
    return _summary(delivered, losses, nopath, cap_d, cap_l)
