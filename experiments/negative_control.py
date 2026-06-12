"""
negative_control.py - CODE AUDIT canary (item CODE, method 3).

Two IDENTICAL routers under different labels must be indistinguishable:
per-seed drop rates must match EXACTLY (bit-for-bit) and TOST must hold
at the strictest published margin (0.2pp).

Any systematic delta is a HARNESS bug (state leakage, RNG contamination,
order dependence), not a router difference. To detect inter-run
contamination, run B happens AFTER an interleaved DRILL run.
"""
import sys, json
sys.path.insert(0, '/home/clopez/emmet/experiments')

import flowsim as FS
import physics_cores as PC
from equivalence import TOPOS, build_topo, tost, N_SEEDS
from emmet_budget import reset
import emmet_budget

CORE = 'archimedes'   # any non-scar core; plain simulate path
STRICT = 0.002        # 0.2 pp


def run_topo(args):
    name, builder, dsrc = args
    A, B, DA, DB = [], [], [], []
    pol = PC.make_physics_policy(CORE)
    for s in range(N_SEEDS):
        _, dem = build_topo(name, builder, dsrc, s)
        sched = FS.gen_flows(dem, 200, s + 9000, birth_rate=0.8,
                             dur_lo=4, dur_hi=12, rate=1)
        G, _ = build_topo(name, builder, dsrc, s); reset(G)
        A.append(FS.simulate_flows(G, sched, 200, pol)['drop_rate'])
        G, _ = build_topo(name, builder, dsrc, s); reset(G)
        DA.append(FS.simulate_flows(G, sched, 200, FS.policy_drill)['drop_rate'])
        G, _ = build_topo(name, builder, dsrc, s); reset(G)
        B.append(FS.simulate_flows(G, sched, 200, pol)['drop_rate'])
        G, _ = build_topo(name, builder, dsrc, s); reset(G)
        DB.append(FS.simulate_flows(G, sched, 200, FS.policy_drill)['drop_rate'])
    return name, A, B, DA, DB


def main():
    emmet_budget.GAMMA = 2.0
    print(f"=== NEGATIVE CONTROL: {CORE} vs itself (B after interleaved DRILL) ===")
    print(f"{'topo':<11} | {'max|A-B|':>12} | {'max|DA-DB|':>12} | TOST@0.2pp | bitexact")
    print('-' * 68)
    worst, rows, fails = 0.0, [], 0
    for t in TOPOS:
        name, A, B, DA, DB = run_topo(t)
        dab = max(abs(a - b) for a, b in zip(A, B))
        ddd = max(abs(a - b) for a, b in zip(DA, DB))
        bit = all(a == b for a, b in zip(A, B)) and \
              all(a == b for a, b in zip(DA, DB))
        if dab == 0.0:
            eq = True  # identical vectors: equivalence trivial (TOST undefined at zero variance)
        else:
            eq, _ = tost(A, B, STRICT)
        worst = max(worst, dab, ddd)
        fails += (not eq) + (not bit)
        rows.append({'topo': name, 'A': A, 'B': B, 'DA': DA, 'DB': DB,
                     'max_AB': dab, 'max_DADB': ddd,
                     'tost_02': bool(eq), 'bitexact': bool(bit)})
        print(f"{name:<11} | {dab:12.3e} | {ddd:12.3e} | "
              f"{'EQUIV' if eq else 'FAIL':>10} | {'YES' if bit else 'NO'}")
    json.dump(rows, open('/home/clopez/emmet/data/negative_control.json', 'w'),
              indent=2)
    print('-' * 68)
    print(f"worst delta anywhere: {worst:.3e}")
    if fails == 0 and worst == 0.0:
        print("VERDICT: PASS - harness is order-independent and leak-free;")
        print("identical routers are bit-identical and trivially TOST-equivalent.")
    else:
        print(f"VERDICT: FAIL - {fails} anomalies. Harness bug suspected:")
        print("state leakage / RNG contamination / order dependence. INVESTIGATE.")


if __name__ == '__main__':
    main()
