"""Run LASP-aug / CONGA-WAN / EMMET-DP under bursty traffic.

Reuses the existing simulators by filtering GAP_SENTINEL tokens
between routing calls and applying edge-load decay on gap steps.
This way the routing logic is unchanged; only the traffic shape
is varied.
"""
import sys
sys.path.insert(0, '/home/clopez/emmet/experiments')
from emmet_budget import edge_potential, BETA, THETA, reset
from emmet_momentum_dp import lasp_aug_route, emmet_momentum_dp_route
from conga_wan import conga_wan_route
from bursty_traffic import GAP_SENTINEL
import networkx as nx

def _walk_packet(G, path):
    """Simulate one packet along path. Returns (delivered, hops_used)."""
    hops = 0
    for i in range(len(path)-1):
        u, v = path[i], path[i+1]
        e = G[u][v]
        e['load'] += 1; hops += 1
        if e['load'] > e['capacity']:
            e['loss'] += 1
            return False, hops
    return True, hops

def _decay(G):
    for u, v in G.edges():
        G[u][v]['load'] *= 0.9

def _decay_snap(snap_l, decay):
    """Decay snap_l in-place. Called every simulated step (incl. gaps)."""
    for k in list(snap_l.keys()):
        snap_l[k] *= decay

def run_bursty_lasp(G, traf, snap):
    snap_l = dict(snap)
    losses = delivered = nopath = 0
    cap_d = cap_l = 0
    from emmet_budget import DECAY
    for step in traf:
        if step == GAP_SENTINEL:
            _decay(G); _decay_snap(snap_l, DECAY); continue
        src, dst = step
        if src == dst:
            _decay(G); _decay_snap(snap_l, DECAY); continue
        path, _ = lasp_aug_route(G, src, dst, snap_l)
        if path is None or len(path) < 2:
            nopath += 1; _decay(G); _decay_snap(snap_l, DECAY); continue
        ok, hops = _walk_packet(G, path)
        if ok:
            delivered += 1; cap_d += hops
        else:
            losses += 1; cap_l += hops
        _decay(G)
        for k in list(snap_l.keys()):
            snap_l[k] *= DECAY
    return _summary(delivered, losses, nopath, cap_d, cap_l)

def run_bursty_conga(G, traf):
    losses = delivered = nopath = 0
    cap_d = cap_l = 0
    for step in traf:
        if step == GAP_SENTINEL:
            _decay(G); continue
        src, dst = step
        if src == dst:
            _decay(G); continue
        path, _ = conga_wan_route(G, src, dst)
        if path is None or len(path) < 2:
            nopath += 1; _decay(G); continue
        ok, hops = _walk_packet(G, path)
        if ok:
            delivered += 1; cap_d += hops
        else:
            losses += 1; cap_l += hops
        _decay(G)
    return _summary(delivered, losses, nopath, cap_d, cap_l)

from momentum_clean import M_MAX, ALPHA_BUDGET

def run_bursty_emmet(G, traf, snap, kappa, n_buckets):
    snap_l = dict(snap)
    losses = delivered = nopath = 0
    cap_d = cap_l = 0
    from emmet_budget import DECAY
    for step in traf:
        if step == GAP_SENTINEL:
            _decay(G); _decay_snap(snap_l, DECAY); continue
        src, dst = step
        if src == dst:
            _decay(G); _decay_snap(snap_l, DECAY); continue
        path, _ = emmet_momentum_dp_route(
            G, src, dst, snap_l, kappa=kappa, m_max=M_MAX,
            alpha_budget=ALPHA_BUDGET, n_buckets=n_buckets)
        if path is None or len(path) < 2:
            nopath += 1; _decay(G); _decay_snap(snap_l, DECAY); continue
        ok, hops = _walk_packet(G, path)
        if ok:
            delivered += 1; cap_d += hops
        else:
            losses += 1; cap_l += hops
        _decay(G)
        for k in list(snap_l.keys()):
            snap_l[k] *= DECAY
    return _summary(delivered, losses, nopath, cap_d, cap_l)

