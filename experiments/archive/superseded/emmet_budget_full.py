"""EMMET-budget full battery: alpha=1.25 over the 20 scenarios.

Same seeds, same topologies, same 100/50 seed counts as combined_v2, so
results are directly comparable. Records:
  - delivery_rate (primary metric)
  - losses (congestion losses)
  - capacity per delivery (capacity overhead)
  - hop count vs SP (detour ratio)
"""
import random, statistics, math, json, time
from pathlib import Path
from multiprocessing import Pool, cpu_count
import sys
sys.path.insert(0, '/home/clopez/emmet/experiments')
from emmet_budget import (
    build_syn, build_real, reset, gen_traf,
    emmet_budget_route, warmup, simulate, run_one, aggregate,
    TRAFFIC_STEPS
)

DATA = Path('/home/clopez/emmet/data')

def battery_jobs(alpha_budget=1.25):
    jobs = []
    for d in [0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40, 0.50]:
        for s in range(100):
            jobs.append((f'ER_n20_p{d:.2f}', build_syn, (20, d), s, alpha_budget))
    for d in [0.05, 0.10, 0.15, 0.20, 0.25, 0.30]:
        for s in range(100):
            jobs.append((f'ER_n50_p{d:.2f}', build_syn, (50, d), s, alpha_budget))
    for d in [0.05, 0.10, 0.15, 0.20]:
        for s in range(50):
            jobs.append((f'ER_n100_p{d:.2f}', build_syn, (100, d), s, alpha_budget))
    for s in range(100):
        jobs.append(('Abilene', build_real, ('Abilene.graphml',), s, alpha_budget))
    for s in range(100):
        jobs.append(('GEANT', build_real, ('Geant.graphml',), s, alpha_budget))
    return jobs

if __name__ == '__main__':
    ALPHA = 1.25
    jobs = battery_jobs(alpha_budget=ALPHA)
    print(f'EMMET-budget full battery: {len(jobs)} jobs')
    print(f'alpha_budget = {ALPHA} (sweet spot from sweep)')
    workers = max(1, cpu_count() - 4)
    print(f'workers: {workers}')
    print()

    t0 = time.time()
    with Pool(workers) as pool:
        results = []
        for i, r in enumerate(pool.imap_unordered(run_one, jobs, chunksize=4)):
            results.append(r)
            if (i+1) % 200 == 0:
                elapsed = time.time() - t0
                rate = (i+1) / elapsed
                eta = (len(jobs) - (i+1)) / rate
                print(f'  {i+1}/{len(jobs)} | {rate:.1f}/s | ETA {eta/60:.1f}m')
    print(f'\nDone in {(time.time()-t0)/60:.1f} min')

    with open(DATA / 'budget_full_raw.json', 'w') as f:
        json.dump(results, f, indent=1)
    summary = aggregate(results)
    with open(DATA / 'budget_full_summary.json', 'w') as f:
        json.dump(summary, f, indent=2)

    print()
    print(f"{'Scenario':<22} {'EM_dr':>7} {'LASP_dr':>8} {'SP_dr':>7} | "
          f"{'EM_loss':>8} {'LASP_loss':>10} | {'EM_cap':>7} {'LASP_cap':>8} | {'EM_hop':>7} {'SP_hop':>7}")
    for s in summary:
        print(f"{s['scenario']:<22} "
              f"{s['emmet_budget_delivery_rate_mean']:>6.1f}% "
              f"{s['lasp_delivery_rate_mean']:>7.1f}% "
              f"{s['sp_delivery_rate_mean']:>6.1f}% | "
              f"{s['emmet_budget_losses_mean']:>8.2f} "
              f"{s['lasp_losses_mean']:>10.2f} | "
              f"{s['emmet_budget_cap_per_delivery_mean']:>7.2f} "
              f"{s['lasp_cap_per_delivery_mean']:>8.2f} | "
              f"{s['emmet_budget_hop_per_delivery_mean']:>7.2f} "
              f"{s['emmet_budget_sp_hop_per_delivery_mean']:>7.2f}")
    print(f"\nSaved budget_full_summary.json + budget_full_raw.json")
