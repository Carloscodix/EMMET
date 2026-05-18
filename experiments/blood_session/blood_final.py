"""Definitive cross-topo bursty: BLOOD with optimized params (gamma=0.5, br=10) vs all."""
import sys
sys.path.insert(0, '/home/clopez/emmet/experiments')
import emmet_budget
from emmet_budget import build_real, reset
from topology_builders import build_grid, build_watts_strogatz
from bursty_traffic import gen_bursty
from bursty_warmup import (warmup_bursty_lasp, warmup_bursty_conga, warmup_bursty_momentum)
from bursty_runner import (run_bursty_lasp, run_bursty_conga, run_bursty_emmet, run_bursty_emmet_live)

STEPS = 200
N = 30
GAMMA_OPT = 0.5
BR_OPT = 10.0

TOPOS = [
    ('GEANT',   lambda s: build_real('Geant.graphml', s)),
    ('Abilene', lambda s: build_real('Abilene.graphml', s)),
    ('Grid7x7', lambda s: build_grid(7, s)),
    ('WS_n50',  lambda s: build_watts_strogatz(50, 4, 0.1, s)),
    ('Grid10',  lambda s: build_grid(10, s)),
]

def run_topo(name, builder):
    res = {'LASP': 0, 'CONGA': 0, 'EMMET_v1': 0, 'BLOOD_def': 0, 'BLOOD_opt': 0}
    for s in range(N):
        emmet_budget.GAMMA = 2.0  # Belt and suspenders: ensure default at start of each seed
        ws = max(20, builder(s).number_of_nodes()*5)
        G = builder(s); reset(G)
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
        emmet_budget.GAMMA = 2.0
        snap_m = warmup_bursty_momentum(G4, wt4, 1.0, 32)
        G5 = builder(s); reset(G5)
        traf5 = gen_bursty(list(G5.nodes()), STEPS, s + 100000)
        res['EMMET_v1'] += run_bursty_emmet(G5, traf5, snap_m, 1.0, 32)['losses']
        G6 = builder(s); reset(G6)
        traf6 = gen_bursty(list(G6.nodes()), STEPS, s + 100000)
        res['BLOOD_def'] += run_bursty_emmet_live(G6, traf6, snap_m, 1.0, 32, blood_rate=5.0)['losses']
        emmet_budget.GAMMA = GAMMA_OPT
        G7 = builder(s); reset(G7)
        wt7 = gen_bursty(list(G7.nodes()), ws, s + 700000)
        snap_o = warmup_bursty_momentum(G7, wt7, 1.0, 32)
        G8 = builder(s); reset(G8)
        traf8 = gen_bursty(list(G8.nodes()), STEPS, s + 100000)
        res['BLOOD_opt'] += run_bursty_emmet_live(G8, traf8, snap_o, 1.0, 32, blood_rate=BR_OPT)['losses']
        emmet_budget.GAMMA = 2.0  # RESTORE default for next iteration (LASP reads GAMMA)
    return res

print(f'DEFINITIVE bursty cross-topo, n={N}')
print(f'BLOOD_def: gamma=2.0, br=5.0  |  BLOOD_opt: gamma={GAMMA_OPT}, br={BR_OPT}')
print(f'{"Topo":<10} {"LASP":>5} {"CONGA":>5} {"EMMETv1":>7} {"BLOODdef":>8} {"BLOODopt":>8} {"opt vs LASP":>11} {"opt vs CONGA":>13}')
print('-' * 80)
for name, builder in TOPOS:
    r = run_topo(name, builder)
    L, C, E, Bd, Bo = r['LASP'], r['CONGA'], r['EMMET_v1'], r['BLOOD_def'], r['BLOOD_opt']
    rel_L = (L - Bo) / max(L, 1) * 100
    rel_C = (C - Bo) / max(C, 1) * 100
    print(f'{name:<10} {L:>5} {C:>5} {E:>7} {Bd:>8} {Bo:>8} {rel_L:>+10.1f}% {rel_C:>+12.1f}%', flush=True)
