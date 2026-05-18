"""Cross-topology BLOOD LIVE: GEANT, Abilene, Grid_7x7, WS_n50_k4_p0.1."""
import sys
sys.path.insert(0, '/home/clopez/emmet/experiments')
from emmet_budget import build_real, reset
from topology_builders import build_grid, build_watts_strogatz
from bursty_traffic import gen_bursty
from bursty_warmup import (warmup_bursty_lasp, warmup_bursty_conga,
                            warmup_bursty_momentum)
from bursty_runner import (run_bursty_lasp, run_bursty_conga,
                            run_bursty_emmet, run_bursty_emmet_live)

STEPS = 200
N = 20
BR = 5.0

TOPOS = [
    ('GEANT',   lambda s: build_real('Geant.graphml', s)),
    ('Abilene', lambda s: build_real('Abilene.graphml', s)),
    ('Grid7x7', lambda s: build_grid(7, s)),
    ('WS_n50',  lambda s: build_watts_strogatz(50, 4, 0.1, s)),
]

def run_topo(name, builder, n_seeds):
    res = {'LASP': 0, 'CONGA': 0, 'EMMET_v1': 0, 'BLOOD': 0}
    for s in range(n_seeds):
        G = builder(s); reset(G)
        ws = max(20, G.number_of_nodes()*5)
        wt = gen_bursty(list(G.nodes()), ws, s + 700000)
        snap_l = warmup_bursty_lasp(G, wt)
        G2 = builder(s); reset(G2)
        traf = gen_bursty(list(G2.nodes()), STEPS, s + 100000)
        res['LASP'] += run_bursty_lasp(G2, traf, snap_l)['losses']
        G3 = builder(s); reset(G3)
        traf3 = gen_bursty(list(G3.nodes()), STEPS, s + 100000)
        res['CONGA'] += run_bursty_conga(G3, traf3)['losses']
        G4 = builder(s); reset(G4)
        wt4 = gen_bursty(list(G4.nodes()), ws, s + 700000)
        snap_m = warmup_bursty_momentum(G4, wt4, 1.0, 32)
        G5 = builder(s); reset(G5)
        traf5 = gen_bursty(list(G5.nodes()), STEPS, s + 100000)
        res['EMMET_v1'] += run_bursty_emmet(G5, traf5, snap_m, 1.0, 32)['losses']
        G6 = builder(s); reset(G6)
        traf6 = gen_bursty(list(G6.nodes()), STEPS, s + 100000)
        res['BLOOD'] += run_bursty_emmet_live(G6, traf6, snap_m, 1.0, 32, blood_rate=BR)['losses']
    return res

print(f'Cross-topo BURSTY, n={N}, BR={BR}')
print(f'{"Topo":<10} {"LASP":>6} {"CONGA":>6} {"EMMETv1":>8} {"BLOOD":>6} {"BLOOD vs LASP":>14} {"BLOOD vs CONGA":>15}')
print('-' * 80)
for name, builder in TOPOS:
    r = run_topo(name, builder, N)
    L, C, E, B = r['LASP'], r['CONGA'], r['EMMET_v1'], r['BLOOD']
    rel_L = (L - B) / max(L, 1) * 100
    rel_C = (C - B) / max(C, 1) * 100
    print(f'{name:<10} {L:>6} {C:>6} {E:>8} {B:>6} {rel_L:>+13.1f}% {rel_C:>+14.1f}%', flush=True)
