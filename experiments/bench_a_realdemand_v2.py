"""Bench A real-demand v2 -- simulator-faithful version.

v1 used simulate_flows (wrong engine); its positive control FAILED.
This version uses the SAME engine as published results (run_bursty +
ripple) and changes EXACTLY ONE thing vs bench_a_v3: spatial demand.
Uniform arm = positive control (reproduces bench_a_v3); real arm feeds
each SNDlib instance its REAL demand via gen_bursty_weighted."""
import sys, json, random
import numpy as np
import networkx as nx
from scipy import stats
from sweep_topologies import tube_sp, GAMMA_OPT, BR_OPT, RIPPLE, RIPPLE_STEPS
from bursty_traffic import gen_bursty, gen_bursty_weighted
from bursty_warmup import warmup_bursty_momentum
from bursty_runner import run_bursty_conga, run_bursty_emmet_live_ripple
from emmet_budget import reset
import emmet_budget
import sndlib_parse as SND

N_SEEDS = 8
NEW_TOPOS = ["polska", "france", "germany50", "nobel-eu", "nobel-us",
             "norway", "cost266", "janos-us", "atlanta", "newyork",
             "india35", "pioro40", "ta1", "zib54", "giul39",
             "dfn-gwin", "di-yuan", "sun"]


def topo_demand(topo):
    """Return (builder_fn, pairs, weights): builder makes the int-relabeled
    SNDlib graph with bench capacity scheme; pairs/weights are the REAL
    demand mapped to integer-node pairs."""
    G0, dem_names = SND.load(topo)
    mapping = {n: i for i, n in enumerate(G0.nodes())}
    pairs, weights = [], []
    for (a, b), v in dem_names.items():
        if a in mapping and b in mapping and v > 0 and mapping[a] != mapping[b]:
            pairs.append((mapping[a], mapping[b])); weights.append(v)
    def builder(seed):
        G = nx.Graph(G0); rng = random.Random(seed)
        for u, v in G.edges():
            G[u][v]["latency"] = rng.uniform(1, 5)
            G[u][v]["capacity"] = rng.randint(2, 4)
            G[u][v]["load"] = 0; G[u][v]["loss"] = 0
        return nx.relabel_nodes(G, mapping)
    return builder, pairs, weights


def run_seed_demand(builder, pairs, weights, seed, mode):
    """run_seed structure; traffic uniform or real-demand-weighted."""
    G1 = builder(seed); reset(G1)
    n = G1.number_of_nodes(); ws = max(20, n * 5)
    if mode == "uniform":
        nodes = list(G1.nodes())
        tr1 = gen_bursty(nodes, 200, seed + 100000)
        wt  = gen_bursty(nodes, ws, seed + 700000)
        tr3 = gen_bursty(nodes, 200, seed + 100000)
    else:
        tr1 = gen_bursty_weighted(pairs, weights, 200, seed + 100000)
        wt  = gen_bursty_weighted(pairs, weights, ws, seed + 700000)
        tr3 = gen_bursty_weighted(pairs, weights, 200, seed + 100000)
    conga = run_bursty_conga(G1, tr1)["losses"]
    emmet_budget.GAMMA = GAMMA_OPT
    G2 = builder(seed); reset(G2)
    snap = warmup_bursty_momentum(G2, wt, 1.0, 32)
    G3 = builder(seed); reset(G3)
    ripple = run_bursty_emmet_live_ripple(G3, tr3, snap, 1.0, 32,
        blood_rate=BR_OPT, ripple=RIPPLE, ripple_steps=RIPPLE_STEPS)["losses"]
    emmet_budget.GAMMA = 2.0
    return conga, ripple


def measure(mode):
    rows = []
    print(f"\n--- MODE: {mode} ---")
    print(f"{'topo':<12} tube/sp  conga ripple   red%")
    for topo in NEW_TOPOS:
        builder, pairs, weights = topo_demand(topo)
        if not pairs:
            print(f"{topo:<12} SKIP"); continue
        tsp = tube_sp(builder(0))
        c = r = 0.0
        for s in range(N_SEEDS):
            cc, rr = run_seed_demand(builder, pairs, weights, s, mode)
            c += cc; r += rr
        c /= N_SEEDS; r /= N_SEEDS
        red = (c - r) / c * 100 if c > 0 else 0.0
        rows.append({"topo": topo, "tube": tsp, "conga": c,
                     "ripple": r, "red": red})
        print(f"{topo:<12}{tsp:7.2f}{c:7.1f}{r:7.1f}{red:7.1f}")
    return rows


def corr(rows):
    t = np.array([x["tube"] for x in rows])
    rd = np.array([x["red"] for x in rows])
    pr, pp = stats.pearsonr(t, rd)
    sr, sp = stats.spearmanr(t, rd)
    return pr, pp, sr, sp


if __name__ == "__main__":
    print("=== PHASE 1 -- POSITIVE CONTROL (uniform, must reproduce ~+0.85) ===")
    ctrl = measure("uniform")
    cpr, cpp, csr, csp = corr(ctrl)
    print(f"\nCONTROL: pearson={cpr:+.3f} (p={cpp:.3f}) spearman={csr:+.3f}")
    passed = cpr >= 0.45
    print(f"CONTROL {'PASSED' if passed else 'FAILED'} (need pearson>=+0.45)")
    out = {"control": {"rows": ctrl, "pearson": cpr, "spearman": csr,
                       "passed": bool(passed)}}
    if not passed:
        print("\nInstrument not faithful -- real arm NOT run.")
        json.dump(out, open("/home/clopez/emmet/data/bench_a_realdemand_v2.json","w"), indent=2)
        sys.exit(0)
    print("\n=== PHASE 2 -- REAL DEMAND (the experiment) ===")
    real = measure("real")
    rpr, rpp, rsr, rsp = corr(real)
    print(f"\nREAL: pearson={rpr:+.3f} (p={rpp:.3f}) spearman={rsr:+.3f}")
    out["real"] = {"rows": real, "pearson": rpr, "spearman": rsr}
    json.dump(out, open("/home/clopez/emmet/data/bench_a_realdemand_v2.json","w"), indent=2)
    print("\nsaved data/bench_a_realdemand_v2.json")
