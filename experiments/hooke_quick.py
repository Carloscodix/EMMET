"""
hooke_quick.py - the fourth physicist's tryout, with a sharp question attached.

Archimedes (QUADRATIC above threshold rho0=0.6) beats the bare substrate on
15/15 topologies. Hooke is LINEAR above a threshold (slack=0.5). So this test
separates two hypotheses about WHY the buoyancy works:
  - THRESHOLD hypothesis: anticipatory early-warning above a density threshold
    is the active ingredient -> Hooke should also beat base.
  - CURVATURE hypothesis: the quadratic growth is essential -> Hooke fails.

Part A: hooke drop rates, 15 topos x 12 seeds, PAIRED against the base seeds
        already stored in data/ablation_redux.json (same seeds, same scheds).
Part B: does Hooke fall into the same attractor? cosine of its util vector vs
        newton/archimedes/pascal on 5 representative topologies.
"""
import sys, json
import numpy as np
from scipy import stats
sys.path.insert(0, '/home/clopez/emmet/experiments')
import flowsim as FS
import physics_cores as PC
from equivalence import TOPOS, build_topo
from emmet_budget import reset

N_SEEDS = 12
redux = {r['topo']: r for r in json.load(open('/home/clopez/emmet/data/ablation_redux.json'))}

# ---- Part A: performance vs base (paired, reusing redux base seeds) ----
print("=== PART A: Hooke vs bare base (paired, 12 seeds) ===")
print(f"{'topo':<11}{'base':>8}{'hooke':>9}{'arch(ref)':>10}  regime")
print('-' * 50)
rows = []
for t in TOPOS:
    name, builder, dsrc = t
    drops = []
    for s in range(N_SEEDS):
        G0, dem = build_topo(name, builder, dsrc, s)
        sched = FS.gen_flows(dem, 200, s + 9000, birth_rate=0.8,
                             dur_lo=4, dur_hi=12, rate=1)
        G, _ = build_topo(name, builder, dsrc, s); reset(G)
        drops.append(FS.simulate_flows(G, sched, 200,
                                       PC.make_physics_policy('hooke'))['drop_rate'])
    r = redux[name]
    rows.append({'topo': name, 'regime': r['regime'],
                 'hooke_seeds': [float(x) for x in drops],
                 'base_seeds': r['base_seeds'],
                 'hooke': float(np.mean(drops)), 'base': r['base'],
                 'arch': r['archimedes']})
    print(f"{name:<11}{r['base']:>8.4f}{rows[-1]['hooke']:>9.4f}"
          f"{r['archimedes']:>10.4f}  {r['regime']}")

json.dump(rows, open('/home/clopez/emmet/data/hooke_quick.json', 'w'), indent=2)

print('\n--- paired tests vs base (negative = hooke BETTER) ---')
wins = sum(1 for r in rows if r['hooke'] <= r['base'])
for rg in ('free', 'contested', 'saturated'):
    sub = [r for r in rows if r['regime'] == rg]
    if not sub:
        continue
    deltas = []
    for r in sub:
        deltas += [a - b for a, b in zip(r['hooke_seeds'], r['base_seeds'])]
    deltas = np.array(deltas)
    try:
        _, p = stats.wilcoxon(deltas)
    except ValueError:
        p = 1.0
    print(f"  {rg:<10} n_topos={len(sub):>2} mean_delta_pp={deltas.mean()*100:+.2f} "
          f"wilcoxon p={p:.1e}")
print(f"  wins vs base: {wins}/15")

# ---- Part B: does Hooke land in the same attractor? ----
print("\n=== PART B: Hooke in the attractor (cos vs the other three) ===")


def cosd(a, b):
    ks = list(a.keys())
    x = np.array([a[k] for k in ks], float); y = np.array([b[k] for k in ks], float)
    nx_, ny_ = np.linalg.norm(x), np.linalg.norm(y)
    return float(np.dot(x, y) / (nx_ * ny_)) if nx_ > 0 and ny_ > 0 else float('nan')


sims = []
for tn in ('Grid5', 'Grid8', 'WS_n50_k6', 'BA_n50_m2', 'GEANT'):
    t = [x for x in TOPOS if x[0] == tn][0]
    name, builder, dsrc = t
    vals = []
    for s in range(3):
        G0, dem = build_topo(name, builder, dsrc, s)
        sched = FS.gen_flows(dem, 200, s + 9000, birth_rate=0.8,
                             dur_lo=4, dur_hi=12, rate=1)
        util = {}
        for c in ('hooke', 'newton', 'archimedes', 'pascal'):
            G, _ = build_topo(name, builder, dsrc, s); reset(G)
            util[c] = FS.simulate_flows_util(G, sched, 200,
                                             PC.make_physics_policy(c),
                                             feed_scar=True)['util']
        vals.append(np.mean([cosd(util['hooke'], util[o])
                             for o in ('newton', 'archimedes', 'pascal')]))
    sims.append(np.mean(vals))
    print(f"  {tn:<11} hooke-vs-others cos = {np.mean(vals):.3f}")
print(f"  MEAN: {np.mean(sims):.3f}")

print('\n=== VERDICT ===')
contested = [r for r in rows if r['regime'] == 'contested']
d_cont = np.mean([np.mean(r['hooke_seeds']) - np.mean(r['base_seeds']) for r in contested])
if wins >= 12 and d_cont < 0:
    print("THRESHOLD hypothesis supported: linear-above-threshold also beats the")
    print("base. The anticipatory threshold is the active ingredient; quadratic")
    print("curvature is a refinement, not the essence. Hooke = fourth witness.")
elif wins <= 8:
    print("CURVATURE hypothesis supported: the linear spring does NOT replicate")
    print("the buoyancy's win - the quadratic growth is essential.")
else:
    print("MIXED: partial wins. Threshold helps but curvature adds real margin.")
