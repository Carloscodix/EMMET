"""Hostile audit v2: addresses Codex findings #2, #3, #5, #6, #7.

Changes vs v1:
- #2: reads momentum_clean_full_raw.json (the headline JSON), not momentum_full_raw.json
- #3: each bucket count gets its own warmup with that same bucket count
- #5: timing measured with 32 buckets (production config)
- #6: relative paths via Path(__file__).resolve().parents[1]
- #7: adds Wilcoxon signed-rank as robustness check alongside paired t-test
"""
import json, statistics, time, math
from pathlib import Path
import sys
import networkx as nx
import random
try:
    from scipy import stats as scipy_stats
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False
    scipy_stats = None

REPO = Path(__file__).resolve().parents[1]
DATA = REPO / 'data'
sys.path.insert(0, str(REPO / 'experiments'))

# ============================================================
# Suspicion 1: cherry-picking via sweep on 5 scenarios
# ============================================================
print('=' * 70)
print('SUSPICION 1: kappa=1.0 from sweep — does it generalize?')
print('=' * 70)
sweep = json.loads((DATA / 'momentum_dp_kappa_sweep.json').read_text())
full = json.loads((DATA / 'momentum_clean_full_summary.json').read_text())

sweep_scenarios = set(s['scenario'] for s in sweep)
full_scenarios = set(s['scenario'] for s in full)
new_scenarios = full_scenarios - sweep_scenarios
print(f'Sweep scenarios: {len(sweep_scenarios)} | New scenarios in full: {len(new_scenarios)}')

wins_new, ties_new, losses_new = 0, 0, 0
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
print()

# ============================================================
# Suspicion 2: capacity in losses (deferred — see momentum_clean_v2 with cap_per_attempt)
# ============================================================
print('=' * 70)
print('SUSPICION 2: capacity wasted in lost packets — see momentum_clean_v2.py')
print('=' * 70)
print('Addressed by adding cap_per_attempt metric (Codex finding #4).')
print()

# ============================================================
# Suspicion 3: timing — measured with 32 buckets (production config)
# ============================================================
print('=' * 70)
print('SUSPICION 3: timing with 32 buckets (Codex #5)')
print('=' * 70)
from emmet_budget import build_real
from emmet_momentum_dp import emmet_momentum_dp_route, lasp_aug_route, M_MAX, ALPHA_BUDGET

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
    emmet_momentum_dp_route(G, src, dst, {}, kappa=1.0, n_buckets=32)
    t_mom.append(time.perf_counter_ns() - t0)

med_lasp = statistics.median(t_lasp) / 1e6
med_mom = statistics.median(t_mom) / 1e6
print(f'LASP-aug median:    {med_lasp:.3f} ms per route')
print(f'Momentum-DP (32 buckets) median: {med_mom:.3f} ms per route')
print(f'Ratio: {med_mom/med_lasp:.1f}x slower')
print()

# ============================================================
# Suspicion 4: determinism
# ============================================================
print('=' * 70)
print('SUSPICION 4: determinism')
print('=' * 70)
from emmet_budget import reset, gen_traf
G = build_real('Geant.graphml', seed=0); reset(G)
runs_paths = []
for trial in range(3):
    G2 = build_real('Geant.graphml', seed=0); reset(G2)
    paths = []
    nodes_l = list(G2.nodes())
    for i in range(20):
        src = nodes_l[i % len(nodes_l)]
        dst = nodes_l[(i*7 + 13) % len(nodes_l)]
        if src == dst: continue
        path, _ = emmet_momentum_dp_route(G2, src, dst, {}, kappa=1.0, n_buckets=32)
        paths.append(tuple(path) if path else None)
    runs_paths.append(paths)
all_match = all(runs_paths[0] == r for r in runs_paths[1:])
print(f'3 runs with same input produced identical paths: {all_match}')
print()

# ============================================================
# Suspicion 5: warmup symmetry — already verified in v1, kept for record
# ============================================================
print('=' * 70)
print('SUSPICION 5: warmup symmetry — addressed in momentum_clean.py')
print('=' * 70)
print('Each algorithm uses its own warmup (warmup_lasp_aug, warmup_momentum).')
print('Verified in momentum_clean.py:run_one()')
print()

# ============================================================
# Suspicion 6: bucket discretization with PROPER warmup per bucket count
# ============================================================
print('=' * 70)
print('SUSPICION 6: buckets with own warmup per bucket (Codex #3)')
print('=' * 70)
from emmet_momentum_dp import warmup as warmup_mom
from emmet_budget import DECAY, TRAFFIC_STEPS

