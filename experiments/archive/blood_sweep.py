"""Blood-rate sweep: self-harm at rest vs advantage under stress.
Rest  = nominal capacity (3,6), no failure  -> low congestion
Stress= reduced capacity (2,3), trunk link (0,2) failed -> real congestion
For each blood_rate, measure RIPPLE vs CONGA in both regimes."""
import sys, json, time
from pathlib import Path
from itertools import product
from multiprocessing import Pool, cpu_count
sys.path.insert(0, '/home/clopez/emmet/experiments')
import emmet_budget
from emmet_budget import reset
from real_traffic import build_geant_real, gen_bursty_real
from bursty_warmup import warmup_bursty_momentum
from bursty_runner import run_bursty_conga, run_bursty_emmet_live_ripple

N_SEEDS = 20
GAMMA_OPT = 0.5
RIPPLE = 0.3
RIPPLE_STEPS = 3
STEPS = 200
BH = 15
FAIL = (0, 2)
BLOOD_RATES = [0, 1, 2, 5, 10, 20]

def make(regime, seed):
    if regime == 'rest':
        G, dem = build_geant_real(seed, cap_lo=3, cap_hi=6)
    else:
        G, dem = build_geant_real(seed, cap_lo=2, cap_hi=3)
        if G.has_edge(*FAIL):
            G.remove_edge(*FAIL)
    return G, dem

def run_cell(args):
    br, regime, seed = args
    G1, dem = make(regime, seed); reset(G1)
    conga = run_bursty_conga(G1, gen_bursty_real(dem, STEPS, seed+100000, burst_hi=BH))['losses']
    emmet_budget.GAMMA = GAMMA_OPT
    G2, d2 = make(regime, seed); reset(G2)
    wt = gen_bursty_real(d2, max(20, G2.number_of_nodes()*5), seed+700000, burst_hi=BH)
    snap = warmup_bursty_momentum(G2, wt, 1.0, 32)
    G3, d3 = make(regime, seed); reset(G3)
    tr3 = gen_bursty_real(d3, STEPS, seed+100000, burst_hi=BH)
    ripple = run_bursty_emmet_live_ripple(G3, tr3, snap, 1.0, 32, blood_rate=br, ripple=RIPPLE, ripple_steps=RIPPLE_STEPS)['losses']
    emmet_budget.GAMMA = 2.0
    return {'br': br, 'regime': regime, 'seed': seed, 'conga': conga, 'ripple': ripple}

def main():
    t0 = time.time()
    jobs = list(product(BLOOD_RATES, ['rest', 'stress'], range(N_SEEDS)))
    print(f"{len(jobs)} jobs", flush=True)
    with Pool(max(1, cpu_count()-4)) as pool:
        res = pool.map(run_cell, jobs, chunksize=2)
    Path('/home/clopez/emmet/data/blood_sweep_raw.json').write_text(json.dumps(res))
    print(f"Saved. {(time.time()-t0)/60:.1f} min", flush=True)

if __name__ == '__main__':
    main()
