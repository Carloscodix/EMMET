import sys
sys.path.insert(0, '/home/clopez/emmet/experiments')
from emmet_budget import build_real, reset, gen_traf, TRAFFIC_STEPS
from momentum_clean import warmup_momentum, simulate_momentum
from emmet_carlos import simulate_carlos

ETAS = [0.0, 0.1, 0.5, 1.0, 2.0]

def one_seed(seed):
    out = {}
    G = build_real('Geant.graphml', seed); reset(G)
    ws_traf = gen_traf(list(G.nodes()), max(20, G.number_of_nodes()*5), seed + 300000)
    snap = warmup_momentum(G, ws_traf, 1.0, 32)
    G2 = build_real('Geant.graphml', seed); reset(G2)
    traf = gen_traf(list(G2.nodes()), TRAFFIC_STEPS, seed + 100000)
    out['v1'] = simulate_momentum(G2, traf, snap, 1.0, 32)['losses']
    for eta in ETAS:
        G3 = build_real('Geant.graphml', seed); reset(G3)
        traf2 = gen_traf(list(G3.nodes()), TRAFFIC_STEPS, seed + 100000)
        r = simulate_carlos(G3, traf2, snap, 1.0, 32, eta=eta)
        out[f'eta={eta}'] = r['losses']
    return out

print('Smoke CARLOS: GEANT, 10 seeds, eta sweep')
print(f'{"seed":>4} {"v1":>4} {"e0.0":>5} {"e0.1":>5} {"e0.5":>5} {"e1.0":>5} {"e2.0":>5}')
print('-' * 42)
tots = {'v1': 0}
for e in ETAS: tots[f'eta={e}'] = 0
for s in range(10):
    r = one_seed(s)
    row = [s, r['v1']] + [r[f'eta={e}'] for e in ETAS]
    for k, v in r.items(): tots[k] += v
    print(' '.join(f'{x:>4}' if isinstance(x, int) else f'{x:>5}' for x in row), flush=True)
print('-' * 42)
tot_row = ['SUM', tots['v1']] + [tots[f'eta={e}'] for e in ETAS]
print(' '.join(f'{x:>4}' if isinstance(x, int) else f'{x:>5}' for x in tot_row))
print()
v1 = tots['v1']
for e in ETAS:
    x = tots[f'eta={e}']
    rel = (v1 - x) / v1 * 100 if v1 else 0
    print(f'eta={e}: {x} losses ({rel:+.1f}% vs v1={v1})')
