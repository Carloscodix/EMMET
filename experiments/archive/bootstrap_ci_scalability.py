"""Bootstrap CI 95% + effect sizes for Phase A scalability data."""
import json, math
from collections import defaultdict
from statistics import mean, stdev
import numpy as np
from scipy import stats

RNG_SEED = 20260520
N_BOOT = 10000
SRC = '/home/clopez/emmet/data/scalability_phaseA_raw.json'
DST = '/home/clopez/emmet/data/scalability_phaseA_bootstrap.json'

def load_paired(path):
    paired = defaultdict(list)
    for run in json.load(open(path)):
        if run.get('kappa', 1.0) != 1.0:
            continue
        paired[run['scenario']].append(
            (run['lasp_aug']['losses'], run['momentum_dp']['losses']))
    return paired

def bootstrap_ci(deltas, n_boot=N_BOOT, alpha=0.05, rng=None):
    rng = rng or np.random.default_rng(RNG_SEED)
    n = len(deltas)
    idx = rng.integers(0, n, size=(n_boot, n))
    bm = np.mean(np.asarray(deltas)[idx], axis=1)
    lo, hi = np.percentile(bm, [100*alpha/2, 100*(1-alpha/2)])
    return float(lo), float(hi)

def cohens_d(deltas):
    a = np.asarray(deltas, dtype=float)
    if len(a) < 2 or a.std(ddof=1) == 0:
        return 0.0
    return float(a.mean() / a.std(ddof=1))

def wilcoxon_r(deltas):
    a = np.asarray(deltas, dtype=float)
    nz = a[a != 0]
    if len(nz) < 2:
        return None, None
    res = stats.wilcoxon(nz, zero_method='wilcox', alternative='two-sided', method='approx')
    z = abs(stats.norm.ppf(res.pvalue / 2))
    return float(res.pvalue), float(z / math.sqrt(len(nz)))

def analyze(scen, pairs, rng):
    n = len(pairs)
    deltas = [l - d for l, d in pairs]
    sum_l = sum(l for l, _ in pairs)
    sum_d = sum(d for _, d in pairs)
    rel_total = ((sum_l - sum_d) / sum_l * 100.0) if sum_l > 0 else 0.0
    mean_delta = mean(deltas)
    if n >= 2 and stdev(deltas) > 0:
        ci_lo, ci_hi = bootstrap_ci(deltas, rng=rng)
    else:
        ci_lo = ci_hi = mean_delta
    rels = [(l-d)/l*100.0 for l, d in pairs if l > 0]
    if len(rels) >= 2:
        mean_rel = mean(rels)
        rel_ci = bootstrap_ci(rels, rng=rng)
    else:
        mean_rel = (rels[0] if rels else None)
        rel_ci = None
    if n >= 2 and stdev(deltas) > 0:
        ts = stats.ttest_rel([l for l, _ in pairs], [d for _, d in pairs])
        t_stat, t_p = float(ts.statistic), float(ts.pvalue)
    else:
        t_stat = t_p = None
    w_p, w_r = wilcoxon_r(deltas)
    d = cohens_d(deltas)
    return dict(scenario=scen, n_seeds=n,
                sum_lasp=int(sum_l), sum_dp=int(sum_d),
                rel_total_pct=round(rel_total, 2),
                mean_delta=round(mean_delta, 4),
                delta_ci95=[round(ci_lo, 4), round(ci_hi, 4)],
                mean_rel_pct=round(mean_rel, 2) if mean_rel is not None else None,
                rel_ci95=[round(rel_ci[0], 2), round(rel_ci[1], 2)] if rel_ci else None,
                t_stat=round(t_stat, 4) if t_stat is not None else None,
                t_p=t_p, wilcoxon_p=w_p,
                wilcoxon_r=round(w_r, 3) if w_r is not None else None,
                cohens_d=round(d, 3))

def main():
    paired = load_paired(SRC)
    rng = np.random.default_rng(RNG_SEED)
    results = [analyze(s, paired[s], rng) for s in sorted(paired)]
    json.dump(results, open(DST, 'w'), indent=2)
    print(f'Saved {DST}')
    return results

def pretty(results):
    h = f'{"Scenario":<22} {"n":>4} {"rel%":>7} {"95% CI":>16} {"d":>6} {"r":>5} {"t_p":>10}'
    print(h)
    print('-' * len(h))
    for r in results:
        rel = f'{r["rel_total_pct"]:.1f}'
        ci = f'[{r["rel_ci95"][0]:.1f},{r["rel_ci95"][1]:.1f}]' if r['rel_ci95'] else '-'
        d = f'{r["cohens_d"]:+.2f}'
        rr = f'{r["wilcoxon_r"]:.2f}' if r['wilcoxon_r'] is not None else '-'
        tp = f'{r["t_p"]:.1e}' if r['t_p'] is not None else '-'
        print(f'{r["scenario"]:<22} {r["n_seeds"]:>4} {rel:>7} {ci:>16} {d:>6} {rr:>5} {tp:>10}')

if __name__ == '__main__':
    pretty(main())
