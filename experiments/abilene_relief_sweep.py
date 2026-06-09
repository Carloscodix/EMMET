"""
abilene_relief_sweep.py - discriminating experiment for the real-Abilene anomaly.

Real Abilene broke the simple cross-topology congestion law: highest drops
(0.22) but middling divergence (0.017). Two competing explanations:
  (a) SATURATION: at 22pct drops it sits past the contested-regime peak, where
      divergence falls again (seen in the causal sweep).
  (b) STRUCTURAL CEILING: 11 nodes / 14 edges = 4 cycles; tube/sp 2.09. There
      is no room to express divergence at ANY pressure.

PRE-COMMITTED PREDICTIONS:
  (a) predicts an inverted-U: relieving capacity (f=1.5-2.5) moves Abilene into
      the contested regime and divergence RISES above the f=1.0 value before
      falling at full relief.
  (b) predicts flat-low: divergence stays at or below ~0.02 at every f.
Both can contribute; the curve tells the mix.
"""
import sys, json
import numpy as np
sys.path.insert(0, '/home/clopez/emmet/experiments')
import flowsim as FS
import physics_cores as PC
from equivalence import TOPOS, build_topo
from emmet_budget import reset

PHYS = ['newton', 'archimedes', 'pascal']
SWEEP = [1.0, 1.25, 1.5, 2.0, 3.0, 4.0]
N_SEEDS = 3


def cosd(a, b):
    ks = list(a.keys())
    x = np.array([a[k] for k in ks], float); y = np.array([b[k] for k in ks], float)
    nx_, ny_ = np.linalg.norm(x), np.linalg.norm(y)
    return float(np.dot(x, y) / (nx_ * ny_)) if nx_ > 0 and ny_ > 0 else float('nan')


t = [x for x in TOPOS if x[0] == 'Abilene'][0]
name, builder, dsrc = t
rows = []
print(f"{'f':>5}{'drop':>9}{'divergence':>12}")
print('-' * 27)
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
    rows.append({'f': f, 'div': float(np.mean(divs)), 'drop': float(np.mean(drops))})
    print(f"{f:>5.2f}{rows[-1]['drop']:>9.4f}{rows[-1]['div']:>12.4f}")

json.dump(rows, open('/home/clopez/emmet/data/abilene_relief.json', 'w'), indent=2)
base = rows[0]['div']
peak = max(r['div'] for r in rows[1:])
print('\n=== VERDICT ===')
print(f"div at f=1.0 (saturated): {base:.4f} | peak under relief: {peak:.4f}")
if peak > 1.5 * base:
    print("INVERTED-U: relieved Abilene diverges MORE -> saturation explains the")
    print("anomaly; the within-topology law holds even here. Ceiling secondary.")
elif peak > 1.15 * base:
    print("MILD RISE: both saturation and ceiling contribute.")
else:
    print("FLAT-LOW: structural ceiling dominates - with 4 cycles there is no room")
    print("to diverge at any pressure. Two-factor law confirmed: drive x room.")
