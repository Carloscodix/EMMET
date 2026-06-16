"""
*** VOIDED -- DO NOT USE. Superseded by bench_a_realdemand_v2.py ***

This first attempt used simulate_flows + policy_emmet_core, a DIFFERENT engine
from the one the two-factor law was measured with. Its positive control FAILED:
the same engine on the bank topologies with uniform demand (where the signal
is known) collapsed 14/15 topologies to zero drop, pearson -0.01. Instrument
not faithful, so the apparent negative is an artifact, not a finding.
Kept as a documented methodological negative. The valid experiment is
bench_a_realdemand_v2.py (run_bursty engine; control PASSED +0.849; real
demand survives +0.767).

--- original (now-voided) header ---
Bench A (real demand): out-of-sample test of the two-factor law using the
REAL SNDlib demand matrix shipped with each instance, not a synthetic proxy.
"""
import sys, json
import numpy as np
from scipy import stats
import flowsim as FS
from emmet_budget import reset
import emmet_budget
from sweep_topologies import tube_sp
import sndlib_parse as SND

NEW_TOPOS = ["polska", "france", "germany50", "nobel-eu", "nobel-us",
             "norway", "cost266", "janos-us", "atlanta", "newyork",
             "india35", "pioro40", "ta1", "zib54", "giul39",
             "dfn-gwin", "di-yuan", "sun"]
N_SEEDS = 8
N_TICKS = 200

def real_demand_indexed(topo, seed):
    """Load SNDlib topo, apply bench capacity scheme, return (G_int,
    idx_demand) mapping integer-node pairs to REAL demand volumes."""
    G0, dem_names = SND.load(topo)
    G_int, mapping = SND.apply_bench_scheme(G0, seed)
    idx_demand = {}
    for (a, b), vol in dem_names.items():
        if a in mapping and b in mapping and vol > 0:
            ia, ib = mapping[a], mapping[b]
            if ia != ib:
                idx_demand[(ia, ib)] = idx_demand.get((ia, ib), 0.0) + vol
    return G_int, idx_demand

def run_one(topo, seed):
    G_int, dem = real_demand_indexed(topo, seed)
    if not dem:
        return None
    sched = FS.gen_flows(dem, N_TICKS, seed + 9000,
                         birth_rate=0.8, dur_lo=4, dur_hi=12, rate=1)
    out = {}
    for label, pol in [("core", FS.policy_emmet_core),
                       ("conga", FS.policy_conga),
                       ("drill", FS.policy_drill)]:
        Gx, _ = real_demand_indexed(topo, seed); reset(Gx)
        out[label] = FS.simulate_flows(Gx, sched, N_TICKS, pol)["drop_rate"]
    return out

def main():
    emmet_budget.GAMMA = 2.0
    rows = []
    print(f"{'topo':<14} tube/sp  core conga drill redC redD  pairs")
    print("-" * 64)
    for topo in NEW_TOPOS:
        G_int, dem = real_demand_indexed(topo, 0)
        tsp = tube_sp(G_int)
        c = co = dr = 0.0; ok = 0
        for s in range(N_SEEDS):
            r = run_one(topo, s)
            if r is None: continue
            c += r["core"]; co += r["conga"]; dr += r["drill"]; ok += 1
        if ok == 0:
            print(f"{topo:<14} SKIP"); continue
        c/=ok; co/=ok; dr/=ok
        rcg = (co-c)/co*100 if co>0 else 0.0
        rdr = (dr-c)/dr*100 if dr>0 else 0.0
        rows.append({"topo":topo,"tube":tsp,"core":c,"conga":co,"drill":dr,
                     "red_conga":rcg,"red_drill":rdr,"pairs":len(dem)})
        print(f"{topo:<14}{tsp:7.2f}{c:6.3f}{co:6.3f}{dr:6.3f}{rcg:6.1f}{rdr:6.1f}{len(dem):7}")
    return rows

def analyze(rows):
    tube = np.array([r["tube"] for r in rows])
    rc = np.array([r["red_conga"] for r in rows])
    rd = np.array([r["red_drill"] for r in rows])
    print("\n=== PRE-COMMITTED CHECKS (see PREREG) ===")
    res = {}
    for name, red in [("vs CONGA", rc), ("vs DRILL", rd)]:
        r, p = stats.pearsonr(tube, red)
        sr, sp = stats.spearmanr(tube, red)
        p1 = "PASS" if r >= 0.45 else "FAIL"
        p2 = "PASS" if sr >= 0.50 else "FAIL"
        print(f"{name}: pearson r={r:+.3f} (P1>=+0.45 {p1}) "
              f"spearman={sr:+.3f} (P2>=+0.50 {p2}) p={p:.3f}")
        res[name] = {"pearson":r,"spearman":sr,"p":p,"P1":p1,"P2":p2}
    return res

if __name__ == "__main__":
    rows = main()
    res = analyze(rows)
    out = {"rows": rows, "checks": res, "n": len(rows),
           "demand": "real_sndlib"}
    json.dump(out, open("/home/clopez/emmet/data/bench_a_realdemand.json","w"),
              indent=2)
    print("\nsaved data/bench_a_realdemand.json")
