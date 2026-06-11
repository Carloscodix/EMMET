"""stale_state.py - THE crown experiment of v6 (rock #1, ~10 votes).
Does the validated core survive bounded-freshness telemetry?
The router decides on a load VIEW refreshed only every T ticks while the
real load evolves underneath. Three reviewer predictions on trial:
 - MiniMax: "the most important experiment this work leaves open"
 - Gemini: stale potential maps induce RESONANCE / severe oscillation
 - Qwen: how does the attractor degrade with staleness N?
PRE-COMMITTED (ours, before running): degradation is SMOOTH and small -
the attractor is a stable basin and the threshold core needs only a
roughly-right field, not a fresh one. Oscillation ratio ~1 (no resonance).
Outputs: drop rate vs T (paired vs T=1) + oscillation metric
(mean temporal variance of real per-edge load, ratio vs T=1).
"""
import sys, json
import numpy as np
from scipy import stats
sys.path.insert(0, '/home/clopez/emmet/experiments')
import flowsim as FS
import physics_cores as PC
from equivalence import TOPOS, build_topo
from emmet_budget import reset

T_VALUES = [1, 2, 5, 10, 20, 40]
N_SEEDS = 6


def simulate_stale(G, sched, n_ticks, route_fn, T):
    flows = []
    served = drop = 0
    keys = [tuple(sorted(e)) for e in G.edges()]
    series = {k: [] for k in keys}
    view = {k: 0.0 for k in keys}
    for u, v in G.edges():
        G[u][v]['load'] = 0.0
    state = {'scars': {}}
    for t in range(n_ticks):
        # decisions read G['load'] which holds the (possibly stale) VIEW
        for (s, d, dur, rate) in sched.get(t, []):
            path = route_fn(G, s, d, state)
            if path and len(path) >= 2:
                flows.append({'rate': rate, 'ttl': dur, 'route': path})
        # real load this tick
        FS._apply_flow_load(G, flows)
        real = {}
        for u, v in G.edges():
            k = tuple(sorted((u, v)))
            real[k] = G[u][v]['load']
            series[k].append(real[k])
        for fl in flows:
            r = fl['route']; lost = False
            for i in range(len(r) - 1):
                if G[r[i]][r[i+1]]['load'] > G[r[i]][r[i+1]]['capacity']:
                    lost = True; break
            if lost:
                drop += 1
            else:
                served += 1
        for fl in flows:
            fl['ttl'] -= 1
        flows = [fl for fl in flows if fl['ttl'] > 0]
        # refresh the view if due, then expose the view for next decisions
        if (t + 1) % T == 0:
            view = real
        for u, v in G.edges():
            G[u][v]['load'] = view[tuple(sorted((u, v)))]
    total = served + drop
    osc = float(np.mean([np.var(series[k]) for k in keys])) if keys else 0.0
    return {'drop_rate': drop / total if total else 0.0, 'osc': osc}


pol = PC.make_physics_policy('archimedes')
rows = []
print(f"{'topo':<11}" + ''.join(f"{'T='+str(T):>9}" for T in T_VALUES))
for t in TOPOS:
    name, builder, dsrc = t
    res = {T: {'drop': [], 'osc': []} for T in T_VALUES}
    for s in range(N_SEEDS):
        G0, dem = build_topo(name, builder, dsrc, s)
        sched = FS.gen_flows(dem, 200, s + 9000, birth_rate=0.8,
                             dur_lo=4, dur_hi=12, rate=1)
        for T in T_VALUES:
            G, _ = build_topo(name, builder, dsrc, s); reset(G)
            r = simulate_stale(G, sched, 200, pol, T)
            res[T]['drop'].append(r['drop_rate'])
            res[T]['osc'].append(r['osc'])
    row = {'topo': name}
    for T in T_VALUES:
        row[f'drop_T{T}'] = float(np.mean(res[T]['drop']))
        row[f'osc_T{T}'] = float(np.mean(res[T]['osc']))
        row[f'drop_T{T}_seeds'] = [float(x) for x in res[T]['drop']]
    rows.append(row)
    print(f"{name:<11}" + ''.join(f"{row[f'drop_T{T}']:>9.4f}" for T in T_VALUES))

json.dump(rows, open('/home/clopez/emmet/data/stale_state.json', 'w'), indent=2)

print('\n=== pooled vs T=1 (paired; positive delta = WORSE with staleness) ===')
print(f"{'T':>4}{'mean_drop':>11}{'delta_pp':>10}{'wilcoxon_p':>12}{'osc_ratio':>11}")
base_d = np.array([x for r in rows for x in r['drop_T1_seeds']])
base_o = np.mean([r['osc_T1'] for r in rows])
for T in T_VALUES:
    d = np.array([x for r in rows for x in r[f'drop_T{T}_seeds']])
    deltas = d - base_d
    if T == 1:
        p = 1.0
    else:
        try:
            _, p = stats.wilcoxon(deltas)
        except ValueError:
            p = 1.0
    oratio = np.mean([r[f'osc_T{T}'] for r in rows]) / base_o if base_o > 0 else 1.0
    print(f"{T:>4}{d.mean():>11.4f}{deltas.mean()*100:>+10.2f}{p:>12.1e}{oratio:>11.3f}")

print('\n=== VERDICT (pre-committed) ===')
d20 = np.array([x for r in rows for x in r['drop_T20_seeds']]) - base_d
o20 = np.mean([r['osc_T20'] for r in rows]) / base_o if base_o > 0 else 1.0
if d20.mean() * 100 < 0.5 and o20 < 1.2:
    print("SMOOTH: at T=20 (5 percent telemetry frequency) degradation is under")
    print("0.5pp and no oscillation inflation. Gemini's resonance is FALSIFIED on")
    print("this bench; the core tolerates stale telemetry. Limitation -> finding.")
elif o20 > 1.5:
    print("RESONANCE CONFIRMED: oscillation inflates >1.5x under staleness -")
    print("Gemini's failure mode is real; map the boundary T per topology.")
else:
    print("GRACEFUL-DEGRADATION: drop rises with T but without resonance.")
    print("Report the curve; the operational boundary is measurable and mild.")
