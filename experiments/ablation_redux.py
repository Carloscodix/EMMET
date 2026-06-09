"""
ablation_redux.py - re-test of the FOUNDATIONAL EMMET hypothesis with today's
tools: does the Newton-III scar (the only layer the original ablation kept)
actually improve drop rate over the bare substrate (gradient + congestion)?

The original ablation was run in the pre-flowsim, pre-scar-fix, pre-real-
Abilene era. Today we have: the base_only router, feed_scar fixed, and the
congestion-gating law, which makes a falsifiable prediction: the scar is
drop-gated, so it can only help where drops exist (contested regime), must be
inert in free flow, and cannot help in saturation.

PRE-COMMITTED VERDICTS:
  - newton beats base in contested topologies -> original ablation replicates;
    the 2-term core earns its keep exactly where the law says it can.
  - newton ~= base everywhere -> the core reduces to the substrate; the
    'EMMET router' claim must be demoted, and we say so.
  - newton WORSE than base anywhere -> scar over-reaction; report it.
Archimedes and Pascal included for the full 'does ANY term beat the substrate?'
picture. 15 topos x 12 seeds, paired by seed (same graph+demand+schedule).
"""
import sys, json
import numpy as np
from scipy import stats
sys.path.insert(0, '/home/clopez/emmet/experiments')
import flowsim as FS
import physics_cores as PC
from equivalence import TOPOS, build_topo
from emmet_budget import reset

CORES = ['newton', 'archimedes', 'pascal']
N_SEEDS = 12


def make_base_only():
    def route_fn(G, s, d, state):
        return PC.route_with_term(G, s, d, state, lambda G, u, v, st: 0.0)
    return route_fn


def regime(d):
    return 'free' if d < 0.01 else ('contested' if d < 0.10 else 'saturated')


rows = []
print(f"{'topo':<11}{'base':>8}{'newton':>9}{'arch':>9}{'pascal':>9}  regime")
print('-' * 58)
for t in TOPOS:
    name, builder, dsrc = t
    res = {c: [] for c in ['base'] + CORES}
    for s in range(N_SEEDS):
        G0, dem = build_topo(name, builder, dsrc, s)
        sched = FS.gen_flows(dem, 200, s + 9000, birth_rate=0.8,
                             dur_lo=4, dur_hi=12, rate=1)
        G, _ = build_topo(name, builder, dsrc, s); reset(G)
        res['base'].append(FS.simulate_flows(G, sched, 200, make_base_only())['drop_rate'])
        for c in CORES:
            G, _ = build_topo(name, builder, dsrc, s); reset(G)
            sim = FS.simulate_flows_scar if c == 'newton' else FS.simulate_flows
            res[c].append(sim(G, sched, 200, PC.make_physics_policy(c))['drop_rate'])
    row = {'topo': name, 'regime': regime(float(np.mean(res['base'])))}
    for k in res:
        row[k] = float(np.mean(res[k]))
        row[k + '_seeds'] = [float(x) for x in res[k]]
    rows.append(row)
    print(f"{name:<11}{row['base']:>8.4f}{row['newton']:>9.4f}"
          f"{row['archimedes']:>9.4f}{row['pascal']:>9.4f}  {row['regime']}")

json.dump(rows, open('/home/clopez/emmet/data/ablation_redux.json', 'w'), indent=2)

print('\n=== paired tests vs base (negative delta = core BETTER) ===')
for c in CORES:
    print(f"--- {c} ---")
    for rg in ('free', 'contested', 'saturated'):
        sub = [r for r in rows if r['regime'] == rg]
        if not sub:
            continue
        deltas = []
        for r in sub:
            deltas += [a - b for a, b in zip(r[c + '_seeds'], r['base_seeds'])]
        deltas = np.array(deltas)
        try:
            _, p = stats.wilcoxon(deltas)
        except ValueError:
            p = 1.0
        print(f"  {rg:<10} n_topos={len(sub):>2} mean_delta={deltas.mean():+.4f} "
              f"(pp {deltas.mean()*100:+.2f}) wilcoxon p={p:.4f}")

print('\nReading: gating law predicts newton helps ONLY in contested, is inert')
print('in free flow, and cannot save saturation. If it helps nowhere, the')
print('2-term core adds nothing over the substrate and we say so.')
