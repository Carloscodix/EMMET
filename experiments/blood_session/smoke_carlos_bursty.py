"""Smoke: EMMET-DP v1 vs CARLOS bursty, GEANT, eta sweep."""
import sys
sys.path.insert(0, '/home/clopez/emmet/experiments')
from emmet_budget import build_real, reset
from bursty_traffic import gen_bursty
from bursty_warmup import warmup_bursty_momentum
from bursty_runner import run_bursty_emmet, run_bursty_carlos

ETAS = [0.0, 0.1, 0.5, 1.0, 2.0, 5.0]
STEPS = 200

def one_seed(seed):
    out = {}
    G = build_real('Geant.graphml', seed); reset(G)
    ws = max(20, G.number_of_nodes()*5)
    wt = gen_bursty(list(G.nodes()), ws, seed + 700000)
    snap = warmup_bursty_momentum(G, wt, 1.0, 32)
    G2 = build_real('Geant.graphml', seed); reset(G2)
    traf = gen_bursty(list(G2.nodes()), STEPS, seed + 100000)
    out['v1'] = run_bursty_emmet(G2, traf, snap, 1.0, 32)['losses']
    for eta in ETAS:
        G3 = build_real('Geant.graphml', seed); reset(G3)
        traf2 = gen_bursty(list(G3.nodes()), STEPS, seed + 100000)
        r = run_bursty_carlos(G3, traf2, snap, 1.0, 32, eta=eta)
        out[f'eta={eta}'] = r['losses']
    return out

print('Smoke CARLOS bursty: GEANT, 10 seeds, eta sweep')
hdr = ['seed', 'v1'] + [f'e{e}' for e in ETAS]
print(' '.join(f'{h:>5}' for h in hdr))
print('-' * (6 * len(hdr)))
tots = {'v1': 0}
for e in ETAS: tots[f'eta={e}'] = 0
for s in range(10):
    r = one_seed(s)
    row = [s, r['v1']] + [r[f'eta={e}'] for e in ETAS]
    for k, v in r.items(): tots[k] += v
    print(' '.join(f'{x:>5}' for x in row), flush=True)
print('-' * (6 * len(hdr)))
tot_row = ['SUM', tots['v1']] + [tots[f'eta={e}'] for e in ETAS]
print(' '.join(f'{str(x):>5}' for x in tot_row))
print()
v1 = tots['v1']
for e in ETAS:
    x = tots[f'eta={e}']
    rel = (v1 - x) / v1 * 100 if v1 else 0
    print(f'eta={e}: {x} losses ({rel:+.1f}% vs v1={v1})')
