"""jain_fairness.py - Jain index of per-edge utilization (LeChat's ask).
If the attractor story is right, all congestion-aware mechanisms should
land on near-identical fairness, distinct from blind routing."""
import sys, json
import numpy as np
sys.path.insert(0, '/home/clopez/emmet/experiments')
import flowsim as FS
import physics_cores as PC
from equivalence import TOPOS, build_topo
from emmet_budget import reset

N_SEEDS = 6


def simulate_util(G, sched, n_ticks, route_fn):
    flows = []
    keys = [tuple(sorted(e)) for e in G.edges()]
    acc = {k: 0.0 for k in keys}
    state = {'scars': {}}
    for t in range(n_ticks):
        for (s, d, dur, rate) in sched.get(t, []):
            path = route_fn(G, s, d, state)
            if path and len(path) >= 2:
                flows.append({'rate': rate, 'ttl': dur, 'route': path})
        FS._apply_flow_load(G, flows)
        for u, v in G.edges():
            k = tuple(sorted((u, v)))
            acc[k] += G[u][v]['load'] / G[u][v]['capacity']
        for fl in flows:
            fl['ttl'] -= 1
        flows = [fl for fl in flows if fl['ttl'] > 0]
    u = np.array([acc[k] / n_ticks for k in keys])
    return float((u.sum() ** 2) / (len(u) * (u ** 2).sum())) if (u ** 2).sum() > 0 else 1.0


ROUTERS = [
           ('newton', PC.make_physics_policy('newton')),
           ('arch', PC.make_physics_policy('archimedes')),
           ('pascal', PC.make_physics_policy('pascal')),
           ('conga16', FS.make_conga_policy(16)),
           ('drill', FS.policy_drill)]
rows = []
print(f"{'topo':<11}" + ''.join(f"{n:>9}" for n, _ in ROUTERS))
for t in TOPOS:
    name, builder, dsrc = t
    res = {n: [] for n, _ in ROUTERS}
    for s in range(N_SEEDS):
        G0, dem = build_topo(name, builder, dsrc, s)
        sched = FS.gen_flows(dem, 200, s + 9000, birth_rate=0.8,
                             dur_lo=4, dur_hi=12, rate=1)
        for n, pol in ROUTERS:
            G, _ = build_topo(name, builder, dsrc, s); reset(G)
            try:
                res[n].append(simulate_util(G, sched, 200, pol))
            except Exception as e:
                print('SKIP', n, name, e); res[n].append(float('nan'))
    row = {'topo': name}
    for n, _ in ROUTERS:
        row[n] = float(np.nanmean(res[n]))
    rows.append(row)
    print(f"{name:<11}" + ''.join(f"{row[n]:>9.3f}" for n, _ in ROUTERS))

json.dump(rows, open('/home/clopez/emmet/data/jain_fairness.json', 'w'), indent=2)
print('\n=== pooled Jain (mean over topologies) ===')
for n, _ in ROUTERS:
    print(f"  {n:<9} {np.nanmean([r[n] for r in rows]):.4f}")
phys = [np.nanmean([r[n] for r in rows]) for n in ('newton', 'arch', 'pascal')]
print(f"\nphysics spread (max-min): {max(phys)-min(phys):.4f}  <- attractor check")
