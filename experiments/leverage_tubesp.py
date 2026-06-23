"""
leverage_tubesp.py - Cook's distance on the tube/sp regression.

A reviewer flagged: the BA points sit below the regression line; if the
correlation depends on a few high-leverage points, the predictor is weak.
This computes Cook's distance for every topology and reports:
  - the regression with all 15 points
  - leave-one-out: r and slope with each point removed
  - the regression with the 3 BA points removed (the specific challenge)
So we can state honestly how robust r=0.78 is.

Data: the tube/sp vs reduction% table from the applicability sweep (section 7).
"""
import numpy as np
from scipy import stats

# (topo, tube/sp, reduction%) from the paper's tube/sp table (section 7)
DATA = [
    ('Abilene',    2.09, -16.3),
    ('Grid5',      2.73,  -6.4),
    ('Grid6',      3.58,   9.5),
    ('GEANT',      3.90,   3.9),
    ('Grid7',      4.33,  40.4),
    ('WS_n30_k4',  4.67,  23.8),
    ('Grid8',      4.81,  44.6),
    ('BA_n50_m2',  5.14,  10.1),
    ('WS_n50_k4',  5.23,  36.7),
    ('BA_n80_m2',  5.85,  15.1),
    ('Grid10',     5.99,  68.4),
    ('WS_n80_k4',  6.49,  37.5),
    ('Grid12',     7.69,  70.7),
    ('WS_n50_k6',  8.57,  61.5),
    ('BA_n50_m3',  9.33,  45.6),
]

names = [d[0] for d in DATA]
x = np.array([d[1] for d in DATA])
y = np.array([d[2] for d in DATA])
n = len(x)

def fit(xx, yy):
    r, p = stats.pearsonr(xx, yy)
    sl, ic, _, _, _ = stats.linregress(xx, yy)
    R2 = r**2
    return r, p, sl, ic, R2

r, p, sl, ic, R2 = fit(x, y)
print("=== FULL REGRESSION (15 points) ===")
print(f"r={r:.3f}  p={p:.4f}  R2={R2:.3f}  slope={sl:.2f}  intercept={ic:.2f}")

# Cook's distance
yhat = sl * x + ic
resid = y - yhat
mse = np.sum(resid**2) / (n - 2)
xbar = np.mean(x)
Sxx = np.sum((x - xbar)**2)
h = 1/n + (x - xbar)**2 / Sxx          # leverage
cook = (resid**2 / (2 * mse)) * (h / (1 - h)**2)
thresh = 4.0 / n                        # common Cook's distance cutoff

print("\n=== COOK'S DISTANCE per topology (cutoff 4/n = %.3f) ===" % thresh)
order = np.argsort(-cook)
for i in order:
    flag = "  <-- INFLUENTIAL" if cook[i] > thresh else ""
    print(f"{names[i]:<11} leverage={h[i]:.3f}  cook={cook[i]:.3f}{flag}")

print("\n=== LEAVE-ONE-OUT: r and slope with each point removed ===")
for i in range(n):
    xx = np.delete(x, i); yy = np.delete(y, i)
    ri, pi, sli, _, _ = fit(xx, yy)
    drop = ri - r
    print(f"without {names[i]:<11} r={ri:.3f} ({drop:+.3f})  slope={sli:.2f}")

print("\n=== KIMI'S CHALLENGE: remove all 3 BA points ===")
keep = [i for i, nm in enumerate(names) if not nm.startswith('BA')]
xx = x[keep]; yy = y[keep]
rb, pb, slb, icb, R2b = fit(xx, yy)
print(f"without BA (n={len(keep)}): r={rb:.3f}  p={pb:.4f}  R2={R2b:.3f}  slope={slb:.2f}")
print(f"vs full: r {r:.3f} -> {rb:.3f}  ({rb-r:+.3f})")

print("\n=== VERDICT ===")
infl = [names[i] for i in range(n) if cook[i] > thresh]
maxdrop = max(abs(fit(np.delete(x,i), np.delete(y,i))[0] - r) for i in range(n))
if rb > 0.6 and pb < 0.05 and maxdrop < 0.15:
    print("ROBUST: correlation survives removing BA and any single point.")
    print(f"r stays >0.6 without BA, max single-point shift {maxdrop:.3f}.")
elif rb > 0.5 and pb < 0.05:
    print("MODERATELY ROBUST: survives BA removal but weakens; report honestly.")
else:
    print("FRAGILE: correlation leans on the BA points. Must caveat hard.")
if infl:
    print(f"Influential points (Cook > 4/n): {infl}")
