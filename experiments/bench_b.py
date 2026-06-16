"""
Bench B: harness-sensitivity sweep.

Does the two-factor law survive shaking the test bench, or does the physical
core only win under one lucky traffic regime? We vary the burst generator:
burst size (lognormal mu), its spread (sigma), and gap heaviness (pareto
alpha), and re-measure tube/sp ~ loss reduction under each.

Positive control (gate): canonical knobs must reproduce the known in-sample
correlation first. Pre-commit: the DIRECTION (positive tube/sp ~ reduction)
must hold in >=90% of variants. A sign flip means the law is a harness
artifact.
"""
import sys, json, time
sys.path.insert(0, "/home/clopez/emmet/experiments")
import numpy as np
from scipy import stats
import multiprocessing as mp
import bursty_traffic as BT
from sweep_topologies import run_seed, TOPOS, tube_sp

import os
N_SEEDS = int(os.environ.get("BENCH_B_SEEDS", "6"))

def _init_worker():
    import sys, os
    sys.path.insert(0, "/home/clopez/emmet/experiments")
    os.chdir("/home/clopez/emmet/experiments")

def sweep_correlation(seeds=N_SEEDS):
    tube = {name: tube_sp(builder(*bargs, seed=0)) for name, builder, bargs in TOPOS}
    jobs = [(name, builder, bargs, s) for name, builder, bargs in TOPOS for s in range(seeds)]
    with mp.Pool(min(20, mp.cpu_count()), initializer=_init_worker) as pool:
        results = pool.map(run_seed, jobs)
    agg = {}
    for r in results:
        agg.setdefault(r['topo'], {'C': 0, 'R': 0})
        agg[r['topo']]['C'] += r['CONGA']; agg[r['topo']]['R'] += r['RIPPLE']
    xs, ys = [], []
    for name in tube:
        if name == 'Abilene':
            continue
        c, rr = agg[name]['C'], agg[name]['R']
        red = (c - rr) / c * 100 if c > 0 else 0
        xs.append(tube[name]); ys.append(red)
    r, p = stats.pearsonr(xs, ys)
    return r, p

# (knob_name, attribute, value). None value = canonical.
VARIANTS = [
    ("canonical",      None,           None),
    ("burst_small",    "LOGNORMAL_MU", __import__("math").log(2.0)),
    ("burst_large",    "LOGNORMAL_MU", __import__("math").log(4.5)),
    ("spread_tight",   "LOGNORMAL_SIGMA", 0.7),
    ("spread_wide",    "LOGNORMAL_SIGMA", 1.4),
    ("gaps_heavy",     "PARETO_ALPHA", 1.2),
    ("gaps_light",     "PARETO_ALPHA", 2.0),
]

def set_knob(attr, val):
    if attr is None:
        return
    setattr(BT, attr, val)

def reset_knobs():
    BT.LOGNORMAL_MU = __import__("math").log(3.0)
    BT.LOGNORMAL_SIGMA = 1.0
    BT.PARETO_ALPHA = 1.5

def main():
    t0 = time.time()
    results = []
    # 1) POSITIVE CONTROL (gate): canonical knobs must reproduce the in-sample law
    reset_knobs()
    print("[gate] running canonical positive control...", flush=True)
    r_ctrl, p_ctrl = sweep_correlation()
    gate_ok = (r_ctrl > 0.5)
    print(f"[gate] canonical Pearson={r_ctrl:+.3f} (p={p_ctrl:.4f}) -> {'PASS' if gate_ok else 'FAIL'}", flush=True)
    results.append({"variant": "canonical", "knob": None, "val": None, "pearson": r_ctrl, "p": p_ctrl})
    if not gate_ok:
        print("[gate] FAILED: pipeline does not reproduce the in-sample law. Aborting.", flush=True)
        json.dump(results, open("/home/clopez/emmet/data/bench_b.json", "w"), indent=2)
        return

    # 2) PERTURBED VARIANTS
    for vname, attr, val in VARIANTS:
        if vname == "canonical":
            continue
        reset_knobs()
        set_knob(attr, val)
        r, p = sweep_correlation()
        results.append({"variant": vname, "knob": attr, "val": val, "pearson": r, "p": p})
        print(f"[var] {vname:14s} ({attr}={val:.3f}): Pearson={r:+.3f} (p={p:.4f})", flush=True)
    reset_knobs()

    # 3) VERDICT
    signs = [x["pearson"] > 0 for x in results]
    held = sum(signs); frac = held / len(signs)
    rmin = min(x["pearson"] for x in results)
    rmax = max(x["pearson"] for x in results)
    print(f"\n=== VERDICT ===", flush=True)
    print(f"direction positive in {held}/{len(signs)} variants ({100*frac:.0f}%)", flush=True)
    print(f"pre-commit (>=90%): {'PASS' if frac >= 0.9 else 'FAIL'}", flush=True)
    print(f"Pearson range across harness: [{rmin:+.3f}, {rmax:+.3f}]", flush=True)
    json.dump({"results": results, "frac_positive": frac, "r_min": rmin, "r_max": rmax},
              open("/home/clopez/emmet/data/bench_b.json", "w"), indent=2)
    print(f"saved. total {(time.time()-t0)/60:.1f} min", flush=True)

if __name__ == "__main__":
    main()
