"""
newton_redemption.py - the honest second look at Newton III.

Two objective reasons the retirement may have been premature:
 (1) CALIBRATION: scar_decay=0.998 -> half-life 346 ticks > the 200-tick sim.
     The scar in the redux never healed: permanent grudge, not reaction.
     deposit/decay were never swept (the sensitivity sweep covered rho0,g,beta).
 (2) HABITAT: the scar is temporal memory, and the whole bench is STATIONARY.
     In a stationary world the instantaneous state is sufficient; memory is
     redundant by construction of the bench, not by fault of the law.
     We evaluated a historian in a world without a past.

PRE-COMMITTED OUTCOMES:
 A) If short-half-life Newton stops HURTING the dense grids / saturation ->
    the redux damage was calibration, not law.
 B) FLAKY BENCH (non-stationary: edges that fail in episodes and look healthy
    in between): if calibrated Newton beats base AND archimedes/hooke there ->
    the law was right, the regime was wrong: Newton is the physicist of memory.
 C) If it adds nothing even in its own habitat -> definitive retirement, signed.

Anti-ghost check: does the accumulated scar identify the flaky edges better
than mean utilization does? (memory must SEE something congestion cannot.)
"""
import sys, json, random
import numpy as np
from scipy import stats
sys.path.insert(0, '/home/clopez/emmet/experiments')
import flowsim as FS
import physics_cores as PC
from equivalence import TOPOS, build_topo
from emmet_budget import reset


def simulate_flaky(G, sched, n_ticks, route_fn, flaky=(), period=0, duration=0,
                   severity=0.2, deposit=1.0, decay=0.998):
    """simulate_flows with scar feeding + optional flaky-link episodes.
    period=0 -> stationary (no episodes). flaky edges share one schedule."""
    flows = []
    state = {'scars': {}}
    scars = state['scars']
    orig = {tuple(sorted(e)): G[e[0]][e[1]]['capacity'] for e in G.edges()}
    flaky = set(tuple(sorted(e)) for e in flaky)
    served = drop = 0
    util_sum = {k: 0.0 for k in orig}
    for t in range(n_ticks):
        in_episode = period > 0 and (t % period) < duration
        for (u, v) in G.edges():
            k = tuple(sorted((u, v)))
            G[u][v]['capacity'] = orig[k] * severity if (in_episode and k in flaky) else orig[k]
        for (s, d, dur, rate) in sched.get(t, []):
            path = route_fn(G, s, d, state)
            if path and len(path) >= 2:
                flows.append({'rate': rate, 'ttl': dur, 'route': path})
        FS._apply_flow_load(G, flows)
        for u, v in G.edges():
            k = tuple(sorted((u, v)))
            util_sum[k] += G[u][v]['load'] / orig[k]
        for fl in flows:
            r = fl['route']; bad = None
            for i in range(len(r) - 1):
                if G[r[i]][r[i+1]]['load'] > G[r[i]][r[i+1]]['capacity']:
                    bad = tuple(sorted((r[i], r[i+1]))); break
            if bad is not None:
                drop += 1
                scars[bad] = scars.get(bad, 0.0) + deposit
            else:
                served += 1
        for k in list(scars.keys()):
            scars[k] *= decay
            if scars[k] < 1e-6:
                del scars[k]
        for fl in flows:
            fl['ttl'] -= 1
        flows = [fl for fl in flows if fl['ttl'] > 0]
    for (u, v) in G.edges():
        G[u][v]['capacity'] = orig[tuple(sorted((u, v)))]
    total = served + drop
    return {'drop_rate': drop / total if total else 0.0,
            'scars': dict(scars), 'util': {k: util_sum[k] / n_ticks for k in util_sum}}


def base_policy():
    return lambda G, s, d, st: PC.route_with_term(G, s, d, st, lambda G, u, v, x: 0.0)


# ============ PART A: calibration on the stationary bench ============
print("=== PART A: was the damage the half-life? (stationary, hurt topologies) ===")
A_TOPOS = ('Grid5', 'Grid6', 'WS_n50_k4', 'GEANT', 'Abilene')
SETTINGS = [(1.0, 0.998, 'historic t1/2=346'), (1.0, 0.95, 't1/2=14'),
            (0.5, 0.98, 't1/2=34'), (0.25, 0.95, 'gentle t1/2=14')]
