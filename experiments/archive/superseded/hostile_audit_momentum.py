"""Hostile audit of EMMET-momentum-DP. Seven suspicions tested."""
import json, statistics, time, math
from pathlib import Path
import sys
sys.path.insert(0, '/home/clopez/emmet/experiments')
import networkx as nx
import random

REPO = Path('/home/clopez/emmet')
DATA = REPO / 'data'

# ============================================================
# Suspicion 1: cherry-picking via sweep on 5 scenarios
# ============================================================
print('=' * 70)
print('SUSPICION 1: kappa=1.0 from sweep — does it generalize?')
print('=' * 70)
sweep = json.loads((DATA / 'momentum_dp_kappa_sweep.json').read_text())
full = json.loads((DATA / 'momentum_full_summary.json').read_text())

sweep_scenarios = set(s['scenario'] for s in sweep)
full_scenarios = set(s['scenario'] for s in full)
new_scenarios = full_scenarios - sweep_scenarios
print(f'Sweep scenarios: {len(sweep_scenarios)} | New scenarios in full: {len(new_scenarios)}')
print(f'New: {sorted(new_scenarios)}')
print()

# How many of the new scenarios show momentum >= laspaug?
wins_new = 0
ties_new = 0
losses_new = 0
for s in full:
    if s['scenario'] not in new_scenarios: continue
    em = s['momentum_dp_losses_mean']
    la = s['lasp_aug_losses_mean']
    if la > 0:
        if em < la * 0.99: wins_new += 1
        elif em > la * 1.01: losses_new += 1
        else: ties_new += 1
    else:
        ties_new += 1
print(f'NEW scenarios (not in sweep): wins={wins_new} ties={ties_new} losses={losses_new}')
print(f'  -> if losses are 0 and wins > 0, generalization is fine')
print()

# ============================================================
# Suspicion 2: capacity in losses (we only measured cap in deliveries)
# ============================================================
print('=' * 70)
print('SUSPICION 2: capacity wasted in lost packets')
print('=' * 70)
raw = json.loads((DATA / 'momentum_full_raw.json').read_text())
# We don't have per-packet caps for losses in raw. Need a focused re-run.
# But we CAN compute approximate: total caps consumed = lasp+ deliveries * cap_per_del
# vs momentum deliveries * cap_per_del. If losses count as wasted partial-path caps,
# we'd need to count them. Without that, the test is incomplete.
# Note this for the report.
print('NOTE: raw data has cap only for deliveries. Lost packet capacity unknown.')
print('To verify properly we need a focused re-run with per-packet logging.')
print('Filing this as DEFERRED — will run a focused experiment if needed.')
print()

# ============================================================
# Suspicion 3: timing — is DP-momentum impractically slow?
# ============================================================
print('=' * 70)
print('SUSPICION 3: timing comparison')
print('=' * 70)
from emmet_budget import build_real, build_syn, reset, gen_traf, edge_potential, BETA, THETA, DECAY
from emmet_momentum_dp import emmet_momentum_dp_route, lasp_aug_route, M_INITIAL, M_MAX, M_BUCKETS, ALPHA_BUDGET
import statistics as st

# Run timing on GEANT, single packet
G = build_real('Geant.graphml', seed=0)
nodes = list(G.nodes())

t_lasp, t_mom = [], []
N_TIMING = 50
for i in range(N_TIMING):
    src = nodes[i % len(nodes)]
    dst = nodes[(i*7 + 13) % len(nodes)]
    if src == dst: continue
    t0 = time.perf_counter_ns()
    lasp_aug_route(G, src, dst, {})
    t_lasp.append(time.perf_counter_ns() - t0)
    t0 = time.perf_counter_ns()
    emmet_momentum_dp_route(G, src, dst, {}, kappa=1.0)
    t_mom.append(time.perf_counter_ns() - t0)

med_lasp = st.median(t_lasp) / 1e6  # ms
med_mom = st.median(t_mom) / 1e6
print(f'LASP-aug median:    {med_lasp:.3f} ms per route')
print(f'Momentum-DP median: {med_mom:.3f} ms per route')
print(f'Ratio: {med_mom/med_lasp:.1f}x slower')
if med_mom / med_lasp > 50:
    print('  -> CONCERN: DP is >50x slower. May limit deployability.')
elif med_mom / med_lasp > 10:
    print('  -> Notable but acceptable in offline/control-plane settings.')
else:
    print('  -> OK for production paths.')
print()

