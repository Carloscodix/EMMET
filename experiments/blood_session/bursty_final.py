"""Final bursty comparison: LASP-aug vs CONGA-WAN vs EMMET-DP vs EMMET-BLOOD-LIVE.
n=30 GEANT, blood_rate=5.0 (sweet spot from previous sweep)."""
import sys
sys.path.insert(0, '/home/clopez/emmet/experiments')
from emmet_budget import build_real, reset
from bursty_traffic import gen_bursty
from bursty_warmup import (
    warmup_bursty_lasp, warmup_bursty_conga, warmup_bursty_momentum
)
from bursty_runner import (
    run_bursty_lasp, run_bursty_conga, run_bursty_emmet, run_bursty_emmet_live
)

STEPS = 200
N = 30
BLOOD_RATE = 5.0

def seed_run(seed):
    out = {}
    ws = max(20, 40*5)
    G = build_real('Geant.graphml', seed); reset(G)
    wt = gen_bursty(list(G.nodes()), ws, seed + 700000)
    snap_l = warmup_bursty_lasp(G, wt)
    G2 = build_real('Geant.graphml', seed); reset(G2)
    traf = gen_bursty(list(G2.nodes()), STEPS, seed + 100000)
    out['LASP'] = run_bursty_lasp(G2, traf, snap_l)['losses']
    G3 = build_real('Geant.graphml', seed); reset(G3)
    traf3 = gen_bursty(list(G3.nodes()), STEPS, seed + 100000)
    out['CONGA'] = run_bursty_conga(G3, traf3)['losses']
    G4 = build_real('Geant.graphml', seed); reset(G4)
    wt4 = gen_bursty(list(G4.nodes()), ws, seed + 700000)
    snap_m = warmup_bursty_momentum(G4, wt4, 1.0, 32)
    G5 = build_real('Geant.graphml', seed); reset(G5)
    traf5 = gen_bursty(list(G5.nodes()), STEPS, seed + 100000)
    out['EMMET_v1'] = run_bursty_emmet(G5, traf5, snap_m, 1.0, 32)['losses']
    G6 = build_real('Geant.graphml', seed); reset(G6)
    traf6 = gen_bursty(list(G6.nodes()), STEPS, seed + 100000)
    out['EMMET_BLOOD'] = run_bursty_emmet_live(G6, traf6, snap_m, 1.0, 32, blood_rate=BLOOD_RATE)['losses']
    return out

print(f'BURSTY FINAL n={N} GEANT (BLOOD_RATE={BLOOD_RATE})')
print(f'{"seed":>5} {"LASP":>6} {"CONGA":>6} {"EMMET":>6} {"BLOOD":>6}')
print('-' * 35)
tots = {'LASP': 0, 'CONGA': 0, 'EMMET_v1': 0, 'EMMET_BLOOD': 0}
for s in range(N):
    r = seed_run(s)
    for k in tots: tots[k] += r[k]
    print(f'{s:>5} {r["LASP"]:>6} {r["CONGA"]:>6} {r["EMMET_v1"]:>6} {r["EMMET_BLOOD"]:>6}', flush=True)
print('-' * 35)
print(f'{"SUM":>5} {tots["LASP"]:>6} {tots["CONGA"]:>6} {tots["EMMET_v1"]:>6} {tots["EMMET_BLOOD"]:>6}')

print()
def rel(a, b): return f'{(a-b)/a*100:+.1f}%' if a else 'n/a'
L, C, E, B = tots['LASP'], tots['CONGA'], tots['EMMET_v1'], tots['EMMET_BLOOD']
print(f'EMMET_v1 vs LASP:    {rel(L, E)}')
print(f'EMMET_v1 vs CONGA:   {rel(C, E)}')
print(f'EMMET_BLOOD vs LASP: {rel(L, B)}')
print(f'EMMET_BLOOD vs CONGA: {rel(C, B)}')
print(f'EMMET_BLOOD vs EMMET_v1: {rel(E, B)}')
