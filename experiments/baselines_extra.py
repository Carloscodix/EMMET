"""Extra baselines: ECMP (RFC 2992) and DRILL (Ghorbani SIGCOMM'17).
Same source-routing frame as conga_wan_route -> fair comparison."""
import sys, math
sys.path.insert(0, '/home/clopez/emmet/experiments')
import networkx as nx

def ecmp_route(G, src, dst, rng):
    """Random shortest-hop path by walking down the distance gradient."""
    try:
        dist = nx.single_source_shortest_path_length(G, dst)
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return None, 'no_path'
    if src not in dist:
        return None, 'no_path'
    path = [src]; cur = src
    while cur != dst:
        nbrs = [n for n in G.neighbors(cur) if dist.get(n, 1e9) == dist[cur] - 1]
        if not nbrs:
            return None, 'no_path'
        cur = rng.choice(nbrs); path.append(cur)
    return path, 'delivered'

def drill_route(G, src, dst, rng, m=2, budget=1.25):
    """DRILL[m,1]: per-hop local load balancing toward dst."""
    try:
        dist = nx.single_source_shortest_path_length(G, dst)
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return None, 'no_path'
    if src not in dist:
        return None, 'no_path'
    max_hops = math.ceil(budget * dist[src])
    path = [src]; cur = src; visited = {src}; prev_best = None
    while cur != dst and len(path) <= max_hops:
        cand = [n for n in G.neighbors(cur) if n not in visited and dist.get(n,1e9) <= dist[cur]]
        if not cand:
            cand = [n for n in G.neighbors(cur) if n not in visited]
        if not cand:
            return None, 'dead_end'
        sample = cand if len(cand) <= m else rng.sample(cand, m)
        if prev_best in cand and prev_best not in sample:
            sample = sample + [prev_best]
        nxt = min(sample, key=lambda n: G[cur][n]['load']/max(G[cur][n]['capacity'],1))
        prev_best = nxt
        path.append(nxt); visited.add(nxt); cur = nxt
    if cur != dst:
        return None, 'ttl_expired'
    return path, 'delivered'

import random
from bursty_runner import _walk_packet, _decay, _summary
from bursty_traffic import GAP_SENTINEL

def run_bursty_ecmp(G, traf, seed=0):
    rng = random.Random(seed + 5555)
    losses = delivered = nopath = 0; cap_d = cap_l = 0
    for step in traf:
        if step == GAP_SENTINEL:
            _decay(G); continue
        src, dst = step
        if src == dst:
            _decay(G); continue
        path, _ = ecmp_route(G, src, dst, rng)
        if path is None or len(path) < 2:
            nopath += 1; _decay(G); continue
        ok, hops = _walk_packet(G, path)
        if ok: delivered += 1; cap_d += hops
        else: losses += 1; cap_l += hops
        _decay(G)
    return _summary(delivered, losses, nopath, cap_d, cap_l)

def run_bursty_drill(G, traf, seed=0, m=2):
    rng = random.Random(seed + 7777)
    losses = delivered = nopath = 0; cap_d = cap_l = 0
    for step in traf:
        if step == GAP_SENTINEL:
            _decay(G); continue
        src, dst = step
        if src == dst:
            _decay(G); continue
        path, _ = drill_route(G, src, dst, rng, m=m)
        if path is None or len(path) < 2:
            nopath += 1; _decay(G); continue
        ok, hops = _walk_packet(G, path)
        if ok: delivered += 1; cap_d += hops
        else: losses += 1; cap_l += hops
        _decay(G)
    return _summary(delivered, losses, nopath, cap_d, cap_l)
