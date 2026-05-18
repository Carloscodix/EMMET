"""Definitive cross-topology bursty test - POST CODEX AUDIT.
Fixes: GAMMA leak, snap decay during gaps, intra-burst feedback."""
import sys
sys.path.insert(0, '/home/clopez/emmet/experiments')
import emmet_budget
from emmet_budget import build_real, reset
from topology_builders import build_grid, build_watts_strogatz
from bursty_traffic import gen_bursty
from bursty_warmup import (warmup_bursty_lasp, warmup_bursty_conga,
                            warmup_bursty_momentum)
from bursty_runner import (run_bursty_lasp, run_bursty_conga,
                            run_bursty_emmet, run_bursty_emmet_live,
                            run_bursty_emmet_live_delayed)

STEPS = 200
N = 30
GAMMA_OPT = 0.5
BR_OPT = 10.0
BR_DEF = 5.0

TOPOS = [
    ('GEANT',   lambda s: build_real('Geant.graphml', s)),
    ('Abilene', lambda s: build_real('Abilene.graphml', s)),
    ('Grid7x7', lambda s: build_grid(7, s)),
    ('WS_n50',  lambda s: build_watts_strogatz(50, 4, 0.1, s)),
    ('Grid10',  lambda s: build_grid(10, s)),
]

def run_topo(builder):
    res = {'LASP':0, 'CONGA':0, 'v1':0, 'LIVE_def':0,
           'LIVE_opt':0, 'DELAY_def':0, 'DELAY_opt':0}
    for s in range(N):
        emmet_budget.GAMMA = 2.0
        ws = max(20, builder(s).number_of_nodes()*5)
        # LASP (uses GAMMA=2.0 via edge_potential)
        G = builder(s); reset(G)
        wt = gen_bursty(list(G.nodes()), ws, s + 700000)
        snap_l = warmup_bursty_lasp(G, wt)
        G2 = builder(s); reset(G2)
        traf = gen_bursty(list(G2.nodes()), STEPS, s + 100000)
        res['LASP'] += run_bursty_lasp(G2, traf, snap_l)['losses']
        # CONGA (no snap, no GAMMA)
        G3 = builder(s); reset(G3)
        traf3 = gen_bursty(list(G3.nodes()), STEPS, s + 100000)
        res['CONGA'] += run_bursty_conga(G3, traf3)['losses']
        # EMMET v1, LIVE_def, DELAY_def all with GAMMA=2.0
        G4 = builder(s); reset(G4)
        wt4 = gen_bursty(list(G4.nodes()), ws, s + 700000)
        snap_m = warmup_bursty_momentum(G4, wt4, 1.0, 32)
        G5 = builder(s); reset(G5)
        traf5 = gen_bursty(list(G5.nodes()), STEPS, s + 100000)
        res['v1'] += run_bursty_emmet(G5, traf5, snap_m, 1.0, 32)['losses']
        G6 = builder(s); reset(G6)
        traf6 = gen_bursty(list(G6.nodes()), STEPS, s + 100000)
        res['LIVE_def'] += run_bursty_emmet_live(G6, traf6, snap_m, 1.0, 32, blood_rate=BR_DEF)['losses']
        G7 = builder(s); reset(G7)
        traf7 = gen_bursty(list(G7.nodes()), STEPS, s + 100000)
        res['DELAY_def'] += run_bursty_emmet_live_delayed(G7, traf7, snap_m, 1.0, 32, blood_rate=BR_DEF)['losses']
        # LIVE_opt and DELAY_opt with GAMMA=0.5 - then RESTORE
        emmet_budget.GAMMA = GAMMA_OPT
        G8 = builder(s); reset(G8)
        wt8 = gen_bursty(list(G8.nodes()), ws, s + 700000)
        snap_o = warmup_bursty_momentum(G8, wt8, 1.0, 32)
        G9 = builder(s); reset(G9)
        traf9 = gen_bursty(list(G9.nodes()), STEPS, s + 100000)
        res['LIVE_opt'] += run_bursty_emmet_live(G9, traf9, snap_o, 1.0, 32, blood_rate=BR_OPT)['losses']
        G10 = builder(s); reset(G10)
        traf10 = gen_bursty(list(G10.nodes()), STEPS, s + 100000)
        res['DELAY_opt'] += run_bursty_emmet_live_delayed(G10, traf10, snap_o, 1.0, 32, blood_rate=BR_OPT)['losses']
        emmet_budget.GAMMA = 2.0  # RESTORE
    return res

print(f'POST-AUDIT bursty cross-topo, n={N}')
print(f'def: gamma=2.0, br=5.0  |  opt: gamma={GAMMA_OPT}, br={BR_OPT}')
print(f'LIVE: blood applied immediately on packet death (orig)')
print(f'DELAY: blood buffered during burst, flushed on GAP (Codex P1 fix)')
print()
hdr = f'{"Topo":<10} {"LASP":>5} {"CONGA":>5} {"v1":>5} {"Ldef":>5} {"Lopt":>5} {"Ddef":>5} {"Dopt":>5}'
print(hdr)
print('-' * len(hdr))
results = {}
for name, builder in TOPOS:
    r = run_topo(builder)
    results[name] = r
    print(f'{name:<10} {r["LASP"]:>5} {r["CONGA"]:>5} {r["v1"]:>5} {r["LIVE_def"]:>5} {r["LIVE_opt"]:>5} {r["DELAY_def"]:>5} {r["DELAY_opt"]:>5}', flush=True)

print()
print('=== Relative reductions (positive = our arm wins) ===')
def rel(ref, x):
    return f'{(ref-x)/ref*100:+.1f}%' if ref else 'n/a'
print(f'{"Topo":<10} {"Lopt vs LASP":>13} {"Lopt vs CONGA":>14} {"Dopt vs LASP":>13} {"Dopt vs CONGA":>14}')
for name, r in results.items():
    L, C = r['LASP'], r['CONGA']
    Lo, Do = r['LIVE_opt'], r['DELAY_opt']
    print(f'{name:<10} {rel(L, Lo):>13} {rel(C, Lo):>14} {rel(L, Do):>13} {rel(C, Do):>14}')
