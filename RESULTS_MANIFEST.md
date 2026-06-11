# Results Manifest

Explicit mapping from every quantitative claim of the current paper
(`paper/paper_v5.tex`) to the script that produced it and the JSON holding
the raw per-seed data. No claim depends on data outside this repository.

| Claim (paper section) | Script | Data |
|---|---|---|
| Attractor: phys-phys cos 0.979 / 1-L1 0.930; controls 0.938 / 0.867; Wilcoxon p=1e-4 on both metrics (attractor) | `experiments/attractor_full.py` | `data/attractor_full.json` |
| Term gating: scar relocates 0-16% of load mass, buoyancy 0-3.3% (both drop-gated), Pascal 3-10% always-on (gating) | `experiments/activity_audit.py` | `data/activity_audit.json` |
| Congestion causes divergence, interventional: Spearman +0.77..+1.00 within topologies; squeezed BA x21, relieved GEANT /8; saturation plateau (causal) | `experiments/causal_capacity_sweep.py` | `data/causal_sweep.json` |
| Structural ceiling: inverted-U inside Abilene, peak 0.030 at f=1.25, one third of richer graphs (ceiling) | `experiments/abilene_relief_sweep.py` | `data/abilene_relief.json` |
| Double dissociation: tube/sp -> gains partial r=+0.59; congestion -> divergence partial r=+0.92 (dissociation) | `experiments/partial_perf.py`, `experiments/divergence_vs_congestion.py` | script-printed tables |
| Ablation redux: scar n.s. in contested (-0.34pp, p=0.12), harmful in saturation; buoyancy beats base 15/15, every regime p<=1e-4 (redux) | `experiments/ablation_redux.py` | `data/ablation_redux.json` |
| Parameter plateau: 14/14 settings win 15/15 (rho0 0.4-0.8, g 2-32, beta 1.5-6) (redux) | `experiments/sensitivity_sweep.py` | `data/sensitivity_sweep.json` |
| Threshold vs curvature: Hooke 15/15; linear ~= quadratic at matched threshold (redux) | `experiments/hooke_quick.py` | `data/hooke_quick.json` |
| Fair-budget equivalence: TOST delta=2pp, 9/12/10 of 15 vs CONGA-K16 and 10/10/10 vs DRILL; margin sweep 2.0 -> 0.2pp (fair bench, margins) | `experiments/equivalence_strict.py` | `data/equivalence_strict_{newton,archimedes,pascal}.json` (20 seeds/topo) |
| Temporal channel: flaky bench, calibrated scar -1.26pp vs base (14/15, p=4e-10), beats Archimedes 13/15 and Hooke 12/15; flaky-edge precision 0.69-0.80 vs 0.20 for load (taxonomy) | `experiments/newton_redemption.py` | `data/newton_redemption.json` |
| tube/sp regression robustness under Cook's-distance leverage analysis (leverage) | `experiments/leverage_tubesp.py` | script-printed tables |
| Stale state: graceful degradation +0.44pp (T=2) to +8.94pp (T=40), monotone, no resonance, oscillation ratio <=1.29 (freshness) | `experiments/stale_state.py` | `data/stale_state.json` |
| Decision cost: physics DP 72-2347 us/decision; ~0.1x the CONGA-K16 catalogue, 5-26x DRILL local sampling, same substrate (freshness) | `experiments/cpu_bench.py` | `data/cpu_bench.json` |
| Bursty arrivals: DRILL +0.59pp pooled (p=0.014), 13/15 within 2pp; vs CONGA-16 mean -0.74pp n.s., 14/15 within 2pp (freshness) | `experiments/bursty_bench.py` | `data/bursty_bench.json` |
| Spatial visibility: k-hop horizon recovers 36/63/77% of the blind-to-global gap at k=1/2/3; k=3 sits +1.75pp from global, inside the margin; both pre-registered checks held (freshness) | `experiments/khop_visibility.py` | `data/khop_visibility.json` |
| Jain fairness of per-edge utilization: physics spread 0.016 (0.581-0.597); DRILL 0.640, CONGA-16 0.710 (attractor) | `experiments/jain_fairness.py` | `data/jain_fairness.json` |

Data files from earlier development phases (bursty, momentum, scalability,
blood sweeps, ...) remain under `data/` for provenance; they back the
historical sections only.
