"""Honest Bloom test: track ALL outcomes, not just losses."""
import random, statistics, math, json, hashlib
from pathlib import Path
from multiprocessing import Pool, cpu_count
import networkx as nx

REPO = Path(__file__).resolve().parents[1]
TOPO = REPO / 'data' / 'topologies'

TRAFFIC_STEPS = 200
ALPHA, BETA, GAMMA = 1.0, 3.0, 2.0
TTL_FACTOR = 1
THETA, HALF_LIFE, EPSILON = 5.0, 500, 0.10
DECAY = math.exp(-math.log(2)/HALF_LIFE)

class Bloom:
    def __init__(self, sz, k):
        self.size, self.k, self.bits = sz, k, 0
    def _h(self, x):
        d = hashlib.md5(str(x).encode()).digest()
        return [int.from_bytes(d[i:i+4],'big')%self.size for i in range(0,4*self.k,4)]
    def add(self, x):
        for i in self._h(x): self.bits |= (1<<i)
    def __contains__(self, x):
        for i in self._h(x):
            if not (self.bits>>i)&1: return False
        return True

def build_syn(n, p, seed):
    rng = random.Random(seed)
    G = nx.erdos_renyi_graph(n, p, seed=seed)
    for u,v in G.edges():
        G[u][v]['latency'] = rng.uniform(1,5)
        G[u][v]['capacity'] = rng.randint(3,6)
        G[u][v]['load'] = 0
        G[u][v]['loss'] = 0
    return G

def build_real(fn, seed):
    G = nx.read_graphml(str(TOPO/fn))
    G = nx.Graph(G)
    G = nx.relabel_nodes(G, {n:i for i,n in enumerate(G.nodes())})
    rng = random.Random(seed)
    for u,v in G.edges():
        G[u][v]['latency'] = rng.uniform(1,5)
        G[u][v]['capacity'] = rng.randint(3,6)
        G[u][v]['load'] = 0
        G[u][v]['loss'] = 0
    return G

def reset(G):
    for u,v in G.edges():
        G[u][v]['load'] = 0
        G[u][v]['loss'] = 0

def gen_traf(nodes, steps, seed):
    rng = random.Random(seed)
    return [(rng.choice(nodes), rng.choice(nodes)) for _ in range(steps)]

def potential(G, cur, nb, dst, snap, beta_eff):
    e = G[cur][nb]
    cong = e['load']/e['capacity']
    k = tuple(sorted([cur,nb]))
    lv = snap.get(k, 0)
    try: d = nx.shortest_path_length(G, nb, dst, weight='latency')
    except nx.NetworkXNoPath: d = 999
    return ALPHA*d + beta_eff*cong + GAMMA*lv

def emmet(G, src, dst, snap, eps_rng, vis_factory):
    n_e = G.number_of_edges()
    temp = sum(G[u][v]['load']/G[u][v]['capacity'] for u,v in G.edges())/n_e if n_e else 0
    beta_eff = BETA*(1+THETA*temp)
    max_hops = TTL_FACTOR*G.number_of_nodes()
    vis = vis_factory()
    path, cur, hops = [src], src, 0
    while cur != dst and hops < max_hops:
        vis.add(cur)
        nbrs = [n for n in G.neighbors(cur) if n not in vis]
        if not nbrs:
            return None, 'dead_end', path
        ranked = sorted(nbrs, key=lambda n: potential(G,cur,n,dst,snap,beta_eff))
        if eps_rng and len(ranked)>1 and eps_rng.random()<EPSILON:
            cur = ranked[1]
        else:
            cur = ranked[0]
        path.append(cur)
        hops += 1
    return (path, 'delivered', path) if cur==dst else (None, 'ttl', path)

def warmup(G, traf, vis_factory):
    snap = {}
    for src, dst in traf:
        if src == dst: continue
        path, _, _ = emmet(G, src, dst, snap, None, vis_factory)
        if path is None: continue
        for i in range(len(path)-1):
            u,v = path[i], path[i+1]
            e = G[u][v]
            e['load'] += 1
            if e['load'] > e['capacity']:
                e['loss'] += 1
                break
        for u,v in G.edges():
            G[u][v]['load'] *= 0.9
    return {tuple(sorted([u,v])): G[u][v]['loss'] for u,v in G.edges()}

