"""2D sweep: blood_rate x gamma on bursty GEANT."""
import sys
sys.path.insert(0, '/home/clopez/emmet/experiments')
import emmet_budget
from emmet_budget import build_real, reset
from bursty_traffic import gen_bursty
from bursty_warmup import warmup_bursty_momentum
from bursty_runner import run_bursty_emmet_live

GAMMAS = [0.5, 1.0, 2.0, 3.0]
RATES = [1.0, 5.0, 10.0]
STEPS = 200
N = 20

def run(seed, gamma, rate):
    emmet_budget.GAMMA = gamma
    G = build_real('Geant.graphml', seed); reset(G)
    ws = max(20, G.number_of_nodes()*5)
    wt = gen_bursty(list(G.nodes()), ws, seed + 700000)
    snap = warmup_bursty_momentum(G, wt, 1.0, 32)
    G2 = build_real('Geant.graphml', seed); reset(G2)
    traf = gen_bursty(list(G2.nodes()), STEPS, seed + 100000)
    return run_bursty_emmet_live(G2, traf, snap, 1.0, 32, blood_rate=rate)['losses']

print(f'2D sweep: gamma x blood_rate on bursty GEANT, {N} seeds')
print(f'   gamma\\\\rate ' + '  '.join(f'br{r:>5.1f}' for r in RATES))
results = {}
for g in GAMMAS:
    for r in RATES:
        tot = 0
        for s in range(N):
            tot += run(s, g, r)
        results[(g, r)] = tot
        print(f'  g={g:.1f}  br={r:.1f}  losses={tot}', flush=True)

print('\n=== TABLE (sum losses, lower is better) ===')
print(f'gamma\\\\rate ' + '  '.join(f'{r:>6.1f}' for r in RATES))
for g in GAMMAS:
    row = [results[(g, r)] for r in RATES]
    print(f'  g={g:<3.1f}    ' + '  '.join(f'{x:>6}' for x in row))

best = min(results.items(), key=lambda kv: kv[1])
print(f'\nBest: gamma={best[0][0]}, blood_rate={best[0][1]}, losses={best[1]}')
