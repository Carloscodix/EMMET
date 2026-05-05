"""Extended topology battery for EMMET-momentum-DP vs LASP-aug.

Runs the clean comparison (own warmup, 32 buckets, kappa=1.0, alpha=1.25,
half-up rounding) on six new topology types:

  - 2D grid 7x7 (49 nodes, regular topology)
  - Barabasi-Albert n=50, m=2 (scale-free, low density)
  - Barabasi-Albert n=50, m=3 (scale-free, medium density)
  - Watts-Strogatz n=50, k=4, p=0.05 (small-world, low rewire)
  - Watts-Strogatz n=50, k=4, p=0.10 (small-world, medium rewire)
  - Watts-Strogatz n=50, k=4, p=0.30 (small-world, high rewire)

Same seed counts as ER battery (100 seeds each) for direct comparison.
"""
import sys
import time
import json
import statistics
from pathlib import Path
from multiprocessing import Pool, cpu_count

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "experiments"))

from topology_builders import (
    build_grid, build_barabasi_albert, build_watts_strogatz,
)
from momentum_clean import (
    run_one as run_one_clean, aggregate, warmup_lasp_aug, warmup_momentum,
    simulate_lasp_aug, simulate_momentum,
)
from emmet_budget import reset, gen_traf, TRAFFIC_STEPS

DATA = REPO / "data"


def run_one(args):
    """Like momentum_clean.run_one but topology builders take diverse args."""
    label, builder, builder_args, seed, kappa = args
    n_buckets = 32
    G = builder(*builder_args, seed=seed)
    n = G.number_of_nodes()
    ws = max(20, n * 5)
    out = {"scenario": label, "seed": seed, "kappa": kappa, "num_nodes": n}

    G = builder(*builder_args, seed=seed); reset(G)
    wt = gen_traf(list(G.nodes()), ws, seed + 300000)
    snap_la = warmup_lasp_aug(G, wt)
    G = builder(*builder_args, seed=seed); reset(G)
    traf = gen_traf(list(G.nodes()), TRAFFIC_STEPS, seed + 100000)
    out["lasp_aug"] = simulate_lasp_aug(G, traf, snap_la)

    G = builder(*builder_args, seed=seed); reset(G)
    wt = gen_traf(list(G.nodes()), ws, seed + 300000)
    snap_m = warmup_momentum(G, wt, kappa, n_buckets)
    G = builder(*builder_args, seed=seed); reset(G)
    traf = gen_traf(list(G.nodes()), TRAFFIC_STEPS, seed + 100000)
    out["momentum_dp"] = simulate_momentum(G, traf, snap_m, kappa, n_buckets)

    return out


def battery_jobs(kappa=1.0):
    jobs = []
    # Grid 7x7
    for s in range(100):
        jobs.append(("Grid_7x7", build_grid, (7,), s, kappa))
    # Barabasi-Albert
    for m in [2, 3]:
        for s in range(100):
            jobs.append((f"BA_n50_m{m}", build_barabasi_albert, (50, m), s, kappa))
    # Watts-Strogatz
    for p in [0.05, 0.10, 0.30]:
        for s in range(100):
            jobs.append((f"WS_n50_k4_p{p:.2f}", build_watts_strogatz,
                         (50, 4, p), s, kappa))
    return jobs


if __name__ == "__main__":
    KAPPA = 1.0
    jobs = battery_jobs(kappa=KAPPA)
    print(f"Extended topology battery: {len(jobs)} jobs (kappa={KAPPA}, 32 buckets)")
    workers = max(1, cpu_count() - 4)
    print(f"workers: {workers}")

    t0 = time.time()
    with Pool(workers) as pool:
        results = []
        for i, r in enumerate(pool.imap_unordered(run_one, jobs, chunksize=4)):
            results.append(r)
            if (i + 1) % 50 == 0:
                elapsed = time.time() - t0
                rate = (i + 1) / elapsed
                eta = (len(jobs) - (i + 1)) / rate
                print(f"  {i+1}/{len(jobs)} | {rate:.1f}/s | ETA {eta/60:.1f}m")
    print(f"\nDone in {(time.time()-t0)/60:.1f} min")

    with open(DATA / "topology_extended_raw.json", "w") as f:
        json.dump(results, f, indent=1)
    summary = aggregate(results)
    with open(DATA / "topology_extended_summary.json", "w") as f:
        json.dump(summary, f, indent=2)

    print()
    fmt_hdr = "{:<22} {:>8} {:>10} {:>10} {:>11} {:>11} {:>10}"
    print(fmt_hdr.format("Scenario", "N", "LASP+ dr", "MOMDP dr",
                         "LASP+ loss", "MOMDP loss", "delta"))
    print("-" * 90)
    for s in summary:
        sc = s["scenario"]
        n = s.get("num_nodes_mean", s.get("num_nodes", 0))
        la_dr = s["lasp_aug_delivery_rate_mean"]
        em_dr = s["momentum_dp_delivery_rate_mean"]
        la_l = s["lasp_aug_losses_mean"]
        em_l = s["momentum_dp_losses_mean"]
        delta = ((la_l - em_l) / la_l * 100) if la_l > 0 else 0
        print(f"{sc:<22} {n:>8} {la_dr:>9.1f}% {em_dr:>9.1f}% "
              f"{la_l:>11.2f} {em_l:>11.2f} {delta:>+9.1f}%")
    print()
    print("Saved topology_extended_summary.json")
