import json
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec

with open('/home/clopez/emmet/data/ecmp_baseline_results.json', 'r') as f:
    results = json.load(f)

scenarios = [r['scenario'] for r in results]
sp_loss   = [r['sp_loss_mean'] for r in results]
sp_loss_s = [r['sp_loss_std']  for r in results]
ec_loss   = [r['ec_loss_mean'] for r in results]
ec_loss_s = [r['ec_loss_std']  for r in results]
em_loss   = [r['em_loss_mean'] for r in results]
em_loss_s = [r['em_loss_std']  for r in results]
sp_lat    = [r['sp_lpp_mean']  for r in results]
sp_lat_s  = [r['sp_lpp_std']   for r in results]
ec_lat    = [r['ec_lpp_mean']  for r in results]
ec_lat_s  = [r['ec_lpp_std']   for r in results]
em_lat    = [r['em_lpp_mean']  for r in results]
em_lat_s  = [r['em_lpp_std']   for r in results]

COL_SP = '#185FA5'
COL_EC = '#CC8400'
COL_EM = '#0F6E56'

x = np.arange(len(scenarios))
w = 0.27

fig = plt.figure(figsize=(15, 9))
fig.suptitle(
    'EMMET vs ECMP vs Shortest Path on Synthetic and Real Topologies\n'
    f'30 runs per scenario | alpha=1.0 beta=3.0 gamma=2.0 | mean ± std',
    fontsize=12, fontweight='bold', y=1.01
)
gs = GridSpec(2, 1, figure=fig, hspace=0.45)

# Losses
ax1 = fig.add_subplot(gs[0])
ax1.bar(x - w, sp_loss, w, yerr=sp_loss_s, label='Shortest Path',
        color=COL_SP, alpha=0.85, capsize=4)
ax1.bar(x,     ec_loss, w, yerr=ec_loss_s, label='ECMP',
        color=COL_EC, alpha=0.85, capsize=4)
ax1.bar(x + w, em_loss, w, yerr=em_loss_s, label='EMMET',
        color=COL_EM, alpha=0.85, capsize=4)
ax1.set_title('Packet Loss (lower is better)', fontweight='bold')
ax1.set_ylabel('Packets lost (mean ± std)')
ax1.set_xticks(x)
ax1.set_xticklabels(scenarios, rotation=10)
ax1.legend()
ax1.grid(axis='y', alpha=0.3)

# Latency
ax2 = fig.add_subplot(gs[1])
ax2.bar(x - w, sp_lat, w, yerr=sp_lat_s, label='Shortest Path',
        color=COL_SP, alpha=0.85, capsize=4)
ax2.bar(x,     ec_lat, w, yerr=ec_lat_s, label='ECMP',
        color=COL_EC, alpha=0.85, capsize=4)
ax2.bar(x + w, em_lat, w, yerr=em_lat_s, label='EMMET',
        color=COL_EM, alpha=0.85, capsize=4)
ax2.set_title('Latency per Packet (lower is better)', fontweight='bold')
ax2.set_ylabel('Latency per packet (mean ± std)')
ax2.set_xticks(x)
ax2.set_xticklabels(scenarios, rotation=10)
ax2.legend()
ax2.grid(axis='y', alpha=0.3)

plt.savefig('/home/clopez/emmet/paper/emmet_vs_ecmp.png',
            dpi=180, bbox_inches='tight')
plt.savefig('/home/clopez/emmet/notebooks/emmet_vs_ecmp.png',
            dpi=180, bbox_inches='tight')
print('Comparative figure saved.')
