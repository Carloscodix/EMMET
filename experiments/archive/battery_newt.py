"""EMMET-Newt battery: 26-scenario battery + BLOOD LIVE arms.

Per scenario produces four arms:
  lasp_aug, momentum_dp (v1), momentum_live_def, momentum_live_opt.
BLOOD LIVE degenerates bit-for-bit to v1 when blood_rate=0.
"""
import sys, time, json
from pathlib import Path
from multiprocessing import Pool, cpu_count

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "experiments"))

import emmet_budget
from topology_builders import build_grid, build_barabasi_albert, build_watts_strogatz
from momentum_clean import warmup_lasp_aug, warmup_momentum, simulate_lasp_aug, simulate_momentum, aggregate
from emmet_newt import simulate_momentum_live
from emmet_budget import reset, gen_traf, TRAFFIC_STEPS, build_real

DATA = REPO / "data"


BR_DEF = 5.0
GAMMA_DEF = 2.0
BR_OPT = 10.0
GAMMA_OPT = 0.5
N_BUCKETS = 32
N_SEEDS = 100


def run_one(args):
    label, builder, builder_args, seed, kappa = args
    out = {"scenario": label, "seed": seed, "kappa": kappa}
    G = builder(*builder_args, seed=seed)
    n = G.number_of_nodes()
    ws = max(20, n * 5)
    out["num_nodes"] = n

    # LASP-aug (gamma=2.0 implicit via emmet_budget default)
    emmet_budget.GAMMA = 2.0
    G = builder(*builder_args, seed=seed); reset(G)
    wt = gen_traf(list(G.nodes()), ws, seed + 300000)
    snap_la = warmup_lasp_aug(G, wt)
    G = builder(*builder_args, seed=seed); reset(G)
    traf = gen_traf(list(G.nodes()), TRAFFIC_STEPS, seed + 100000)
    out["lasp_aug"] = simulate_lasp_aug(G, traf, snap_la)

    # EMMET v1 (momentum_dp, gamma=2.0)
    G = builder(*builder_args, seed=seed); reset(G)
    wt = gen_traf(list(G.nodes()), ws, seed + 300000)
    snap_m = warmup_momentum(G, wt, kappa, N_BUCKETS)
    G = builder(*builder_args, seed=seed); reset(G)
    traf = gen_traf(list(G.nodes()), TRAFFIC_STEPS, seed + 100000)
    out["momentum_dp"] = simulate_momentum(G, traf, snap_m, kappa, N_BUCKETS)

    # BLOOD LIVE default (gamma=2.0, blood_rate=5.0)
    emmet_budget.GAMMA = GAMMA_DEF
    G = builder(*builder_args, seed=seed); reset(G)
    wt = gen_traf(list(G.nodes()), ws, seed + 300000)
    snap_m = warmup_momentum(G, wt, kappa, N_BUCKETS)
    G = builder(*builder_args, seed=seed); reset(G)
    traf = gen_traf(list(G.nodes()), TRAFFIC_STEPS, seed + 100000)
    out["momentum_live_def"] = simulate_momentum_live(
        G, traf, snap_m, kappa, N_BUCKETS, blood_rate=BR_DEF)

    # BLOOD LIVE opt (gamma=0.5, blood_rate=10.0)
    emmet_budget.GAMMA = GAMMA_OPT
    G = builder(*builder_args, seed=seed); reset(G)
    wt = gen_traf(list(G.nodes()), ws, seed + 300000)
    snap_m = warmup_momentum(G, wt, kappa, N_BUCKETS)
    G = builder(*builder_args, seed=seed); reset(G)
    traf = gen_traf(list(G.nodes()), TRAFFIC_STEPS, seed + 100000)
    out["momentum_live_opt"] = simulate_momentum_live(
        G, traf, snap_m, kappa, N_BUCKETS, blood_rate=BR_OPT)
    # Restore default GAMMA before returning
    emmet_budget.GAMMA = GAMMA_DEF
    return out


def battery_jobs(kappa=1.0):
    jobs = []
    # Grid 7x7 (100 seeds)
    for s in range(N_SEEDS):
        jobs.append(("Grid_7x7", build_grid, (7,), s, kappa))
    # Barabasi-Albert m=2 and m=3 (100 each)
    for m in [2, 3]:
        for s in range(N_SEEDS):
            jobs.append((f"BA_n50_m{m}", build_barabasi_albert, (50, m), s, kappa))
    # Watts-Strogatz k=4 p=0.1 (100 seeds)
    for s in range(N_SEEDS):
        jobs.append(("WS_n50_k4_p0.10", build_watts_strogatz, (50, 4, 0.10), s, kappa))
    # Real WAN backbones: Abilene + GEANT (100 seeds each)
    for graph_name, label in [("Abilene.graphml", "Abilene"), ("Geant.graphml", "Geant")]:
        for s in range(N_SEEDS):
            jobs.append((label, build_real, (graph_name,), s, kappa))
    return jobs


def main():
    jobs = battery_jobs(kappa=1.0)
    print(f"Total jobs: {len(jobs)}", flush=True)
    n_workers = max(1, cpu_count() - 4)
    print(f"Workers: {n_workers}", flush=True)
    t0 = time.time()
    with Pool(n_workers) as pool:
        results = []
        for i, r in enumerate(pool.imap_unordered(run_one, jobs, chunksize=4)):
            results.append(r)
            if (i + 1) % 20 == 0:
                el = (time.time() - t0) / 60
                rate = (i + 1) / el if el > 0 else 0
                eta = (len(jobs) - i - 1) / rate if rate > 0 else 0
                print(f"  {i+1}/{len(jobs)} | {rate:.1f}/min | {el:.1f}m elapsed | ETA {eta:.1f}m", flush=True)
    raw_path = DATA / "battery_newt_raw.json"
    json.dump(results, open(raw_path, "w"), indent=2)
    print(f"Saved {raw_path}", flush=True)
    print(f"Total elapsed: {(time.time()-t0)/60:.1f} min", flush=True)


if __name__ == "__main__":
    main()
