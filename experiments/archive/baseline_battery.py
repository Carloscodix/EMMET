"""4-way battery under link failure: CONGA vs ECMP vs DRILL vs EMMET-Newt.
GEANT real topology+demand, 12 trunk links, two capacity regimes.
The decisive meh-vs-wow test: does EMMET-Newt beat DRILL, the strong
simple local-balancing baseline?"""
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
from baselines_extra import run_bursty_ecmp, run_bursty_drill

N_SEEDS = 30
GAMMA_OPT = 0.5
BR = 2
RIPPLE = 0.3
RIPPLE_STEPS = 3
STEPS = 200
BH = 15
CAPS = [(2,4),(2,2)]
LINKS = [(0,2),(2,6),(0,4),(1,6),(6,21),(4,18),(4,6),(0,9),(3,4),(5,6),(15,21),(8,9)]

def mk(cap, fail, seed):
    G, dem = build_geant_real(seed, cap_lo=cap[0], cap_hi=cap[1])
    if G.has_edge(*fail):
        G.remove_edge(*fail)
    return G, dem

def run_cell(args):
    cap, fail, seed = args
    out = {'cap': list(cap), 'fail': list(fail), 'seed': seed}
    tr = lambda: gen_bursty_real(mk(cap, fail, seed)[1], STEPS, seed+100000, burst_hi=BH)
    G,_ = mk(cap,fail,seed); reset(G); out['CONGA']=run_bursty_conga(G, tr())['losses']
    G,_ = mk(cap,fail,seed); reset(G); out['ECMP']=run_bursty_ecmp(G, tr(), seed=seed)['losses']
    G,_ = mk(cap,fail,seed); reset(G); out['DRILL']=run_bursty_drill(G, tr(), seed=seed)['losses']
    emmet_budget.GAMMA = GAMMA_OPT
    G,d = mk(cap,fail,seed); reset(G)
    wt = gen_bursty_real(d, max(20,G.number_of_nodes()*5), seed+700000, burst_hi=BH)
    snap = warmup_bursty_momentum(G, wt, 1.0, 32)
    G,_ = mk(cap,fail,seed); reset(G)
    out['EMMET']=run_bursty_emmet_live_ripple(G, tr(), snap, 1.0, 32, blood_rate=BR, ripple=RIPPLE, ripple_steps=RIPPLE_STEPS)['losses']
    emmet_budget.GAMMA = 2.0
    return out

def main():
    t0 = time.time()
    jobs = list(product(CAPS, LINKS, range(N_SEEDS)))
    print(f"{len(jobs)} jobs x 4 routers", flush=True)
    with Pool(max(1, cpu_count()-4)) as pool:
        res = pool.map(run_cell, jobs, chunksize=2)
    Path('/home/clopez/emmet/data/baseline_battery_raw.json').write_text(json.dumps(res))
    print(f"Saved. {(time.time()-t0)/60:.1f} min", flush=True)

if __name__ == '__main__':
    main()