def _summary(delivered, losses, nopath, cap_d, cap_l):
    att = delivered + losses + nopath
    routed = delivered + losses
    total = cap_d + cap_l
    return dict(
        delivered=delivered, losses=losses, nopath=nopath,
        delivery_rate=delivered/att*100 if att else 0,
        cap_per_delivery=cap_d/delivered if delivered else 0,
        cap_per_attempt=total/att if att else 0,
        cap_per_routed_attempt=total/routed if routed else 0,
        cap_consumed_lost=cap_l,
    )


def run_bursty_pressure(G, traf, snap, kappa, n_buckets, eta=0.0):
    """Bursty simulator using EMMET-CARLOS routing."""
    from emmet_newt import emmet_pressure_route
    from emmet_budget import DECAY
    snap_l = dict(snap)
    losses = delivered = nopath = 0
    cap_d = cap_l = 0
    for step in traf:
        if step == GAP_SENTINEL:
            _decay(G); _decay_snap(snap_l, DECAY); continue
        src, dst = step
        if src == dst:
            _decay(G); _decay_snap(snap_l, DECAY); continue
        path, _ = emmet_pressure_route(
            G, src, dst, snap_l, eta=eta, kappa=kappa, m_max=M_MAX,
            alpha_budget=ALPHA_BUDGET, n_buckets=n_buckets)
        if path is None or len(path) < 2:
            nopath += 1; _decay(G); _decay_snap(snap_l, DECAY); continue
        ok, hops = _walk_packet(G, path)
        if ok:
            delivered += 1; cap_d += hops
        else:
            losses += 1; cap_l += hops
        _decay(G)
        for k in list(snap_l.keys()):
            snap_l[k] *= DECAY
    return _summary(delivered, losses, nopath, cap_d, cap_l)


def _walk_packet_bleed(G, path):
    """Like _walk_packet but also returns the bleeding edge key when loss."""
    hops = 0
    for i in range(len(path)-1):
        u, v = path[i], path[i+1]
        e = G[u][v]
        e['load'] += 1; hops += 1
        if e['load'] > e['capacity']:
            e['loss'] += 1
            return False, hops, tuple(sorted([u, v]))
    return True, hops, None


def run_bursty_emmet_live(G, traf, snap, kappa, n_buckets, blood_rate=1.0):
    """EMMET-DP with BLOOD LIVE: snap[e] increments when a packet dies on e."""
    from emmet_momentum_dp import emmet_momentum_dp_route
    from emmet_budget import DECAY
    snap_l = dict(snap)
    losses = delivered = nopath = 0
    cap_d = cap_l = 0
    for step in traf:
        if step == GAP_SENTINEL:
            _decay(G); _decay_snap(snap_l, DECAY); continue
        src, dst = step
        if src == dst:
            _decay(G); _decay_snap(snap_l, DECAY); continue
        path, _ = emmet_momentum_dp_route(
            G, src, dst, snap_l, kappa=kappa, m_max=M_MAX,
            alpha_budget=ALPHA_BUDGET, n_buckets=n_buckets)
        if path is None or len(path) < 2:
            nopath += 1; _decay(G); _decay_snap(snap_l, DECAY); continue
        ok, hops, bleed_key = _walk_packet_bleed(G, path)
        if ok:
            delivered += 1; cap_d += hops
        else:
            losses += 1; cap_l += hops
            snap_l[bleed_key] = snap_l.get(bleed_key, 0) + blood_rate
        _decay(G)
        for k in list(snap_l.keys()):
            snap_l[k] *= DECAY
    return _summary(delivered, losses, nopath, cap_d, cap_l)


