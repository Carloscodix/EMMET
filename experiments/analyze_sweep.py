"""Analyze topology sweep: tube/sp vs Ripple-over-CONGA reduction."""
import json, math
from collections import defaultdict
import numpy as np
from scipy import stats
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

d = json.load(open('/home/clopez/emmet/data/sweep_topologies_raw.json'))
tube = d['tube']; meta = d['meta']; runs = d['runs']

# Aggregate losses per topo
agg = defaultdict(lambda: {'CONGA': [], 'RIPPLE': []})
for r in runs:
    agg[r['topo']]['CONGA'].append(r['CONGA'])
    agg[r['topo']]['RIPPLE'].append(r['RIPPLE'])

rows = []
for topo in sorted(agg.keys(), key=lambda t: tube[t]):
    c = sum(agg[topo]['CONGA']); r = sum(agg[topo]['RIPPLE'])
    if c == 0 and r == 0:
        red = None  # no signal
    else:
        red = (c - r) / c * 100 if c > 0 else 0.0
    rows.append({'topo': topo, 'tube': tube[topo], 'n': meta[topo]['n'],
                 'conga': c, 'ripple': r, 'reduction': red})

print(f"{'Topo':<12}{'tube/sp':>8}{'n':>5}{'CONGA':>7}{'RIPPLE':>7}{'red%':>8}")
print('-' * 50)
for x in rows:
    rd = f"{x['reduction']:+.1f}" if x['reduction'] is not None else "n/a"
    print(f"{x['topo']:<12}{x['tube']:>8.2f}{x['n']:>5}{x['conga']:>7}{x['ripple']:>7}{rd:>8}")

# Correlation + regression on topos with signal
valid = [x for x in rows if x['reduction'] is not None]
xs = np.array([x['tube'] for x in valid])
ys = np.array([x['reduction'] for x in valid])
pear = stats.pearsonr(xs, ys)
spear = stats.spearmanr(xs, ys)
slope, intercept, r, p, se = stats.linregress(xs, ys)
threshold = -intercept / slope  # tube/sp where reduction crosses 0
print(f"\nPearson r={pear[0]:.3f} (p={pear[1]:.4f})")
print(f"Spearman rho={spear[0]:.3f} (p={spear[1]:.4f})")
print(f"Regression: reduction = {slope:.2f} * tube/sp + ({intercept:.2f})")
print(f"R^2 = {r**2:.3f}")
print(f"Zero-crossing (break-even tube/sp) = {threshold:.2f}")

fig, ax = plt.subplots(figsize=(7, 5))
for x in valid:
    color = '#2a9d8f' if x['reduction'] > 0 else '#e76f51'
    ax.scatter(x['tube'], x['reduction'], c=color, s=70, zorder=3, edgecolor='k', linewidth=0.5)
    ax.annotate(x['topo'], (x['tube'], x['reduction']), fontsize=7, xytext=(4, 4), textcoords='offset points')
xline = np.linspace(xs.min(), xs.max(), 100)
ax.plot(xline, slope * xline + intercept, '--', color='#264653', lw=1.5, label=f'fit: R2={r**2:.2f}, p={p:.1e}')
ax.axhline(0, color='gray', lw=0.8)
ax.axvline(threshold, color='#e9c46a', lw=1.5, ls=':', label=f'break-even={threshold:.1f}')
ax.set_xlabel('tube/sp (path-budget envelope width / shortest path)')
ax.set_ylabel('Loss reduction vs CONGA-WAN (%)')
ax.set_title('EMMET-Newt advantage scales with maneuvering room')
ax.legend(fontsize=8); ax.grid(alpha=0.2)
plt.tight_layout()
plt.savefig('/home/clopez/emmet/paper/figure_tube_sweep.pdf')
plt.savefig('/home/clopez/emmet/paper/figure_tube_sweep.png', dpi=130)
print("Saved figure")
