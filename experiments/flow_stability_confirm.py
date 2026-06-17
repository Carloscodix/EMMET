"""
CONFIRMATORY run of the flow-stability finding, on FRESH seeds (100-119).
Pre-registered in PREREG_flow_stability_confirm.md (committed before run).
Tests: core path_change_rate < CONGA in LOW band, CONGA-core >= 0.15, core
wins in >= 6/7 LOW topos. Reuses machinery in flow_stability.py.
"""
import sys, json
import numpy as np
import flow_stability as FS

SEEDS = list(range(100, 120))


def band(topos, label):
    print(f"\n--- {label} ---")
    print(f"{'topo':<11}{'core':>8}{'conga':>8}{'drill':>8}  c<cg?")
    rows = []
    for topo in topos:
        b = FS._builder(topo)
        acc = {"core": 0.0, "conga": 0.0, "drill": 0.0}
        for s in SEEDS:
            r = FS.measure_topo(b, s)
            for k in acc:
                acc[k] += r[k]["path_change_rate"]
        for k in acc:
            acc[k] /= len(SEEDS)
        win = acc["core"] < acc["conga"]
        rows.append({"topo": topo, **acc, "core_more_stable": bool(win)})
        print(f"{topo:<11}{acc['core']:>8.3f}{acc['conga']:>8.3f}"
              f"{acc['drill']:>8.3f}  {'YES' if win else 'no'}")
    return rows


if __name__ == "__main__":
    print("=== P3 POSITIVE CONTROL (first) ===")
    if not FS.positive_control():
        print("Control failed -- voided."); sys.exit(0)
    low = band(FS.LOW, "LOW fresh 100-119")
    high = band(FS.HIGH, "HIGH fresh 100-119")
    def bmean(rows):
        return {k: float(np.mean([r[k] for r in rows]))
                for k in ["core", "conga", "drill"]}
    lm, hm = bmean(low), bmean(high)
    gap_low = lm["conga"] - lm["core"]
    gap_high = hm["conga"] - hm["core"]
    wins = sum(1 for r in low if r["core_more_stable"])
    print("\n=== CONFIRMATORY VERDICT ===")
    print(f"LOW : core={lm['core']:.3f} conga={lm['conga']:.3f} gap={gap_low:+.3f}")
    print(f"HIGH: core={hm['core']:.3f} conga={hm['conga']:.3f} gap={gap_high:+.3f}")
    h_pass = gap_low >= 0.15 and wins >= 6
    s1_pass = gap_high < gap_low
    print(f"H  (gap>=0.15 AND wins>=6/7): gap={gap_low:+.3f} wins={wins}/7 -> {'PASS' if h_pass else 'FAIL'}")
    print(f"S1 (gap shrinks HIGH): {gap_low:+.3f}->{gap_high:+.3f} -> {'PASS' if s1_pass else 'FAIL'}")
    out = {"seeds": SEEDS, "low": low, "high": high, "low_mean": lm,
           "high_mean": hm, "gap_low": gap_low, "gap_high": gap_high,
           "wins_low": wins, "H_pass": bool(h_pass), "S1_pass": bool(s1_pass)}
    json.dump(out, open("/home/clopez/emmet/data/flow_stability_confirm.json","w"), indent=2)
    print("\nsaved data/flow_stability_confirm.json")