def run_bursty_emmet_live_delayed(G, traf, snap, kappa, n_buckets, blood_rate=1.0):
    """EMMET-DP BLOOD LIVE DELAYED: blood is buffered during a burst and
    flushed to snap_l only when GAP_SENTINEL arrives (Codex P1 fix)."""
    from emmet_momentum_dp import emmet_momentum_dp_route
    from emmet_budget import DECAY
    snap_l = dict(snap)
    pending = {}
    losses = delivered = nopath = 0
    cap_d = cap_l = 0
    for step in traf:
        if step == GAP_SENTINEL:
            for k, v in pending.items():
                snap_l[k] = snap_l.get(k, 0) + v
            pending = {}
            _decay(G); _decay_snap(snap_l, DECAY); continue
        src, dst = step
        if src == dst:
            _decay(G); _decay_snap(snap_l, DECAY); continue
        path, _ = emmet_momentum_dp_route(
            G, src, dst, snap_l, kappa=kappa, m_max=M_MAX,
            alpha_budget=ALPHA_BUDGET, n_buckets=n_buckets)
        if path is None or len(path) < 2:
            nopath += 1; _decay(G); _decay_snap(snap_l, DECAY); continue
        ok, hops, bleed_key = _walk_packet_bleed(G, path)
        if ok:
            delivered += 1; cap_d += hops
        else:
            losses += 1; cap_l += hops
            # Buffer blood, don't apply to snap_l yet
            pending[bleed_key] = pending.get(bleed_key, 0) + blood_rate
        _decay(G); _decay_snap(snap_l, DECAY)
    # Flush any remaining blood at end of traffic
    for k, v in pending.items():
        snap_l[k] = snap_l.get(k, 0) + v
    return _summary(delivered, losses, nopath, cap_d, cap_l)


# ARCHIMEDES variant: blood deposit scaled by displaced fluid.
# blood = blood_rate * m_eff * (load/capacity) at point of death.

def _walk_packet_archimedes(G, path, kappa):
    """Walk packet tracking m_eff. Returns
    (ok, hops, bleed_key, m_eff_at_death, rho_at_death)."""
    hops = 0
    m_eff = 1.0
    for i in range(len(path) - 1):
        u, v = path[i], path[i+1]
        e = G[u][v]
        rho_before = e['load'] / e['capacity']
        e['load'] += 1; hops += 1
        if e['load'] > e['capacity']:
            e['loss'] += 1
            return False, hops, tuple(sorted([u, v])), m_eff, rho_before
        m_eff = min(m_eff * (1 + kappa * rho_before), M_MAX)
    return True, hops, None, m_eff, 0.0


def run_bursty_emmet_live_archimedes(G, traf, snap, kappa, n_buckets, blood_rate=1.0):
    """LIVE with Archimedes-scaled blood: blood_rate * m_eff * rho."""
    from emmet_momentum_dp import emmet_momentum_dp_route
    from emmet_budget import DECAY
    snap_l = dict(snap)
    losses = delivered = nopath = 0
    cap_d = cap_l = 0
    for step in traf:
        if step == GAP_SENTINEL:
            _decay(G); _decay_snap(snap_l, DECAY); continue
        src, dst = step
        if src == dst:
            _decay(G); _decay_snap(snap_l, DECAY); continue
        path, _ = emmet_momentum_dp_route(
            G, src, dst, snap_l, kappa=kappa, m_max=M_MAX,
            alpha_budget=ALPHA_BUDGET, n_buckets=n_buckets)
        if path is None or len(path) < 2:
            nopath += 1; _decay(G); _decay_snap(snap_l, DECAY); continue
        ok, hops, bk, m_eff, rho = _walk_packet_archimedes(G, path, kappa)
        if ok:
            delivered += 1; cap_d += hops
        else:
            losses += 1; cap_l += hops
            deposit = blood_rate * m_eff * rho
            snap_l[bk] = snap_l.get(bk, 0) + deposit
        _decay(G)
        for k in list(snap_l.keys()):
            snap_l[k] *= DECAY
    return _summary(delivered, losses, nopath, cap_d, cap_l)


