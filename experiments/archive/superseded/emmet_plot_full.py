"""Final figures for the paper using emmet_full (adaptive beta + thermal).

Reads data/adaptive_summary.json (computed by emmet_beta_adaptive.py).
Generates publication-grade figures:
  1. emmet_full_synthetic.png   — density sweeps n=20/50/100 with 6 strategies
  2. emmet_full_real.png        — Abilene + GEANT bar chart
  3. emmet_full_advantage.png   — % loss reduction vs LASP curve
  4. emmet_full_dominance.png   — Pareto dominance count
"""
import json
import re
from pathlib import Path
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec
import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR  = REPO_ROOT / 'data'
PAPER_DIR = REPO_ROOT / 'paper'
NB_DIR    = REPO_ROOT / 'notebooks'

with open(DATA_DIR / 'adaptive_summary.json', 'r') as f:
    summary = json.load(f)

COL_SP = '#185FA5'
COL_LA = '#CC8400'
COL_EM = '#5BAA8C'
COL_ET = '#0F6E56'
COL_AD = '#A26FBD'
COL_FU = '#7A1F4F'

STRATS = [
    ('sp',             'SP',             COL_SP, 'o'),
    ('lasp',           'LASP',           COL_LA, 's'),
    ('emmet_cold',     'EMMET cold',     COL_EM, '^'),
    ('emmet_thermal',  'EMMET thermal',  COL_ET, 'D'),
    ('emmet_adaptive', 'EMMET adaptive', COL_AD, 'P'),
    ('emmet_full',     'EMMET full',     COL_FU, '*'),
]

# Parse synthetic scenarios
synthetic = {20: [], 50: [], 100: []}
real = {}
pat = re.compile(r'ER_n(\d+)_p([\d.]+)')
for s in summary:
    m = pat.match(s['scenario'])
    if m:
        n = int(m.group(1)); d = float(m.group(2))
        synthetic[n].append((d, s))
    else:
        real[s['scenario']] = s
for n in synthetic:
    synthetic[n].sort(key=lambda x: x[0])

# ---------- Figure 1: synthetic sweeps (6 strategies) ----------
fig = plt.figure(figsize=(15, 10))
fig.suptitle(
    'EMMET full vs Baselines on Erdős–Rényi Topologies (100 seeds per point)\n'
    'α=1.0  β_base=3.0  γ=2.0  half-life=100  ε=0.10  θ=1.0',
    fontsize=12, fontweight='bold', y=1.00
)
gs = GridSpec(3, 2, figure=fig, hspace=0.50, wspace=0.28)

for row, n in enumerate([20, 50, 100]):
    bucket = synthetic[n]
    if not bucket:
        continue
    densities = [d for d, _ in bucket]
    ax1 = fig.add_subplot(gs[row, 0])
    for key, label, col, marker in STRATS:
        means = [s[f'{key}_losses_mean'] for _, s in bucket]
        stds  = [s[f'{key}_losses_std']  for _, s in bucket]
        ax1.errorbar(densities, means, yerr=stds, fmt=f'{marker}-',
                     color=col, lw=1.4, capsize=3, label=label, alpha=0.85,
                     markersize=6)
    ax1.set_title(f'n = {n} — Packet Loss', fontweight='bold')
    ax1.set_xlabel('Density (p)')
    ax1.set_ylabel('Packets lost (mean ± std)')
    ax1.legend(fontsize=7, ncol=2, loc='upper right')
    ax1.grid(alpha=0.3)

    ax2 = fig.add_subplot(gs[row, 1])
    for key, label, col, marker in STRATS:
        means = [s[f'{key}_lat_delivered_mean'] for _, s in bucket]
        ax2.plot(densities, means, f'{marker}-', color=col, lw=1.4,
                 label=label, alpha=0.85, markersize=6)
    ax2.set_title(f'n = {n} — Latency per Delivered Packet', fontweight='bold')
    ax2.set_xlabel('Density (p)')
    ax2.set_ylabel('Lat / delivered (mean)')
    ax2.legend(fontsize=7, ncol=2, loc='upper right')
    ax2.grid(alpha=0.3)

plt.savefig(PAPER_DIR / 'emmet_full_synthetic.png', dpi=180, bbox_inches='tight')
plt.savefig(NB_DIR    / 'emmet_full_synthetic.png', dpi=180, bbox_inches='tight')
print('Synthetic figure saved.')
plt.close()

# ---------- Figure 2: real topologies bar chart ----------
topos = ['Abilene', 'GEANT']
fig = plt.figure(figsize=(13, 6))
fig.suptitle(
    'EMMET full on Real Internet Topologies (Internet Topology Zoo, 100 seeds each)',
    fontsize=12, fontweight='bold', y=1.02
)
gs = GridSpec(1, 2, figure=fig, wspace=0.30)

x = np.arange(len(topos))
w = 0.13

