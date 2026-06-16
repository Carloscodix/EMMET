# Audit Log

This document summarizes the audits the EMMET algorithm and codebase
have been subjected to during development. It is included for
transparency: a reviewer or implementer can see what was checked,
what was fixed, and what remains open.

## Internal hostile audit (round 1)

Seven suspicions were tested on the `EMMET-momentum-DP` algorithm
and its experimental harness. All findings were addressed before the
public release; the test script remains in
`experiments/hostile_audit_momentum_v2.py`.

| # | Suspicion | Outcome |
|---|---|---|
| 1 | κ chosen via cherry-picking on a small sweep | Validated: κ=1.0 generalizes across a 22-scenario battery and a clean 6-value × 5-scenario × 100-seed sweep |
| 2 | Capacity per-attempt undercounted on dropped packets | Fixed: `cap_per_attempt`, `cap_per_routed_attempt`, and `cap_consumed_lost` now reported separately |
| 3 | Routing decision time prohibitive at production B=32 | Measured: ~8.8× slower than LASP-aug per route; suitable for control-plane traffic engineering |
| 4 | Determinism violation under same seed | Verified deterministic: same seed → identical paths across 3 independent runs |
| 5 | Warmup snapshot asymmetric between algorithms | Fixed: each algorithm uses its own warmup; reduced GÉANT improvement from −66.4 % (asymmetric) to −60.2 % (corrected) |
| 6 | Bucket discretization (B=8) hides a coarseness artifact | Verified: improvement is stable across B ∈ {8, 16, 32, 64} (range 0.2 losses on GÉANT) |
| 7 | t-test inappropriate for discrete, zero-inflated differences | Wilcoxon signed-rank added: W=4137.5, p=1.1×10⁻⁸ confirms the result |

## External code audits

The codebase was audited by an independent reviewer in four rounds.
Each round produced concrete findings; all bloquantes and importantes
were addressed. The complete commit history under `git log` documents
each fix with the round number it addressed.

| Round | Findings | Resolution |
|---|---|---|
| 1 | 8 findings on the earlier `EMMET-fb` algorithm (selection bias, asymmetric information, lookahead inconsistencies) | Algorithm pivoted to budget-DP, then to mass-aware DP |
| 2 | 7 findings on `momentum-DP`: 1 BLOCKER (bucket non-idempotency), 5 IMPORTANT, 1 MINOR | All addressed; commit `f68b7c0` |
| 3 | 4 findings on the post-fix code, plus 3 review-risks for Tier-2 venue submission | All code findings addressed; commit `0a6fb63`. Review-risks tracked in this paper's positioning |
| 4 | 6 findings on the cleaned codebase: 4 IMPORTANT, 2 MINOR | All addressed; commit `6158431` |

## Statistical reproducibility

The headline GÉANT result (−60.2 % loss reduction) reproduces exactly
from the raw JSON file `data/momentum_clean_full_raw.json` over 100
seeds. Re-running `experiments/momentum_clean_full.py` from scratch
produces byte-identical aggregate metrics, modulo floating-point
ordering at the 5th decimal.

## Open items

- Wilcoxon sensitivity to zero-handling method (`zsplit` vs `pratt`
  vs `wilcox`). The current report uses `zsplit`. A sensitivity
  table is planned for the camera-ready version.
- Comparison against learning-based routers (RL, DRL backpressure).
  Out of scope for the present paper; mentioned in §7 (Discussion)
  as future work.
- Hardware-accelerated DP variants (FPGA, eBPF). Mentioned in §7 as
  a deployment path beyond the controller plane.
﻿
## Adversarial battery (June 2026, rounds 2-6)

- **Scar-feeding bug:** the attractor experiments ran the Newton core with
  its scar field starved (cosine 1.000000 against the bare substrate);
  fixed (`feed_scar`), re-run: 0.979, significance improved to p=1e-4.
- **Retracted theory:** a min-cut argument for the attractor predicted the
  wrong sign of the tube/sp-divergence relation; retracted and replaced by
  the interventional two-factor law.
- **Bench duplication:** the harness loaded the GEANT graph under the
  "Abilene" label; fixed with the real 11-node Abilene. All tables
  regenerated (verdict counts barely moved; the real Abilene became the
  saturation boundary case).
- **Ablation redux:** the original keep-scar / drop-buoyancy verdict
  inverted on the modern bench (buoyancy 15/15 in every regime; scar
  n.s. or harmful) - a harness artifact of the packet-era simulator.
