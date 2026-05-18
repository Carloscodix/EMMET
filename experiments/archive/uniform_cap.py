"""Decisive test: UNIFORM capacity (all links equal, like real GEANT).
Removes invented heterogeneity. If EMMET-Newt still wins, result is robust."""
import sys, json, time
from pathlib import Path
from itertools import product
from multiprocessing import Pool, cpu_count
sys.path.insert(0, '/home/clopez/emmet/experiments')
from window_width import run_cell
N_SEEDS = 30
CAPS = [(2,2),(3,3),(4,4),(5,5)]
LINKS = [(0,2),(2,6),(0,4),(1,6),(6,21),(4,18),(4,6),(0,9),(3,4),(5,6),(15,21),(8,9)]

def main():
    t0 = time.time()
    jobs = list(product(CAPS, LINKS, range(N_SEEDS)))
    print(f"{len(jobs)} jobs", flush=True)
    with Pool(max(1, cpu_count()-4)) as pool:
        res = pool.map(run_cell, jobs, chunksize=2)
    Path('/home/clopez/emmet/data/uniform_cap_raw.json').write_text(json.dumps(res))
    print(f"Saved. {(time.time()-t0)/60:.1f} min", flush=True)

if __name__ == '__main__':
    main()
