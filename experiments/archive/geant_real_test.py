"""GEANT-22 real topology: real demand matrix vs uniform traffic.
Compares CONGA vs EMMET-Newt Ripple_opt under both traffic models."""
import sys, json, time
from pathlib import Path
from multiprocessing import Pool, cpu_count
sys.path.insert(0, '/home/clopez/emmet/experiments')
import emmet_budget
from emmet_budget import reset
from real_traffic import build_geant_real, gen_bursty_real
from bursty_traffic import gen_bursty
from bursty_warmup import warmup_bursty_momentum
from bursty_runner import run_bursty_conga, run_bursty_emmet_live_ripple

N_SEEDS = 30
GAMMA_OPT = 0.5
BR_OPT = 10.0
RIPPLE = 0.3
RIPPLE_STEPS = 3
STEPS = 200

def run_seed(seed):
    out = {'seed': seed}
    G0, dem = build_geant_real(seed)
    ws = max(20, G0.number_of_nodes() * 5)
    nodes = list(G0.nodes())
    gens = [
        ('real', lambda s: gen_bursty_real(dem, ws, s + 700000),
                 lambda s: gen_bursty_real(dem, STEPS, s + 100000)),
        ('unif', lambda s: gen_bursty(nodes, ws, s + 700000),
                 lambda s: gen_bursty(nodes, STEPS, s + 100000)),
    ]
    for label, warm_fn, test_fn in gens:
        G1, _ = build_geant_real(seed); reset(G1)
        out[f'{label}_CONGA'] = run_bursty_conga(G1, test_fn(seed))['losses']
        emmet_budget.GAMMA = GAMMA_OPT
        G2, _ = build_geant_real(seed); reset(G2)
        snap = warmup_bursty_momentum(G2, warm_fn(seed), 1.0, 32)
        G3, _ = build_geant_real(seed); reset(G3)
        out[f'{label}_RIPPLE'] = run_bursty_emmet_live_ripple(G3, test_fn(seed), snap, 1.0, 32, blood_rate=BR_OPT, ripple=RIPPLE, ripple_steps=RIPPLE_STEPS)['losses']
        emmet_budget.GAMMA = 2.0
    return out

def main():
    t0 = time.time()
    with Pool(min(N_SEEDS, max(1, cpu_count() - 4))) as pool:
        results = pool.map(run_seed, range(N_SEEDS))
    Path('/home/clopez/emmet/data/geant_real_raw.json').write_text(json.dumps(results, indent=2))
    print(f"Saved. {(time.time()-t0)/60:.1f} min")

if __name__ == '__main__':
    main()
