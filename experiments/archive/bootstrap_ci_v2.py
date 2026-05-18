"""Bootstrap CI 95% + Cohen's d + Wilcoxon r for EMMET v2.0."""
import json, math
from collections import defaultdict
from statistics import mean, stdev
import numpy as np
from scipy import stats

RNG_SEED = 20260520
N_BOOT = 10000
DATA_FILES = [
    '/home/clopez/emmet/data/momentum_clean_full_raw.json',
    '/home/clopez/emmet/data/topology_extended_raw.json',
]

def load_paired(files):
    paired = defaultdict(list)
    for f in files:
        for run in json.load(open(f)):
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

def cohens_d_paired(deltas):
    a = np.asarray(deltas, dtype=float)
    if len(a) < 2 or a.std(ddof=1) == 0:
        return 0.0
    return float(a.mean() / a.std(ddof=1))

def hedges_g(d, n):
    if n < 2:
        return d
    J = 1.0 - 3.0/(4*(n-1) - 1)
    return d * J

def wilcoxon_with_r(deltas):
    a = np.asarray(deltas, dtype=float)
    nz = a[a != 0]
    if len(nz) < 2:
        return dict(stat=None, p=None, r=None, n_nonzero=int(len(nz)))
    res = stats.wilcoxon(nz, zero_method='wilcox',
                         alternative='two-sided', method='approx')
    z = abs(stats.norm.ppf(res.pvalue / 2))
    r = z / math.sqrt(len(nz))
    return dict(stat=float(res.statistic), p=float(res.pvalue),
                r=float(r), n_nonzero=int(len(nz)))

def rel_improvement(pairs):
    return [(l-d)/l*100.0 for l, d in pairs if l > 0]

def analyze_scenario(scen, pairs, rng):
    n = len(pairs)
    deltas = [l - d for l, d in pairs]
    sum_lasp = sum(l for l, _ in pairs)
    sum_dp = sum(d for _, d in pairs)
    rel_total = ((sum_lasp-sum_dp)/sum_lasp*100.0) if sum_lasp>0 else 0.0
    mean_delta = mean(deltas)
    ci_lo, ci_hi = bootstrap_ci(deltas, rng=rng)
    rels = rel_improvement(pairs)
    if rels:
        mr = mean(rels)
        crl, crh = (bootstrap_ci(rels, rng=rng) if len(rels)>=2 else (mr,mr))
    else:
        mr = crl = crh = None
    if n >= 2 and stdev(deltas) > 0:
        ts = stats.ttest_rel([l for l,_ in pairs], [d for _,d in pairs])
        t_stat, t_p = float(ts.statistic), float(ts.pvalue)
    else:
        t_stat = t_p = None
    wilc = wilcoxon_with_r(deltas)
    dd = cohens_d_paired(deltas)
    gg = hedges_g(dd, n)
    return dict(scenario=scen, n_seeds=n,
        sum_lasp=int(sum_lasp), sum_dp=int(sum_dp),
        rel_total_pct=round(rel_total, 2),
        mean_delta=round(mean_delta, 3),
        delta_ci95=[round(ci_lo,3), round(ci_hi,3)],
        mean_rel_pct=round(mr,2) if mr is not None else None,
        rel_ci95=[round(crl,2), round(crh,2)] if mr is not None else None,
        t_stat=round(t_stat,4) if t_stat is not None else None,
        t_p=t_p, wilcoxon_p=wilc['p'],
        wilcoxon_r=round(wilc['r'],3) if wilc['r'] is not None else None,
        cohens_d=round(dd,3), hedges_g=round(gg,3))

def main():
    paired = load_paired(DATA_FILES)
    rng = np.random.default_rng(RNG_SEED)
    results = [analyze_scenario(s, paired[s], rng) for s in sorted(paired)]
    pooled = analyze_scenario('POOLED_26_SCENARIOS',
                              [p for v in paired.values() for p in v], rng)
    results.append(pooled)
    out = '/home/clopez/emmet/data/v2_bootstrap_ci.json'
    json.dump(results, open(out, 'w'), indent=2)
    return results, out

def pretty_print(results):
    h = f'{"Scenario":<22} {"n":>4} {"rel%":>7} {"95% CI":>16} {"t":>7} {"p":>10} {"r":>5} {"d":>6}'
    print(h)
    print('-' * len(h))
    for r in results:
        rel = f'{r["rel_total_pct"]:.1f}'
        ci = f'[{r["rel_ci95"][0]:.1f},{r["rel_ci95"][1]:.1f}]' if r['rel_ci95'] else '-'
        t = f'{r["t_stat"]:.2f}' if r["t_stat"] is not None else '-'
        p = f'{r["t_p"]:.1e}' if r["t_p"] is not None else '-'
        rr = f'{r["wilcoxon_r"]:.2f}' if r["wilcoxon_r"] is not None else '-'
        dd = f'{r["cohens_d"]:+.2f}'
        print(f'{r["scenario"]:<22} {r["n_seeds"]:>4} {rel:>7} {ci:>16} {t:>7} {p:>10} {rr:>5} {dd:>6}')

if __name__ == '__main__':
    results, out = main()
    pretty_print(results)
    print(f'\nSaved to {out}')
