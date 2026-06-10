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
