"""
Bench A v3: out-of-sample two-factor law test, using the CANONICAL harness.

Key fix over v1/v2: instead of reimplementing the advantage metric, this
reuses sweep_topologies.run_seed verbatim (RIPPLE vs CONGA, bursty
traffic, losses) -- the exact pipeline behind the paper\047s +0.59. A
builder wrapper feeds SNDlib graphs into it.

GATE: a positive control runs the BANK topologies through this same path
first. It must reproduce tube/sp ~ reduction Pearson ~ +0.7 (raw) before
any out-of-sample number is trusted. If the control fails, STOP.
"""
import sys, json
import numpy as np
from scipy import stats
import random
import networkx as nx
from sweep_topologies import run_seed, tube_sp, TOPOS
import sndlib_parse as SND

def make_sndlib_builder(topo):
    """Return a builder(seed=...) that yields the SNDlib graph relabeled to
    ints with the bench capacity/latency scheme -- matching what run_seed
    expects from a synthetic builder."""
    G0, _ = SND.load(topo)
    def builder(seed=0):
        G = nx.Graph(G0)
        rng = random.Random(seed)
        for u, v in G.edges():
            G[u][v]["latency"] = rng.uniform(1, 5)
            G[u][v]["capacity"] = rng.randint(2, 4)
            G[u][v]["load"] = 0; G[u][v]["loss"] = 0
        return nx.relabel_nodes(G, {n: i for i, n in enumerate(G.nodes())})
    return builder

N_SEEDS = 8


def reduction_for(name, builder, bargs):
    """Aggregate CONGA and RIPPLE losses over seeds via the canonical
    run_seed, return reduction% = (CONGA - RIPPLE)/CONGA * 100."""
    c = r = 0.0
    for s in range(N_SEEDS):
        out = run_seed((name, builder, bargs, s))
        c += out["CONGA"]; r += out["RIPPLE"]
    if c <= 0:
        return None, c, r
    return (c - r) / c * 100, c, r

def positive_control():
    """Run BANK topologies through run_seed; must reproduce tube/sp ~
    reduction. Returns (passed, rows)."""
    print("=== POSITIVE CONTROL (bank topologies, canonical harness) ===")
    rows = []
    for name, builder, bargs in TOPOS:
        if name == "Abilene":
            continue  # excluded in the paper analysis (n=14)
        G = builder(*bargs, seed=0)
        tsp = tube_sp(G)
        red, c, r = reduction_for(name, builder, bargs)
        if red is None:
            print(f"  {name:<12} tube={tsp:.2f} no signal")
            continue
        rows.append({"topo": name, "tube": tsp, "reduction": red})
        print(f"  {name:<12} tube={tsp:5.2f}  red={red:+6.1f}pct  (C={c:.0f} R={r:.0f})")
    tube = np.array([x["tube"] for x in rows])
    red = np.array([x["reduction"] for x in rows])
    pr, pp = stats.pearsonr(tube, red)
    sr, sp = stats.spearmanr(tube, red)
    print(f"\n  control: pearson r={pr:+.3f} p={pp:.4f} | spearman {sr:+.3f}  (paper raw ~+0.72)")
    passed = pr >= 0.55
    print("  GATE PASS" if passed else "  GATE FAIL -- pipeline not faithful, STOP")
    return passed, rows

NEW_TOPOS = ["polska", "france", "germany50", "nobel-eu", "nobel-us",
             "norway", "cost266", "janos-us", "atlanta", "newyork",
             "india35", "pioro40", "ta1", "zib54", "giul39",
             "dfn-gwin", "di-yuan", "sun"]


def out_of_sample():
    print("\n=== OUT-OF-SAMPLE (SNDlib backbones, same harness) ===")
    rows = []
    for topo in NEW_TOPOS:
        builder = make_sndlib_builder(topo)
        G = builder(seed=0)
        tsp = tube_sp(G)
        red, c, r = reduction_for(topo, builder, ())
        if red is None:
            print(f"  {topo:<12} tube={tsp:.2f} no signal")
            continue
        rows.append({"topo": topo, "tube": tsp, "reduction": red})
        print(f"  {topo:<12} tube={tsp:5.2f}  red={red:+6.1f}pct  (C={c:.0f} R={r:.0f})")
    return rows

if __name__ == "__main__":
    passed, ctrl = positive_control()
    if not passed:
        print("\nABORT: positive control failed; out-of-sample skipped.")
        json.dump({"control": ctrl, "gate": "FAIL"},
                  open("/home/clopez/emmet/data/bench_a_v3.json", "w"), indent=2)
        sys.exit(1)
    oos = out_of_sample()
    tube = np.array([x["tube"] for x in oos])
    red = np.array([x["reduction"] for x in oos])
    pr, pp = stats.pearsonr(tube, red)
    sr, sp = stats.spearmanr(tube, red)
    print(f"\n=== OUT-OF-SAMPLE RESULT (n={len(oos)}) ===")
    print(f"tube/sp ~ reduction: pearson r={pr:+.3f} p={pp:.4f} spearman {sr:+.3f} p={sp:.4f}")
    verdict = "PASS" if (pr >= 0.45 and pp < 0.10) else ("WEAK" if pr > 0 else "FAIL")
    print(f"pre-commit (r>=0.45, p<0.10): {verdict}")
    json.dump({"gate":"PASS","control":ctrl,"oos":oos,"oos_pearson":pr,"oos_p":pp,"oos_spearman":sr}, open("/home/clopez/emmet/data/bench_a_v3.json","w"), indent=2)
    print("\nsaved data/bench_a_v3.json")