- **Parameter sweep:** 14/14 settings reproduce the 15/15 win; not overfit.
- **Newton re-examined:** temporal mis-calibration (scar half-life 346
  ticks in a 200-tick simulation) accounted for the harm; on a
  non-stationary (flaky-links) bench the calibrated scar beats all
  memoryless cores, identifying flaky edges with precision 0.69-0.80
  where load statistics reach 0.20. Pre-registered outcomes throughout.


## June 11 - External review round 2 and the freshness battery

- **Nine independent reviews** of the v5 manuscript (including the two
  harshest reviewers of round 1, whose round had surfaced five fatal flaws
  and preceded a desk rejection). Result: zero undeclared technical flaws
  in nine readings; the two consensus criticisms were exactly the
  limitations the paper already states (idealized global state; flow-level
  granularity). One stale caveat from a pre-fix revision survived in the
  limitations list, was caught by four readers, and is corrected in v5.1.
- **Stale-state experiment** (the "single most important experiment this
  work leaves open", now run): graceful, monotone degradation (+0.44pp at
  T=2 up to +8.94pp at T=40). Our pre-registered prediction (<0.5pp at
  T=20) missed the magnitude and is reported as such; the
  reviewer-predicted resonance failure mode did not appear (oscillation
  ratio <=1.29 across the sweep). Stale state blinds the core; it does
  not destabilize it.
- **Decision-cost benchmark:** physics DP ~0.1x the CONGA-K16 catalogue
  cost and 5-26x DRILL local sampling, same substrate; 0.07-2.3 ms per
  flow.
- **Bursty-arrival stress:** DRILL +0.59pp pooled (p=0.014); 13/15
  topologies within the 2pp margin; vs CONGA-K16 the core concedes
  nothing.
- **Reproducibility bug found and fixed:** a module-level import of the
  retired momentum layer broke `policy_drill` on a clean clone
  (`bursty_runner.py`); now guarded so legacy runners fail only if
  actually invoked.

- **Spatial-visibility experiment (k-hop horizon):** both pre-registered
  checks held this time: k=2 recovers 63% of the blind-to-global gap
  (>=50% registered), k=3 recovers 77% (>=66%); at k=3 the core sits
  +1.75pp from the global view, inside the 2pp margin.
- **Jain fairness:** the three physics cores land within 0.016 of each
  other; engineered balancers sit visibly apart. The attractor through a
  third metric.
- **Formal appendix added (tube/sp):** faithful definition, three
  elementary propositions, and the walk-vs-path overcount identified as a
  mechanical source of the predictor residual -- consistent with
  scale-free graphs fitting the regression loosest.
- **Verified citation added:** Alistarh, Nadiradze & Sabour,
  Algorithmica 2022 (dynamic averaging on graphs), as the conceptual
  neighbour of the attractor in router-free load-balancing theory.

## 2026-06-12: related-work restoration and code-audit start

- **Coverage regression found and fixed:** the v2 rewrite of the
  related-work section had silently dropped four literature families
  present in the original draft (149 lines, 12 citations reduced to 59
  lines, 4 citations). v3 restores backpressure/queue-gradient,
  learning-based routing, and per-packet congestion state, with
  positioning updated to the equivalence framing.
- **Three citation errors caught by verification before publication:**
  a survey cited with the wrong year (2020 vs 2021, COMST); multipath
  QUIC cited as an RFC when it is still an Internet-Draft; and the
  draft title itself had changed at rev 21. All references now verified
  against dblp, doi.org or the IETF datatracker.
- **Future-work hygiene:** every remaining future-work mention is now
  explicitly one of: done, requires another instrument (stated), or
  open problem. A misplaced paragraph after the conclusion was moved
  into the future-work subsection.
- **Code audit opened (method 3 first):** negative control PASS, see
  docs/CODE_AUDIT.md.

## 2026-06-13: TOST cross-implementation audit + provenance catch

- **Statistic certified (method 4):** our paired TOST reproduces
  statsmodels.ttost_paired and the confidence-interval form exactly
  (p-values to 1e-16) on synthetic data and on all 90 per-seed vectors
  behind the paper tables. No implementation error.
- **Stale data artefact caught and quarantined:** the audit first ran
  against the non-strict `equivalence_*.json`, which disagreed on 4 of
  15 topologies. Root cause was not the statistic but provenance: those
  JSONs predate the Abilene fix and are not the paper source. They were
  moved to `data/_superseded/` with a README. The paper tables are
  backed by post-fix `equivalence_strict_*.json` (20 seeds/topo, per
  RESULTS_MANIFEST); re-running the audit there gives a clean PASS.

