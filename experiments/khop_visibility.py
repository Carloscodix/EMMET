"""khop_visibility.py - the spatial axis of rock #1 (the last one with teeth).
The deciding node sees REAL load only on edges within k hops of itself;
beyond the horizon it sees load 0 (pure static gradient). k=0 is the blind
router (static shortest-potential); k=INF is the global view. The question:
how much VISION does the physics need to recover the congestion-aware gap?
PRE-REGISTERED (cautious, after the staleness lesson):
 (a) monotone improvement with k, no resonance;
 (b) k=2 recovers >=50% of the blind->global gap; k=3 recovers >=66%;
 (c) topologies with longer mean shortest paths suffer more at small k.
"""
import sys, json
import numpy as np
from scipy import stats
import networkx as nx
sys.path.insert(0, '/home/clopez/emmet/experiments')
import flowsim as FS
import physics_cores as PC
from equivalence import TOPOS, build_topo
from emmet_budget import reset

K_VALUES = [0, 1, 2, 3, 99]   # 99 = global view
N_SEEDS = 6


def simulate_khop(G, sched, n_ticks, route_fn, k, hops):
    flows = []
    served = drop = 0
    keys = [tuple(sorted(e)) for e in G.edges()]
    real = {kk: 0.0 for kk in keys}
    state = {'scars': {}}
    for t in range(n_ticks):
        for (s, d, dur, rate) in sched.get(t, []):
            # build this decider's view: real load within k hops, 0 beyond
            if k >= 99:
                for u, v in G.edges():
                    G[u][v]['load'] = real[tuple(sorted((u, v)))]
            else:
                hs = hops[s]
                for u, v in G.edges():
                    vis = min(hs.get(u, 99), hs.get(v, 99)) <= k
                    G[u][v]['load'] = real[tuple(sorted((u, v)))] if vis else 0.0
            path = route_fn(G, s, d, state)
            if path and len(path) >= 2:
                flows.append({'rate': rate, 'ttl': dur, 'route': path})
        FS._apply_flow_load(G, flows)
        for u, v in G.edges():
            real[tuple(sorted((u, v)))] = G[u][v]['load']
        for fl in flows:
            r = fl['route']; lost = False
            for i in range(len(r) - 1):
                if G[r[i]][r[i+1]]['load'] > G[r[i]][r[i+1]]['capacity']:
                    lost = True; break
            if lost:
                drop += 1
            else:
                served += 1
        for fl in flows:
            fl['ttl'] -= 1
        flows = [fl for fl in flows if fl['ttl'] > 0]
    total = served + drop
    return drop / total if total else 0.0


pol = PC.make_physics_policy('archimedes')
rows = []
print(f"{'topo':<11}" + ''.join(f"{'k='+str(k) if k<99 else 'global':>9}" for k in K_VALUES))
for t in TOPOS:
    name, builder, dsrc = t
    res = {k: [] for k in K_VALUES}
    for s in range(N_SEEDS):
        G0, dem = build_topo(name, builder, dsrc, s)
        sched = FS.gen_flows(dem, 200, s + 9000, birth_rate=0.8,
                             dur_lo=4, dur_hi=12, rate=1)
        hops = dict(nx.all_pairs_shortest_path_length(G0))
        for k in K_VALUES:
            G, _ = build_topo(name, builder, dsrc, s); reset(G)
            res[k].append(simulate_khop(G, sched, 200, pol, k, hops))
    row = {'topo': name,
           'mean_sp_hops': float(np.mean([np.mean(list(h.values())) for h in hops.values()]))}
    for k in K_VALUES:
        row[f'drop_k{k}'] = float(np.mean(res[k]))
        row[f'drop_k{k}_seeds'] = [float(x) for x in res[k]]
    rows.append(row)
    print(f"{name:<11}" + ''.join(f"{row[f'drop_k{k}']:>9.4f}" for k in K_VALUES))

json.dump(rows, open('/home/clopez/emmet/data/khop_visibility.json', 'w'), indent=2)

blind = np.array([x for r in rows for x in r['drop_k0_seeds']])
glob = np.array([x for r in rows for x in r['drop_k99_seeds']])
gap = blind.mean() - glob.mean()
print('\n=== pooled: how much vision does the physics need? ===')
print(f"blind (k=0) mean drop : {blind.mean():.4f}")
print(f"global view mean drop : {glob.mean():.4f}")
print(f"blind->global gap     : {gap*100:.2f}pp")
print(f"\n{'k':>7}{'mean_drop':>11}{'vs global pp':>14}{'gap recovered':>15}{'wilcoxon_p':>12}")
for k in K_VALUES:
    d = np.array([x for r in rows for x in r[f'drop_k{k}_seeds']])
    rec = (blind.mean() - d.mean()) / gap * 100 if gap > 0 else 0.0
    try:
        _, p = stats.wilcoxon(d - glob)
    except ValueError:
        p = 1.0
    lab = str(k) if k < 99 else 'global'
    print(f"{lab:>7}{d.mean():>11.4f}{(d.mean()-glob.mean())*100:>+14.2f}{rec:>14.1f}%{p:>12.1e}")

print('\n=== VERDICT vs pre-registered ===')
d2 = np.array([x for r in rows for x in r['drop_k2_seeds']])
d3 = np.array([x for r in rows for x in r['drop_k3_seeds']])
r2 = (blind.mean() - d2.mean()) / gap * 100 if gap > 0 else 0
r3 = (blind.mean() - d3.mean()) / gap * 100 if gap > 0 else 0
print(f"k=2 recovers {r2:.0f}% (pre-commit >=50%): {'HIT' if r2 >= 50 else 'MISS'}")
print(f"k=3 recovers {r3:.0f}% (pre-commit >=66%): {'HIT' if r3 >= 66 else 'MISS'}")