ax1 = fig.add_subplot(gs[0])
for i, (key, label, col, _) in enumerate(STRATS):
    means = [real[t][f'{key}_losses_mean'] for t in topos]
    stds  = [real[t][f'{key}_losses_std']  for t in topos]
    ax1.bar(x + (i - 2.5) * w, means, w, yerr=stds, label=label,
            color=col, alpha=0.85, capsize=3)
ax1.set_title('Packet Loss', fontweight='bold')
ax1.set_ylabel('Packets lost (mean ± std)')
ax1.set_xticks(x); ax1.set_xticklabels(topos)
ax1.legend(fontsize=8, ncol=2, loc='upper right')
ax1.grid(axis='y', alpha=0.3)

ax2 = fig.add_subplot(gs[1])
for i, (key, label, col, _) in enumerate(STRATS):
    means = [real[t][f'{key}_lat_delivered_mean'] for t in topos]
    stds  = [real[t][f'{key}_lat_delivered_std']  for t in topos]
    ax2.bar(x + (i - 2.5) * w, means, w, yerr=stds, label=label,
            color=col, alpha=0.85, capsize=3)
ax2.set_title('Latency per Delivered Packet', fontweight='bold')
ax2.set_ylabel('Lat / delivered (mean ± std)')
ax2.set_xticks(x); ax2.set_xticklabels(topos)
ax2.legend(fontsize=8, ncol=2, loc='upper right')
ax2.grid(axis='y', alpha=0.3)

plt.savefig(PAPER_DIR / 'emmet_full_real.png', dpi=180, bbox_inches='tight')
plt.savefig(NB_DIR    / 'emmet_full_real.png', dpi=180, bbox_inches='tight')
print('Real topologies figure saved.')
plt.close()

# ---------- Figure 3: % advantage vs LASP across density (n=20) ----------
n20 = synthetic[20]
densities = [d for d, _ in n20]
la_l = [s['lasp_losses_mean'] for _, s in n20]
adv_curves = {}
for key, label, col, _ in STRATS[2:]:  # only EMMET variants
    adv = []
    for i, (_, s) in enumerate(n20):
        v = s[f'{key}_losses_mean']
        if la_l[i] > 0.01:
            adv.append((la_l[i] - v) / la_l[i] * 100)
        else:
            adv.append(0)
    adv_curves[label] = (col, adv)

fig, ax = plt.subplots(figsize=(11, 6))
for label, (col, adv) in adv_curves.items():
    ax.plot(densities, adv, 'o-', color=col, lw=2, markersize=7, label=label, alpha=0.9)
ax.axhline(0, color='gray', lw=0.8, ls=':')
ax.axvspan(0.15, 0.30, alpha=0.10, color='orange', label='Phase transition zone')
ax.set_title('EMMET Variants — Loss Reduction vs LASP (n=20, 100 seeds)',
             fontweight='bold')
ax.set_xlabel('Network density (p)')
ax.set_ylabel('Loss reduction vs LASP (%)')
ax.legend(fontsize=10, loc='best')
ax.grid(alpha=0.3)
plt.savefig(PAPER_DIR / 'emmet_full_advantage.png', dpi=180, bbox_inches='tight')
plt.savefig(NB_DIR    / 'emmet_full_advantage.png', dpi=180, bbox_inches='tight')
print('Advantage curve saved.')
plt.close()

# ---------- Figure 4: Pareto dominance count ----------
def is_dominated(point, others):
    px, py = point
    for ox, oy in others:
        if (ox <= px and oy <= py) and (ox < px or oy < py):
            return True
    return False

counts = {k: 0 for k, _, _, _ in STRATS}
total = len(summary)
for s in summary:
    pts = {k: (s[f'{k}_lat_delivered_mean'], s[f'{k}_losses_mean'])
           for k, _, _, _ in STRATS}
    for k in pts:
        others = [pts[k2] for k2 in pts if k2 != k]
        if not is_dominated(pts[k], others):
            counts[k] += 1

fig, ax = plt.subplots(figsize=(9, 5))
labels = [s[1] for s in STRATS]
values = [counts[s[0]] for s in STRATS]
colors = [s[2] for s in STRATS]
bars = ax.bar(labels, values, color=colors, alpha=0.85)
for bar, val in zip(bars, values):
    ax.text(bar.get_x() + bar.get_width()/2, val + 0.3,
            f'{val}/{total}\n({val/total*100:.0f}%)',
            ha='center', fontsize=9, fontweight='bold')
ax.set_title(
    f'Pareto-Optimal Frequency Across {total} Scenarios',
    fontweight='bold', fontsize=11
)
ax.set_ylabel('Scenarios where strategy is Pareto-optimal')
ax.set_ylim(0, total + 2)
ax.grid(axis='y', alpha=0.3)
plt.xticks(rotation=15)
plt.tight_layout()
plt.savefig(PAPER_DIR / 'emmet_full_dominance.png', dpi=180, bbox_inches='tight')
plt.savefig(NB_DIR    / 'emmet_full_dominance.png', dpi=180, bbox_inches='tight')
print('Dominance chart saved.')
plt.close()

print(f"\nDominance counts: {counts}")
print(f"\nAll figures saved to paper/ and notebooks/.")