def run_bursty_emmet_live_delayed_archimedes(G, traf, snap, kappa, n_buckets, blood_rate=1.0):
    """DELAYED with Archimedes-scaled blood (Codex P1 conservative)."""
    from emmet_momentum_dp import emmet_momentum_dp_route
    from emmet_budget import DECAY
    snap_l = dict(snap)
    pending = {}
    losses = delivered = nopath = 0
    cap_d = cap_l = 0
    for step in traf:
        if step == GAP_SENTINEL:
            # Burst boundary: flush pending blood into snap_l
            for k, v in pending.items():
                snap_l[k] = snap_l.get(k, 0) + v
            pending = {}
            _decay(G); _decay_snap(snap_l, DECAY); continue
        src, dst = step
        if src == dst:
            _decay(G); _decay_snap(snap_l, DECAY); continue
        path, _ = emmet_momentum_dp_route(
            G, src, dst, snap_l, kappa=kappa, m_max=M_MAX,
            alpha_budget=ALPHA_BUDGET, n_buckets=n_buckets)
        if path is None or len(path) < 2:
            nopath += 1; _decay(G); _decay_snap(snap_l, DECAY); continue
        ok, hops, bk, m_eff, rho = _walk_packet_archimedes(G, path, kappa)
        if ok:
            delivered += 1; cap_d += hops
        else:
            losses += 1; cap_l += hops
            deposit = blood_rate * m_eff * rho
            pending[bk] = pending.get(bk, 0) + deposit
        _decay(G)
        for k in list(snap_l.keys()):
            snap_l[k] *= DECAY
    # End of traffic: flush remaining pending
    for k, v in pending.items():
        snap_l[k] = snap_l.get(k, 0) + v
    return _summary(delivered, losses, nopath, cap_d, cap_l)


# =====================================================================
# SPLASH variant: Archimedes + lateral propagation to neighbour edges.
# When a packet dies on edge e:
#   snap[e]  += rate * m_eff * rho                    (own edge)
#   snap[e'] += rate * m_eff * rho * splash_factor    (each neighbour e')
# where neighbour means an edge sharing one endpoint with e.
# Splash simulates the lateral spread of failure information.
# =====================================================================

def _neighbour_edges(G, u, v):
    """Return list of edge keys (sorted tuple) adjacent to (u,v),
    excluding (u,v) itself."""
    out = []
    for nb in G.neighbors(u):
        if nb != v:
            out.append(tuple(sorted([u, nb])))
    for nb in G.neighbors(v):
        if nb != u:
            out.append(tuple(sorted([v, nb])))
    return out


def run_bursty_emmet_live_splash(G, traf, snap, kappa, n_buckets, blood_rate=1.0, splash=0.3):
    """LIVE with splash: blood on dying edge AND fraction on neighbours."""
    from emmet_momentum_dp import emmet_momentum_dp_route
    from emmet_budget import DECAY
    snap_l = dict(snap)
    losses = delivered = nopath = 0
    cap_d = cap_l = 0
    for step in traf:
        if step == GAP_SENTINEL:
            _decay(G); _decay_snap(snap_l, DECAY); continue
        src, dst = step
        if src == dst:
            _decay(G); _decay_snap(snap_l, DECAY); continue
        path, _ = emmet_momentum_dp_route(
            G, src, dst, snap_l, kappa=kappa, m_max=M_MAX,
            alpha_budget=ALPHA_BUDGET, n_buckets=n_buckets)
        if path is None or len(path) < 2:
            nopath += 1; _decay(G); _decay_snap(snap_l, DECAY); continue
        ok, hops, bk, m_eff, rho = _walk_packet_archimedes(G, path, kappa)
        if ok:
            delivered += 1; cap_d += hops
        else:
            losses += 1; cap_l += hops
            base = blood_rate * m_eff * rho
            snap_l[bk] = snap_l.get(bk, 0) + base
            # Splash to neighbour edges
            u, v = bk
            for ek in _neighbour_edges(G, u, v):
                snap_l[ek] = snap_l.get(ek, 0) + base * splash
        _decay(G)
        for k in list(snap_l.keys()):
            snap_l[k] *= DECAY
    return _summary(delivered, losses, nopath, cap_d, cap_l)


