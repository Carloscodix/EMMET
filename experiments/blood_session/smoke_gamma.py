"""GAMMA sweep on bursty GEANT. Tests whether v1's gamma=2.0 is underspecified."""
import sys
sys.path.insert(0, '/home/clopez/emmet/experiments')
import emmet_budget
from emmet_budget import build_real, reset
from bursty_traffic import gen_bursty
from bursty_warmup import warmup_bursty_momentum
from bursty_runner import run_bursty_emmet

GAMMAS = [2.0, 5.0, 10.0, 20.0]
STEPS = 200
N_SEEDS = 30

def one_seed(seed, gamma):
    emmet_budget.GAMMA = gamma  # monkey-patch
    G = build_real('Geant.graphml', seed); reset(G)
    ws = max(20, G.number_of_nodes()*5)
    wt = gen_bursty(list(G.nodes()), ws, seed + 700000)
    snap = warmup_bursty_momentum(G, wt, 1.0, 32)
    G2 = build_real('Geant.graphml', seed); reset(G2)
    traf = gen_bursty(list(G2.nodes()), STEPS, seed + 100000)
    return run_bursty_emmet(G2, traf, snap, 1.0, 32)['losses']

print(f'GAMMA sweep bursty GEANT, {N_SEEDS} seeds')
print(f'{"seed":>4} ' + ' '.join(f'g{g:.0f}'.rjust(6) for g in GAMMAS))
print('-' * (5 + 7*len(GAMMAS)))
tots = {g: 0 for g in GAMMAS}
for s in range(N_SEEDS):
    row_vals = []
    for g in GAMMAS:
        x = one_seed(s, g)
        tots[g] += x
        row_vals.append(x)
    print(f'{s:>4} ' + ' '.join(f'{v:>6}' for v in row_vals), flush=True)
print('-' * (5 + 7*len(GAMMAS)))
print(f'{"SUM":>4} ' + ' '.join(f'{tots[g]:>6}' for g in GAMMAS))
print()
ref = tots[2.0]
for g in GAMMAS:
    rel = (ref - tots[g]) / ref * 100 if ref else 0
    print(f'gamma={g}: {tots[g]} losses ({rel:+.1f}% vs v1 gamma=2.0)')
