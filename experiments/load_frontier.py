"""
Load-frontier experiment (gap A). Pre-registered in PREREG_load_frontier.md.
Tests whether the tube/sp law's strength is bell-shaped along the traffic-
pressure axis: strong in the middle band, weak in the drop-zero and collapse
extremes. Same faithful engine as bench A.

VERDICT (post-run, audited): the bell shape was NOT confirmed. P1/P3/P4 failed.
Two things survive into the paper; the rest is discarded here:
  (1) DROP-ZERO MUTING (P2 passed): at high capacity every router drops zero
      packets and the law's correlation goes to 0 -- nothing to redistribute.
      Reported in the two-factor microfoundation.
  (2) BASELINE FAIRNESS (audit spin-off): LASP and ECMP run alongside show
      CONGA is a STRONG baseline in the operating band (blind routers lose to
      it), so equivalence is parity with the best of the class. Reported in
      the fair-comparison section.
The COLLAPSE r=0.959 is an ARTIFACT, not a paper finding: the 4-router audit
showed LASP beats CONGA there MORE than the core does -- the "advantage" is
CONGA degrading under collapse in dense high-tube/sp graphs, not physics
rescuing the net. The bell-shape framing is dropped.
"""
import sys, json
import numpy as np
import networkx as nx
import random
from scipy import stats
from sweep_topologies import tube_sp, GAMMA_OPT, BR_OPT, RIPPLE, RIPPLE_STEPS
from bursty_traffic import gen_bursty
from bursty_warmup import warmup_bursty_momentum
from bursty_runner import run_bursty_conga, run_bursty_emmet_live_ripple
from emmet_budget import reset
import emmet_budget
import sndlib_parse as SND

TOPOS = ["nobel-us", "polska", "atlanta", "nobel-eu", "cost266", "janos-us",
         "zib54", "france", "norway", "sun", "germany50", "india35",
         "pioro40", "giul39", "newyork", "di-yuan", "dfn-gwin"]
SEEDS = list(range(200, 208))
BANDS = {"collapse": (1, 2), "middle": (4, 7), "dropzero": (14, 22)}


def make_builder(topo, cap_lo, cap_hi):
    G0, _ = SND.load(topo)
    mapping = {n: i for i, n in enumerate(G0.nodes())}
    def builder(seed):
        G = nx.Graph(G0); rng = random.Random(seed)
        for u, v in G.edges():
            G[u][v]["latency"] = rng.uniform(1, 5)
            G[u][v]["capacity"] = rng.randint(cap_lo, cap_hi)
            G[u][v]["load"] = 0; G[u][v]["loss"] = 0
        return nx.relabel_nodes(G, mapping)
    return builder


def run_seed(builder, seed):
    G1 = builder(seed); reset(G1)
    nodes = list(G1.nodes()); n = len(nodes); ws = max(20, n * 5)
    tr1 = gen_bursty(nodes, 200, seed + 100000)
    conga = run_bursty_conga(G1, tr1)["losses"]
    emmet_budget.GAMMA = GAMMA_OPT
    G2 = builder(seed); reset(G2)
    wt = gen_bursty(nodes, ws, seed + 700000)
    snap = warmup_bursty_momentum(G2, wt, 1.0, 32)
    G3 = builder(seed); reset(G3)
    tr3 = gen_bursty(nodes, 200, seed + 100000)
    ripple = run_bursty_emmet_live_ripple(G3, tr3, snap, 1.0, 32,
        blood_rate=BR_OPT, ripple=RIPPLE, ripple_steps=RIPPLE_STEPS)["losses"]
    emmet_budget.GAMMA = 2.0
    return conga, ripple


def measure_band(band_name, cap):
    lo, hi = cap
    print(f"\n--- BAND {band_name} (cap {lo}-{hi}) ---")
    tubes, advs, rows = [], [], []
    for topo in TOPOS:
        b = make_builder(topo, lo, hi)
        tsp = tube_sp(b(0))
        c = r = 0.0
        for s in SEEDS:
            cc, rr = run_seed(b, s)
            c += cc; r += rr
        c /= len(SEEDS); r /= len(SEEDS)
        adv = (c - r) / c * 100 if c > 0 else 0.0
        tubes.append(tsp); advs.append(adv)
        rows.append({"topo": topo, "tube": tsp, "conga": c, "ripple": r, "adv": adv})
        print(f"{topo:<11}{tsp:>7.2f}{c:>7.1f}{r:>7.1f}{adv:>7.1f}")
    # degenerate guard: if advantages have ~no variance (drop-zero band),
    # correlation is undefined -> report as no-signal (r=0), the law is mute.
    if np.std(advs) < 1e-6:
        pr, pp, sr = 0.0, 1.0, 0.0
    else:
        pr, pp = stats.pearsonr(tubes, advs)
        sr, _ = stats.spearmanr(tubes, advs)
    mc = float(np.mean([x["conga"] for x in rows]))
    print(f"  r(tube,adv)={pr:+.3f} (p={pp:.3f}) spearman={sr:+.3f} meanCONGA={mc:.1f}")
    return {"band": band_name, "cap": cap, "pearson": pr, "spearman": sr,
            "mean_conga_losses": mc, "rows": rows}


if __name__ == "__main__":
    res = {}
    for name in ["collapse", "middle", "dropzero"]:
        res[name] = measure_band(name, BANDS[name])
    rm = res["middle"]["pearson"]
    rc = res["collapse"]["pearson"]
    rz = res["dropzero"]["pearson"]
    p1 = rm >= 0.45
    p2 = abs(rz) < abs(rm) - 0.20
    p3 = abs(rc) < abs(rm) - 0.15
    p4 = rm == max(rm, rc, rz)
    print("\n=== VERDICT ===")
    print(f"r_middle  ={rm:+.3f} (meanCONGA {res['middle']['mean_conga_losses']:.1f})")
    print(f"r_collapse={rc:+.3f} (meanCONGA {res['collapse']['mean_conga_losses']:.1f})")
    print(f"r_dropzero={rz:+.3f} (meanCONGA {res['dropzero']['mean_conga_losses']:.1f})")
    print(f"P1 middle>=+0.45: {rm:+.3f} -> {'PASS' if p1 else 'FAIL'}")
    print(f"P2 |r_zero|<|r_mid|-0.20: -> {'PASS' if p2 else 'FAIL'}")
    print(f"P3 |r_coll|<|r_mid|-0.15: -> {'PASS' if p3 else 'FAIL'}")
    print(f"P4 middle is max: -> {'PASS' if p4 else 'FAIL'}")
    out = {"bands": res, "r_middle": rm, "r_collapse": rc, "r_dropzero": rz,
           "P1": bool(p1), "P2": bool(p2), "P3": bool(p3), "P4": bool(p4)}
    json.dump(out, open("/home/clopez/emmet/data/load_frontier.json","w"), indent=2)
    print("\nsaved data/load_frontier.json")
