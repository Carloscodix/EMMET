"""Final comparative figure for the paper: SP, LASP, EMMET cold, EMMET thermal
across synthetic Erdos-Renyi and real Internet topologies (v6 audit-clean)."""
import json
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec

with open('/home/clopez/emmet/data/thermal_v6_results.json', 'r') as f:
    results = json.load(f)

scenarios = [r['scenario'] for r in results]
labels_clean = ['ER ρ=0.15', 'ER ρ=0.30', 'ER ρ=0.50', 'Abilene', 'GEANT']

sp_l   = [r['sp_loss_mean'] for r in results]
sp_ls  = [r['sp_loss_std']  for r in results]
la_l   = [r['la_loss_mean'] for r in results]
la_ls  = [r['la_loss_std']  for r in results]
em_l   = [r['em_loss_mean'] for r in results]
em_ls  = [r['em_loss_std']  for r in results]
et_l   = [r['et_loss_mean'] for r in results]
et_ls  = [r['et_loss_std']  for r in results]

sp_la  = [r['sp_lpp_mean']  for r in results]
sp_las = [r['sp_lpp_std']   for r in results]
la_la  = [r['la_lpp_mean']  for r in results]
la_las = [r['la_lpp_std']   for r in results]
em_la  = [r['em_lpp_mean']  for r in results]
em_las = [r['em_lpp_std']   for r in results]
et_la  = [r['et_lpp_mean']  for r in results]
et_las = [r['et_lpp_std']   for r in results]

COL_SP = '#185FA5'
COL_LA = '#CC8400'
COL_EM = '#5BAA8C'
COL_ET = '#0F6E56'

x = np.arange(len(scenarios))
w = 0.20

fig = plt.figure(figsize=(15, 10))
fig.suptitle(
    'EMMET vs Baselines on Synthetic and Real Internet Topologies (v6 audit-clean)\n'
    'α=1.0  β=3.0  γ=2.0  |  half-life=100  |  ε=0.05  |  30 runs per scenario',
    fontsize=12, fontweight='bold', y=1.00
)
gs = GridSpec(2, 1, figure=fig, hspace=0.42)

# Losses
ax1 = fig.add_subplot(gs[0])
ax1.bar(x - 1.5*w, sp_l, w, yerr=sp_ls, label='SP',
        color=COL_SP, alpha=0.85, capsize=3)
ax1.bar(x - 0.5*w, la_l, w, yerr=la_ls, label='LASP',
        color=COL_LA, alpha=0.85, capsize=3)
ax1.bar(x + 0.5*w, em_l, w, yerr=em_ls, label='EMMET cold',
        color=COL_EM, alpha=0.85, capsize=3)
ax1.bar(x + 1.5*w, et_l, w, yerr=et_ls, label='EMMET thermal',
        color=COL_ET, alpha=0.85, capsize=3)
ax1.set_title('Packet Loss (lower is better)', fontweight='bold')
ax1.set_ylabel('Packets lost (mean ± std)')
ax1.set_xticks(x)
ax1.set_xticklabels(labels_clean)
ax1.legend(fontsize=9, ncol=4, loc='upper right')
ax1.grid(axis='y', alpha=0.3)

# Latency
ax2 = fig.add_subplot(gs[1])
ax2.bar(x - 1.5*w, sp_la, w, yerr=sp_las, label='SP',
        color=COL_SP, alpha=0.85, capsize=3)
ax2.bar(x - 0.5*w, la_la, w, yerr=la_las, label='LASP',
        color=COL_LA, alpha=0.85, capsize=3)
ax2.bar(x + 0.5*w, em_la, w, yerr=em_las, label='EMMET cold',
        color=COL_EM, alpha=0.85, capsize=3)
ax2.bar(x + 1.5*w, et_la, w, yerr=et_las, label='EMMET thermal',
        color=COL_ET, alpha=0.85, capsize=3)
ax2.set_title('Latency per Packet (lower is better)', fontweight='bold')
ax2.set_ylabel('Latency per packet (mean ± std)')
ax2.set_xticks(x)
ax2.set_xticklabels(labels_clean)
ax2.legend(fontsize=9, ncol=4, loc='upper right')
ax2.grid(axis='y', alpha=0.3)

plt.savefig('/home/clopez/emmet/paper/emmet_v6_comparison.png',
            dpi=180, bbox_inches='tight')
plt.savefig('/home/clopez/emmet/notebooks/emmet_v6_comparison.png',
            dpi=180, bbox_inches='tight')
print('v6 comparison figure saved.')
