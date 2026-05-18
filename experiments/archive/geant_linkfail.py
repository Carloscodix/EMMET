"""GEANT-22 resilience under single-link failure (real demand matrix).
Fails each non-bridge edge one at a time; compares CONGA vs EMMET-Newt
Ripple_opt at rerouting the real traffic around the dead link."""
import sys, json, time
from pathlib import Path
from itertools import product
from multiprocessing import Pool, cpu_count
sys.path.insert(0, '/home/clopez/emmet/experiments')
import networkx as nx
import emmet_budget
from emmet_budget import reset
from real_traffic import build_geant_real, gen_bursty_real
from bursty_warmup import warmup_bursty_momentum
from bursty_runner import run_bursty_conga, run_bursty_emmet_live_ripple

N_SEEDS = 30
BURST_HI = 15
GAMMA_OPT = 0.5
BR_OPT = 10.0
RIPPLE = 0.3
RIPPLE_STEPS = 3
STEPS = 200

def edge_list():
    G, _ = build_geant_real(0)
    return [tuple(sorted(e)) for e in G.edges()]

def build_failed(seed, fail):
    G, dem = build_geant_real(seed)
    if G.has_edge(*fail):
        G.remove_edge(*fail)
    return G, dem

def run_one(args):
    fail, seed = args
    G1, dem = build_failed(seed, fail); reset(G1)
    tr = gen_bursty_real(dem, STEPS, seed + 100000, burst_hi=BURST_HI)
    conga = run_bursty_conga(G1, tr)['losses']
    emmet_budget.GAMMA = GAMMA_OPT
    G2, d2 = build_failed(seed, fail); reset(G2)
    wt = gen_bursty_real(d2, max(20, G2.number_of_nodes()*5), seed+700000, burst_hi=BURST_HI)
    snap = warmup_bursty_momentum(G2, wt, 1.0, 32)
    G3, d3 = build_failed(seed, fail); reset(G3)
    tr3 = gen_bursty_real(d3, STEPS, seed+100000, burst_hi=BURST_HI)
    ripple = run_bursty_emmet_live_ripple(G3, tr3, snap, 1.0, 32, blood_rate=BR_OPT, ripple=RIPPLE, ripple_steps=RIPPLE_STEPS)['losses']
    emmet_budget.GAMMA = 2.0
    return {'fail': list(fail), 'seed': seed, 'conga': conga, 'ripple': ripple}

def main():
    t0 = time.time()
    edges = edge_list()
    jobs = list(product(edges, range(N_SEEDS)))
    print(f"{len(edges)} edges x {N_SEEDS} seeds = {len(jobs)} jobs", flush=True)
    with Pool(max(1, cpu_count() - 4)) as pool:
        results = pool.map(run_one, jobs, chunksize=4)
    Path('/home/clopez/emmet/data/geant_linkfail_raw.json').write_text(json.dumps(results))
    print(f"Saved. {(time.time()-t0)/60:.1f} min", flush=True)

if __name__ == '__main__':
    main()
