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
| 5 | Baseline fidelity vs published specs (DRILL, CONGA) | **PASS** |
| 6 | Seed and pairing audit (RNG isolation) | **PASS** |
| 7 | Known-answer tests on hand-checkable graphs | **PASS** |
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
## Method 5: baseline fidelity (2026-06-15)

DRILL (Ghorbani et al., SIGCOMM 2017) is implemented as DRILL[m,1]:
at each hop it samples up to m candidate next-hops biased toward the
destination, picks the least loaded by load/capacity, and remembers the
previous best to damp per-packet oscillation. The paper describes it as
"a near-stateless balancer that makes per-hop local decisions", which
matches the code.

CONGA (Alizadeh et al., SIGCOMM 2014) is congestion-aware multipath
load balancing, originally for leaf-spine datacenter fabrics. Here it
is adapted to general WAN topologies as a K-shortest-path selector that
picks the least congested path (ties broken by latency). The paper
states this plainly: CONGA "scores K shortest paths and selects the
least congested". This is an adaptation, not a literal datacenter CONGA,
and is labelled as such; the essence preserved is global congestion-aware
path choice over a bounded candidate set.

**Lesson encoded:** the K=4 grid artefact (an early result where CONGA
looked weak because K was too small) is now a regression test: K must
expose the disjoint paths for CONGA to exploit congestion. The reported
equivalence uses K=16/32. Five behavioural tests in
`tests/test_baseline_fidelity.py` confirm both baselines act as
described; all pass.

**Honest limitation:** behavioural fidelity is verified, not
bit-equivalence with the authors reference code (not public for either).
The baselines are faithful to the published *descriptions* and to the
adaptations the paper declares.
## Method 7: known-answer tests (2026-06-15)

Five tiny graphs with hand-built schedules where served/drop counts are
worked out by pencil and checked against the simulator, with routes
forced so only the load/drop mechanic is under test: a single flow under
capacity, an overflow where all flows drop, the exact-capacity boundary
(load == capacity must NOT drop, pinning the strict > condition), a
second-hop bottleneck (drop scans every edge), and exact flow-lifetime
(TTL) accounting. All five match the arithmetic. Tests:
`tests/test_known_answer.py`.
## Method 6: seed and pairing isolation (2026-06-15)

The equivalence comparisons are paired: per seed, one schedule is built
once and every router runs it on a freshly rebuilt graph. Four tests
confirm the isolation that makes the pairing valid: gen_flows is
deterministic in its seed and sensitive to it; simulate_flows does not
mutate the shared schedule; and a DRILL run reproduces its solo result
even after an interleaved EMMET run (its internal RNG does not leak into
other runs). This complements the negative control, which proved the
same at the result level. Tests: tests/test_seed_isolation.py.