N_A = 6
print(f"{'topo':<11}{'base':>8}" + ''.join(f"{lbl.split()[0][:9]:>11}" for _, _, lbl in SETTINGS))
for tn in A_TOPOS:
    t = [x for x in TOPOS if x[0] == tn][0]
    name, builder, dsrc = t
    res = {i: [] for i in range(-1, len(SETTINGS))}
    for s in range(N_A):
        G0, dem = build_topo(name, builder, dsrc, s)
        sched = FS.gen_flows(dem, 200, s + 9000, birth_rate=0.8, dur_lo=4, dur_hi=12, rate=1)
        G, _ = build_topo(name, builder, dsrc, s); reset(G)
        res[-1].append(simulate_flaky(G, sched, 200, base_policy())['drop_rate'])
        for i, (dep, dec, _) in enumerate(SETTINGS):
            G, _ = build_topo(name, builder, dsrc, s); reset(G)
            res[i].append(simulate_flaky(G, sched, 200, PC.make_physics_policy('newton'),
                                         deposit=dep, decay=dec)['drop_rate'])
    line = f"{tn:<11}{np.mean(res[-1]):>8.4f}"
    for i in range(len(SETTINGS)):
        line += f"{np.mean(res[i]):>11.4f}"
    print(line)

# ============ PART B: the flaky bench (Newton's habitat) ============
print("\n=== PART B: flaky links (non-stationary). period=40, duration=8, sev=0.2 ===")
ROUTERS = [('base', base_policy(), 1.0, 0.998),
           ('newton_cal', PC.make_physics_policy('newton'), 0.5, 0.98),
           ('newton_hist', PC.make_physics_policy('newton'), 1.0, 0.998),
           ('archimedes', PC.make_physics_policy('archimedes'), 1.0, 0.998),
           ('hooke', PC.make_physics_policy('hooke'), 1.0, 0.998)]
N_B = 6
rows = []
print(f"{'topo':<11}" + ''.join(f"{n[:10]:>12}" for n, _, _, _ in ROUTERS))
for t in TOPOS:
    name, builder, dsrc = t
    res = {n: [] for n, _, _, _ in ROUTERS}
    keep = {}
    for s in range(N_B):
        G0, dem = build_topo(name, builder, dsrc, s)
        sched = FS.gen_flows(dem, 200, s + 9000, birth_rate=0.8, dur_lo=4, dur_hi=12, rate=1)
        edges = [tuple(sorted(e)) for e in G0.edges()]
        rng = random.Random(1000 + s)
        flaky = rng.sample(edges, max(2, int(0.15 * len(edges))))
        for n, pol, dep, dec in ROUTERS:
            G, _ = build_topo(name, builder, dsrc, s); reset(G)
            r = simulate_flaky(G, sched, 200, pol, flaky=flaky, period=40,
                               duration=8, severity=0.2, deposit=dep, decay=dec)
            res[n].append(r['drop_rate'])
            if n == 'newton_cal' and s == 0:
                keep = {'scars': r['scars'], 'util': r['util'], 'flaky': set(flaky)}
    row = {'topo': name, 'keep': keep}
    for n, _, _, _ in ROUTERS:
        row[n] = res[n]
    rows.append(row)
    print(f"{name:<11}" + ''.join(f"{np.mean(res[n]):>12.4f}" for n, _, _, _ in ROUTERS))

print('\n--- paired tests on the flaky bench (negative = first is BETTER) ---')
for a, b in (('newton_cal', 'base'), ('newton_cal', 'archimedes'),
             ('newton_cal', 'hooke'), ('newton_hist', 'base')):
    deltas = []
    wins = 0
    for r in rows:
        deltas += [x - y for x, y in zip(r[a], r[b])]
        if np.mean(r[a]) <= np.mean(r[b]):
            wins += 1
    deltas = np.array(deltas)
    try:
        _, p = stats.wilcoxon(deltas)
    except ValueError:
        p = 1.0
    print(f"  {a} vs {b:<12} mean_delta_pp={deltas.mean()*100:+.2f}  "
          f"wins={wins}/15  wilcoxon p={p:.1e}")

# ============ PART C: anti-ghost - does the scar SEE the flaky edges? ============
print("\n=== PART C: does the scar identify the flaky edges? (precision@|flaky|) ===")
for r in rows:
    k = r['keep']
    if not k or not k.get('scars'):
        continue
    if r['topo'] not in ('Grid8', 'WS_n50_k4', 'BA_n50_m2', 'GEANT'):
        continue
    nf = len(k['flaky'])
    top_scar = set(sorted(k['scars'], key=k['scars'].get, reverse=True)[:nf])
    top_util = set(sorted(k['util'], key=k['util'].get, reverse=True)[:nf])
    ps_ = len(top_scar & k['flaky']) / nf
    pu_ = len(top_util & k['flaky']) / nf
    print(f"  {r['topo']:<11} scar precision={ps_:.2f}  util precision={pu_:.2f}"
          f"  ({'scar SEES what load cannot' if ps_ > pu_ else 'no extra signal'})")

json.dump([{kk: vv for kk, vv in r.items() if kk != 'keep'} for r in rows],
          open('/home/clopez/emmet/data/newton_redemption.json', 'w'), indent=2)
print("\nsaved data/newton_redemption.json")
