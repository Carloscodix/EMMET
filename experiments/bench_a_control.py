"""Positive control for bench A: training topologies through the EXACT
bench_a pipeline. If signal cannot be detected here, the pipeline is
broken and v1/v2 mean nothing."""
import sys
sys.path.insert(0, "experiments")
import numpy as np, random
from scipy import stats
import flowsim as FS
from equivalence import unif_demand
from emmet_budget import reset
import emmet_budget
from sweep_topologies import tube_sp, TOPOS, build_grid, build_watts_strogatz, build_barabasi_albert, build_real

emmet_budget.GAMMA = 2.0
N_SEEDS = 8
N_TICKS = 200
def _scheme(G, seed):
    rng = random.Random(seed)
    for u, v in G.edges():
        G[u][v]["latency"] = rng.uniform(1, 5)
        G[u][v]["capacity"] = rng.randint(2, 4)
        G[u][v]["load"] = 0; G[u][v]["loss"] = 0
    return G

def measure_bank(builder, bargs, birth):
    acc = {"core": 0.0, "conga": 0.0, "drill": 0.0}
    for s in range(N_SEEDS):
        G = _scheme(builder(*bargs, seed=s), s)
        dem = unif_demand(G)
        sched = FS.gen_flows(dem, N_TICKS, s + 9000, birth_rate=birth, dur_lo=4, dur_hi=12, rate=1)
        for label, pol in [("core", FS.policy_emmet_core), ("conga", FS.policy_conga), ("drill", FS.policy_drill)]:
            G2 = _scheme(builder(*bargs, seed=s), s); reset(G2)
            acc[label] += FS.simulate_flows(G2, sched, N_TICKS, pol)["drop_rate"]
    return {k: v / N_SEEDS for k, v in acc.items()}
rows = []
print("topo          tube   core  conga  drill   advC")
for name, builder, bargs in TOPOS:
    G = builder(*bargs, seed=0)
    tsp = tube_sp(G)
    m = measure_bank(builder, bargs, 0.8)
    advC = (m["conga"] - m["core"]) * 100
    rows.append({"topo": name, "tube": tsp, "advC": advC, **m})
    print("%-12s%6.2f%7.3f%7.3f%7.3f%7.2f" % (name, tsp, m["core"], m["conga"], m["drill"], advC))

tube = np.array([r["tube"] for r in rows])
adv = np.array([r["advC"] for r in rows])
r, p = stats.pearsonr(tube, adv); sr, sp = stats.spearmanr(tube, adv)
print()
print("IN-SAMPLE via bench_a pipeline: pearson r=%+.3f p=%.3f | spearman=%+.3f p=%.3f" % (r, p, sr, sp))
print("paper in-sample partial was +0.59. If near 0, the PIPELINE is broken.")
