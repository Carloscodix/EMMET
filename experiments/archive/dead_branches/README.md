# Legacy experiments

These scripts were used in earlier iterations of EMMET (v1–v6). They are
preserved here for transparency and reproducibility of the development
history but **should not be used for new experiments**.

## Why they are here, not deleted

Three independent code reviews (two by Claude, one by Codex) identified
issues that affect the quantitative results these scripts produce:

1. **Asymmetric loss information.** Scripts using `e['loss']` directly
   in the potential give EMMET live information that SP/ECMP do not have.
   Affects: `emmet_beta_sweep.py`, `emmet_density_sweep.py`,
   `emmet_ecmp_baseline.py`, `emmet_momentum.py`, `emmet_real_topologies.py`,
   `emmet_experiment.py`, `emmet_thermal_v5.py`.

2. **Inert exploration_floor.** Adding a constant to all neighbor
   potentials does not change the `min()` ranking. The thermal background
   term in v5/v6 was mathematically a no-op. Affects: `emmet_thermal_v5.py`,
   `emmet_thermal_v6.py`.

3. **Hard-coded paths to /home/clopez/...** — not portable across machines.

## Use the v7 implementation instead

`experiments/emmet_thermal_v7.py` is the canonical, audit-clean version.
It uses portable paths, snapshot-based loss with read-only access during
measurement, half-life decay, and **epsilon-greedy stochastic exploration**
that actually changes routing decisions.

The findings reported in the paper are based on v7. Numbers from earlier
versions are kept in JSON files but are documented as superseded.
