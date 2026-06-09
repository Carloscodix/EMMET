"""
causal_capacity_sweep.py - the INTERVENTIONAL experiment.

Everything so far is correlational ACROSS heterogeneous topologies. This holds
the topology FIXED and turns the congestion knob: scale every edge capacity by
a factor f, and measure how inter-core divergence responds. Same graph, same
demand, same seeds - only the pressure changes. If divergence tracks drop rate
within each topology, congestion is established as the CAUSE of mechanism
divergence, not a correlate.

PRE-COMMITTED PREDICTIONS (falsifiable):
  1. Within every topology, divergence rises monotonically as capacity shrinks.
  2. BA_n50_m2 (converged today, near-zero drops) DIVERGES once squeezed.
  3. GEANT (divergent today, high drops) CONVERGES once relieved (f=1.5).
If any of these fail, the congestion mechanism is wrong and we say so.

4 topologies x 6 capacity factors x 3 seeds x 3 cores. Newton scar fed.
Saves data/causal_sweep.json.
"""
import sys, json
import numpy as np
from scipy import stats
sys.path.insert(0, '/home/clopez/emmet/experiments')
import flowsim as FS
import physics_cores as PC
from equivalence import TOPOS, build_topo
from emmet_budget import reset

PHYS = ['newton', 'archimedes', 'pascal']
SWEEP = [1.5, 1.2, 1.0, 0.8, 0.6, 0.45]
TARGETS = ['Grid8', 'BA_n50_m2', 'WS_n50_k6', 'GEANT']
N_SEEDS = 3


def cosd(a, b):
    ks = list(a.keys())
    x = np.array([a[k] for k in ks], float); y = np.array([b[k] for k in ks], float)
    nx_, ny_ = np.linalg.norm(x), np.linalg.norm(y)
    return float(np.dot(x, y) / (nx_ * ny_)) if nx_ > 0 and ny_ > 0 else float('nan')


rows = []
print(f"{'topo':<11}{'f':>5}{'drop':>9}{'divergence':>12}")
print('-' * 38)
for tn in TARGETS:
    t = [x for x in TOPOS if x[0] == tn][0]
    name, builder, dsrc = t
    for f in SWEEP:
        divs, drops = [], []
        for s in range(N_SEEDS):
            G0, dem = build_topo(name, builder, dsrc, s)
            sched = FS.gen_flows(dem, 200, s + 9000, birth_rate=0.8,
                                 dur_lo=4, dur_hi=12, rate=1)
            util = {}; dr = []
            for c in PHYS:
                G, _ = build_topo(name, builder, dsrc, s)
                for u, v in G.edges():
                    G[u][v]['capacity'] = G[u][v]['capacity'] * f
                reset(G)
                r = FS.simulate_flows_util(G, sched, 200,
                                           PC.make_physics_policy(c), feed_scar=True)
                util[c] = r['util']; dr.append(r['drop_rate'])
            pp = np.mean([cosd(util['newton'], util['archimedes']),
                          cosd(util['newton'], util['pascal']),
                          cosd(util['archimedes'], util['pascal'])])
            divs.append(1.0 - pp); drops.append(np.mean(dr))
        row = {'topo': tn, 'f': f, 'div': float(np.mean(divs)),
               'drop': float(np.mean(drops))}
        rows.append(row)
        print(f"{tn:<11}{f:>5.2f}{row['drop']:>9.4f}{row['div']:>12.4f}")
    print()

json.dump(rows, open('/home/clopez/emmet/data/causal_sweep.json', 'w'), indent=2)

print('=== WITHIN-TOPOLOGY correlation drop <-> divergence ===')
ok = 0
for tn in TARGETS:
    sub = [r for r in rows if r['topo'] == tn]
    d = np.array([r['drop'] for r in sub]); v = np.array([r['div'] for r in sub])
    pr, pp_ = stats.pearsonr(d, v)
    sr, sp_ = stats.spearmanr(d, v)
    flag = 'CONFIRMS' if sr > 0.7 else ('weak' if sr > 0.3 else 'FAILS')
    ok += sr > 0.7
    print(f"{tn:<11} pearson r={pr:+.3f} p={pp_:.4f} | spearman {sr:+.3f} p={sp_:.4f}  -> {flag}")

print('\n=== pre-committed endpoint checks ===')
for tn, lo, hi in (('BA_n50_m2', 1.5, 0.45), ('GEANT', 1.5, 0.45)):
    a = [r for r in rows if r['topo'] == tn and r['f'] == lo][0]
    b = [r for r in rows if r['topo'] == tn and r['f'] == hi][0]
    print(f"{tn}: div at f={lo} -> {a['div']:.4f} (drop {a['drop']:.4f}) | "
          f"f={hi} -> {b['div']:.4f} (drop {b['drop']:.4f})")
print('\nIf relieved nets converge and squeezed nets diverge - same graph, same')
print('demand - congestion is the CAUSE. Interventional, not observational.')
