import json
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.gridspec import GridSpec

# ----------------------------
# Cargar datos del barrido
# ----------------------------
with open('/home/clopez/emmet/data/density_sweep_results.json', 'r') as f:
    results = json.load(f)

densities     = [r['density']      for r in results]
sp_lpp_m      = [r['sp_lpp_mean']  for r in results]
sp_lpp_s      = [r['sp_lpp_std']   for r in results]
fx_lpp_m      = [r['fx_lpp_mean']  for r in results]
fx_lpp_s      = [r['fx_lpp_std']   for r in results]
sp_loss_m     = [r['sp_loss_mean'] for r in results]
sp_loss_s     = [r['sp_loss_std']  for r in results]
fx_loss_m     = [r['fx_loss_mean'] for r in results]
fx_loss_s     = [r['fx_loss_std']  for r in results]
delta_lat     = [r['delta_lat']    for r in results]
losses_saved  = [r['losses_saved'] for r in results]
connected_pct = [r['connected_pct']for r in results]
fx_dead       = [r['fx_dead_mean'] for r in results]

COL_SP   = '#185FA5'
COL_FX   = '#0F6E56'
COL_CONN = '#888888'
COL_ZONE = '#FFF3CD'

# ----------------------------
# FIGURA PRINCIPAL — 2x2
# ----------------------------
fig = plt.figure(figsize=(15, 11))
fig.suptitle(
    'EMMET Phase Transition: Field Collapse as a Function of Network Density\n'
    r'$P = \alpha \cdot dist + \beta \cdot congestion + \gamma \cdot loss$'
    f'   |   α=1.0  β=3.0  γ=2.0  |  20 nodes  |  30 runs per point',
    fontsize=12, fontweight='bold', y=1.01
)
gs = GridSpec(2, 2, figure=fig, hspace=0.38, wspace=0.30)

# Zona de transición
TRANSITION_LOW  = 0.15
TRANSITION_HIGH = 0.30

def shade_transition(ax):
    ax.axvspan(TRANSITION_LOW, TRANSITION_HIGH,
               alpha=0.18, color='orange', label='Transition zone')
    ax.axvline(TRANSITION_LOW,  color='orange', lw=1.0, ls='--', alpha=0.7)
    ax.axvline(TRANSITION_HIGH, color='orange', lw=1.0, ls='--', alpha=0.7)

# ---- Panel 1: Latencia por paquete ----
ax1 = fig.add_subplot(gs[0, 0])
ax1.plot(densities, sp_lpp_m, 'o-', color=COL_SP, lw=2, label='Shortest Path')
ax1.fill_between(densities,
                 [m-s for m,s in zip(sp_lpp_m, sp_lpp_s)],
                 [m+s for m,s in zip(sp_lpp_m, sp_lpp_s)],
                 alpha=0.15, color=COL_SP)
ax1.plot(densities, fx_lpp_m, 's--', color=COL_FX, lw=2, label='EMMET')
ax1.fill_between(densities,
                 [m-s for m,s in zip(fx_lpp_m, fx_lpp_s)],
                 [m+s for m,s in zip(fx_lpp_m, fx_lpp_s)],
                 alpha=0.15, color=COL_FX)
shade_transition(ax1)
ax1.set_title('Latency per Packet (mean ± std)', fontweight='bold')
ax1.set_xlabel('Network Density (p)')
ax1.set_ylabel('Latency per packet')
ax1.legend(fontsize=9)
ax1.grid(alpha=0.25)

# ---- Panel 2: Pérdidas ----
ax2 = fig.add_subplot(gs[0, 1])
ax2.plot(densities, sp_loss_m, 'o-', color=COL_SP, lw=2, label='Shortest Path')
ax2.fill_between(densities,
                 [max(0,m-s) for m,s in zip(sp_loss_m, sp_loss_s)],
                 [m+s for m,s in zip(sp_loss_m, sp_loss_s)],
                 alpha=0.15, color=COL_SP)
