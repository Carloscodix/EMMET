# Reproducibility Guide

**Environment:** Python 3.10+, `pip install -r requirements.txt`
(networkx, numpy, scipy). Every experiment is a standalone script with
fixed seeds and no arguments:

```bash
python3 experiments/<script>.py
```

Results are printed (verdict block at the end) and saved to `data/`.
Paired comparisons share graph, demand and flow schedule per seed.

| Script | Approx. runtime | Reproduces |
|---|---|---|
| `attractor_full.py` | ~10 min | attractor table, both metrics |
| `activity_audit.py` | ~3 min | term-gating percentages |
| `causal_capacity_sweep.py` | ~6 min | interventional sweep |
| `abilene_relief_sweep.py` | ~2 min | ceiling / inverted-U |
| `ablation_redux.py` | ~8 min | core inversion |
| `sensitivity_sweep.py` | ~13 min | parameter plateau |
| `hooke_quick.py` | ~4 min | threshold vs curvature |
| `equivalence_strict.py` | ~25 min | fair-budget TOST + margin sweep |
| `newton_redemption.py` | ~7 min | temporal channel (flaky bench) |
| `partial_perf.py`, `divergence_vs_congestion.py`, `leverage_tubesp.py` | 2-4 min each | dissociation, leverage |
| `stale_state.py` | ~3 min | freshness pricing (staleness sweep) |
| `khop_visibility.py` | ~4 min | spatial visibility (k-hop sweep) |
| `bursty_bench.py` | ~5 min | bursty-arrival stress |
| `cpu_bench.py` | ~1 min | per-decision cost benchmark |
| `jain_fairness.py` | ~8 min | Jain fairness, attractor third lens |
| `negative_control.py` | ~8 min | harness integrity: identical routers must tie exactly (expect PASS, worst delta 0.0) |

The printed verdict blocks match the paper's numbers to the digits shown.
Claim-to-data mapping: [`RESULTS_MANIFEST.md`](RESULTS_MANIFEST.md).
