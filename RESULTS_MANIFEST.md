# Results Manifest

This document gives the **explicit mapping from every quantitative
claim in the paper** to the script that produced it, the raw and
aggregate JSON files containing the data, and the section of the
paper where the claim appears. No claim in the paper depends on any
file outside this manifest.

## Headline claims

### GÉANT loss reduction: −60.2 %

| Component | Path |
|---|---|
| Algorithm under test | `experiments/emmet_momentum_dp.py` |
| Baseline (LASP-aug) | `experiments/momentum_clean.py:lasp_aug_route` (uses `emmet_budget.edge_potential`) |
| Battery script | `experiments/momentum_clean_full.py` |
| Raw data (per seed) | `data/momentum_clean_full_raw.json` |
| Aggregate summary | `data/momentum_clean_full_summary.json` |
| Paper section | §6.1 (Headline) — Table 1 |
| Reproduction | `python3 experiments/momentum_clean_full.py` (~6 min, 28 cores) |

**Verification snippet:**
```python
import json, statistics as st
raw = json.load(open('data/momentum_clean_full_raw.json'))
geant = [r for r in raw if r['scenario'] == 'GEANT']
la = st.mean(r['lasp_aug']['losses'] for r in geant)
mom = st.mean(r['momentum_dp']['losses'] for r in geant)
assert 60.0 < (la - mom) / la * 100 < 60.5, "Headline number drift"
```

### Statistical significance: t = 5.21, Wilcoxon p = 1.1×10⁻⁸

| Component | Path |
|---|---|
| Computation | `experiments/hostile_audit_momentum_v2.py` |
| Input | `data/momentum_clean_full_raw.json` (GÉANT subset) |
| Paper section | §5.6 and §6.1 |
| Reproduction | `python3 experiments/hostile_audit_momentum_v2.py` |

### Capacity per routed attempt: +0.04 hops

| Component | Path |
|---|---|
| Source script | `experiments/momentum_clean.py:simulate_lasp_aug` and `:simulate_momentum` |
| Aggregate | `data/momentum_clean_full_summary.json` keys `*_cap_per_routed_attempt_mean` |
| Paper section | §6.1 — Table 1 |

## Generalization claims

### 22-scenario battery, 5 topology families

| Component | Path |
|---|---|
| ER + Real (16 + 2 scenarios) | `experiments/momentum_clean_full.py` → `data/momentum_clean_full_*.json` |
| Grid + BA + WS (1 + 2 + 3 scenarios) | `experiments/topology_extended_battery.py` → `data/topology_extended_*.json` |
| Topology builders | `experiments/topology_builders.py` |
| Paper section | §6.2 — Table 2, Figure 4 |
| Reproduction | `python3 experiments/topology_extended_battery.py` (~5 min) |

## Hyperparameter justification

### κ = 1.0 chosen by sweep, Pareto-optimal

| Component | Path |
|---|---|
| Sweep script | `experiments/momentum_clean_kappa_sweep.py` |
| Sweep range | κ ∈ {0, 0.1, 0.3, 0.5, 1.0, 1.5} × 5 scenarios × 100 seeds = 3000 runs |
| Raw data | `data/momentum_clean_kappa_sweep_raw.json` |
| Summary | `data/momentum_clean_kappa_sweep_summary.json` |
| Paper section | §6.3 — Table 3, Figure 5 |
| Reproduction | `python3 experiments/momentum_clean_kappa_sweep.py` (~4 min) |

### Bucket discretization (B = 32) stability

| Component | Path |
|---|---|
| Sensitivity test | `experiments/hostile_audit_momentum_v2.py` (suspicion #6) |
| Test scope | B ∈ {8, 16, 32, 64} × 20 GÉANT seeds with own warmup per B |
| Result | Range across bucket counts: 0.20 losses (stable) |
| Paper section | §5.5 (mentioned), §6.3 (referenced) |

## Audit history

| Audit | Outcome | Document |
|---|---|---|
| Internal hostile suspicions (7) | All addressed | `docs/AUDIT_LOG.md` |
| External code audit, 4 rounds | All bloquantes/importantes addressed | `docs/AUDIT_LOG.md` + commit history |

## What is NOT in this manifest

The `archive/` directories contain superseded experiments
(EMMET-thermal, EMMET-budget without mass, EMMET-fb with shortest-path
fallback, ablations of mechanisms ultimately discarded). **These do
not support any claim in the paper.** They are preserved for
traceability of the development process. A reviewer or implementer
who wants to understand why certain design choices were made can find
the rationale in `docs/AUDIT_LOG.md` and `docs/internal/ROADMAP.md`.
