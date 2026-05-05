import json
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec

with open('/home/clopez/emmet/data/beta_sweep_results.json', 'r') as f:
    results = json.load(f)

betas        = [r['beta']         for r in results]
fx_lpp_m     = [r['fx_lpp_mean']  for r in results]
fx_lpp_s     = [r['fx_lpp_std']   for r in results]
fx_loss_m    = [r['fx_loss_mean'] for r in results]
fx_loss_s    = [r['fx_loss_std']  for r in results]
delta_lat    = [r['delta_lat']    for r in results]
losses_saved = [r['losses_saved'] for r in results]
sp_lpp       = results[0]['sp_lpp_mean']
sp_loss      = results[0]['sp_loss_mean']

COL_SP = '#185FA5'
COL_FX = '#0F6E56'

fig = plt.figure(figsize=(14, 9))
fig.suptitle(
    'EMMET Beta Sweep: The Physical Control Parameter\n'
    r'$P = \alpha \cdot dist + \beta \cdot congestion + \gamma \cdot loss$'
    f'   |   α=1.0  γ=2.0  |  density=0.30  |  20 nodes  |  30 runs per point',
    fontsize=12, fontweight='bold', y=1.01
)
gs = GridSpec(2, 2, figure=fig, hspace=0.40, wspace=0.30)

# Sweet spot zone
SWEET_LOW, SWEET_HIGH = 3.5, 4.0

def shade_sweet(ax):
    ax.axvspan(SWEET_LOW, SWEET_HIGH, alpha=0.18, color='green')
    ax.axvline(SWEET_LOW,  color='green', lw=1.0, ls='--', alpha=0.7)
    ax.axvline(SWEET_HIGH, color='green', lw=1.0, ls='--', alpha=0.7)

# Panel 1: Latencia
ax1 = fig.add_subplot(gs[0, 0])
ax1.axhline(sp_lpp, color=COL_SP, lw=1.5, ls=':', label=f'SP baseline ({sp_lpp:.3f})')
ax1.plot(betas, fx_lpp_m, 's-', color=COL_FX, lw=2, label='EMMET')
ax1.fill_between(betas,
                 [m-s for m,s in zip(fx_lpp_m, fx_lpp_s)],
                 [m+s for m,s in zip(fx_lpp_m, fx_lpp_s)],
                 alpha=0.15, color=COL_FX)
shade_sweet(ax1)
ax1.set_title('Latency per Packet vs Beta', fontweight='bold')
ax1.set_xlabel('Beta (congestion weight)')
ax1.set_ylabel('Latency per packet')
ax1.legend(fontsize=9)
ax1.grid(alpha=0.25)

# Panel 2: Pérdidas
ax2 = fig.add_subplot(gs[0, 1])
ax2.axhline(sp_loss, color=COL_SP, lw=1.5, ls=':', label=f'SP baseline ({sp_loss:.2f})')
ax2.plot(betas, fx_loss_m, 's-', color=COL_FX, lw=2, label='EMMET')
ax2.fill_between(betas,
                 [max(0, m-s) for m,s in zip(fx_loss_m, fx_loss_s)],
                 [m+s for m,s in zip(fx_loss_m, fx_loss_s)],
                 alpha=0.15, color=COL_FX)
shade_sweet(ax2)
ax2.set_title('Packet Loss vs Beta', fontweight='bold')
ax2.set_xlabel('Beta (congestion weight)')
ax2.set_ylabel('Packets lost (mean)')
ax2.legend(fontsize=9)
ax2.grid(alpha=0.25)
ax2.annotate('Zero loss\nregime',
             xy=(3.75, 0.01), fontsize=8,
             color='darkgreen', fontweight='bold', ha='center')

# Panel 3: Delta latencia
ax3 = fig.add_subplot(gs[1, 0])
ax3.plot(betas, delta_lat, 'D-', color='#8B0000', lw=2)
ax3.fill_between(betas, 0, delta_lat, alpha=0.12, color='#8B0000')
shade_sweet(ax3)
ax3.set_title('Delta Latency (%) vs Beta', fontweight='bold')
ax3.set_xlabel('Beta (congestion weight)')
ax3.set_ylabel('Δ latency vs SP (%)')
ax3.grid(alpha=0.25)
ax3.annotate('Sweet spot\nβ ≈ 3.5–4.0',
             xy=(3.75, max(delta_lat)*0.5), fontsize=8,
             color='darkgreen', fontweight='bold', ha='center')

# Panel 4: Losses saved
ax4 = fig.add_subplot(gs[1, 1])
ax4.bar(betas, losses_saved, width=0.3, color=COL_FX, alpha=0.75)
shade_sweet(ax4)
ax4.set_title('Losses Saved vs Beta', fontweight='bold')
ax4.set_xlabel('Beta (congestion weight)')
ax4.set_ylabel('Losses saved vs SP (avg)')
ax4.grid(alpha=0.25, axis='y')
ax4.annotate('Maximum\nsavings',
             xy=(3.75, max(losses_saved)*0.7), fontsize=8,
             color='darkgreen', fontweight='bold', ha='center')

plt.savefig('/home/clopez/emmet/paper/emmet_beta_sweep.png',
            dpi=180, bbox_inches='tight')
plt.savefig('/home/clopez/emmet/notebooks/emmet_beta_sweep.png',
            dpi=180, bbox_inches='tight')
print('Beta sweep figure saved.')
