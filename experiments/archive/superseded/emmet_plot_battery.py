"""Final battery figures: density sweeps at n=20/50/100 + real topologies.

Reads data/battery_summary.json (computed by emmet_battery.py).
Generates two publication-grade figures:
  1. emmet_battery_synthetic.png — density sweeps at three scales
  2. emmet_battery_real.png      — Abilene + GEANT comparison
"""
import json
import re
from pathlib import Path
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec

REPO_ROOT  = Path(__file__).resolve().parents[1]
DATA_DIR   = REPO_ROOT / 'data'
PAPER_DIR  = REPO_ROOT / 'paper'
NB_DIR     = REPO_ROOT / 'notebooks'

with open(DATA_DIR / 'battery_summary.json', 'r') as f:
    summary = json.load(f)

COL_SP = '#185FA5'
COL_LA = '#CC8400'
COL_EM = '#5BAA8C'
COL_ET = '#0F6E56'

# ----------------------------------------------------------------
# Parse synthetic scenarios into (n, density) buckets
# ----------------------------------------------------------------
synthetic = {20: [], 50: [], 100: []}
real = {}
pat = re.compile(r'ER_n(\d+)_p([\d.]+)')

for s in summary:
    m = pat.match(s['scenario'])
    if m:
        n = int(m.group(1))
        d = float(m.group(2))
        synthetic[n].append((d, s))
    else:
        real[s['scenario']] = s

for n in synthetic:
    synthetic[n].sort(key=lambda x: x[0])

# ----------------------------------------------------------------
# FIGURE 1 — synthetic density sweeps
# ----------------------------------------------------------------
fig = plt.figure(figsize=(15, 10))
fig.suptitle(
    'EMMET vs Baselines on Erdős–Rényi Topologies (battery: 100 seeds per point)\n'
    'α=1.0  β=3.0  γ=2.0  half-life=100  ε=0.10',
    fontsize=12, fontweight='bold', y=1.00
)
gs = GridSpec(3, 2, figure=fig, hspace=0.50, wspace=0.28)

for row, n in enumerate([20, 50, 100]):
    bucket = synthetic[n]
    if not bucket:
        continue
    densities = [d for d, _ in bucket]
    sp_l   = [s['sp_losses_mean'] for _, s in bucket]
    sp_ls  = [s['sp_losses_std']  for _, s in bucket]
    la_l   = [s['lasp_losses_mean'] for _, s in bucket]
    la_ls  = [s['lasp_losses_std']  for _, s in bucket]
    em_l   = [s['emmet_cold_losses_mean'] for _, s in bucket]
    em_ls  = [s['emmet_cold_losses_std']  for _, s in bucket]
    et_l   = [s['emmet_thermal_losses_mean'] for _, s in bucket]
    et_ls  = [s['emmet_thermal_losses_std']  for _, s in bucket]
    sp_la  = [s['sp_lat_delivered_mean'] for _, s in bucket]
    la_la_ = [s['lasp_lat_delivered_mean'] for _, s in bucket]
    em_la  = [s['emmet_cold_lat_delivered_mean'] for _, s in bucket]
    et_la  = [s['emmet_thermal_lat_delivered_mean'] for _, s in bucket]

    ax1 = fig.add_subplot(gs[row, 0])
    ax1.errorbar(densities, sp_l, yerr=sp_ls, fmt='o-', color=COL_SP, lw=1.5,
                 capsize=3, label='SP', alpha=0.85)
    ax1.errorbar(densities, la_l, yerr=la_ls, fmt='s-', color=COL_LA, lw=1.5,
                 capsize=3, label='LASP', alpha=0.85)
    ax1.errorbar(densities, em_l, yerr=em_ls, fmt='^--', color=COL_EM, lw=1.5,
                 capsize=3, label='EMMET cold', alpha=0.85)
    ax1.errorbar(densities, et_l, yerr=et_ls, fmt='D--', color=COL_ET, lw=1.5,
                 capsize=3, label='EMMET thermal', alpha=0.85)
    ax1.set_title(f'n = {n} — Packet Loss', fontweight='bold')
    ax1.set_xlabel('Density (p)')
    ax1.set_ylabel('Packets lost (mean ± std)')
    ax1.legend(fontsize=8, loc='upper right')
    ax1.grid(alpha=0.3)

    ax2 = fig.add_subplot(gs[row, 1])
    ax2.plot(densities, sp_la,  'o-',  color=COL_SP, lw=1.5, label='SP')
    ax2.plot(densities, la_la_, 's-',  color=COL_LA, lw=1.5, label='LASP')
    ax2.plot(densities, em_la,  '^--', color=COL_EM, lw=1.5, label='EMMET cold')
    ax2.plot(densities, et_la,  'D--', color=COL_ET, lw=1.5, label='EMMET thermal')
    ax2.set_title(f'n = {n} — Latency per Delivered Packet', fontweight='bold')
    ax2.set_xlabel('Density (p)')
    ax2.set_ylabel('Lat / delivered (mean)')
    ax2.legend(fontsize=8, loc='upper right')
    ax2.grid(alpha=0.3)

