"""Phase B of scalability v2: n=1000 only (400 jobs).
Run after Phase A is validated."""
import sys, time, json
from pathlib import Path
from multiprocessing import Pool, cpu_count

sys.path.insert(0, '/home/clopez/emmet/experiments')
from scalability_v2 import battery_jobs, save_checkpoint
from topology_extended_battery import run_one
from momentum_clean import aggregate

REPO = Path('/home/clopez/emmet')
DATA = REPO / 'data'

all_jobs = battery_jobs()
jobs = [j for j in all_jobs if int(j[2][0]) == 1000]
print(f'Phase B: {len(jobs)} jobs (n=1000 only)')

workers = max(1, cpu_count() - 4)
print(f'workers: {workers} (of {cpu_count()} cores)')
sys.stdout.flush()

raw_out = DATA / 'scalability_phaseB_raw.json'
ckpt_out = DATA / 'scalability_phaseB_checkpoint.json'
summary_out = DATA / 'scalability_phaseB_summary.json'

t0 = time.time()
results = []
with Pool(workers) as pool:
    for i, r in enumerate(pool.imap_unordered(run_one, jobs, chunksize=1)):
        results.append(r)
        if (i + 1) % 10 == 0:
            elapsed = time.time() - t0
            rate = (i + 1) / elapsed
            eta = (len(jobs) - (i + 1)) / rate
            print(f'  {i+1}/{len(jobs)} | {rate:.2f}/s | elapsed {elapsed/60:.1f}m | ETA {eta/60:.1f}m')
            sys.stdout.flush()
            save_checkpoint(results, ckpt_out)

elapsed = time.time() - t0
print(f'\nDone in {elapsed/60:.1f} min ({elapsed/3600:.2f}h)')

with open(raw_out, 'w') as f:
    json.dump(results, f, indent=1)
summary = aggregate(results)
with open(summary_out, 'w') as f:
    json.dump(summary, f, indent=2)
print(f'\nSaved {raw_out}')
print(f'Saved {summary_out}')

print()
fmt = '{:<22} {:>8} {:>10} {:>10} {:>11} {:>11} {:>10}'
print(fmt.format('Scenario', 'N', 'LASP+ dr', 'MOMDP dr',
                 'LASP+ loss', 'MOMDP loss', 'delta'))
print('-' * 92)
for s in summary:
    n = s.get('num_nodes_mean', s.get('num_nodes', 0))
    la_l = s['lasp_aug_losses_mean']
    em_l = s['momentum_dp_losses_mean']
    delta = ((la_l - em_l) / la_l * 100) if la_l > 0 else 0
    print(fmt.format(s['scenario'], f"{n:.0f}",
        f"{s['lasp_aug_delivery_rate_mean']:.1f}%",
        f"{s['momentum_dp_delivery_rate_mean']:.1f}%",
        f"{la_l:.2f}", f"{em_l:.2f}", f"{delta:+.1f}%"))
