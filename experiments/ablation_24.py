"""Ablation: strip EMMET-Newt layers one at a time, measure vs DRILL.
Regime: GEANT real, uniform cap (2,2), trunk-link failure, n=30."""
import sys, json, time
from pathlib import Path
from itertools import product
from multiprocessing import Pool, cpu_count
sys.path.insert(0, '/home/clopez/emmet/experiments')
import emmet_budget
import emmet_momentum_dp as edp
from emmet_budget import reset
from real_traffic import build_geant_real, gen_bursty_real
from bursty_warmup import warmup_bursty_momentum
from bursty_runner import run_bursty_emmet_live_ripple
from baselines_extra import run_bursty_drill

N_SEEDS = 30
BH = 15
STEPS = 200
CAP = (2, 4)
LINKS = [(0,2),(2,6),(0,4),(1,6),(6,21),(4,18),(4,6),(0,9),(3,4),(5,6),(15,21),(8,9)]

# Each variant = dict of overrides. GAMMA/THETA are module globals;
# kappa/blood_rate/ripple/ripple_steps are call args.
VARIANTS = {
    'FULL':     dict(GAMMA=2.0, THETA=5.0, kappa=0.3, blood=2.0, ripple=0.3, rsteps=3),
    '-ripple':  dict(GAMMA=2.0, THETA=5.0, kappa=0.3, blood=2.0, ripple=0.0, rsteps=0),
    '-blood':   dict(GAMMA=2.0, THETA=5.0, kappa=0.3, blood=0.0, ripple=0.0, rsteps=0),
    '-mass':    dict(GAMMA=2.0, THETA=5.0, kappa=0.0, blood=2.0, ripple=0.3, rsteps=3),
    '-thermo':  dict(GAMMA=2.0, THETA=0.0, kappa=0.3, blood=2.0, ripple=0.3, rsteps=3),
    'CORE':     dict(GAMMA=0.0, THETA=0.0, kappa=0.0, blood=0.0, ripple=0.0, rsteps=0),
}

def mk(fail, seed):
    G, dem = build_geant_real(seed, cap_lo=CAP[0], cap_hi=CAP[1])
    if G.has_edge(*fail):
        G.remove_edge(*fail)
    return G, dem

def run_variant(args):
    vname, fail, seed = args
    v = VARIANTS[vname]
    emmet_budget.GAMMA = v['GAMMA']
    emmet_budget.THETA = v['THETA']
    G, dem = mk(fail, seed); reset(G)
    wt = gen_bursty_real(dem, max(20, G.number_of_nodes()*5), seed+700000, burst_hi=BH)
    snap = warmup_bursty_momentum(G, wt, 1.0, 32)
    G2, d2 = mk(fail, seed); reset(G2)
    tr = gen_bursty_real(d2, STEPS, seed+100000, burst_hi=BH)
    losses = run_bursty_emmet_live_ripple(G2, tr, snap, v['kappa'], 32, blood_rate=v['blood'], ripple=v['ripple'], ripple_steps=v['rsteps'])['losses']
    emmet_budget.GAMMA = 2.0; emmet_budget.THETA = 5.0
    return {'variant': vname, 'fail': list(fail), 'seed': seed, 'losses': losses}

def run_drill(args):
    fail, seed = args
    G, dem = mk(fail, seed); reset(G)
    tr = gen_bursty_real(dem, STEPS, seed+100000, burst_hi=BH)
    return {'variant': 'DRILL', 'fail': list(fail), 'seed': seed,
            'losses': run_bursty_drill(G, tr, seed=seed)['losses']}

def main():
    t0 = time.time()
    vjobs = [(vn, f, s) for vn in VARIANTS for f in LINKS for s in range(N_SEEDS)]
    djobs = [(f, s) for f in LINKS for s in range(N_SEEDS)]
    print(f"{len(vjobs)} variant + {len(djobs)} drill jobs", flush=True)
    with Pool(max(1, cpu_count()-4)) as pool:
        res = pool.map(run_variant, vjobs, chunksize=4)
        dres = pool.map(run_drill, djobs, chunksize=4)
    Path('/home/clopez/emmet/data/ablation_24_raw.json').write_text(json.dumps(res+dres))
    print(f"Saved. {(time.time()-t0)/60:.1f} min", flush=True)

if __name__ == '__main__':
    main()
