"""
equivalence_strict.py - re-run the equivalence bench saving RAW per-seed drop
rates, then evaluate TOST at several margins (2.0, 1.0, 0.5, 0.2 pp).

Why: reviewers flagged that delta=2pp is lax when drop rates sit
between 0-2%. This shows how many equivalences SURVIVE as we tighten the margin.
The ones that survive delta=0.5pp are the bulletproof ones.

Saves data/equivalence_strict_<core>.json with the raw vectors so we never have
to re-run to test another margin (or a mixed-effects model later).
"""
import sys, json
import numpy as np
sys.path.insert(0, '/home/clopez/emmet/experiments')

import flowsim as FS
import physics_cores as PC
from equivalence import TOPOS, build_topo, tost, N_SEEDS
from emmet_budget import reset
import emmet_budget

CONGA_K = 16
MARGINS = [0.02, 0.01, 0.005, 0.002]  # 2.0, 1.0, 0.5, 0.2 pp


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
    return {'topo': name,
            'core_seeds': [float(x) for x in contender],
            'conga_seeds': [float(x) for x in conga],
            'drill_seeds': [float(x) for x in drill]}


def main():
    core = sys.argv[1] if len(sys.argv) > 1 else 'archimedes'
    emmet_budget.GAMMA = 2.0
    print(f"=== {core}: raw bench, TOST at margins {[m*100 for m in MARGINS]} pp ===")
    rows = [run_topo(t, core) for t in TOPOS]
    json.dump(rows, open(f'/home/clopez/emmet/data/equivalence_strict_{core}.json', 'w'), indent=2)

    # evaluate TOST at each margin
    print(f"\n{'topo':<11} | " + " | ".join(f"d={m*100:.1f}".rjust(11) for m in MARGINS))
    print(f"{'':11} | " + " | ".join(" C / D ".rjust(11) for _ in MARGINS))
    print('-' * (13 + 14 * len(MARGINS)))
    counts = {m: {'C': 0, 'D': 0} for m in MARGINS}
    for r in rows:
        cells = []
        for m in MARGINS:
            ec, _ = tost(r['core_seeds'], r['conga_seeds'], m)
            ed, _ = tost(r['core_seeds'], r['drill_seeds'], m)
            counts[m]['C'] += bool(ec); counts[m]['D'] += bool(ed)
            cells.append(f"{'Y' if ec else '.'}/{'Y' if ed else '.'}".rjust(11))
        print(f"{r['topo']:<11} | " + " | ".join(cells))
    print('-' * (13 + 14 * len(MARGINS)))
    print(f"{'CONGA-K16':<11} | " + " | ".join(f"{counts[m]['C']}/15".rjust(11) for m in MARGINS))
    print(f"{'DRILL':<11} | " + " | ".join(f"{counts[m]['D']}/15".rjust(11) for m in MARGINS))

    print("\n=== READING ===")
    for m in MARGINS:
        print(f"delta={m*100:.1f}pp: equiv CONGA {counts[m]['C']}/15, DRILL {counts[m]['D']}/15")
    print("\nThe equivalences that survive delta=0.5pp (0.005) are the bulletproof ones.")


if __name__ == '__main__':
    main()