def simulate(G, traffic, snap, eps_rng, vis_factory):
    snap_l = dict(snap)
    losses = delivered = dead = ttl = 0
    total_lat = 0.0
    for src, dst in traffic:
        if src == dst: continue
        path, reason, _ = emmet(G, src, dst, snap_l, eps_rng, vis_factory)
        if path is None:
            if reason == 'dead_end': dead += 1
            else: ttl += 1
            continue
        lost = False
        for i in range(len(path)-1):
            u,v = path[i], path[i+1]
            e = G[u][v]
            e['load'] += 1
            if e['load'] > e['capacity']:
                e['loss'] += 1
                losses += 1
                lost = True
                break
            total_lat += e['latency']
        if not lost:
            delivered += 1
        for u,v in G.edges():
            G[u][v]['load'] *= 0.9
        for k in list(snap_l.keys()):
            snap_l[k] *= DECAY
    return {'losses': losses, 'delivered': delivered, 'dead': dead, 'ttl': ttl,
            'lat': total_lat/delivered if delivered else 0}

def run_one(args):
    label, builder, bargs, seed, variant = args
    G = builder(*bargs, seed=seed)
    n = G.number_of_nodes()
    ws = max(20, n*5)
    if variant == 'set':
        vf = lambda: set()
    else:
        sz, k = variant
        vf = lambda: Bloom(sz, k)
    G = builder(*bargs, seed=seed); reset(G)
    wt = gen_traf(list(G.nodes()), ws, seed+300000)
    snap = warmup(G, wt, vf)
    G2 = builder(*bargs, seed=seed); reset(G2)
    traf = gen_traf(list(G2.nodes()), TRAFFIC_STEPS, seed+100000)
    res = simulate(G2, traf, snap, random.Random(seed+400000), vf)
    return {'label': label, 'seed': seed, 'variant': str(variant), **res}

if __name__ == '__main__':
    scenarios = [
        ('ER_n20_p0.10', build_syn, (20, 0.10), 100),
        ('ER_n50_p0.05', build_syn, (50, 0.05), 100),
        ('ER_n50_p0.10', build_syn, (50, 0.10), 100),
        ('Abilene', build_real, ('Abilene.graphml',), 100),
        ('GEANT', build_real, ('Geant.graphml',), 100),
    ]
    variants = [
        'set',
        (32, 2), (64, 2), (96, 3), (128, 3), (192, 3), (256, 3), (512, 4),
    ]
    jobs = []
    for sn, b, ba, ns in scenarios:
        for v in variants:
            for s in range(ns):
                jobs.append((sn, b, ba, s, v))
    print(f'Honest Bloom: {len(jobs)} jobs')
    with Pool(max(1, cpu_count()-4)) as p:
        results = p.map(run_one, jobs)

    by = {}
    for r in results:
        by.setdefault((r['label'], r['variant']), []).append(r)

    print()
    print(f"{'Scenario':<16} {'Variant':>10} {'Loss':>7} {'Deliv':>7} {'Dead':>7} {'TTL':>5} {'Total':>7} {'%aborted':>9}")
    out = []
    for (sc, var), runs in sorted(by.items()):
        L = statistics.mean(r['losses'] for r in runs)
        D = statistics.mean(r['delivered'] for r in runs)
        DE = statistics.mean(r['dead'] for r in runs)
        T = statistics.mean(r['ttl'] for r in runs)
        total = L + D + DE + T
        aborted_pct = (DE + T) / total * 100 if total > 0 else 0
        print(f"{sc:<16} {var:>10} {L:>7.2f} {D:>7.1f} {DE:>7.1f} {T:>5.1f} {total:>7.1f} {aborted_pct:>8.1f}%")
        out.append({'scenario': sc, 'variant': var, 'losses': L, 'delivered': D,
                    'dead': DE, 'ttl': T, 'aborted_pct': aborted_pct})

    with open(REPO/'data'/'bloom_honest.json', 'w') as f:
        json.dump(out, f, indent=2)
    print('\nSaved bloom_honest.json')
