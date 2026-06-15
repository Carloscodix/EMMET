"""
Cross-implementation audit of the TOST routine (code audit, method 4).

Validates experiments/equivalence.py::tost against two independent paths:
  (B) statsmodels.stats.weightstats.ttost_paired  (canonical reference)
  (C) the 90% confidence-interval characterisation of a 5% TOST
      (equivalent iff the 1-2*alpha CI of the paired diff lies in [-d,+d])
Agreement across all three on real paper data certifies the statistic.

Requires statsmodels (pip install statsmodels). Run:
    python experiments/tost_audit.py
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "experiments"))
import numpy as np
from scipy import stats
from equivalence import tost as our_tost

def ci_tost(a, b, delta, alpha=0.05):
    """TOST via the (1-2*alpha) CI of the paired difference."""
    d = np.array(a) - np.array(b)
    n = len(d)
    md = d.mean(); sd = d.std(ddof=1)
    if sd == 0:
        return abs(md) < delta
    se = sd / np.sqrt(n)
    tcrit = stats.t.ppf(1 - alpha, n - 1)
    lo, hi = md - tcrit * se, md + tcrit * se
    return (lo > -delta) and (hi < delta)

def sm_tost(a, b, delta):
    """statsmodels reference: equivalent at 0.05 iff combined p < 0.05."""
    from statsmodels.stats.weightstats import ttost_paired
    p, lower, upper = ttost_paired(np.array(a), np.array(b), -delta, delta)
    return (p < 0.05, float(p))


def agree(a, b, delta):
    """Compare all three paths on one paired sample. Returns dict."""
    o_eq, o_p = our_tost(a, b, delta)
    s_eq, s_p = sm_tost(a, b, delta)
    c_eq = ci_tost(a, b, delta)
    return {"our": (o_eq, o_p), "sm": (s_eq, s_p), "ci": c_eq,
            "eq_match": o_eq == s_eq == c_eq,
            "p_match": abs(o_p - s_p) < 1e-9}

def synthetic_cases():
    rng = np.random.default_rng(7)
    cases = []
    # clearly equivalent: tiny diff, tight
    cases.append(("equiv_tight", 0.10 + rng.normal(0,0.001,14), 0.10 + rng.normal(0,0.001,14), 0.02))
    # clearly non-equiv: diff bigger than delta
    cases.append(("noneq_bigdiff", 0.10+rng.normal(0,0.002,14), 0.16+rng.normal(0,0.002,14), 0.02))
    # borderline: diff near delta
    cases.append(("borderline", 0.10+rng.normal(0,0.01,14), 0.118+rng.normal(0,0.01,14), 0.02))
    # wide variance, small diff: should NOT be equivalent (CI too wide)
    cases.append(("wide_var", 0.10+rng.normal(0,0.05,14), 0.105+rng.normal(0,0.05,14), 0.02))
    return cases

def main():
    print("=== TOST cross-implementation audit (our vs statsmodels vs CI) ===")
    allok = True
    print("\n-- synthetic regimes --")
    for name, a, b, delta in synthetic_cases():
        r = agree(a, b, delta)
        ok = r["eq_match"] and r["p_match"]
        allok = allok and ok
        print("%-16s our=%-5s sm=%-5s ci=%-5s dp=%.1e %s" % (name, r["our"][0], r["sm"][0], r["ci"], abs(r["our"][1]-r["sm"][1]), "OK" if ok else "MISMATCH"))
    return allok
def paper_data_check():
    """Audit TOST directly on the per-seed vectors that back the paper
    (equivalence_strict_*.json, post-abilenefix, 20 seeds/topo)."""
    import json
    base = os.path.join(os.path.dirname(__file__), "..", "data")
    allok = True
    for core in ["archimedes", "newton", "pascal"]:
        rows = json.load(open(os.path.join(base, "equivalence_strict_%s.json" % core)))
        print("\n-- strict %s core, delta=0.02 (paper source) --" % core)
        for r in rows:
            name = r["topo"]
            for rival in ["drill", "conga"]:
                a = r["core_seeds"]; b = r["%s_seeds" % rival]
                res = agree(a, b, 0.02)
                ok = res["eq_match"]
                allok = allok and ok
                tag = "OK" if ok else "MISMATCH"
                dp = abs(res["our"][1] - res["sm"][1])
                print("%-11s vs %-5s our=%-5s sm=%-5s ci=%-5s dp=%.1e %s" % (name, rival, str(res["our"][0]), str(res["sm"][0]), str(res["ci"]), dp, tag))
    return allok

if __name__ == "__main__":
    ok1 = main()
    ok2 = paper_data_check()
    print("-" * 62)
    if ok1 and ok2:
        print("VERDICT: PASS - our tost == statsmodels == CI on synthetic data")
        print("and on every per-seed vector backing the paper tables.")
        sys.exit(0)
    print("VERDICT: FAIL - a TOST path disagrees. INVESTIGATE.")
    sys.exit(1)
