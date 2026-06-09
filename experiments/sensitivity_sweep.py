"""
sensitivity_sweep.py - the LAST test of the battery: tuning provenance.

After the redux, gradient+Archimedes is the project's core, so rho0 and g_arq
are now its most important parameters (plus the substrate's BETA). Question:
is the 15/15 win over the bare substrate a PLATEAU (robust across reasonable
parameters) or a NEEDLE (overfit to rho0=0.6, g=8, beta=3)?

PRE-COMMITTED VERDICTS:
  - PLATEAU: arch wins >=12/15 topologies across most of the grid -> core is
    parameter-robust, claim is bulletproof.
  - NEEDLE: wins collapse away from the defaults -> overfit; must be reported
    and the core's claim softened.

Sweep A: rho0 in {0.4,0.5,0.6,0.7,0.8} at g=8; g in {2,4,8,16,32} at rho0=0.6.
Sweep B: BETA in {1.5,3.0,4.5,6.0} (affects base AND arch; arch at defaults).
15 topos x 6 seeds, paired vs the bare base at the same BETA.
"""
import sys, json
import numpy as np
from scipy import stats
sys.path.insert(0, '/home/clopez/emmet/experiments')
import flowsim as FS
import physics_cores as PC
from equivalence import TOPOS, build_topo
from emmet_budget import reset

N_SEEDS = 6


def make_arch_policy(rho0, g):
    def term(G, u, v, state):
        return PC.term_archimedes(G, u, v, state, rho0=rho0, g_arq=g)
    def route_fn(G, s, d, state):
        return PC.route_with_term(G, s, d, state, term)
    return route_fn


def make_base_policy():
    def route_fn(G, s, d, state):
        return PC.route_with_term(G, s, d, state, lambda G, u, v, st: 0.0)
    return route_fn


def bench(policy):
    """drop rates per topo per seed for a given policy (current PC.BETA)."""
    out = {}
    for t in TOPOS:
        name, builder, dsrc = t
        drops = []
        for s in range(N_SEEDS):
            G0, dem = build_topo(name, builder, dsrc, s)
            sched = FS.gen_flows(dem, 200, s + 9000, birth_rate=0.8,
                                 dur_lo=4, dur_hi=12, rate=1)
            G, _ = build_topo(name, builder, dsrc, s); reset(G)
            drops.append(FS.simulate_flows(G, sched, 200, policy)['drop_rate'])
        out[name] = drops
    return out


def compare(arch, base):
    """(mean paired delta pp, wins/15, pooled wilcoxon p)."""
    deltas, wins = [], 0
    for name in arch:
        d = [a - b for a, b in zip(arch[name], base[name])]
        deltas += d
        if np.mean(arch[name]) <= np.mean(base[name]):
            wins += 1
    deltas = np.array(deltas)
    try:
        _, p = stats.wilcoxon(deltas)
    except ValueError:
        p = 1.0
    return deltas.mean() * 100, wins, p


results = {'A_rho0': [], 'A_g': [], 'B_beta': []}

# ---- Sweep A (BETA fixed at default 3.0) ----
PC.BETA = 3.0
base_30 = bench(make_base_policy())

print("=== SWEEP A1: rho0 (g=8, beta=3.0) ===")
print(f"{'rho0':>6}{'delta_pp':>10}{'wins/15':>9}{'p':>10}")
for rho0 in (0.4, 0.5, 0.6, 0.7, 0.8):
    d, w, p = compare(bench(make_arch_policy(rho0, 8.0)), base_30)
    results['A_rho0'].append({'rho0': rho0, 'delta_pp': d, 'wins': w, 'p': p})
    print(f"{rho0:>6.1f}{d:>10.3f}{w:>9}{p:>10.1e}")

print("\n=== SWEEP A2: g_arq (rho0=0.6, beta=3.0) ===")
print(f"{'g':>6}{'delta_pp':>10}{'wins/15':>9}{'p':>10}")
for g in (2.0, 4.0, 8.0, 16.0, 32.0):
    d, w, p = compare(bench(make_arch_policy(0.6, g)), base_30)
    results['A_g'].append({'g': g, 'delta_pp': d, 'wins': w, 'p': p})
    print(f"{g:>6.0f}{d:>10.3f}{w:>9}{p:>10.1e}")

print("\n=== SWEEP B: BETA (arch at rho0=0.6, g=8) ===")
print(f"{'beta':>6}{'base_drop':>11}{'delta_pp':>10}{'wins/15':>9}{'p':>10}")
for beta in (1.5, 3.0, 4.5, 6.0):
    PC.BETA = beta
    base_b = base_30 if beta == 3.0 else bench(make_base_policy())
    arch_b = bench(make_arch_policy(0.6, 8.0))
    d, w, p = compare(arch_b, base_b)
    bm = np.mean([np.mean(v) for v in base_b.values()])
    results['B_beta'].append({'beta': beta, 'base_drop': float(bm),
                              'delta_pp': d, 'wins': w, 'p': p})
    print(f"{beta:>6.1f}{bm:>11.4f}{d:>10.3f}{w:>9}{p:>10.1e}")
PC.BETA = 3.0

json.dump(results, open('/home/clopez/emmet/data/sensitivity_sweep.json', 'w'),
          indent=2, default=float)

print("\n=== VERDICT ===")
allrows = results['A_rho0'] + results['A_g'] + results['B_beta']
strong = sum(1 for r in allrows if r['wins'] >= 12 and r['p'] < 0.01)
print(f"settings with wins>=12/15 and p<0.01: {strong}/{len(allrows)}")
if strong >= len(allrows) - 2:
    print("PLATEAU: the buoyancy core wins across the parameter grid. Robust,")
    print("not overfit. The 15/15 claim stands on solid ground.")
elif strong >= len(allrows) // 2:
    print("PARTIAL PLATEAU: robust in a region, weaker at the edges. Report the")
    print("region; the claim holds with stated bounds.")
else:
    print("NEEDLE: the win depends on the specific defaults. Overfit - the")
    print("claim must be softened and the tuning reported.")
