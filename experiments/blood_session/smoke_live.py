"""BLOOD LIVE: snap updates dynamically when packets die. n=30 GEANT bursty."""
import sys
sys.path.insert(0, '/home/clopez/emmet/experiments')
from emmet_budget import build_real, reset
from bursty_traffic import gen_bursty
from bursty_warmup import warmup_bursty_momentum
from bursty_runner import run_bursty_emmet, run_bursty_emmet_live

RATES = [0.0, 0.5, 1.0, 2.0, 5.0, 10.0]
STEPS = 200
N = 30

def seed_run(seed, rate):
    G = build_real('Geant.graphml', seed); reset(G)
    ws = max(20, G.number_of_nodes()*5)
    wt = gen_bursty(list(G.nodes()), ws, seed + 700000)
    snap = warmup_bursty_momentum(G, wt, 1.0, 32)
    G2 = build_real('Geant.graphml', seed); reset(G2)
    traf = gen_bursty(list(G2.nodes()), STEPS, seed + 100000)
    if rate == 'v1':
        return run_bursty_emmet(G2, traf, snap, 1.0, 32)['losses']
    return run_bursty_emmet_live(G2, traf, snap, 1.0, 32, blood_rate=rate)['losses']

print(f'BLOOD LIVE bursty GEANT, {N} seeds')
hdr = ['seed', 'v1'] + [f'br{r}' for r in RATES]
print(' '.join(f'{h:>6}' for h in hdr))
print('-' * (7 * len(hdr)))
tots = {'v1': 0}
for r in RATES: tots[r] = 0
for s in range(N):
    v1 = seed_run(s, 'v1')
    tots['v1'] += v1
    row = [s, v1]
    for r in RATES:
        x = seed_run(s, r)
        tots[r] += x
        row.append(x)
    print(' '.join(f'{v:>6}' for v in row), flush=True)
print('-' * (7 * len(hdr)))
ref = tots['v1']
print(f'\nv1 baseline: {ref} losses')
for r in RATES:
    x = tots[r]
    rel = (ref - x) / ref * 100 if ref else 0
    print(f'BLOOD LIVE br={r}: {x} losses ({rel:+.1f}% vs v1)')
