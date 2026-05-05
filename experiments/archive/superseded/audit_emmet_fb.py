"""Pre-Codex audit of EMMET-fb. Three suspicions:

1. Auto-congestion: EMMET-fb consumes more capacity per delivered packet
   than SP/LASP because the EMMET prefix wastes hops before the SP tail.
2. Fallback frequency: how often does the field "fail" the algorithm?
3. Loss attribution: are losses on the SP tail counted against EMMET?

To answer these I need per-packet hop counts. The current raw data only
has aggregates. So I'll instrument a focused re-run on representative
scenarios and compute the metrics that Codex would ask for.
"""
import random, statistics, math, json, hashlib
from pathlib import Path
from multiprocessing import Pool, cpu_count
import networkx as nx

REPO = Path(__file__).resolve().parents[1]
TOPO = REPO / 'data' / 'topologies'
DATA = REPO / 'data'

TRAFFIC_STEPS = 200
ALPHA, BETA, GAMMA = 1.0, 3.0, 2.0
TTL_FACTOR = 1
THETA, HALF_LIFE, EPSILON = 5.0, 500, 0.10
DECAY = math.exp(-math.log(2) / HALF_LIFE)
BLOOM_SIZE, BLOOM_K, EWMA = 128, 3, 0.10

class Bloom:
    def __init__(self, sz, k):
        self.size, self.k, self.bits = sz, k, 0
    def _h(self, x):
        d = hashlib.md5(str(x).encode()).digest()
        return [int.from_bytes(d[i:i+4], 'big') % self.size for i in range(0, 4*self.k, 4)]
    def add(self, x):
        for i in self._h(x): self.bits |= (1 << i)
    def __contains__(self, x):
        for i in self._h(x):
            if not (self.bits >> i) & 1: return False
        return True

def build_syn(n, p, seed):
    rng = random.Random(seed)
    G = nx.erdos_renyi_graph(n, p, seed=seed)
    for u, v in G.edges():
        G[u][v]['latency'] = rng.uniform(1, 5)
        G[u][v]['capacity'] = rng.randint(3, 6)
        G[u][v]['load'] = 0
        G[u][v]['loss'] = 0
    return G

def build_real(fn, seed):
    G = nx.read_graphml(str(TOPO / fn))
    G = nx.Graph(G)
    G = nx.relabel_nodes(G, {n: i for i, n in enumerate(G.nodes())})
    rng = random.Random(seed)
    for u, v in G.edges():
        G[u][v]['latency'] = rng.uniform(1, 5)
        G[u][v]['capacity'] = rng.randint(3, 6)
        G[u][v]['load'] = 0
        G[u][v]['loss'] = 0
    return G

def reset(G):
    for u, v in G.edges():
        G[u][v]['load'] = 0
        G[u][v]['loss'] = 0

def gen_traf(nodes, steps, seed):
    rng = random.Random(seed)
    return [(rng.choice(nodes), rng.choice(nodes)) for _ in range(steps)]

def potential(G, cur, nb, dst, snap, beta_eff):
    e = G[cur][nb]
    cong = e['load'] / e['capacity']
    k = tuple(sorted([cur, nb]))
    lv = snap.get(k, 0)
    try: d = nx.shortest_path_length(G, nb, dst, weight='latency')
    except nx.NetworkXNoPath: d = 999
    return ALPHA * d + beta_eff * cong + GAMMA * lv

def emmet_fb(G, src, dst, snap, eps_rng):
    n_e = G.number_of_edges()
    temp = sum(G[u][v]['load']/G[u][v]['capacity'] for u,v in G.edges())/n_e if n_e else 0
    beta_eff = BETA * (1 + THETA * temp)
    max_hops = TTL_FACTOR * G.number_of_nodes()
    vis = Bloom(BLOOM_SIZE, BLOOM_K)
    path, cur, hops = [src], src, 0
    fb_triggered_at = None
    while cur != dst and hops < max_hops:
        vis.add(cur)
        nbrs = [n for n in G.neighbors(cur) if n not in vis]
        if not nbrs:
            try: tail = nx.shortest_path(G, cur, dst, weight='latency')
            except nx.NetworkXNoPath: return None, 'no_path', None, len(path)-1
            fb_triggered_at = len(path) - 1  # hops before fallback
            path.extend(tail[1:])
            return path, 'fallback', fb_triggered_at, len(path)-1
        ranked = sorted(nbrs, key=lambda n: potential(G, cur, n, dst, snap, beta_eff))
        if eps_rng and len(ranked) > 1 and eps_rng.random() < EPSILON:
            cur = ranked[1]
        else:
            cur = ranked[0]
        path.append(cur)
        hops += 1
    if cur == dst:
        return path, 'delivered', None, hops
    # TTL also falls back
    try: tail = nx.shortest_path(G, cur, dst, weight='latency')
    except nx.NetworkXNoPath: return None, 'no_path', None, hops
    fb_triggered_at = hops
    path.extend(tail[1:])
    return path, 'fallback', fb_triggered_at, len(path)-1

