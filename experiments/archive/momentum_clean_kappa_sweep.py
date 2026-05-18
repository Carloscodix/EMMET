"""Clean kappa sweep — addresses Codex round 4 finding #1.

Runs the kappa sweep with the SAME configuration as the headline battery:
- own warmup per algorithm (warmup_lasp_aug, warmup_momentum)
- 32 buckets
- half-up rounding (already in module after Codex r3 #3)
- alpha_budget=1.25
- 100 seeds per (scenario, kappa) cell

The previous data/momentum_dp_kappa_sweep.json was generated with the
prototype's run_one (shared warmup, default M_BUCKETS=8). This was used
to justify kappa=1.0 originally. We re-justify kappa=1.0 from a clean
sweep here.
"""
import sys
import time
import json
import statistics
from pathlib import Path
from multiprocessing import Pool, cpu_count

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "experiments"))

from momentum_clean import (
    run_one as run_one_clean, aggregate,
)
from emmet_budget import build_real, build_syn

DATA = REPO / "data"


if __name__ == "__main__":
    scenarios = [
        ("GEANT",          build_real, ("Geant.graphml",), 100),
        ("Abilene",        build_real, ("Abilene.graphml",), 100),
        ("ER_n50_p0.05",   build_syn,  (50, 0.05), 100),
        ("ER_n50_p0.10",   build_syn,  (50, 0.10), 100),
        ("ER_n20_p0.20",   build_syn,  (20, 0.20), 100),
    ]
    kappa_values = [0.0, 0.1, 0.3, 0.5, 1.0, 1.5]

    jobs = []
    for sn, b, ba, ns in scenarios:
        for k in kappa_values:
            for s in range(ns):
                jobs.append((sn, b, ba, s, k))

    print(f"Clean kappa sweep: {len(jobs)} jobs "
          f"({len(scenarios)} scenarios x {len(kappa_values)} kappas x 100 seeds)")
    workers = max(1, cpu_count() - 4)
    print(f"workers: {workers}")

    t0 = time.time()
    with Pool(workers) as pool:
        results = []
        for i, r in enumerate(pool.imap_unordered(run_one_clean, jobs, chunksize=4)):
            results.append(r)
            if (i + 1) % 100 == 0:
                elapsed = time.time() - t0
                rate = (i + 1) / elapsed
                eta = (len(jobs) - (i + 1)) / rate
                print(f"  {i+1}/{len(jobs)} | {rate:.1f}/s | ETA {eta/60:.1f}m")
    print(f"\nDone in {(time.time()-t0)/60:.1f} min")

    # Aggregate by (scenario, kappa)
    by = {}
    for r in results:
        by.setdefault((r["scenario"], r["kappa"]), []).append(r)

    summary = []
    for (sc, k), runs in sorted(by.items()):
        row = {"scenario": sc, "kappa": k, "n_runs": len(runs)}
        for strat in ["lasp_aug", "momentum_dp"]:
            for key in ["delivered", "losses", "delivery_rate",
                        "cap_per_delivery", "cap_per_attempt",
                        "cap_per_routed_attempt", "cap_consumed_lost"]:
                vals = [r[strat][key] for r in runs]
                row[f"{strat}_{key}_mean"] = statistics.mean(vals)
                if len(vals) > 1:
                    row[f"{strat}_{key}_std"] = statistics.stdev(vals)
        summary.append(row)

    with open(DATA / "momentum_clean_kappa_sweep_raw.json", "w") as f:
        json.dump(results, f, indent=1)
    with open(DATA / "momentum_clean_kappa_sweep_summary.json", "w") as f:
        json.dump(summary, f, indent=2)

    print()
    print(f"{'Scenario':<18} {'kappa':>6} {'LASP+ loss':>11} "
          f"{'MOMDP loss':>11} {'delta':>8}")
    print("-" * 70)
    for s in summary:
        la_l = s["lasp_aug_losses_mean"]
        em_l = s["momentum_dp_losses_mean"]
        delta = ((la_l - em_l) / la_l * 100) if la_l > 0 else 0
        print(f"{s['scenario']:<18} {s['kappa']:>6.2f} "
              f"{la_l:>11.2f} {em_l:>11.2f} {delta:>+7.1f}%")
    print()
    print("Saved momentum_clean_kappa_sweep_summary.json")
