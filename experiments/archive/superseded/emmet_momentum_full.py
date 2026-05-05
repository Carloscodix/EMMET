"""EMMET-momentum-DP full battery: kappa=1.0 over 20 scenarios."""
import random, statistics, math, json, time
from pathlib import Path
from multiprocessing import Pool, cpu_count
import sys
sys.path.insert(0, '/home/clopez/emmet/experiments')
from emmet_momentum_dp import (
    build_syn, build_real, run_one, aggregate
)

DATA = Path('/home/clopez/emmet/data')

def battery_jobs(kappa=1.0):
    jobs = []
    for d in [0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40, 0.50]:
        for s in range(100):
            jobs.append((f'ER_n20_p{d:.2f}', build_syn, (20, d), s, kappa))
    for d in [0.05, 0.10, 0.15, 0.20, 0.25, 0.30]:
        for s in range(100):
            jobs.append((f'ER_n50_p{d:.2f}', build_syn, (50, d), s, kappa))
    for d in [0.05, 0.10, 0.15, 0.20]:
        for s in range(50):
            jobs.append((f'ER_n100_p{d:.2f}', build_syn, (100, d), s, kappa))
    for s in range(100):
        jobs.append(('Abilene', build_real, ('Abilene.graphml',), s, kappa))
    for s in range(100):
        jobs.append(('GEANT', build_real, ('Geant.graphml',), s, kappa))
    return jobs

if __name__ == '__main__':
    KAPPA = 1.0
    jobs = battery_jobs(kappa=KAPPA)
    print(f'EMMET-momentum-DP full battery: {len(jobs)} jobs (kappa={KAPPA})')
    workers = max(1, cpu_count() - 4)
    print(f'workers: {workers}')

    t0 = time.time()
    with Pool(workers) as pool:
        results = []
        for i, r in enumerate(pool.imap_unordered(run_one, jobs, chunksize=4)):
            results.append(r)
            if (i+1) % 100 == 0:
                elapsed = time.time() - t0
                rate = (i+1) / elapsed
                eta = (len(jobs) - (i+1)) / rate
                print(f'  {i+1}/{len(jobs)} | {rate:.1f}/s | ETA {eta/60:.1f}m')
    print(f'\nDone in {(time.time()-t0)/60:.1f} min')

    with open(DATA / 'momentum_full_raw.json', 'w') as f:
        json.dump(results, f, indent=1)
    summary = aggregate(results)
    with open(DATA / 'momentum_full_summary.json', 'w') as f:
        json.dump(summary, f, indent=2)

    print()
    print(f"{'Scenario':<22} {'LASP+ dr':>10} {'MOMDP dr':>10} | "
          f"{'LASP+ loss':>11} {'MOMDP loss':>11} | {'Δ losses':>10} | {'cap diff':>9}")
    print('-' * 110)
    for s in summary:
        delta = ((s['lasp_aug_losses_mean'] - s['momentum_dp_losses_mean'])
                 / s['lasp_aug_losses_mean'] * 100
                 if s['lasp_aug_losses_mean'] > 0 else 0)
        cap_diff = (s['momentum_dp_cap_per_delivery_mean']
                    - s['lasp_aug_cap_per_delivery_mean'])
        print(f"{s['scenario']:<22} "
              f"{s['lasp_aug_delivery_rate_mean']:>9.1f}% "
              f"{s['momentum_dp_delivery_rate_mean']:>9.1f}% | "
              f"{s['lasp_aug_losses_mean']:>11.2f} "
              f"{s['momentum_dp_losses_mean']:>11.2f} | "
              f"{delta:>+9.1f}% | {cap_diff:>+8.2f}")
