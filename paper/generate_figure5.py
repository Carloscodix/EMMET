"""Generate Figure 5: kappa sweep curves.

For each scenario in the kappa sweep, plot loss reduction (%) as a
function of kappa, showing kappa=1.0 as the Pareto sweet spot.

Output: paper/figure5_kappa_sweep.pdf
"""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

REPO = Path('/home/clopez/emmet')
DATA = REPO / 'data'
PAPER = REPO / 'paper'

sweep = json.load(open(DATA / 'momentum_clean_kappa_sweep_summary.json'))

# Pivot: scenario -> {kappa: delta_pct}
by_scenario = {}
for r in sweep:
    sc = r['scenario']
    k = r['kappa']
    la = r['lasp_aug_losses_mean']
    mom = r['momentum_dp_losses_mean']
    delta = (la - mom) / la * 100 if la > 0 else 0
    by_scenario.setdefault(sc, {})[k] = delta

# Plot
plt.rcParams.update({
    'font.family': 'serif',
    'font.size': 10,
    'axes.labelsize': 11,
    'axes.spines.top': False,
    'axes.spines.right': False,
})
fig, ax = plt.subplots(figsize=(6, 4))

scenario_styles = {
    'GEANT':         {'color': '#D62728', 'marker': 'o', 'lw': 2.0},
    'Abilene':       {'color': '#FF7F0E', 'marker': 's', 'lw': 1.4},
    'ER_n50_p0.05':  {'color': '#2E78B7', 'marker': '^', 'lw': 1.4},
    'ER_n50_p0.10':  {'color': '#2CA02C', 'marker': 'D', 'lw': 1.4},
    'ER_n20_p0.20':  {'color': '#9467BD', 'marker': 'v', 'lw': 1.4},
}

for sc in ['GEANT', 'Abilene', 'ER_n50_p0.05', 'ER_n50_p0.10', 'ER_n20_p0.20']:
    if sc not in by_scenario:
        continue
    kappas = sorted(by_scenario[sc].keys())
    deltas = [by_scenario[sc][k] for k in kappas]
    style = scenario_styles[sc]
    ax.plot(kappas, deltas, marker=style['marker'], color=style['color'],
            linewidth=style['lw'], markersize=6,
            label=sc.replace('_', ' '))

# Annotate kappa=1.0 as chosen value
ax.axvline(1.0, linestyle='--', color='gray', linewidth=0.8, alpha=0.6)
ax.text(1.02, ax.get_ylim()[1] * 0.95, r'$\kappa{=}1.0$ (chosen)',
        fontsize=8.5, color='gray')

ax.axhline(0, color='black', linewidth=0.5)
ax.set_xlabel(r'$\kappa$ (mass growth rate)')
ax.set_ylabel('Loss reduction (%)')
ax.set_xlim(-0.05, 1.6)
ax.legend(loc='lower right', frameon=False, fontsize=9)
ax.grid(True, alpha=0.25)

plt.tight_layout()
out = PAPER / 'figure5_kappa_sweep.pdf'
plt.savefig(out, bbox_inches='tight')
print(f"Figure 5 written to {out}")
