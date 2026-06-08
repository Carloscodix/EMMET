"""
attractor_test.py - does the topology force one load distribution (Carlos's
"all roads lead to Rome / Sabadell-or-Barcelona"), or does the router choose it?

For each topology we run five routers on the SAME graph+demand and record each
router's per-edge utilization vector (from simulate_flows_util). Then we compare
how similar those load distributions are:

  - three physics cores: newton, archimedes, pascal (via physics_cores)
  - two controls: shortest (ignores congestion), ecmp (hash spread)

Cosine similarity of util vectors = "do they push load through the same edges in
the same proportions?". 1.0 = identical distribution = same attractor.

THREE PRE-COMMITTED OUTCOMES
  (1) phys-phys similarity >> phys-shortest: the three physics converge to one
      distribution that the blind controls do NOT share -> congestion-aware
      attractor (explains the hat-trick).
  (2) everything ~equally high, even shortest: the attractor is purely
      TOPOLOGICAL - the road forces the destination, the driver is irrelevant
      (Carlos's roads thesis in its strong form).
  (3) nothing converges cleanly: no attractor, mirage -> bury it.

Plus: does divergence-between-physics track tube/sp? (does room-to-manoeuvre
let routers differ?)
"""
import sys, math
import numpy as np
sys.path.insert(0, '/home/clopez/emmet/experiments')

import flowsim as FS
import physics_cores as PC
from equivalence import TOPOS, build_topo
from emmet_budget import reset
from sweep_topologies import tube_sp

N_SEEDS = 3
ROUTERS = ['newton', 'archimedes', 'pascal', 'shortest', 'ecmp']


def get_policy(name):
    if name in ('newton', 'archimedes', 'pascal'):
        return PC.make_physics_policy(name)
    if name == 'shortest':
        return FS.policy_shortest
    if name == 'ecmp':
        return FS.policy_ecmp
    raise ValueError(name)


def cosine(ua, ub):
    keys = list(ua.keys())
    a = np.array([ua[k] for k in keys])
    b = np.array([ub[k] for k in keys])
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na == 0 or nb == 0:
        return float('nan')
    return float(np.dot(a, b) / (na * nb))


def run_topo(args):
    name, builder, dsrc = args
    # collect util vectors per router, averaged over seeds via concatenation of sims
    sims = {r: [] for r in ROUTERS}      # list of util dicts, one per seed
    tubes = []
    for s in range(N_SEEDS):
        G0, dem = build_topo(name, builder, dsrc, s)
        tubes.append(tube_sp(G0))
        sched = FS.gen_flows(dem, 200, s + 9000, birth_rate=0.8,
                             dur_lo=4, dur_hi=12, rate=1)
        for r in ROUTERS:
            G, _ = build_topo(name, builder, dsrc, s); reset(G)
            res = FS.simulate_flows_util(G, sched, 200, get_policy(r))
            sims[r].append(res['util'])
    # per-seed pairwise cosine, then average over seeds
    def mean_sim(ra, rb):
        vals = [cosine(sims[ra][s], sims[rb][s]) for s in range(N_SEEDS)]
        vals = [v for v in vals if not math.isnan(v)]
        return float(np.mean(vals)) if vals else float('nan')

    phys = ['newton', 'archimedes', 'pascal']
    pp = np.mean([mean_sim(a, b) for i, a in enumerate(phys) for b in phys[i+1:]])
    ps = np.mean([mean_sim(a, 'shortest') for a in phys])
    pe = np.mean([mean_sim(a, 'ecmp') for a in phys])
    return {'topo': name, 'tube_sp': float(np.mean(tubes)),
            'phys_phys': float(pp), 'phys_short': float(ps), 'phys_ecmp': float(pe)}


def main():
    print(f"{'topo':<11}{'tube/sp':>8}{'physMphys':>10}{'physMshort':>11}{'physMecmp':>10}")
    print('-' * 50)
    rows = []
    for t in TOPOS:
        r = run_topo(t)
        rows.append(r)
        print(f"{r['topo']:<11}{r['tube_sp']:>8.2f}{r['phys_phys']:>10.3f}"
              f"{r['phys_short']:>11.3f}{r['phys_ecmp']:>10.3f}")
    print('-' * 50)

    pp = np.array([r['phys_phys'] for r in rows])
    ps = np.array([r['phys_short'] for r in rows])
    pe = np.array([r['phys_ecmp'] for r in rows])
    tube = np.array([r['tube_sp'] for r in rows])
    print("\n=== MEANS across topologies ===")
    print(f"physics-physics similarity: {np.nanmean(pp):.3f}")
    print(f"physics-shortest similarity: {np.nanmean(ps):.3f}")
    print(f"physics-ecmp similarity:     {np.nanmean(pe):.3f}")

    print("\n=== OUTCOME ===")
    gap_short = np.nanmean(pp) - np.nanmean(ps)
    if np.nanmean(pp) > 0.9 and np.nanmean(ps) > 0.9 and np.nanmean(pe) > 0.9:
        print("(2) EVERYTHING converges (incl. shortest/ecmp): PURELY TOPOLOGICAL")
        print("    attractor. The road forces the load; the router barely matters.")
    elif np.nanmean(pp) > 0.85 and gap_short > 0.1:
        print("(1) physics converge to a shared distribution the blind controls")
        print("    do NOT: a CONGESTION-AWARE attractor. Explains the hat-trick.")
    elif np.nanmean(pp) < 0.7:
        print("(3) physics do not converge: NO clean attractor. Mirage.")
    else:
        print("MIXED: partial convergence. Needs reading row by row.")

    # correlation: does divergence-between-physics grow with tube/sp?
    div = 1.0 - pp
    if len(tube) > 2 and np.std(div) > 1e-9:
        r = np.corrcoef(tube, div)[0, 1]
        print(f"\ncorr(tube/sp, physics-divergence) = {r:+.3f}")
        if r > 0.4:
            print("  -> more room to manoeuvre => routers diverge more (atractor weakens"
                  " as tube/sp grows). Consistent with topology-forced convergence.")
        elif r < -0.4:
            print("  -> LESS room => MORE divergence: opposite of the roads intuition.")
        else:
            print("  -> divergence largely independent of tube/sp.")


if __name__ == '__main__':
    main()