def warmup(G, traf):
    snap = {}
    for src, dst in traf:
        if src == dst: continue
        path, _, _, _ = emmet_fb(G, src, dst, snap, None)
        if path is None: continue
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

def simulate_emmet_instrumented(G, traffic, snap, eps_rng):
    """Returns per-packet detail to compute capacity-per-delivery, etc."""
    snap_l = dict(snap)
    pkts = []
    for src, dst in traffic:
        if src == dst: continue
        path, reason, fb_at, total_hops = emmet_fb(G, src, dst, snap_l, eps_rng)
        if path is None:
            pkts.append({'reason': 'no_path', 'hops_consumed': 0,
                         'used_fallback': False, 'lost_in_prefix': False,
                         'lost_in_tail': False, 'delivered': False})
            continue
        # Walk path edge by edge
        used_fb = (reason == 'fallback')
        lost = False
        lost_in_prefix = False
        lost_in_tail = False
        capacity_consumed = 0
        for i in range(len(path)-1):
            u, v = path[i], path[i+1]
            e = G[u][v]
            e['load'] += 1
            capacity_consumed += 1
            if e['load'] > e['capacity']:
                e['loss'] += 1
                lost = True
                # Was this loss in the EMMET prefix or in the SP tail?
                if used_fb and fb_at is not None and i >= fb_at:
                    lost_in_tail = True
                else:
                    lost_in_prefix = True
                break
        pkts.append({
            'reason': reason if not lost else 'congestion_loss',
            'hops_consumed': capacity_consumed,
            'used_fallback': used_fb,
            'fb_prefix_hops': fb_at if used_fb else None,
            'lost_in_prefix': lost_in_prefix,
            'lost_in_tail': lost_in_tail,
            'delivered': not lost,
        })
        for u, v in G.edges():
            G[u][v]['load'] *= 0.9
        for k in list(snap_l.keys()):
            snap_l[k] *= DECAY
    return pkts

def simulate_sp_instrumented(G, traffic):
    pkts = []
    for src, dst in traffic:
        if src == dst: continue
        try: path = nx.shortest_path(G, src, dst, weight='latency')
        except nx.NetworkXNoPath:
            pkts.append({'delivered': False, 'hops_consumed': 0, 'reason': 'no_path'})
            continue
        lost = False
        cap = 0
        for i in range(len(path)-1):
            u, v = path[i], path[i+1]
            e = G[u][v]
            e['load'] += 1
            cap += 1
            if e['load'] > e['capacity']:
                e['loss'] += 1
                lost = True
                break
        pkts.append({'delivered': not lost, 'hops_consumed': cap,
                     'reason': 'delivered' if not lost else 'congestion_loss'})
        for u, v in G.edges():
            G[u][v]['load'] *= 0.9
    return pkts

def simulate_lasp_instrumented(G, traffic):
    pkts = []
    for src, dst in traffic:
        if src == dst: continue
        def w(u, v, d): return d['latency'] * (1 + d['load']/d['capacity'])
        try: path = nx.shortest_path(G, src, dst, weight=w)
        except nx.NetworkXNoPath:
            pkts.append({'delivered': False, 'hops_consumed': 0, 'reason': 'no_path'})
            continue
        lost = False
        cap = 0
        for i in range(len(path)-1):
            u, v = path[i], path[i+1]
            e = G[u][v]
            e['load'] += 1
            cap += 1
            if e['load'] > e['capacity']:
                e['loss'] += 1
                lost = True
                break
        pkts.append({'delivered': not lost, 'hops_consumed': cap,
                     'reason': 'delivered' if not lost else 'congestion_loss'})
        for u, v in G.edges():
            G[u][v]['load'] *= 0.9
    return pkts

