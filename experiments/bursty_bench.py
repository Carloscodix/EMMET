"""bursty_bench.py - rock #2 partial mitigation, declared as partial.
Bursty demand at flow level: calm trickle + sharp 5-tick bursts of short
flows every 25 ticks. Does DRILL's reactive advantage open a gap against
the threshold core when traffic arrives in bursts? (True micro-bursts are
packet-scale and remain out of scope - this stresses the flow-level
analogue.) PRE-COMMITTED: DRILL improves relatively (its territory);
question is whether the core stays within ~2pp."""
import sys, json, random
import numpy as np
from scipy import stats
sys.path.insert(0, '/home/clopez/emmet/experiments')
import flowsim as FS
import physics_cores as PC
from equivalence import TOPOS, build_topo
from emmet_budget import reset

N_SEEDS = 6
PERIOD, BURST = 25, 5


def bursty_sched(dem, seed):
    dense = FS.gen_flows(dem, 200, seed, birth_rate=2.4, dur_lo=2, dur_hi=6, rate=1)
    rng = random.Random(seed + 777)
    out = {}
    for t, births in dense.items():
        in_burst = (t % PERIOD) < BURST
        keep = [b for b in births if in_burst or rng.random() < 0.15]
        if keep:
            out[t] = keep
    return out


ROUTERS = [('arch', PC.make_physics_policy('archimedes')),
           ('drill', FS.policy_drill),
           ('conga16', FS.make_conga_policy(16))]
rows = []
print(f"{'topo':<11}{'arch':>9}{'drill':>9}{'conga16':>9}")
for t in TOPOS:
    name, builder, dsrc = t
    res = {n: [] for n, _ in ROUTERS}
    for s in range(N_SEEDS):
        G0, dem = build_topo(name, builder, dsrc, s)
        sched = bursty_sched(dem, s + 9000)
        for n, pol in ROUTERS:
            G, _ = build_topo(name, builder, dsrc, s); reset(G)
            res[n].append(FS.simulate_flows(G, sched, 200, pol)['drop_rate'])
    row = {'topo': name}
    for n, _ in ROUTERS:
        row[n] = float(np.mean(res[n]))
        row[n + '_seeds'] = [float(x) for x in res[n]]
    rows.append(row)
    print(f"{name:<11}{row['arch']:>9.4f}{row['drill']:>9.4f}{row['conga16']:>9.4f}")

json.dump(rows, open('/home/clopez/emmet/data/bursty_bench.json', 'w'), indent=2)
print('\n=== paired arch vs rivals on bursty traffic (negative = arch better) ===')
for rival in ('drill', 'conga16'):
    deltas = []
    wins = 0
    for r in rows:
        deltas += [a - b for a, b in zip(r['arch_seeds'], r[rival + '_seeds'])]
        if r['arch'] <= r[rival]:
            wins += 1
    deltas = np.array(deltas)
    try:
        _, p = stats.wilcoxon(deltas)
    except ValueError:
        p = 1.0
    within = sum(1 for r in rows if abs(r['arch'] - r[rival]) <= 0.02)
    print(f"  arch vs {rival:<8} mean_delta_pp={deltas.mean()*100:+.2f}  "
          f"wins={wins}/15  within-2pp={within}/15  p={p:.1e}")
