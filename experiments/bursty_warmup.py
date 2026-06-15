"""Bursty-aware warmups for the three baselines.

The original warmups in momentum_clean.py expect a flat list of
(src, dst) pairs and apply edge-load decay after every step. Under
bursty traffic we must also decay during GAP_SENTINEL steps (without
routing), so that the snapshot reflects the on/off structure of the
workload, not just packet pacing.

These wrappers reuse the underlying logic and only differ in the
traffic iteration loop.
"""
import sys
sys.path.insert(0, '/home/clopez/emmet/experiments')
import networkx as nx
from emmet_budget import edge_potential, BETA, THETA, reset
from emmet_momentum_dp import lasp_aug_route, emmet_momentum_dp_route
from conga_wan import conga_wan_route
from bursty_traffic import GAP_SENTINEL
from emmet_momentum_dp import M_MAX, ALPHA_BUDGET

def _decay(G):
    for u, v in G.edges():
        G[u][v]['load'] *= 0.9

def _snap(G):
    return {tuple(sorted([u, v])): G[u][v]['loss'] for u, v in G.edges()}

def warmup_bursty_lasp(G, traf):
    snap = {}
    for step in traf:
        if step == GAP_SENTINEL:
            _decay(G); continue
        src, dst = step
        if src == dst:
            _decay(G); continue
        n_e = G.number_of_edges()
        temp = sum(G[u][v]['load']/G[u][v]['capacity'] for u,v in G.edges())/n_e if n_e else 0
        beta_eff = BETA * (1 + THETA * temp)
        def w(u, v, d):
            e = G[u][v]
            cong = e['load']/e['capacity']
            k = tuple(sorted([u, v]))
            return 1.0*e['latency'] + beta_eff*cong + 2.0*snap.get(k, 0)
        try:
            path = nx.shortest_path(G, src, dst, weight=w)
        except nx.NetworkXNoPath:
            _decay(G); continue
        for i in range(len(path)-1):
            u, v = path[i], path[i+1]
            e = G[u][v]
            e['load'] += 1
            if e['load'] > e['capacity']:
                e['loss'] += 1; break
        _decay(G)
    return _snap(G)

def warmup_bursty_conga(G, traf):
    for step in traf:
        if step == GAP_SENTINEL:
            _decay(G); continue
        src, dst = step
        if src == dst:
            _decay(G); continue
        path, _ = conga_wan_route(G, src, dst)
        if path is None or len(path) < 2:
            _decay(G); continue
        for i in range(len(path)-1):
            u, v = path[i], path[i+1]
            e = G[u][v]
            e['load'] += 1
            if e['load'] > e['capacity']:
                e['loss'] += 1; break
        _decay(G)
    return _snap(G)

def warmup_bursty_momentum(G, traf, kappa, n_buckets):
    snap = {}
    for step in traf:
        if step == GAP_SENTINEL:
            _decay(G); continue
        src, dst = step
        if src == dst:
            _decay(G); continue
        path, _ = emmet_momentum_dp_route(
            G, src, dst, snap, kappa=kappa, m_max=M_MAX,
            alpha_budget=ALPHA_BUDGET, n_buckets=n_buckets)
        if path is None or len(path) < 2:
            _decay(G); continue
        for i in range(len(path)-1):
            u, v = path[i], path[i+1]
            e = G[u][v]
            e['load'] += 1
            if e['load'] > e['capacity']:
                e['loss'] += 1; break
        _decay(G)
    return _snap(G)
