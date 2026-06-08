"""
attractor_full.py - the robust version of the attractor test.

Smoke (3 seeds, cosine only) said: the three physics cores converge to one load
distribution (~0.99), controls lag (shortest 0.95, ecmp 0.88), and divergence
tracks tube/sp (r=+0.54). This version hardens that before it can go in the paper:

  - 12 seeds (not 3) for stable similarities + std bars
  - TWO divergence metrics that must agree:
      * cosine similarity of per-edge utilization vectors
      * 1 - normalized L1 distance (earth-mover-ish: how much load mass must move)
  - significance: paired test on (phys-phys vs phys-shortest) gap, and p-value
    on the tube/sp <-> divergence correlation
  - 5 routers: newton, archimedes, pascal (physics) + shortest, ecmp (controls)

Same identical-bench discipline: same graph+demand per seed for all routers.
"""
import sys, math
import numpy as np
from scipy import stats
sys.path.insert(0, '/home/clopez/emmet/experiments')

import flowsim as FS
import physics_cores as PC
from equivalence import TOPOS, build_topo
from emmet_budget import reset
from sweep_topologies import tube_sp

N_SEEDS = 12
PHYS = ['newton', 'archimedes', 'pascal']
ROUTERS = PHYS + ['shortest', 'ecmp']


def get_policy(name):
    if name in PHYS:
        return PC.make_physics_policy(name)
    return {'shortest': FS.policy_shortest, 'ecmp': FS.policy_ecmp}[name]


def vecs(ua, ub):
    keys = list(ua.keys())
    a = np.array([ua[k] for k in keys], float)
    b = np.array([ub[k] for k in keys], float)
    return a, b


def cosine(ua, ub):
    a, b = vecs(ua, ub)
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    return float(np.dot(a, b) / (na * nb)) if na > 0 and nb > 0 else float('nan')


def l1_sim(ua, ub):
    """1 - normalized L1: how much normalized load mass coincides.
    Each vector normalized to sum 1, then 1 - 0.5*sum|a-b| (in [0,1])."""
    a, b = vecs(ua, ub)
    sa, sb = a.sum(), b.sum()
    if sa == 0 or sb == 0:
        return float('nan')
    a, b = a / sa, b / sb
    return float(1.0 - 0.5 * np.sum(np.abs(a - b)))


def run_topo(args):
    name, builder, dsrc = args
    util = {r: [] for r in ROUTERS}
    tubes = []
    for s in range(N_SEEDS):
        G0, dem = build_topo(name, builder, dsrc, s)
        tubes.append(tube_sp(G0))
        sched = FS.gen_flows(dem, 200, s + 9000, birth_rate=0.8,
                             dur_lo=4, dur_hi=12, rate=1)
        for r in ROUTERS:
            G, _ = build_topo(name, builder, dsrc, s); reset(G)
            fs = r in PHYS  # feed Newton-III scar for the physical cores (others ignore it)
            util[r].append(FS.simulate_flows_util(G, sched, 200, get_policy(r), feed_scar=fs)['util'])

    def pair_mean(ra, rb, fn):
        v = [fn(util[ra][s], util[rb][s]) for s in range(N_SEEDS)]
        v = [x for x in v if not math.isnan(x)]
        return float(np.mean(v)) if v else float('nan')

    res = {'topo': name, 'tube_sp': float(np.mean(tubes))}
    for tag, fn in (('cos', cosine), ('l1', l1_sim)):
        pp = np.mean([pair_mean(a, b, fn) for i, a in enumerate(PHYS) for b in PHYS[i+1:]])
        ps = np.mean([pair_mean(a, 'shortest', fn) for a in PHYS])
        pe = np.mean([pair_mean(a, 'ecmp', fn) for a in PHYS])
        res[f'pp_{tag}'] = float(pp); res[f'ps_{tag}'] = float(ps); res[f'pe_{tag}'] = float(pe)
    return res


def main():
    print(f"N_SEEDS={N_SEEDS}  (cos = cosine sim, l1 = 1 - normalized L1)")
    print(f"{'topo':<11}{'tube':>6}{'pp_cos':>8}{'ps_cos':>8}{'pp_l1':>8}{'ps_l1':>8}")
    print('-' * 49)
    rows = [run_topo(t) for t in TOPOS]
    for r in rows:
        print(f"{r['topo']:<11}{r['tube_sp']:>6.2f}{r['pp_cos']:>8.3f}"
              f"{r['ps_cos']:>8.3f}{r['pp_l1']:>8.3f}{r['ps_l1']:>8.3f}")
    print('-' * 49)

    import json
    json.dump(rows, open('/home/clopez/emmet/data/attractor_full.json', 'w'), indent=2)

    for tag in ('cos', 'l1'):
        pp = np.array([r[f'pp_{tag}'] for r in rows])
        ps = np.array([r[f'ps_{tag}'] for r in rows])
        pe = np.array([r[f'pe_{tag}'] for r in rows])
        print(f"\n=== metric: {tag} ===")
        print(f"physics-physics  : {np.nanmean(pp):.3f} +/- {np.nanstd(pp):.3f}")
        print(f"physics-shortest : {np.nanmean(ps):.3f} +/- {np.nanstd(ps):.3f}")
        print(f"physics-ecmp     : {np.nanmean(pe):.3f} +/- {np.nanstd(pe):.3f}")
        # paired: is phys-phys > phys-shortest across topologies?
        t, p = stats.wilcoxon(pp, ps)
        print(f"phys-phys vs phys-shortest (Wilcoxon): p={p:.4f} "
              f"({'distinct' if p < 0.05 else 'NOT distinct'})")
        # correlation tube/sp <-> divergence
        tube = np.array([r['tube_sp'] for r in rows])
        div = 1.0 - pp
        if np.std(div) > 1e-9:
            rho, pv = stats.pearsonr(tube, div)
            print(f"corr(tube/sp, divergence): r={rho:+.3f}, p={pv:.4f}")

    print("\n=== VERDICT ===")
    pp = np.array([r['pp_cos'] for r in rows]); ps = np.array([r['ps_cos'] for r in rows])
    ppl = np.array([r['pp_l1'] for r in rows])
    _, p_gap = stats.wilcoxon(pp, ps)
    both_high = np.nanmean(pp) > 0.95 and np.nanmean(ppl) > 0.90
    if both_high and p_gap < 0.05:
        print("ROBUST: physics converge to one load distribution on BOTH metrics,")
        print("significantly tighter than blind controls. Topology-forced attractor,")
        print("refined by congestion-awareness. -> paper material.")
    elif both_high:
        print("Physics converge on both metrics but gap vs controls not significant:")
        print("attractor is essentially PURELY topological. Still paper material, ")
        print("different emphasis (router barely matters).")
    else:
        print("Metrics DISAGREE or convergence weak -> not robust, do NOT put in paper yet.")


if __name__ == '__main__':
    main()
