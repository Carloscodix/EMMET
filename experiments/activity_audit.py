"""
activity_audit.py - per-topology activity of each physical term, measured as
how much load mass it relocates away from the bare base substrate.

Closes audit CATCH 1 (the activity-degeneracy confound): where a term moves
~0% of the load, that core IS the base by construction, and its agreement with
its siblings is degenerate, not evidence of convergence. The convergence claim
in the paper must be conditioned on this table.

Per topology (3 seeds): mean drop level across the three cores, and for each
core the L1 mass moved vs base (% of normalized load relocated). Newton runs
with its scar fed (flowsim feed_scar). Saves data/activity_audit.json.
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
N_SEEDS = 3


def make_base_only():
    def route_fn(G, s, d, state):
        return PC.route_with_term(G, s, d, state, lambda G, u, v, st: 0.0)
    return route_fn


def l1mass(a, b):
    ks = list(a.keys())
    x = np.array([a[k] for k in ks], float); y = np.array([b[k] for k in ks], float)
    sx, sy = x.sum(), y.sum()
    if sx == 0 or sy == 0:
        return float('nan')
    return float(0.5 * np.abs(x / sx - y / sy).sum())


rows = []
print(f"{'topo':<11}{'drop':>8}{'newton%':>9}{'archim%':>9}{'pascal%':>9}")
print('-' * 46)
for t in TOPOS:
    name, builder, dsrc = t
    mv = {c: [] for c in PHYS}; drops = []
    for s in range(N_SEEDS):
        G0, dem = build_topo(name, builder, dsrc, s)
        sched = FS.gen_flows(dem, 200, s + 9000, birth_rate=0.8,
                             dur_lo=4, dur_hi=12, rate=1)
        G, _ = build_topo(name, builder, dsrc, s); reset(G)
        base = FS.simulate_flows_util(G, sched, 200, make_base_only(), feed_scar=True)
        for c in PHYS:
            G, _ = build_topo(name, builder, dsrc, s); reset(G)
            r = FS.simulate_flows_util(G, sched, 200, PC.make_physics_policy(c),
                                       feed_scar=True)
            mv[c].append(l1mass(r['util'], base['util']))
            drops.append(r['drop_rate'])
    row = {'topo': name, 'drop': float(np.mean(drops))}
    for c in PHYS:
        row[f'{c}_l1'] = float(np.mean(mv[c]))
    rows.append(row)
    print(f"{name:<11}{row['drop']:>8.4f}{row['newton_l1']*100:>9.2f}"
          f"{row['archimedes_l1']*100:>9.2f}{row['pascal_l1']*100:>9.2f}")

json.dump(rows, open('/home/clopez/emmet/data/activity_audit.json', 'w'), indent=2)

drop = np.array([r['drop'] for r in rows])
print('\n=== does activity track congestion? ===')
for c in PHYS:
    a = np.array([r[f'{c}_l1'] for r in rows])
    rr, pp = stats.pearsonr(drop, a)
    print(f"corr(activity_{c}, drop) = {rr:+.3f}  p={pp:.4f}   "
          f"range {a.min()*100:.2f}%-{a.max()*100:.2f}%")
print('\nPairs where BOTH cores moved <1%: degenerate (they ARE the base there).')
print('Convergence among ACTIVE cores is the claim the paper can defend.')