ax2.plot(densities, fx_loss_m, 's--', color=COL_FX, lw=2, label='EMMET')
ax2.fill_between(densities,
                 [max(0,m-s) for m,s in zip(fx_loss_m, fx_loss_s)],
                 [m+s for m,s in zip(fx_loss_m, fx_loss_s)],
                 alpha=0.15, color=COL_FX)
shade_transition(ax2)
ax2.set_title('Packet Loss (mean ± std)', fontweight='bold')
ax2.set_xlabel('Network Density (p)')
ax2.set_ylabel('Packets lost')
ax2.legend(fontsize=9)
ax2.grid(alpha=0.25)

# ---- Panel 3: Delta latencia + conectividad ----
ax3 = fig.add_subplot(gs[1, 0])
ax3b = ax3.twinx()

ax3.axhline(0, color='gray', lw=0.8, ls=':')
ax3.plot(densities, delta_lat, 'D-', color='#8B0000', lw=2, label='Δ lat/packet (%)')
ax3.fill_between(densities, 0, delta_lat,
                 where=[d >= 0 for d in delta_lat],
                 alpha=0.12, color='#8B0000', label='EMMET slower (expected cost)')
ax3.fill_between(densities, 0, delta_lat,
                 where=[d < 0 for d in delta_lat],
                 alpha=0.20, color='green', label='EMMET faster (emergent regime)')
shade_transition(ax3)

ax3b.plot(densities, connected_pct, '^:', color=COL_CONN, lw=1.5,
          alpha=0.7, label='% connected graphs')
ax3b.set_ylabel('% connected graphs', color=COL_CONN, fontsize=9)
ax3b.tick_params(axis='y', labelcolor=COL_CONN)

ax3.set_title('Δ Latency & Connectivity vs Density', fontweight='bold')
ax3.set_xlabel('Network Density (p)')
ax3.set_ylabel('Δ latency (%)')
lines1, labels1 = ax3.get_legend_handles_labels()
lines2, labels2 = ax3b.get_legend_handles_labels()
ax3.legend(lines1 + lines2, labels1 + labels2, fontsize=8, loc='lower right')
ax3.grid(alpha=0.25)

# ---- Panel 4: Losses saved + dead ends ----
ax4 = fig.add_subplot(gs[1, 1])
ax4b = ax4.twinx()

bars = ax4.bar(densities, losses_saved, width=0.03,
               color=COL_FX, alpha=0.75, label='Losses saved by EMMET')
shade_transition(ax4)

ax4b.plot(densities, fx_dead, 'v:', color='#CC5500', lw=1.8,
          label='Dead ends (EMMET)', alpha=0.85)
ax4b.set_ylabel('Dead ends (avg)', color='#CC5500', fontsize=9)
ax4b.tick_params(axis='y', labelcolor='#CC5500')

ax4.set_title('Losses Saved & Dead Ends vs Density', fontweight='bold')
ax4.set_xlabel('Network Density (p)')
ax4.set_ylabel('Losses saved (avg)')
lines1, labels1 = ax4.get_legend_handles_labels()
lines2, labels2 = ax4b.get_legend_handles_labels()
ax4.legend(lines1 + lines2, labels1 + labels2, fontsize=8, loc='upper right')
ax4.grid(alpha=0.25, axis='y')

# Anotación knee point
ax4.annotate('Knee point\nρ ≈ 0.15–0.30',
             xy=(0.225, max(losses_saved)*0.6),
             fontsize=8, color='darkorange', fontweight='bold',
             ha='center')

plt.savefig('/home/clopez/emmet/paper/emmet_phase_transition.png',
            dpi=180, bbox_inches='tight')
plt.savefig('/home/clopez/emmet/notebooks/emmet_phase_transition.png',
            dpi=180, bbox_inches='tight')
print('Figures saved.')
plt.show()