# ============================================================
# Suspicion 4: determinism
# ============================================================
print('=' * 70)
print('SUSPICION 4: determinism — same seed -> same result?')
print('=' * 70)
G = build_real('Geant.graphml', seed=0)
reset(G)
snap = {}
runs_paths = []
for trial in range(3):
    G2 = build_real('Geant.graphml', seed=0)
    reset(G2)
    paths = []
    nodes_l = list(G2.nodes())
    for i in range(20):
        src = nodes_l[i % len(nodes_l)]
        dst = nodes_l[(i*7 + 13) % len(nodes_l)]
        if src == dst: continue
        path, _ = emmet_momentum_dp_route(G2, src, dst, snap, kappa=1.0)
        paths.append(tuple(path) if path else None)
    runs_paths.append(paths)

all_match = all(runs_paths[0] == r for r in runs_paths[1:])
print(f'3 runs with same input produced identical paths: {all_match}')
print()

# ============================================================
# Suspicion 5: warmup uses momentum routing
# ============================================================
print('=' * 70)
print('SUSPICION 5: warmup uses momentum — does this give it an unfair edge?')
print('=' * 70)
print('Both LASP-aug and momentum use the same warmup snapshot (built with momentum).')
print('The asymmetry concern is: maybe LASP-aug would do better with its OWN warmup?')
print('Test: rerun GEANT with each algorithm using its own warmup, compare deltas.')
print('Filing as VERIFY NEEDED — let me do this run.')
print()

# Quick verify: compute LASP-aug warmup vs momentum warmup, both for LASP-aug
from emmet_momentum_dp import warmup as warmup_mom
from emmet_budget import warmup as warmup_budget

def warmup_lasp(G, traf):
    """Warmup using only LASP-aug routes."""
    snap = {}
    for src, dst in traf:
        if src == dst: continue
        n_e = G.number_of_edges()
        temp = sum(G[u][v]['load']/G[u][v]['capacity'] for u,v in G.edges())/n_e if n_e else 0
        beta_eff = BETA * (1 + THETA * temp)
        def w(u, v, d):
            e = G[u][v]
            cong = e['load']/e['capacity']
            k = tuple(sorted([u,v]))
            return 1.0*e['latency'] + beta_eff*cong + 2.0*snap.get(k, 0)
        try: path = nx.shortest_path(G, src, dst, weight=w)
        except nx.NetworkXNoPath: continue
        for i in range(len(path)-1):
            u, v = path[i], path[i+1]
            e = G[u][v]
            e['load'] += 1
            if e['load'] > e['capacity']:
                e['loss'] += 1
                break
        for u, v in G.edges():
            G[u][v]['load'] *= 0.9
    return {tuple(sorted([u,v])): G[u][v]['loss'] for u,v in G.edges()}

# Compare two warmups on GEANT
TRAFFIC_STEPS = 200
def simulate_lasp_only(G, traf, snap):
    snap_l = dict(snap)
    delivered = losses = 0
    for src, dst in traf:
        if src == dst: continue
        n_e = G.number_of_edges()
        temp = sum(G[u][v]['load']/G[u][v]['capacity'] for u,v in G.edges())/n_e if n_e else 0
        beta_eff = BETA * (1 + THETA * temp)
        def w(u, v, d):
            e = G[u][v]
            cong = e['load']/e['capacity']
            k = tuple(sorted([u,v]))
            return 1.0*e['latency'] + beta_eff*cong + 2.0*snap_l.get(k, 0)
        try: path = nx.shortest_path(G, src, dst, weight=w)
        except nx.NetworkXNoPath: continue
        lost = False
        for i in range(len(path)-1):
            u, v = path[i], path[i+1]
            e = G[u][v]
            e['load'] += 1
            if e['load'] > e['capacity']:
                e['loss'] += 1
                losses += 1
                lost = True
                break
        if not lost: delivered += 1
        for u, v in G.edges():
            G[u][v]['load'] *= 0.9
        for k in list(snap_l.keys()):
            snap_l[k] *= DECAY
    return delivered, losses

losses_mom_warmup = []
losses_lasp_warmup = []
for seed in range(20):
    G = build_real('Geant.graphml', seed=seed); reset(G)
    wt = gen_traf(list(G.nodes()), max(20, G.number_of_nodes()*5), seed+300000)
    snap_m = warmup_mom(G, wt, kappa=1.0, m_max=M_MAX, alpha_budget=ALPHA_BUDGET)

    G = build_real('Geant.graphml', seed=seed); reset(G)
    wt = gen_traf(list(G.nodes()), max(20, G.number_of_nodes()*5), seed+300000)
    snap_l = warmup_lasp(G, wt)

    G = build_real('Geant.graphml', seed=seed); reset(G)
    traf = gen_traf(list(G.nodes()), TRAFFIC_STEPS, seed+100000)
    _, l_mom_w = simulate_lasp_only(G, traf, snap_m)
    losses_mom_warmup.append(l_mom_w)

    G = build_real('Geant.graphml', seed=seed); reset(G)
    traf = gen_traf(list(G.nodes()), TRAFFIC_STEPS, seed+100000)
    _, l_lasp_w = simulate_lasp_only(G, traf, snap_l)
    losses_lasp_warmup.append(l_lasp_w)

