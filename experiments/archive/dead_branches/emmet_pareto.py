"""Pareto frontier analysis with all six strategies.

Reads data/adaptive_summary.json (6 strategies: SP, LASP, EMMET cold,
EMMET thermal, EMMET adaptive, EMMET full).

For each scenario, identifies which strategies are Pareto-optimal in the
(latency-per-delivered, mean-loss) plane. Saves:
  - data/pareto_summary.json  (per-scenario optimal sets)
  - paper/emmet_pareto.png    (scatter plots, representative scenarios)
  - paper/emmet_pareto_dominance.png  (count chart)
"""
import json
from pathlib import Path
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec

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

def is_dominated(point, others):
    px, py = point
    for ox, oy in others:
        if (ox <= px and oy <= py) and (ox < px or oy < py):
            return True
    return False

def pareto_analysis(scen):
    points = {k: (scen[f'{k}_lat_delivered_mean'],
                  scen[f'{k}_losses_mean']) for k, _, _, _ in STRATS}
    keys = list(points.keys())
    optimal = {k: not is_dominated(points[k],
                                    [points[k2] for k2 in keys if k2 != k])
               for k in keys}
    return optimal, points

# ---------- per-scenario analysis ----------
analysis = []
for s in summary:
    optimal, points = pareto_analysis(s)
    analysis.append({
        'scenario': s['scenario'],
        'n_runs':   s['n_runs'],
        'optimal_strategies': [k for k, v in optimal.items() if v],
        'points': {k: list(p) for k, p in points.items()},
    })

with open(DATA_DIR / 'pareto_summary.json', 'w') as f:
    json.dump(analysis, f, indent=2)

print("=== Pareto-optimal strategies per scenario (6 strategies) ===")
print(f"{'Scenario':<24} {'N':>4} Pareto-optimal")
print('-' * 90)
for a in analysis:
    print(f"{a['scenario']:<24} {a['n_runs']:>4} {', '.join(a['optimal_strategies'])}")

# ---------- counts ----------
counts = {k: 0 for k, _, _, _ in STRATS}
for a in analysis:
    for s in a['optimal_strategies']:
        counts[s] += 1
total = len(analysis)
print(f"\n=== Pareto dominance count (out of {total} scenarios) ===")
for k, label, _, _ in STRATS:
    print(f"  {label:<16} {counts[k]:>3} / {total}  ({counts[k]/total*100:.0f}%)")

# ---------- main figure ----------
showcase = [
    'ER_n20_p0.10', 'ER_n20_p0.15', 'ER_n20_p0.30',
    'ER_n50_p0.05', 'Abilene', 'GEANT',
]
showcase_data = {a['scenario']: a for a in analysis if a['scenario'] in showcase}

fig = plt.figure(figsize=(15, 10))
fig.suptitle(
    'Pareto Frontier: Latency vs Packet Loss (six strategies, 100 seeds per point)\n'
    'Lower-left is better. Stars mark Pareto-optimal strategies.',
    fontsize=12, fontweight='bold', y=1.00
)
gs = GridSpec(2, 3, figure=fig, hspace=0.40, wspace=0.30)

for idx, scen in enumerate(showcase):
    if scen not in showcase_data:
        continue
    a = showcase_data[scen]
    ax = fig.add_subplot(gs[idx // 3, idx % 3])
    for k, label, col, marker in STRATS:
        x, y = a['points'][k]
        is_opt = k in a['optimal_strategies']
        size = 220 if is_opt else 90
        edge = 'black' if is_opt else 'none'
        lw   = 2 if is_opt else 0
        ax.scatter(x, y, s=size, c=col, marker=marker, label=label,
                   edgecolors=edge, linewidths=lw, alpha=0.9, zorder=3)
        if is_opt:
            ax.scatter(x, y, s=420, c='none', edgecolors='gold',
                       linewidths=1.5, marker='*', alpha=0.6, zorder=2)
    ax.set_title(scen, fontweight='bold', fontsize=10)
    ax.set_xlabel('Latency / delivered (mean)')
    ax.set_ylabel('Packets lost (mean)')
    ax.legend(fontsize=6, loc='best', ncol=2)
    ax.grid(alpha=0.3)

plt.savefig(PAPER_DIR / 'emmet_pareto.png', dpi=180, bbox_inches='tight')
plt.savefig(NB_DIR    / 'emmet_pareto.png', dpi=180, bbox_inches='tight')
print('\nFigure saved.')
plt.close()

# ---------- dominance chart ----------
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
    f'Pareto-Optimal Frequency Across {total} Scenarios (six strategies)',
    fontweight='bold', fontsize=11
)
ax.set_ylabel('Scenarios where strategy is Pareto-optimal')
ax.set_ylim(0, total + 2)
ax.grid(axis='y', alpha=0.3)
plt.xticks(rotation=15)
plt.tight_layout()
plt.savefig(PAPER_DIR / 'emmet_pareto_dominance.png', dpi=180, bbox_inches='tight')
plt.savefig(NB_DIR    / 'emmet_pareto_dominance.png', dpi=180, bbox_inches='tight')
print('Dominance chart saved.')
