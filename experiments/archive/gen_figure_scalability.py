"""Generate paper/figure_scalability.pdf — WS scaling trend with CI bars."""
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from pathlib import Path

REPO = Path('/home/clopez/emmet')
boot = json.load(open(REPO / 'data/scalability_phaseA_bootstrap.json'))
boot_by = {r['scenario']: r for r in boot}

ns = [100, 250, 500]
rels = []
lo_err = []
hi_err = []
for n in ns:
    b = boot_by[f'WS_n{n}_k4_p0.10']
    rel = b['rel_total_pct']
    ci = b['rel_ci95']
    rels.append(rel)
    lo_err.append(max(0, rel - ci[0]))
    hi_err.append(max(0, ci[1] - rel))

fig, ax = plt.subplots(figsize=(5.5, 3.6))
ax.errorbar(ns, rels, yerr=[lo_err, hi_err], fmt='o-',
            color='#0b6e4f', ecolor='#0b6e4f', capsize=4, lw=1.8,
            markersize=7, label='WS small-world (k=4, p=0.10)')
ax.set_xlabel('Network size $n$ (nodes)', fontsize=11)
ax.set_ylabel('Relative loss reduction (\\%)', fontsize=10)
ax.set_xscale('log')
ax.set_xticks(ns)
ax.set_xticklabels([str(n) for n in ns])
ax.set_ylim(0, 110)
ax.grid(True, alpha=0.3, linestyle=':')
ax.axhline(y=0, color='black', lw=0.5)
ax.set_title('EMMET-DP scaling on WS small-world (100 seeds/config)', fontsize=9)
ax.legend(loc='lower right', fontsize=9)
plt.tight_layout()
out = REPO / 'paper/figure_scalability.pdf'
plt.savefig(out, dpi=300, bbox_inches='tight')
print(f'Wrote {out}')