## 2026-06-15: baseline fidelity audited (method 5)

- **DRILL and CONGA verified behaviourally** against their published
  descriptions (Ghorbani 2017; Alizadeh 2014). DRILL samples and picks
  least-loaded per hop (not a global argmin); CONGA selects the least
  congested of K shortest paths. Five tests, all pass.
- **K=4 artefact encoded as a regression test.** Reported results use
  K=16/32.
- **Declared limitation:** fidelity is to the published descriptions and
  the WAN adaptation the paper states, not bit-equivalence with
  unreleased reference code.

## 2026-06-15: known-answer tests (method 7)

- **Five hand-computed cases** confirm the load/drop mechanic to the
  tick: under-capacity, full overflow, the exact-capacity boundary
  (verifying the drop condition is strict >, not >=), a second-hop
  bottleneck (drop scans the whole path), and TTL lifetime accounting.
  All pass. The boundary test would catch a systematic off-by-one in
  every reported drop-rate. Tests: tests/test_known_answer.py.

## 2026-06-15: seed/pairing isolation (method 6)

- **Four tests confirm the paired design is sound:** gen_flows is
  deterministic and seed-sensitive; the shared schedule is not mutated
  by a simulation; DRILL reproduces its solo result after an interleaved
  run (RNG does not leak across runs). Complements the negative control
  at the mechanism level. Tests: tests/test_seed_isolation.py.

## 2026-06-15: static analysis (method 8) + reproducibility finding

- **Core is clean:** ruff (correctness rules) and mypy report nothing on
  the seven scripts that produce the paper numbers. Config in ruff.toml;
  experiments/archive excluded as dead code.
- **FINDING (reproducibility, fix before submission):** three scripts in
  RESULTS_MANIFEST cannot be imported/run as committed, because their
  dependency momentum_clean was moved to experiments/archive/ in a later
  cleanup. Affected: sweep_topologies.py, bursty_warmup.py (broken
  import); divergence_vs_congestion.py (depends on the former + an
  undefined simulate_util_scar). The numbers they back (tube/sp; the
  congestion->divergence partial r=+0.92) are in the paper but the code
  as committed does not reproduce them. Single moved module is the root
  cause. Fix: restore/re-point dependency, repair the undefined name,
  regenerate, confirm match.

## 2026-06-15 (cont.): reproducibility finding resolved

The broken import chain from method 8 is fixed (commit above) and, more
importantly, the scope of the finding was pinned down by regenerating
the affected numbers:

- **The headline interventional result reproduces exactly.** Re-running
  causal_capacity_sweep.py gives within-topology Spearman +0.94, +1.00,
  +1.00, +0.77 (drop vs divergence), matching the paper and the stored
  causal_sweep.json bit-for-bit. This is the source of the
  congestion-drives-divergence claim.
- **The broken script was secondary, not the source of the headline
  number.** divergence_vs_congestion.py runs an OBSERVATIONAL cross-
  topology correlation (15 points), which the paper itself flags as the
  noisy one. The partial r=+0.92 / r=+0.59 dissociation is computed by
  partial_perf.py (Abilene excluded, n=14, documented in its header) on
  top of the causal data, not by the broken script. So the paper number
  never depended on the break.
- **Net:** code now reproduces; the headline result is verified; the
  observational script is repaired and available but remains the weaker,
  caveated angle it always was.

- **Minor note (non-blocking):** four analysis scripts (partial_perf,
  divergence_vs_congestion, causal_capacity_sweep, bursty_warmup) run
  their analysis at import time (no `if __name__` guard). They are
  single-use command-line scripts, so this affects no paper number;
  importing one just runs it. Left as-is for now to avoid touching
  working code before submission; a future cleanup could add guards.

## 2026-06-15 (cont.): in-sample +0.59 reproducibility confirmed post-fix

After re-pointing bursty_runner.py off the archived momentum_clean (the
None bug that would have crashed the ripple runner), the in-sample sweep
was regenerated from scratch with the live code:
- reduction% per topology matches the paper ROWS table exactly (all 15
  bit-identical: Grid5 -6.4, Grid7 +40.4, Grid12 +70.7, ...).
- raw tube/sp ~ reduction: Pearson +0.719, Spearman +0.776 (n=14,
  Abilene excluded as in the paper) -- identical to reported values.
- break-even tube/sp = 2.45, canonical. Regenerated JSON is byte-
  identical to the committed one: the number was always correct; the bug
  only threatened future reproducibility, now restored.
