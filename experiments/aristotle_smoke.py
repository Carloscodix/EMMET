"""
aristotle_smoke.py - minimal conceptual test of the toothed-wheel idea.

QUESTION (the ghost test): is "gear-mesh waste" a real, distinct lever for
routing, or does it collapse into ordinary congestion?

SETUP
- Graph with HETEROGENEOUS per-edge quantum Q(e) (the tooth pitch / MTU).
- Packets with VARIABLE size S.
- A packet of size S crossing an edge of quantum Q occupies ceil(S/Q)*Q of the
  edge's capacity. The padding ceil(S/Q)*Q - S is wasted capacity: it carries no
  payload but still consumes the link. Bad mesh -> link saturates sooner.

ROUTERS COMPARED (same hop-budget DP engine, only the per-edge cost differs)
  shortest    : cost = latency only (ignores everything)
  congestion  : cost = latency + beta * load/capacity   (the ghost: classic
                congestion, blind to packet size / quantum)
  aristotle   : cost = latency + beta * load/capacity + gamma * padding(S,Q)
                (adds the gear-mesh term: per-(packet,edge), size-aware)

AUDIT BUILT IN
- If aristotle ~ congestion on every metric, the mesh term is a ghost -> bury it.
- aristotle earns its keep ONLY if it beats congestion on wasted-capacity AND
  that buys fewer drops. Both, or it's noise.
"""
import math, random
import numpy as np
import networkx as nx

BETA = 3.0
GAMMA = 3.0
ALPHA_BUDGET = 1.25
# quantum menu: links come in a few "tooth pitches"
QUANTA = [4, 8, 16, 64]          # heterogeneous, spread an order of magnitude
SIZES  = [5, 12, 30, 50, 100]    # packet sizes, deliberately NOT multiples of all Q


def build_graph(n, seed):
    rng = random.Random(seed)
    G = nx.connected_watts_strogatz_graph(n, 4, 0.3, seed=seed)
    for u, v in G.edges():
        G[u][v]['latency']  = rng.uniform(1, 5)
        G[u][v]['quantum']  = rng.choice(QUANTA)     # the tooth pitch
        G[u][v]['capacity'] = rng.choice([240, 480]) # capacity in payload units
        G[u][v]['load']     = 0.0
    return G


def padding(S, Q):
    """Wasted capacity when a packet of size S crosses a link of quantum Q."""
    return math.ceil(S / Q) * Q - S


def occupied(S, Q):
    """Total capacity the packet consumes on the link (payload + padding)."""
    return math.ceil(S / Q) * Q


def edge_cost(G, u, v, S, mode):
    e = G[u][v]
    base = e['latency']
    if mode == 'shortest':
        return base
    cong = BETA * (e['load'] / e['capacity'])
    if mode == 'congestion':
        return base + cong
    if mode == 'aristotle':
        pad = GAMMA * (padding(S, e['quantum']) / e['quantum'])  # normalized mesh waste
        return base + cong + pad
    raise ValueError(mode)


def route(G, src, dst, S, mode, budget=ALPHA_BUDGET):
    if src == dst:
        return [src]
    try:
        sp = nx.shortest_path_length(G, src, dst)
    except nx.NetworkXNoPath:
        return None
    k = max(sp, math.ceil(budget * sp))
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
                c = f[h-1][u] + edge_cost(G, u, v, S, mode)
                if c < best:
                    best, bu = c, u
            f[h][v] = best; par[h][v] = bu
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
    path.reverse(); return path


def simulate(G, demand, mode, decay=0.9):
    for u, v in G.edges():
        G[u][v]['load'] = 0.0
    delivered = drops = 0
    wasted = 0.0           # total padding capacity burned
    payload = 0.0          # total payload moved
    for (src, dst, S) in demand:
        p = route(G, src, dst, S, mode)
        if not p or len(p) < 2:
            drops += 1; continue
        lost = False
        for i in range(len(p) - 1):
            e = G[p[i]][p[i+1]]
            occ = occupied(S, e['quantum'])
            e['load'] += occ
            if e['load'] > e['capacity']:
                drops += 1; lost = True; break
            wasted += padding(S, e['quantum'])
        if not lost:
            delivered += 1; payload += S
        for u, v in G.edges():
            G[u][v]['load'] *= decay
    total = delivered + drops
    return {
        'drop_rate': drops / total if total else 0.0,
        'waste_frac': wasted / (wasted + payload) if (wasted + payload) else 0.0,
        'delivered': delivered,
    }


def gen_demand(G, n_pkts, seed):
    rng = random.Random(seed + 7000)
    nodes = list(G.nodes())
    dem = []
    for _ in range(n_pkts):
        a, b = rng.sample(nodes, 2)
        dem.append((a, b, rng.choice(SIZES)))
    return dem


if __name__ == '__main__':
    print(f"{'seed':>4} | {'mode':>10} | drop_rate  waste_frac  delivered")
    print('-' * 56)
    agg = {m: {'drop': [], 'waste': []} for m in ('shortest', 'congestion', 'aristotle')}
    for seed in range(8):
        G = build_graph(30, seed)
        dem = gen_demand(G, 300, seed)
        for mode in ('shortest', 'congestion', 'aristotle'):
            r = simulate(G, dem, mode)
            agg[mode]['drop'].append(r['drop_rate'])
            agg[mode]['waste'].append(r['waste_frac'])
            print(f"{seed:>4} | {mode:>10} | {r['drop_rate']:.4f}     {r['waste_frac']:.4f}      {r['delivered']}")
        print('-' * 56)
    print("\n=== MEANS over 8 seeds ===")
    print(f"{'mode':>10} | {'drop_rate':>10} | {'waste_frac':>10}")
    for m in ('shortest', 'congestion', 'aristotle'):
        print(f"{m:>10} | {np.mean(agg[m]['drop']):>10.4f} | {np.mean(agg[m]['waste']):>10.4f}")
    print("\n=== GHOST CHECK: aristotle vs congestion ===")
    dd = np.mean(agg['congestion']['drop']) - np.mean(agg['aristotle']['drop'])
    dw = np.mean(agg['congestion']['waste']) - np.mean(agg['aristotle']['waste'])
    print(f"drop reduction  (congestion - aristotle): {dd:+.4f}")
    print(f"waste reduction (congestion - aristotle): {dw:+.4f}")
    if dw > 0.005 and dd > 0.002:
        print("-> aristotle cuts BOTH waste and drops: real, distinct lever. Worth the full bench.")
    elif dw > 0.005 and dd <= 0.002:
        print("-> aristotle cuts waste but NOT drops: real mechanism, no payoff (honest negative).")
    else:
        print("-> aristotle ~ congestion: GHOST. mesh term collapses into congestion. Bury it.")
