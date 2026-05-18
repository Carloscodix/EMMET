"""
equivalence_physics.py - run the equivalence bench for ANY physics core.

Reuses the exact bench from equivalence.py (same TOPOS, build_topo, tost,
N_SEEDS) but swaps in a physics_cores core as the contender, and uses a FAIR
CONGA budget (K=16) from the start - no K=4 artifact this time.

Usage: python3 equivalence_physics.py <core_name>   e.g. archimedes
Writes data/equivalence_<core>.json and prints the table.
"""
import sys, json
import numpy as np
from pathlib import Path

sys.path.insert(0, '/home/clopez/emmet/experiments')
import flowsim as FS
import physics_cores as PC
from equivalence import TOPOS, build_topo, tost, N_SEEDS, DELTA
from emmet_budget import reset
import emmet_budget

CONGA_K = 16  # fair budget from the outset


def run_topo(args, core_name):
    name, builder, dsrc = args
    contender, conga, drill = [], [], []
    policy = PC.make_physics_policy(core_name)
    conga_pol = FS.make_conga_policy(CONGA_K)
    for s in range(N_SEEDS):
        _, dem = build_topo(name, builder, dsrc, s)
        sched = FS.gen_flows(dem, 200, s + 9000, birth_rate=0.8,
                             dur_lo=4, dur_hi=12, rate=1)
        G, _ = build_topo(name, builder, dsrc, s); reset(G)
        sim = FS.simulate_flows_scar if core_name == 'newton' else FS.simulate_flows
        contender.append(sim(G, sched, 200, policy)['drop_rate'])
        G, _ = build_topo(name, builder, dsrc, s); reset(G)
        conga.append(FS.simulate_flows(G, sched, 200, conga_pol)['drop_rate'])
        G, _ = build_topo(name, builder, dsrc, s); reset(G)
        drill.append(FS.simulate_flows(G, sched, 200, FS.policy_drill)['drop_rate'])
    ec, pc = tost(contender, conga, DELTA)
    ed, pd = tost(contender, drill, DELTA)
    return {'topo': name, 'core': float(np.mean(contender)),
            'conga': float(np.mean(conga)), 'drill': float(np.mean(drill)),
            'eq_conga': bool(ec), 'eq_drill': bool(ed)}


def main():
    core_name = sys.argv[1] if len(sys.argv) > 1 else 'archimedes'
    emmet_budget.GAMMA = 2.0
    print(f"=== equivalence bench: {core_name} vs CONGA-K{CONGA_K} / DRILL ===")
    results = [run_topo(t, core_name) for t in TOPOS]
    Path(f'/home/clopez/emmet/data/equivalence_{core_name}.json').write_text(
        json.dumps(results, indent=2))
    print(f"{'topo':<11}{core_name[:6]:>7}{'CONGA':>7}{'DRILL':>7}  {'eqC':>5}{'eqD':>5}")
    print('-' * 50)
    nc = nd = 0
    for r in results:
        ec = 'YES' if r['eq_conga'] else 'no'
        ed = 'YES' if r['eq_drill'] else 'no'
        nc += r['eq_conga']; nd += r['eq_drill']
        print(f"{r['topo']:<11}{r['core']:>7.3f}{r['conga']:>7.3f}"
              f"{r['drill']:>7.3f}  {ec:>5}{ed:>5}")
    print('-' * 50)
    print(f"{core_name}: equivalent to CONGA-K{CONGA_K} in {nc}/{len(results)}, "
          f"to DRILL in {nd}/{len(results)} (TOST, delta={DELTA}pp)")


if __name__ == '__main__':
    main()
