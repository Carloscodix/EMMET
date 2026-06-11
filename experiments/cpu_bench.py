"""cpu_bench.py - rock #1b: microseconds per routing decision.
Physics DP O(k|E|) vs CONGA-K16 (selection over precomputed paths) vs
DRILL (local per-hop). Warm load state, 300 timed decisions each."""
import sys, time, json, random
import numpy as np
sys.path.insert(0, '/home/clopez/emmet/experiments')
import flowsim as FS
import physics_cores as PC
from equivalence import TOPOS, build_topo
from emmet_budget import reset

TARGETS = ('Grid8', 'Grid12', 'WS_n50_k6', 'GEANT', 'Abilene')
N_DEC = 300
ROUTERS = [('physics_dp', PC.make_physics_policy('archimedes')),
           ('conga_k16', FS.make_conga_policy(16)),
           ('drill', FS.policy_drill)]
out = []
print(f"{'topo':<11}{'physics_dp':>12}{'conga_k16':>12}{'drill':>10}   (us/decision)")
for tn in TARGETS:
    t = [x for x in TOPOS if x[0] == tn][0]
    name, builder, dsrc = t
    G, dem = build_topo(name, builder, dsrc, 0); reset(G)
    sched = FS.gen_flows(dem, 200, 9000, birth_rate=0.8, dur_lo=4, dur_hi=12, rate=1)
    FS.simulate_flows(G, sched, 60, PC.make_physics_policy('archimedes'))  # warm loads
    nodes = list(G.nodes())
    rng = random.Random(42)
    pairs = []
    while len(pairs) < N_DEC:
        s, d = rng.sample(nodes, 2)
        pairs.append((s, d))
    row = {'topo': name}
    line = f"{name:<11}"
    for rn, pol in ROUTERS:
        state = {'scars': {}}
        t0 = time.perf_counter()
        for (s, d) in pairs:
            pol(G, s, d, state)
        us = (time.perf_counter() - t0) / N_DEC * 1e6
        row[rn] = us
        line += f"{us:>12.1f}" if rn != 'drill' else f"{us:>10.1f}"
    out.append(row)
    print(line)
json.dump(out, open('/home/clopez/emmet/data/cpu_bench.json', 'w'), indent=2)
print('\nRatios physics/conga and physics/drill per topo:')
for r in out:
    print(f"  {r['topo']:<11} vs conga x{r['physics_dp']/r['conga_k16']:.1f}   "
          f"vs drill x{r['physics_dp']/r['drill']:.1f}")
