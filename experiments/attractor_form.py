"""
Functional form of the pinned fraction f(tube/sp).

Geometric picture: of the w edges in the alpha-stretch tube of a demand pair,
only a fraction p actually carries alternative-path flow; the rest are dead
branches. If a fraction p of the tube absorbs flow, the pinned fraction is
    f = sp/(sp + p*(w-sp)) = 1/(1 + p*(x-1)),  x = tube/sp = w/sp.
A one-parameter hyperbola derived from tube geometry, not fitted ad hoc. It
beats linear and log fits on AIC with one fewer parameter, and p is stable to
1.3% under leave-one-out. Open: deriving p from the graph in closed form.
"""
import json
import numpy as np
from scipy import optimize, stats

rows = json.load(open("/home/clopez/emmet/data/attractor_full.json"))
x = np.array([r["tube_sp"] for r in rows])
f = np.array([r["pe_cos"] for r in rows])
n = len(x)

def hyper(xx, p):
    return 1.0 / (1.0 + p * (xx - 1.0))

def aic(rss, k):
    return n * np.log(rss / n) + 2 * k

popt, _ = optimize.curve_fit(hyper, x, f, p0=[0.05], maxfev=99999)
rss_h = np.sum((f - hyper(x, *popt)) ** 2)
r2_h = 1 - rss_h / np.sum((f - f.mean()) ** 2)
sl, ic, rl, _, _ = stats.linregress(x, f)
rss_l = np.sum((f - (sl * x + ic)) ** 2)
slg, icg, rg, _, _ = stats.linregress(np.log(x), f)
rss_g = np.sum((f - (slg * np.log(x) + icg)) ** 2)

print(f"hyperbolic f=1/(1+p(x-1)) p={popt[0]:.4f} R2={r2_h:.3f} AIC={aic(rss_h,1):.2f}")
print(f"linear     f=a+b*x        R2={rl**2:.3f} AIC={aic(rss_l,2):.2f}")
print(f"log        f=a+b*ln(x)    R2={rg**2:.3f} AIC={aic(rss_g,2):.2f}")

ps = []
for i in range(n):
    po, _ = optimize.curve_fit(hyper, np.delete(x, i), np.delete(f, i), p0=[0.05], maxfev=99999)
    ps.append(po[0])
ps = np.array(ps)
print(f"\np leave-one-out: {ps.mean():.4f} +/- {ps.std():.4f} ({100*ps.std()/ps.mean():.1f}% var)")