print(f'GEANT 20 seeds:')
print(f'  LASP-aug WITH momentum-warmup snap:   loss mean={st.mean(losses_mom_warmup):.2f}')
print(f'  LASP-aug WITH lasp-warmup snap:       loss mean={st.mean(losses_lasp_warmup):.2f}')
diff = st.mean(losses_lasp_warmup) - st.mean(losses_mom_warmup)
print(f'  Difference: {diff:+.2f} (positive = lasp-warmup HURTS lasp-aug)')
if abs(diff) < 0.5:
    print('  -> snapshot source is NOT a confounding factor')
else:
    print('  -> POSSIBLE confound. Need deeper investigation.')
print()

# ============================================================
# Suspicion 6: bucket count
# ============================================================
print('=' * 70)
print('SUSPICION 6: bucket discretization (M_BUCKETS=8)')
print('=' * 70)
from emmet_momentum_dp import emmet_momentum_dp_route as mom_route, warmup
losses_b8 = []
losses_b16 = []
losses_b32 = []
for seed in range(15):
    G = build_real('Geant.graphml', seed=seed); reset(G)
    wt = gen_traf(list(G.nodes()), max(20, G.number_of_nodes()*5), seed+300000)
    snap = warmup(G, wt, kappa=1.0, m_max=M_MAX, alpha_budget=ALPHA_BUDGET)

    for buckets, store in [(8, losses_b8), (16, losses_b16), (32, losses_b32)]:
        G2 = build_real('Geant.graphml', seed=seed); reset(G2)
        traf = gen_traf(list(G2.nodes()), TRAFFIC_STEPS, seed+100000)
        snap_l = dict(snap)
        l = 0
        for src, dst in traf:
            if src == dst: continue
            path, _ = mom_route(G2, src, dst, snap_l, kappa=1.0, m_max=M_MAX,
                                alpha_budget=ALPHA_BUDGET, n_buckets=buckets)
            if path is None or len(path) < 2: continue
            for i in range(len(path)-1):
                u, v = path[i], path[i+1]
                e = G2[u][v]
                e['load'] += 1
                if e['load'] > e['capacity']:
                    e['loss'] += 1
                    l += 1
                    break
            for u, v in G2.edges():
                G2[u][v]['load'] *= 0.9
            for k in list(snap_l.keys()):
                snap_l[k] *= DECAY
        store.append(l)

print(f'GEANT 15 seeds, kappa=1.0:')
print(f'  M_BUCKETS=8:  loss mean={st.mean(losses_b8):.2f}')
print(f'  M_BUCKETS=16: loss mean={st.mean(losses_b16):.2f}')
print(f'  M_BUCKETS=32: loss mean={st.mean(losses_b32):.2f}')
diff_8_16 = abs(st.mean(losses_b8) - st.mean(losses_b16))
if diff_8_16 < 0.3:
    print('  -> 8 buckets is sufficient discretization')
else:
    print(f'  -> RECONSIDER: 8 vs 16 buckets differ by {diff_8_16:.2f}')
print()

# ============================================================
# Suspicion 7: statistical significance
# ============================================================
print('=' * 70)
print('SUSPICION 7: statistical significance of GEANT delta')
print('=' * 70)
# Pull per-seed losses from raw_full
geant_runs = [r for r in raw if r['scenario'] == 'GEANT']
mom_losses = [r['momentum_dp']['losses'] for r in geant_runs]
la_losses = [r['lasp_aug']['losses'] for r in geant_runs]
print(f'GEANT n={len(geant_runs)} seeds:')
print(f'  LASP-aug:    mean={st.mean(la_losses):.2f}  std={st.stdev(la_losses):.2f}')
print(f'  Momentum-DP: mean={st.mean(mom_losses):.2f}  std={st.stdev(mom_losses):.2f}')

# Paired Mann-Whitney via simple z approx (or just paired t-test)
# Use difference per-seed
diffs = [l - m for l, m in zip(la_losses, mom_losses)]
mean_diff = st.mean(diffs)
sd_diff = st.stdev(diffs)
n = len(diffs)
t_stat = mean_diff / (sd_diff / math.sqrt(n))
print(f'  Per-seed difference: mean={mean_diff:.2f}  std={sd_diff:.2f}  n={n}')
print(f'  Paired t-statistic: t={t_stat:.2f}')
if abs(t_stat) > 4:
    print('  -> Highly significant (|t|>4, p << 0.001)')
elif abs(t_stat) > 2:
    print('  -> Significant (|t|>2, p < 0.05)')
else:
    print('  -> NOT significant')
print()
print('=' * 70)
print('AUDIT COMPLETE')
print('=' * 70)
