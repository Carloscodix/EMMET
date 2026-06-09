"""
partial_perf.py - the open risk from the deep review: is tube/sp~reduction%
(the paper's flagship regression, the Cook's-robust one) ALSO a congestion
proxy, like the divergence link turned out to be? Or does it retain an
independent role?

Data: (tube/sp, reduction%) from the paper's applicability table (sweep
harness, real Abilene there) merged with mean physics drop rates from the
divergence experiment (12 seeds). Abilene EXCLUDED (n=14): its drop number in
the old bench belonged to GEANT's graph (duplication bug), so we have no valid
congestion measure for the real Abilene yet.

Reading guide:
- if tube/sp | drops vanishes -> tube/sp was a proxy too, we lose a pillar
- if it survives -> two predictors, two roles: congestion = how much the
  mechanism matters; tube/sp = how much rerouting can gain.
"""
import numpy as np
from scipy import stats

# (topo, tube_sp, reduction_pct, mean_phys_drop)
ROWS = [
    ('Grid5',     2.73,  -6.4, .0297),
    ('Grid6',     3.58,   9.5, .0264),
    ('GEANT',     3.90,   3.9, .0704),
    ('Grid7',     4.33,  40.4, .0188),
    ('WS_n30_k4', 4.67,  23.8, .0275),
    ('Grid8',     4.81,  44.6, .0082),
    ('BA_n50_m2', 5.14,  10.1, .0054),
    ('WS_n50_k4', 5.23,  36.7, .0239),
    ('BA_n80_m2', 5.85,  15.1, .0014),
    ('Grid10',    5.99,  68.4, .0051),
    ('WS_n80_k4', 6.49,  37.5, .0305),
    ('Grid12',    7.69,  70.7, .0057),
    ('WS_n50_k6', 8.57,  61.5, .0050),
    ('BA_n50_m3', 9.33,  45.6, .0007),
]

tube = np.array([r[1] for r in ROWS])
red = np.array([r[2] for r in ROWS])
drop = np.array([r[3] for r in ROWS])


def partial_corr(x, y, z):
    def resid(a, b):
        sl, ic, _, _, _ = stats.linregress(b, a)
        return a - (sl * b + ic)
    rx = resid(np.array(x, float), np.array(z, float))
    ry = resid(np.array(y, float), np.array(z, float))
    return stats.pearsonr(rx, ry)


print("n=14 (Abilene excluded: no valid congestion measure for the real graph yet)")
print("\n=== raw correlations with reduction% ===")
r1, p1 = stats.pearsonr(tube, red)
r2, p2 = stats.pearsonr(drop, red)
s1, sp1 = stats.spearmanr(tube, red)
s2, sp2 = stats.spearmanr(drop, red)
print(f"tube/sp ~ reduction : pearson r={r1:+.3f} p={p1:.4f} | spearman {s1:+.3f} p={sp1:.4f}")
print(f"drop    ~ reduction : pearson r={r2:+.3f} p={p2:.4f} | spearman {s2:+.3f} p={sp2:.4f}")
print(f"(collinearity: tube~drop r={stats.pearsonr(tube, drop)[0]:+.3f})")

print("\n=== partial correlations (the decisive test) ===")
rt, pt = partial_corr(tube, red, drop)
rd, pd = partial_corr(drop, red, tube)
print(f"tube/sp ~ reduction | controlling drop : r={rt:+.3f}  p={pt:.4f}")
print(f"drop    ~ reduction | controlling tube : r={rd:+.3f}  p={pd:.4f}")

print("\n=== VERDICT ===")
if abs(rt) > 0.5 and pt < 0.05:
    print("tube/sp SURVIVES the congestion control: it retains an independent,")
    print("significant link to performance. Two predictors, two roles:")
    print("  congestion -> how much mechanism identity matters (divergence)")
    print("  tube/sp    -> how much rerouting can gain (performance)")
elif abs(rt) > 0.4:
    print("tube/sp retains a moderate partial link - report with that nuance.")
else:
    print("tube/sp largely COLLAPSES under congestion control - the flagship")
    print("regression is also a proxy. Pillar lost; reframe required.")
print("\nCaveat to verify later: relative reduction% on near-zero baselines")
print("(grids with drops ~0.005) inflates percentages; absolute reduction TBD.")
