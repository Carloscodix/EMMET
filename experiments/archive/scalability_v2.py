"""Scalability battery for EMMET v2.0 - n in {100, 250, 500, 1000}.

Reuses the same runner used in the v1 paper (topology_extended_battery.run_one):
same kappa=1.0, 32 mass buckets, alpha=1.25 hop budget, paired warmup.
Only the network size varies.

Topologies:
  ER (Erdos-Renyi) n x p
  WS (Watts-Strogatz) n x k=4, p=0.10

Seeds: 100 per configuration.
"""
import sys, time, json
from pathlib import Path
from multiprocessing import Pool, cpu_count

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "experiments"))

from topology_extended_battery import run_one
from topology_builders import build_watts_strogatz
from momentum_clean import aggregate
import networkx as nx
import random

def build_er(n, p, seed):
    """Build an Erdos-Renyi graph with the same edge attributes used by v1."""
    G = nx.erdos_renyi_graph(n, p, seed=seed)
    rng = random.Random(seed)
    for u, v in G.edges():
        G[u][v]["latency"] = rng.uniform(1, 5)
        G[u][v]["capacity"] = rng.randint(3, 6)
        G[u][v]["load"] = 0
        G[u][v]["loss"] = 0
    return G

DATA = REPO / "data"
N_SEEDS = 100
KAPPA = 1.0

def battery_jobs():
    """Build the job list: (label, builder, args, seed, kappa) tuples."""
    jobs = []
    # ER scalability: n in {100,250,500,1000} x p in {0.05, 0.10, 0.20}
    for n in [100, 250, 500, 1000]:
        for p in [0.05, 0.10, 0.20]:
            label = f"ER_n{n}_p{p:.2f}"
            for s in range(N_SEEDS):
                jobs.append((label, build_er, (n, p), s, KAPPA))
    # WS scalability: n in {100,250,500,1000} x k=4, p=0.10
    for n in [100, 250, 500, 1000]:
        label = f"WS_n{n}_k4_p0.10"
        for s in range(N_SEEDS):
            jobs.append((label, build_watts_strogatz, (n, 4, 0.10), s, KAPPA))
    return jobs

def save_checkpoint(results, path):
    """Save current results to disk for resumability."""
    with open(path, "w") as f:
        json.dump(results, f, indent=1)

def main():
    jobs = battery_jobs()
    total = len(jobs)
    print(f"Scalability v2 battery: {total} jobs (kappa={KAPPA}, 32 buckets)")
    print(f"  ER: 4 sizes x 3 densities x {N_SEEDS} seeds = {4*3*N_SEEDS}")
    print(f"  WS: 4 sizes x 1 config x {N_SEEDS} seeds = {4*N_SEEDS}")
    sys.stdout.flush()

    workers = max(1, cpu_count() - 4)
    print(f"  workers: {workers} (of {cpu_count()} cores)")
    sys.stdout.flush()

    raw_out = DATA / "scalability_v2_raw.json"
    ckpt_out = DATA / "scalability_v2_checkpoint.json"
    summary_out = DATA / "scalability_v2_summary.json"

    t0 = time.time()
    results = []
    with Pool(workers) as pool:
        for i, r in enumerate(pool.imap_unordered(run_one, jobs, chunksize=1)):
            results.append(r)
            if (i + 1) % 50 == 0:
                elapsed = time.time() - t0
                rate = (i + 1) / elapsed
                eta = (total - (i + 1)) / rate
                print(f"  {i+1}/{total} | {rate:.2f}/s | elapsed {elapsed/60:.1f}m | ETA {eta/60:.1f}m")
                sys.stdout.flush()
                save_checkpoint(results, ckpt_out)

    elapsed = time.time() - t0
    print(f"\nDone in {elapsed/60:.1f} min ({elapsed/3600:.2f}h)")

    with open(raw_out, "w") as f:
        json.dump(results, f, indent=1)
    summary = aggregate(results)
    with open(summary_out, "w") as f:
        json.dump(summary, f, indent=2)

    print()
    fmt = "{:<22} {:>8} {:>10} {:>10} {:>11} {:>11} {:>10}"
    print(fmt.format("Scenario", "N", "LASP+ dr", "MOMDP dr",
                     "LASP+ loss", "MOMDP loss", "delta"))
    print("-" * 92)
    for s in summary:
        sc = s["scenario"]
        n = s.get("num_nodes_mean", s.get("num_nodes", 0))
        la_dr = s["lasp_aug_delivery_rate_mean"]
        em_dr = s["momentum_dp_delivery_rate_mean"]
        la_l = s["lasp_aug_losses_mean"]
        em_l = s["momentum_dp_losses_mean"]
        delta = ((la_l - em_l) / la_l * 100) if la_l > 0 else 0
        print(fmt.format(sc, f"{n:.0f}", f"{la_dr:.1f}%", f"{em_dr:.1f}%",
                          f"{la_l:.2f}", f"{em_l:.2f}", f"{delta:+.1f}%"))
    print(f"\nSaved {raw_out}")
    print(f"Saved {summary_out}")

if __name__ == "__main__":
    main()
