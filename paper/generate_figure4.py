"""Generate Figure 4: bar chart of loss reduction across all 22 scenarios,
grouped by topology family.

Output: paper/figure4_battery.pdf

Uses matplotlib with serif font + tight figure to match LaTeX paper style.
"""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

REPO = Path('/home/clopez/emmet')
DATA = REPO / 'data'
PAPER = REPO / 'paper'

full = json.load(open(DATA / 'momentum_clean_full_summary.json'))
topo = json.load(open(DATA / 'topology_extended_summary.json'))

def family(sc):
    if sc.startswith('GEANT') or sc.startswith('Abilene'): return 'Real'
    if sc.startswith('ER_'): return 'ER'
    if sc.startswith('Grid'): return 'Grid'
    if sc.startswith('BA'): return 'BA'
    if sc.startswith('WS'): return 'WS'
    return '??'

rows = []
for r in full + topo:
    la = r['lasp_aug_losses_mean']
    mom = r['momentum_dp_losses_mean']
    if la == 0:
        continue  # skip zero-loss scenarios (uncongested)
    delta = (la - mom) / la * 100
    rows.append({'family': family(r['scenario']),
                 'scenario': r['scenario'].replace('_', ' '),
                 'delta': delta,
                 'la_loss': la})

# Sort by family then by delta (best improvements first within family)
family_order = ['Real', 'ER', 'Grid', 'BA', 'WS']
family_colors = {
    'Real': '#D62728',  # warmred
    'ER':   '#2E78B7',  # coolblue
    'Grid': '#2CA02C',  # packetgreen
    'BA':   '#FF7F0E',  # packetorange
    'WS':   '#9467BD',  # snapshotpurple
}
rows.sort(key=lambda r: (family_order.index(r['family']), -r['delta']))

# Plot
plt.rcParams.update({
    'font.family': 'serif',
    'font.size': 10,
    'axes.labelsize': 11,
    'axes.spines.top': False,
    'axes.spines.right': False,
})
fig, ax = plt.subplots(figsize=(7, max(4, 0.28 * len(rows))))

y_positions = list(range(len(rows)))
colors = [family_colors[r['family']] for r in rows]
deltas = [r['delta'] for r in rows]
labels = [r['scenario'] for r in rows]

bars = ax.barh(y_positions, deltas, color=colors, edgecolor='black',
               linewidth=0.4, height=0.7)

# Value labels at end of each bar
for i, (bar, d) in enumerate(zip(bars, deltas)):
    x = bar.get_width()
    ha = 'left' if x >= 0 else 'right'
    offset = 1.0 if x >= 0 else -1.0
    ax.text(x + offset, bar.get_y() + bar.get_height()/2,
            f"{d:+.0f}%", va='center', ha=ha, fontsize=8.5)

ax.set_yticks(y_positions)
ax.set_yticklabels(labels, fontsize=9)
ax.invert_yaxis()  # first row at top
ax.axvline(0, color='black', linewidth=0.5)
ax.set_xlabel('Loss reduction (\%) — higher is better')
ax.set_xlim(-5, max(deltas) * 1.18)

# Family legend
handles = [Patch(facecolor=family_colors[f], edgecolor='black',
                 linewidth=0.4, label=f) for f in family_order]
ax.legend(handles=handles, loc='lower right', frameon=False, fontsize=9)

plt.tight_layout()
out = PAPER / 'figure4_battery.pdf'
plt.savefig(out, bbox_inches='tight')
print(f"Figure 4 written to {out}")
print(f"Scenarios with non-zero loss: {len(rows)}")
