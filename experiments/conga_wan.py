"""CONGA-WAN: a CONGA-style multi-path congestion-aware load balancer.

Adapts Cisco's CONGA (SIGCOMM 2014) from datacenter CLOS to WAN.
We borrow only the structural form (multi-path + congestion-aware
selection). Per packet:
  1. K-shortest simple paths from src to dst (latency-weighted).
  2. Estimate path congestion = mean(load/capacity) across its edges.
  3. Pick min congestion. Tie-break: shortest latency.

This is the strongest stateless multi-path baseline using the same
observable congestion signal as LASP-aug and EMMET-DP.
"""
import sys
import networkx as nx
from itertools import islice

sys.path.insert(0, '/home/clopez/emmet/experiments')

K_PATHS = 4

def k_shortest_paths(G, src, dst, k=K_PATHS, weight='latency'):
    try:
        gen = nx.shortest_simple_paths(G, src, dst, weight=weight)
        return list(islice(gen, k))
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return []

def path_congestion(G, path):
    if len(path) < 2:
        return 0.0
    s = 0.0; n = 0
    for i in range(len(path) - 1):
        u, v = path[i], path[i + 1]
        e = G[u][v]
        s += e['load'] / max(e['capacity'], 1); n += 1
    return s / n if n else 0.0

def path_latency(G, path):
    if len(path) < 2:
        return 0.0
    return sum(G[path[i]][path[i+1]]['latency'] for i in range(len(path)-1))

def conga_wan_route(G, src, dst, k=K_PATHS):
    """Pick the min-congestion path among K-shortest candidates."""
    paths = k_shortest_paths(G, src, dst, k=k)
    if not paths:
        return None, 'no_path'
    if len(paths) == 1:
        return paths[0], 'delivered'
    # Score by (congestion, latency) — lex order: min congestion wins,
    # ties broken by shorter latency
    best = min(paths, key=lambda p: (path_congestion(G, p), path_latency(G, p)))
    return best, 'delivered'

def warmup_conga(G, traf, k=K_PATHS):
    """Warmup run identical in structure to warmup_lasp_aug."""
    for src, dst in traf:
        if src == dst: continue
        path, _ = conga_wan_route(G, src, dst, k=k)
        if path is None or len(path) < 2: continue
        for i in range(len(path)-1):
            u, v = path[i], path[i+1]
            e = G[u][v]
            e['load'] += 1
            if e['load'] > e['capacity']:
                e['loss'] += 1
                break
        for u, v in G.edges():
            G[u][v]['load'] *= 0.9
    return {tuple(sorted([u,v])): G[u][v]['loss'] for u,v in G.edges()}

def simulate_conga(G, traffic, snap=None, k=K_PATHS):
    losses = delivered = nopath = 0
    cap_d = 0
    cap_l = 0
    for src, dst in traffic:
        if src == dst: continue
        path, _ = conga_wan_route(G, src, dst, k=k)
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
    return _summarize(delivered, losses, nopath, cap_d, cap_l)

def _summarize(delivered, losses, nopath, cap_d, cap_l):
    attempted = delivered + losses + nopath
    routed = delivered + losses
    total_cap = cap_d + cap_l
    return {
        'delivered': delivered, 'losses': losses, 'nopath': nopath,
        'delivery_rate': delivered/attempted*100 if attempted else 0,
        'cap_per_delivery': cap_d/delivered if delivered else 0,
        'cap_per_attempt': total_cap/attempted if attempted else 0,
        'cap_per_routed_attempt': total_cap/routed if routed else 0,
        'cap_consumed_lost': cap_l,
    }
