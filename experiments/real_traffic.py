"""Real GEANT topology + measured demand matrix (SNDlib / Uhlig TOTEM)."""
import sys, random, math
sys.path.insert(0, '/home/clopez/emmet/experiments')
import networkx as nx
from bursty_traffic import GAP_SENTINEL

def parse_sndlib(path):
    nodes, edges, demand = [], [], {}
    section = None
    for line in open(path):
        s = line.strip()
        if s.startswith('NODES ('): section = 'N'; continue
        if s.startswith('LINKS ('): section = 'L'; continue
        if s.startswith('DEMANDS ('): section = 'D'; continue
        if s == ')': section = None; continue
        if not s or s.startswith('#'): continue
        if section == 'N':
            nodes.append(s.split()[0])
        elif section == 'L':
            p = s.split(); edges.append((p[2], p[3]))
        elif section == 'D':
            p = s.split(); demand[(p[2], p[3])] = float(p[-2])
    return nodes, edges, demand

GEANT_PATH = '/home/clopez/emmet/data/real_traffic/sndlib-instances-native/geant/geant.txt'

def build_geant_real(seed, path=GEANT_PATH, cap_lo=3, cap_hi=6):
    """Build GEANT-22 graph with same attr scheme as emmet_budget.build_real.
    Returns (G, idx_demand) where idx_demand maps (i,j) int pairs -> weight."""
    names, edges, demand = parse_sndlib(path)
    idx = {nm: i for i, nm in enumerate(names)}
    G = nx.Graph()
    G.add_nodes_from(range(len(names)))
    for a, b in edges:
        G.add_edge(idx[a], idx[b])
    rng = random.Random(seed)
    for u, v in G.edges():
        G[u][v]['latency'] = rng.uniform(1, 5)
        G[u][v]['capacity'] = rng.randint(cap_lo, cap_hi)
        G[u][v]['load'] = 0
        G[u][v]['loss'] = 0
    idx_demand = {}
    for (a, b), w in demand.items():
        if a in idx and b in idx:
            idx_demand[(idx[a], idx[b])] = w
    return G, idx_demand

def gen_bursty_real(idx_demand, target_steps, seed, burst_hi=8):
    """Like gen_bursty but samples (src,dst) proportional to real demand."""
    pairs = list(idx_demand.keys())
    weights = [idx_demand[p] for p in pairs]
    rng = random.Random(seed)
    out = []
    produced = 0
    while produced < target_steps:
        blen = rng.randint(3, burst_hi)
        for _ in range(blen):
            if produced >= target_steps: break
            s, d = rng.choices(pairs, weights=weights, k=1)[0]
            out.append((s, d)); produced += 1
        glen = rng.randint(1, 3)
        for _ in range(glen):
            if produced >= target_steps: break
            out.append(GAP_SENTINEL); produced += 1
    return out