plt.savefig(PAPER_DIR / 'emmet_battery_synthetic.png', dpi=180, bbox_inches='tight')
plt.savefig(NB_DIR    / 'emmet_battery_synthetic.png', dpi=180, bbox_inches='tight')
print('Synthetic figure saved.')
plt.close()

# ----------------------------------------------------------------
# FIGURE 2 — real topologies
# ----------------------------------------------------------------
import numpy as np

topos = ['Abilene', 'GEANT']
strats = ['sp', 'lasp', 'emmet_cold', 'emmet_thermal']
strat_labels = ['SP', 'LASP', 'EMMET cold', 'EMMET thermal']
colors = [COL_SP, COL_LA, COL_EM, COL_ET]

fig = plt.figure(figsize=(13, 6))
fig.suptitle(
    'EMMET on Real Internet Topologies (Internet Topology Zoo, 100 seeds each)',
    fontsize=12, fontweight='bold', y=1.02
)
gs = GridSpec(1, 2, figure=fig, wspace=0.30)

x = np.arange(len(topos))
w = 0.20

ax1 = fig.add_subplot(gs[0])
for i, (strat, label, col) in enumerate(zip(strats, strat_labels, colors)):
    means = [real[t][f'{strat}_losses_mean'] for t in topos]
    stds  = [real[t][f'{strat}_losses_std']  for t in topos]
    ax1.bar(x + (i - 1.5) * w, means, w, yerr=stds, label=label,
            color=col, alpha=0.85, capsize=4)
ax1.set_title('Packet Loss', fontweight='bold')
ax1.set_ylabel('Packets lost (mean ± std)')
ax1.set_xticks(x)
ax1.set_xticklabels(topos)
ax1.legend(fontsize=9, loc='upper right')
ax1.grid(axis='y', alpha=0.3)

ax2 = fig.add_subplot(gs[1])
for i, (strat, label, col) in enumerate(zip(strats, strat_labels, colors)):
    means = [real[t][f'{strat}_lat_delivered_mean'] for t in topos]
    stds  = [real[t][f'{strat}_lat_delivered_std']  for t in topos]
    ax2.bar(x + (i - 1.5) * w, means, w, yerr=stds, label=label,
            color=col, alpha=0.85, capsize=4)
ax2.set_title('Latency per Delivered Packet', fontweight='bold')
ax2.set_ylabel('Lat / delivered (mean ± std)')
ax2.set_xticks(x)
ax2.set_xticklabels(topos)
ax2.legend(fontsize=9, loc='upper right')
ax2.grid(axis='y', alpha=0.3)

plt.savefig(PAPER_DIR / 'emmet_battery_real.png', dpi=180, bbox_inches='tight')
plt.savefig(NB_DIR    / 'emmet_battery_real.png', dpi=180, bbox_inches='tight')
print('Real topologies figure saved.')
plt.close()

# ----------------------------------------------------------------
# FIGURE 3 — phase transition: thermal advantage vs density (n=20)
# ----------------------------------------------------------------
n20 = synthetic[20]
densities = [d for d, _ in n20]
em_l = [s['emmet_cold_losses_mean']    for _, s in n20]
et_l = [s['emmet_thermal_losses_mean'] for _, s in n20]
la_l = [s['lasp_losses_mean']          for _, s in n20]

# % advantage of thermal vs LASP
adv_cold = []
adv_therm = []
for i in range(len(la_l)):
    if la_l[i] > 0.01:
        adv_cold.append((la_l[i] - em_l[i]) / la_l[i] * 100)
        adv_therm.append((la_l[i] - et_l[i]) / la_l[i] * 100)
    else:
        adv_cold.append(0)
        adv_therm.append(0)

fig, ax = plt.subplots(figsize=(10, 6))
ax.fill_between(densities, 0, adv_therm, alpha=0.20, color=COL_ET,
                label='EMMET thermal advantage zone')
ax.plot(densities, adv_cold,  '^--', color=COL_EM, lw=2, label='EMMET cold vs LASP')
ax.plot(densities, adv_therm, 'D-',  color=COL_ET, lw=2, label='EMMET thermal vs LASP')
ax.axhline(0, color='gray', lw=0.8, ls=':')
ax.axvspan(0.15, 0.30, alpha=0.12, color='orange', label='Transition zone')
ax.set_title('EMMET Loss Reduction vs LASP — Density Sweep (n=20, 100 seeds)',
             fontweight='bold')
ax.set_xlabel('Network density (p)')
ax.set_ylabel('Loss reduction vs LASP (%)')
ax.legend(fontsize=10, loc='upper right')
ax.grid(alpha=0.3)
plt.savefig(PAPER_DIR / 'emmet_thermal_advantage.png', dpi=180, bbox_inches='tight')
plt.savefig(NB_DIR    / 'emmet_thermal_advantage.png', dpi=180, bbox_inches='tight')
print('Thermal advantage figure saved.')
plt.close()

print('\nAll battery figures written to paper/ and notebooks/.')