def run_bursty_emmet_live_delayed_splash(G, traf, snap, kappa, n_buckets, blood_rate=1.0, splash=0.3):
    """DELAYED splash: blood buffered until burst end, then flushed
    with splash to neighbours."""
    from emmet_momentum_dp import emmet_momentum_dp_route
    from emmet_budget import DECAY
    snap_l = dict(snap)
    pending = {}
    losses = delivered = nopath = 0
    cap_d = cap_l = 0
    for step in traf:
        if step == GAP_SENTINEL:
            for k, v in pending.items():
                snap_l[k] = snap_l.get(k, 0) + v
            pending = {}
            _decay(G); _decay_snap(snap_l, DECAY); continue
        src, dst = step
        if src == dst:
            _decay(G); _decay_snap(snap_l, DECAY); continue
        path, _ = emmet_momentum_dp_route(
            G, src, dst, snap_l, kappa=kappa, m_max=M_MAX,
            alpha_budget=ALPHA_BUDGET, n_buckets=n_buckets)
        if path is None or len(path) < 2:
            nopath += 1; _decay(G); _decay_snap(snap_l, DECAY); continue
        ok, hops, bk, m_eff, rho = _walk_packet_archimedes(G, path, kappa)
        if ok:
            delivered += 1; cap_d += hops
        else:
            losses += 1; cap_l += hops
            base = blood_rate * m_eff * rho
            pending[bk] = pending.get(bk, 0) + base
            u, v = bk
            for ek in _neighbour_edges(G, u, v):
                pending[ek] = pending.get(ek, 0) + base * splash
        _decay(G)
        for k in list(snap_l.keys()):
            snap_l[k] *= DECAY
    for k, v in pending.items():
        snap_l[k] = snap_l.get(k, 0) + v
    return _summary(delivered, losses, nopath, cap_d, cap_l)


# RIPPLE variant: Archimedes + temporal wave propagation.
# When packet dies on edge e at step t, deposits scheduled at
# t, t+1, ..., t+ripple_steps with decay factor ripple^k.

def run_bursty_emmet_live_ripple(G, traf, snap, kappa, n_buckets,
                                  blood_rate=1.0, ripple=0.5,
                                  ripple_steps=5):
    """LIVE with Archimedes + temporal ripple."""
    from emmet_momentum_dp import emmet_momentum_dp_route
    from emmet_budget import DECAY
    snap_l = dict(snap)
    pending_ripples = []  # list of (edge_key, base, remaining_steps)
    losses = delivered = nopath = 0
    cap_d = cap_l = 0
    for step in traf:
        # Apply scheduled ripples at start of every step (incl. gaps)
        new_pending = []
        for ek, base, k_left in pending_ripples:
            if k_left > 0:
                deposit = base * (ripple ** (ripple_steps - k_left + 1))
                snap_l[ek] = snap_l.get(ek, 0) + deposit
                new_pending.append((ek, base, k_left - 1))
        pending_ripples = new_pending

        if step == GAP_SENTINEL:
            _decay(G); _decay_snap(snap_l, DECAY); continue
        src, dst = step
        if src == dst:
            _decay(G); _decay_snap(snap_l, DECAY); continue
        path, _ = emmet_momentum_dp_route(
            G, src, dst, snap_l, kappa=kappa, m_max=M_MAX,
            alpha_budget=ALPHA_BUDGET, n_buckets=n_buckets)
        if path is None or len(path) < 2:
            nopath += 1; _decay(G); _decay_snap(snap_l, DECAY); continue
        ok, hops, bk, m_eff, rho = _walk_packet_archimedes(G, path, kappa)
        if ok:
            delivered += 1; cap_d += hops
        else:
            losses += 1; cap_l += hops
            base = blood_rate * m_eff * rho
            snap_l[bk] = snap_l.get(bk, 0) + base
            if ripple_steps > 0:
                pending_ripples.append((bk, base, ripple_steps))
        _decay(G)
        for k in list(snap_l.keys()):
            snap_l[k] *= DECAY
    return _summary(delivered, losses, nopath, cap_d, cap_l)
