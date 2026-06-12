# Code Audit

The simulation code behind every number in the paper is subject to an
adversarial audit. The goal is not style but correctness: find any defect
that would change or invalidate published results. This document tracks
method, scope and findings.

## Scope

Core (everything depends on it): `flowsim.py`, `physics_cores.py`,
`emmet_budget.py`, `equivalence.py`, `equivalence_strict.py`,
`baselines_extra.py`. Battery scripts are audited as they are touched.

## Methods and status

| # | Method | Status |
|---|---|---|
| 1 | External adversarial review of the core scripts | in progress |
| 2 | Invariant test suite (conservation, reset, pairing) | planned |
| 3 | Negative control: identical routers must tie exactly | **PASS** |
| 4 | Cross-implementation of metrics (TOST vs statsmodels) | planned |
| 5 | Baseline fidelity vs published specs (DRILL, CONGA) | planned |
| 6 | Seed and pairing audit (RNG isolation) | planned |
| 7 | Known-answer tests on hand-checkable graphs | planned |
| 8 | Static analysis (ruff, mypy) | planned |

## Method 3: negative control (2026-06-12)

Two instances of the same router (archimedes core) ran under different
labels across the full 15-topology bench, with a DRILL run interleaved
between them to expose any inter-run contamination. Per-seed drop rates
were compared pairwise.

Result: **bit-identical in 15/15 topologies; worst absolute delta
exactly 0.0** for both the physics pair and the DRILL pair. The harness
is deterministic, order-independent, and free of RNG or state leakage
between paired runs. Any equivalence reported between two *different*
routers therefore reflects the routers, not the harness.

Script: `experiments/negative_control.py`. Raw data:
`data/negative_control.json`.