def run_one(args):
    label, builder, bargs, seed = args
    G = builder(*bargs, seed=seed); reset(G)
    n = G.number_of_nodes()
    ws = max(20, n*5)
    traf = gen_traf(list(G.nodes()), TRAFFIC_STEPS, seed + 100000)

    # SP
    G_sp = builder(*bargs, seed=seed); reset(G_sp)
    sp_pkts = simulate_sp_instrumented(G_sp, traf)

    # LASP
    G_la = builder(*bargs, seed=seed); reset(G_la)
    la_pkts = simulate_lasp_instrumented(G_la, traf)

    # EMMET-fb
    G_w = builder(*bargs, seed=seed); reset(G_w)
    wt = gen_traf(list(G_w.nodes()), ws, seed + 300000)
    snap = warmup(G_w, wt)
    G_em = builder(*bargs, seed=seed); reset(G_em)
    em_pkts = simulate_emmet_instrumented(G_em, traf, snap, random.Random(seed + 400000))

    return {'scenario': label, 'seed': seed, 'sp': sp_pkts, 'lasp': la_pkts, 'em': em_pkts}

def analyze(results):
    by_scen = {}
    for r in results:
        by_scen.setdefault(r['scenario'], []).append(r)
    print()
    print(f"{'Scenario':<18} {'Strategy':<12} {'Deliv':>6} {'Loss':>5} {'Cap/del':>8} "
          f"{'FB%':>6} {'Loss in tail':>14}")
    print('-' * 80)
    out = []
    for sc, runs in sorted(by_scen.items()):
        for strat in ['sp', 'lasp', 'em']:
            all_pkts = []
            for r in runs:
                all_pkts.extend(r[strat])
            n_deliv = sum(1 for p in all_pkts if p['delivered'])
            n_loss = sum(1 for p in all_pkts if p.get('reason') == 'congestion_loss')
            cap_total = sum(p['hops_consumed'] for p in all_pkts if p['delivered'])
            cap_per_del = cap_total / n_deliv if n_deliv else 0
            n_fb = sum(1 for p in all_pkts if p.get('used_fallback', False))
            fb_pct = n_fb / len(all_pkts) * 100 if all_pkts else 0
            n_loss_tail = sum(1 for p in all_pkts if p.get('lost_in_tail', False))
            loss_tail_pct = n_loss_tail / n_loss * 100 if n_loss else 0
            print(f"{sc:<18} {strat:<12} {n_deliv:>6} {n_loss:>5} "
                  f"{cap_per_del:>8.2f} {fb_pct:>5.1f}% {loss_tail_pct:>13.1f}%")
            out.append({
                'scenario': sc, 'strategy': strat,
                'delivered': n_deliv, 'losses': n_loss,
                'capacity_per_delivery': cap_per_del,
                'fallback_pct': fb_pct,
                'losses_in_tail_pct': loss_tail_pct,
            })
    return out

if __name__ == '__main__':
    scenarios = [
        ('ER_n20_p0.20', build_syn, (20, 0.20), 100),
        ('ER_n20_p0.30', build_syn, (20, 0.30), 100),
        ('ER_n50_p0.10', build_syn, (50, 0.10), 100),
        ('ER_n50_p0.05', build_syn, (50, 0.05), 100),
        ('Abilene', build_real, ('Abilene.graphml',), 100),
        ('GEANT', build_real, ('Geant.graphml',), 100),
    ]
    jobs = []
    for sn, b, ba, ns in scenarios:
        for s in range(ns):
            jobs.append((sn, b, ba, s))
    print(f'Pre-Codex audit of EMMET-fb: {len(jobs)} jobs')
    with Pool(max(1, cpu_count()-4)) as p:
        results = p.map(run_one, jobs)
    out = analyze(results)
    with open(DATA / 'audit_emmet_fb.json', 'w') as f:
        json.dump(out, f, indent=2)
    print('\nSaved audit_emmet_fb.json')
