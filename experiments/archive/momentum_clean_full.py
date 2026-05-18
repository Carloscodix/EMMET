"""Full clean battery: 20 scenarios, own warmup per algorithm, 32 buckets."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'experiments'))
from momentum_clean import (
    build_syn, build_real, run_one, aggregate
)
from multiprocessing import Pool, cpu_count
from pathlib import Path
import time, json

DATA = Path(__file__).resolve().parents[1] / 'data'

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
    print(f'Full clean battery: {len(jobs)} jobs (kappa={KAPPA}, 32 buckets, own warmup)')
    workers = max(1, cpu_count() - 4)
    t0 = time.time()
    with Pool(workers) as pool:
        results = []
        for i, r in enumerate(pool.imap_unordered(run_one, jobs, chunksize=4)):
            results.append(r)
            if (i+1) % 100 == 0:
                elapsed = time.time() - t0
                print(f'  {i+1}/{len(jobs)} | {(i+1)/elapsed:.1f}/s | '
                      f'ETA {(len(jobs)-(i+1))/((i+1)/elapsed)/60:.1f}m')
    print(f'Done in {(time.time()-t0)/60:.1f} min')

    with open(DATA / 'momentum_clean_full_raw.json', 'w') as f:
        json.dump(results, f, indent=1)
    summary = aggregate(results)
    with open(DATA / 'momentum_clean_full_summary.json', 'w') as f:
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