losses_b = {8: [], 16: [], 32: [], 64: []}
N_SEEDS = 20
for seed in range(N_SEEDS):
    for buckets in [8, 16, 32, 64]:
        # OWN warmup with this bucket count
        G_w = build_real('Geant.graphml', seed=seed); reset(G_w)
        wt = gen_traf(list(G_w.nodes()), max(20, G_w.number_of_nodes()*5), seed+300000)
        snap = {}
        for src, dst in wt:
            if src == dst: continue
            path, _ = emmet_momentum_dp_route(G_w, src, dst, snap,
                                               kappa=1.0, m_max=M_MAX,
                                               alpha_budget=ALPHA_BUDGET,
                                               n_buckets=buckets)
            if path is None or len(path) < 2: continue
            for i in range(len(path)-1):
                u, v = path[i], path[i+1]
                e = G_w[u][v]
                e['load'] += 1
                if e['load'] > e['capacity']:
                    e['loss'] += 1
                    break
            for u, v in G_w.edges():
                G_w[u][v]['load'] *= 0.9
        snap = {tuple(sorted([u,v])): G_w[u][v]['loss'] for u,v in G_w.edges()}

        # Measurement run with same bucket count
        G2 = build_real('Geant.graphml', seed=seed); reset(G2)
        traf = gen_traf(list(G2.nodes()), TRAFFIC_STEPS, seed+100000)
        snap_l = dict(snap)
        l = 0
        for src, dst in traf:
            if src == dst: continue
            path, _ = emmet_momentum_dp_route(G2, src, dst, snap_l,
                                               kappa=1.0, m_max=M_MAX,
                                               alpha_budget=ALPHA_BUDGET,
                                               n_buckets=buckets)
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
        losses_b[buckets].append(l)

print(f'GEANT {N_SEEDS} seeds, kappa=1.0, OWN warmup per bucket count:')
for b in [8, 16, 32, 64]:
    print(f'  buckets={b:>3}: loss mean={statistics.mean(losses_b[b]):.2f} '
          f'std={statistics.stdev(losses_b[b]):.2f}')
ranges = max(statistics.mean(v) for v in losses_b.values()) - min(statistics.mean(v) for v in losses_b.values())
print(f'  Range across bucket counts: {ranges:.2f}')
if ranges < 0.5:
    print('  -> Discretization stable across reasonable bucket counts')
else:
    print(f'  -> Notable variation. May warrant further investigation.')
print()

# ============================================================
# Suspicion 7: stat significance — t-test + Wilcoxon (Codex #2 + #7)
# ============================================================
print('=' * 70)
print('SUSPICION 7: stat significance with CORRECT json (Codex #2)')
print('=' * 70)
raw = json.loads((DATA / 'momentum_clean_full_raw.json').read_text())
geant_runs = [r for r in raw if r['scenario'] == 'GEANT']
mom_losses = [r['momentum_dp']['losses'] for r in geant_runs]
la_losses = [r['lasp_aug']['losses'] for r in geant_runs]
print(f'GEANT n={len(geant_runs)} seeds (clean json):')
print(f'  LASP-aug:    mean={statistics.mean(la_losses):.2f}  std={statistics.stdev(la_losses):.2f}')
print(f'  Momentum-DP: mean={statistics.mean(mom_losses):.2f}  std={statistics.stdev(mom_losses):.2f}')

diffs = [l - m for l, m in zip(la_losses, mom_losses)]
mean_diff = statistics.mean(diffs)
sd_diff = statistics.stdev(diffs)
n = len(diffs)
t_stat = mean_diff / (sd_diff / math.sqrt(n))
print(f'  Per-seed difference: mean={mean_diff:.2f}  std={sd_diff:.2f}  n={n}')
print(f'  Paired t-statistic: t={t_stat:.3f}')

# Wilcoxon signed-rank (robust to non-normality)
if HAS_SCIPY:
    try:
        w_stat, w_p = scipy_stats.wilcoxon(la_losses, mom_losses,
                                             alternative='greater',
                                             zero_method='zsplit')
        print(f'  Wilcoxon signed-rank: W={w_stat:.1f}  p={w_p:.2e}')
    except Exception as e:
        print(f'  Wilcoxon error: {e}')
else:
    # Fallback: simple sign test (less powerful but no scipy needed)
    pos = sum(1 for d in diffs if d > 0)
    neg = sum(1 for d in diffs if d < 0)
    n_nonzero = pos + neg
    print(f'  scipy not installed; sign test only:')
    print(f'    pos={pos} neg={neg} (out of {n_nonzero} non-zero diffs)')
    print(f'    install scipy>=1.10 for full Wilcoxon signed-rank')

# Sign distribution diagnostic (Codex finding #7)
positive = sum(1 for d in diffs if d > 0)
zero = sum(1 for d in diffs if d == 0)
negative = sum(1 for d in diffs if d < 0)
print(f'  Sign distribution: pos={positive} zero={zero} neg={negative}')
print()
print('=' * 70)
print('AUDIT v2 COMPLETE')
print('=' * 70)
