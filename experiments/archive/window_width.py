"""How wide is the Goldilocks window? Sweep capacity regimes finely around
(2,4) over the 12 trunk links, br=2, n=30. Plateau => robust; spike => fragile."""
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

N_SEEDS = 30
GAMMA_OPT = 0.5
RIPPLE = 0.3
RIPPLE_STEPS = 3
STEPS = 200
BH = 15
BR = 2
CAPS = [(2,5),(2,4),(3,5),(3,4),(2,3)]
LINKS = [(0,2),(2,6),(0,4),(1,6),(6,21),(4,18),(4,6),(0,9),(3,4),(5,6),(15,21),(8,9)]

def make(cap, fail, seed):
    G, dem = build_geant_real(seed, cap_lo=cap[0], cap_hi=cap[1])
    if G.has_edge(*fail):
        G.remove_edge(*fail)
    return G, dem

def run_cell(args):
    cap, fail, seed = args
    G1, dem = make(cap, fail, seed); reset(G1)
    conga = run_bursty_conga(G1, gen_bursty_real(dem, STEPS, seed+100000, burst_hi=BH))['losses']
    emmet_budget.GAMMA = GAMMA_OPT
    G2, d2 = make(cap, fail, seed); reset(G2)
    wt = gen_bursty_real(d2, max(20, G2.number_of_nodes()*5), seed+700000, burst_hi=BH)
    snap = warmup_bursty_momentum(G2, wt, 1.0, 32)
    G3, d3 = make(cap, fail, seed); reset(G3)
    tr3 = gen_bursty_real(d3, STEPS, seed+100000, burst_hi=BH)
    ripple = run_bursty_emmet_live_ripple(G3, tr3, snap, 1.0, 32, blood_rate=BR, ripple=RIPPLE, ripple_steps=RIPPLE_STEPS)['losses']
    emmet_budget.GAMMA = 2.0
    return {'cap': list(cap), 'fail': list(fail), 'seed': seed, 'conga': conga, 'ripple': ripple}

def main():
    t0 = time.time()
    jobs = list(product(CAPS, LINKS, range(N_SEEDS)))
    print(f"{len(jobs)} jobs", flush=True)
    with Pool(max(1, cpu_count()-4)) as pool:
        res = pool.map(run_cell, jobs, chunksize=2)
    Path('/home/clopez/emmet/data/window_width_raw.json').write_text(json.dumps(res))
    print(f"Saved. {(time.time()-t0)/60:.1f} min", flush=True)

if __name__ == '__main__':
    main()
