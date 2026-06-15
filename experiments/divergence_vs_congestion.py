"""
divergence_vs_congestion.py - is inter-core divergence driven by congestion,
not tube/sp? Hypothesis: where there are real drops to avoid, each mechanism
avoids them differently (divergence); where there are none, they coincide.

For each topology (12 seeds): measure
  - divergence = 1 - mean pairwise cosine of the three physical cores' util
  - drop_level = mean drop rate across the three cores (the congestion actually seen)
  - tube_sp
Then correlate divergence with drop_level and with tube/sp, and run a partial
correlation: does tube/sp retain any link to divergence once drop_level is
controlled for? If drop_level explains it and tube/sp does not (after control),
the honest mechanism is congestion, with tube/sp a mere proxy.
"""
import sys
import numpy as np
from scipy import stats
sys.path.insert(0, '/home/clopez/emmet/experiments')
import flowsim as FS
import physics_cores as PC
from equivalence import TOPOS, build_topo
from emmet_budget import reset
from sweep_topologies import tube_sp
# reuse the scar-feeding util simulator
exec(open('/tmp/audit_physics_weight.py').read().split('print("How')[0])

PHYS = ['newton', 'archimedes', 'pascal']
N_SEEDS = 12


def cos2(a, b):
    ks = list(a.keys())
    x = np.array([a[k] for k in ks]); y = np.array([b[k] for k in ks])
    return float(np.dot(x, y) / (np.linalg.norm(x) * np.linalg.norm(y)))


def partial_corr(x, y, z):
    """corr(x,y) controlling for z."""
    def resid(a, b):
        sl, ic, _, _, _ = stats.linregress(b, a)
        return a - (sl * b + ic)
    rx = resid(np.array(x), np.array(z))
    ry = resid(np.array(y), np.array(z))
    r, p = stats.pearsonr(rx, ry)
    return r, p


rows = []
for t in TOPOS:
    name, builder, dsrc = t
    divs, drops, tubes = [], [], []
    for s in range(N_SEEDS):
        G0, dem = build_topo(name, builder, dsrc, s)
        tubes.append(tube_sp(G0))
        sched = FS.gen_flows(dem, 200, s + 9000, birth_rate=0.8, dur_lo=4, dur_hi=12, rate=1)
        util = {}; dr = []
        for core in PHYS:
            G, _ = build_topo(name, builder, dsrc, s); reset(G)
            # simulate_flows_util returns BOTH drop_rate and the per-edge util
            # vector in one pass; feed_scar=True keeps Newton-III memory alive
            # for the scar-reading core, matching simulate_flows_scar.
            res = FS.simulate_flows_util(G, sched, 200,
                                         PC.make_physics_policy(core),
                                         feed_scar=(core == "newton"))
            dr.append(res["drop_rate"])
            util[core] = res["util"]
        pp = np.mean([cos2(util['newton'], util['archimedes']),
                      cos2(util['newton'], util['pascal']),
                      cos2(util['archimedes'], util['pascal'])])
        divs.append(1.0 - pp); drops.append(np.mean(dr))
    rows.append({'topo': name, 'div': float(np.mean(divs)),
                 'drop': float(np.mean(drops)), 'tube': float(np.mean(tubes))})

print(f"{'topo':<11}{'divergence':>11}{'drop_rate':>11}{'tube_sp':>9}")
print('-' * 42)
for r in rows:
    print(f"{r['topo']:<11}{r['div']:>11.4f}{r['drop']:>11.4f}{r['tube']:>9.2f}")

div = np.array([r['div'] for r in rows])
drop = np.array([r['drop'] for r in rows])
tube = np.array([r['tube'] for r in rows])

print("\n=== CORRELATIONS with divergence ===")
rd, pd = stats.pearsonr(drop, div)
rt, pt = stats.pearsonr(tube, div)
print(f"divergence ~ drop_rate : r={rd:+.3f}  p={pd:.4f}")
print(f"divergence ~ tube/sp   : r={rt:+.3f}  p={pt:.4f}")

print("\n=== PARTIAL CORRELATIONS ===")
rt_d, pt_d = partial_corr(tube, div, drop)
rd_t, pd_t = partial_corr(drop, div, tube)
print(f"tube/sp ~ divergence | controlling drop_rate : r={rt_d:+.3f}  p={pt_d:.4f}")
print(f"drop_rate ~ divergence | controlling tube/sp  : r={rd_t:+.3f}  p={pd_t:.4f}")

print("\n=== VERDICT ===")
if abs(rd) > abs(rt) and abs(rd_t) > 0.4 and abs(rt_d) < 0.4:
    print("CONGESTION drives divergence; tube/sp was a proxy. Genuine mechanism:")
    print("cores diverge where there are real drops to avoid, agree where there are none.")
elif abs(rt_d) > 0.4 and abs(rd_t) > 0.4:
    print("BOTH retain independent links - more complex, report both honestly.")
elif abs(rt) > abs(rd):
    print("tube/sp dominates after all - congestion hypothesis NOT supported.")
else:
    print("Neither clean - mechanism unclear, do not over-claim.")
print(f"\ncorr(drop, tube/sp) = {stats.pearsonr(drop, tube)[0]:+.3f} (how proxied they are)")
