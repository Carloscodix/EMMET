"""Bootstrap CI 95% for EMMET-Newt battery (4 arms).

Computes three paired comparisons per scenario:
  - LASP_aug vs momentum_live_opt (vs strong baseline)
  - momentum_dp (v1) vs momentum_live_def (improvement default)
  - momentum_dp (v1) vs momentum_live_opt (improvement opt)

Same statistical machinery as bootstrap_ci_generic.py.
"""
import sys, json, math
from collections import defaultdict
from statistics import mean, stdev
import numpy as np
from scipy import stats

RNG_SEED = 20260520
N_BOOT = 10000


def paired_rel_reduction(a, b):
    """Mean of (a - b) / a, per-pair, with handling for a=0."""
    pairs = [(ai, bi) for ai, bi in zip(a, b) if ai > 0]
    if not pairs:
        return 0.0
    return mean((ai - bi) / ai for ai, bi in pairs) * 100


def bootstrap_rel(a, b, n_boot=N_BOOT, rng=None):
    if rng is None:
        rng = np.random.default_rng(RNG_SEED)
    a_arr = np.array(a, dtype=float)
    b_arr = np.array(b, dtype=float)
    n = len(a_arr)
    if n == 0:
        return 0.0, (0.0, 0.0)
    rels = []
    for _ in range(n_boot):
        idx = rng.integers(0, n, size=n)
        rels.append(paired_rel_reduction(a_arr[idx].tolist(), b_arr[idx].tolist()))
    rels = np.array(rels)
    return paired_rel_reduction(a, b), (float(np.percentile(rels, 2.5)), float(np.percentile(rels, 97.5)))


def cohens_d_paired(a, b):
    diffs = [bi - ai for ai, bi in zip(a, b)]
    if len(diffs) < 2:
        return 0.0
    sd = stdev(diffs)
    return (mean(diffs) / sd) if sd > 0 else 0.0


def wilcoxon_safe(a, b):
    """Returns (p_value, effect_size_r) or (None, None) if not computable."""
    if len(a) < 2:
        return None, None
    try:
        diffs = [bi - ai for ai, bi in zip(a, b)]
        if all(d == 0 for d in diffs):
            return 1.0, 0.0
        stat, p = stats.wilcoxon(a, b, zero_method='wilcox')
        z = stats.norm.isf(p / 2) if 0 < p < 1 else 0.0
        n = sum(1 for d in diffs if d != 0)
        r = z / math.sqrt(n) if n > 0 else 0.0
        return float(p), float(r)
    except ValueError:
        return None, None


def process(src, dst):
    raw = json.load(open(src))
    bs = defaultdict(lambda: {'lasp':[],'v1':[],'ldef':[],'lopt':[]})
    for r in raw:
        s = r['scenario']
        bs[s]['lasp'].append(r['lasp_aug']['losses'])
        bs[s]['v1'].append(r['momentum_dp']['losses'])
        bs[s]['ldef'].append(r['momentum_live_def']['losses'])
        bs[s]['lopt'].append(r['momentum_live_opt']['losses'])
    out = []
    for s in sorted(bs.keys()):
        a = bs[s]
        n = len(a['lasp'])
        row = {'scenario': s, 'n': n,
               'lasp_mean': mean(a['lasp']),
               'v1_mean': mean(a['v1']),
               'ldef_mean': mean(a['ldef']),
               'lopt_mean': mean(a['lopt'])}
        for lab, x, y in [('lasp_vs_lopt', a['lasp'], a['lopt']),
                          ('v1_vs_ldef', a['v1'], a['ldef']),
                          ('v1_vs_lopt', a['v1'], a['lopt'])]:
            rel, ci = bootstrap_rel(x, y)
            d = cohens_d_paired(x, y)
            p, r_e = wilcoxon_safe(x, y)
            row[lab] = {'rel_pct': rel, 'ci95': ci, 'd': d, 'p': p, 'r': r_e}
        out.append(row)
    json.dump(out, open(dst, 'w'), indent=2)
    return out


def fmt_ci(ci):
    lo, hi = ci
    return f"[{lo:+.1f}, {hi:+.1f}]"


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else 'data/battery_newt_raw.json'
    dst = sys.argv[2] if len(sys.argv) > 2 else 'data/battery_newt_bootstrap.json'
    out = process(src, dst)
    print(f"Saved {dst}\n")
    print(f"{'Scenario':<22}{'n':>4}  LASP->Lopt              v1->Ldef                v1->Lopt")
    print('-' * 96)
    for r in out:
        a = r['lasp_vs_lopt']; b = r['v1_vs_ldef']; c = r['v1_vs_lopt']
        print(f"{r['scenario']:<22}{r['n']:>4}  "
              f"{a['rel_pct']:+6.1f}% {fmt_ci(a['ci95']):<15} "
              f"{b['rel_pct']:+6.1f}% {fmt_ci(b['ci95']):<15} "
              f"{c['rel_pct']:+6.1f}% {fmt_ci(c['ci95']):<15}")


if __name__ == '__main__':
    main()
