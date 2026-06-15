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
| 2 | Invariant test suite (conservation, reset, pairing) | **PASS** |
| 3 | Negative control: identical routers must tie exactly | **PASS** |
| 4 | Cross-implementation of metrics (TOST vs statsmodels) | **PASS** |
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

## Method 2: invariant suite (2026-06-12)

Seven invariants, checked across the first four topologies and two
seeds per policy (shortest, DRILL, EMMET): flow conservation, drop_rate
range, drop_rate/count consistency, determinism, reset clearing edge
load, births bounded by schedule entries, and per-tick load reset. All
pass. Suite: `tests/test_invariants.py` (self-contained, runs without
pytest).
## Method 4: cross-implementation of TOST (2026-06-13)

The equivalence statistic in `equivalence.py::tost` was checked against
two independent paths: the canonical `statsmodels.stats.weightstats.
ttost_paired`, and the (1-2*alpha) confidence-interval characterisation
of a 5% TOST. On four synthetic regimes and on every per-seed vector
backing the paper tables (3 cores x 15 topologies x {DRILL, CONGA},
90 paired comparisons), all three paths agree on the equivalence
verdict and the p-values match to ~1e-16 or better. Script:
`experiments/tost_audit.py`.
