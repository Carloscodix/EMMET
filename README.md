# EMMET: Effective-Mass Memory Edge Transport

> *Mass-aware routing with a hat-tip to Dr. Emmett Brown.*

A stateful extension to gradient-based adaptive network routing where
each packet carries an internal scalar---its **mass**---that grows
multiplicatively with the congestion of edges traversed. The mass
scales the cost of candidate edges at every routing decision,
producing emergent load balancing without central coordination.

## Headline result

On the **GÉANT** topology (real European backbone, 40 nodes,
61 edges; loaded from `data/topologies/Geant.graphml`),
100 random traffic seeds:

| Metric | LASP-aug baseline | Mass-Aware DP | Δ |
|---|---|---|---|
| Congestion losses (per run) | 3.24 | 1.29 | **−60.2%** |
| Delivery rate | 98.3% | 99.3% | +1.0pp |
| Capacity per routed attempt | 3.70 hops | 3.74 hops | +0.04 hops |

Paired t-test: t = 5.21, p ≪ 0.001.
Wilcoxon signed-rank: W = 4137.5, p = 1.1×10⁻⁸.

The improvement generalizes across **26 scenarios in 5 topology
families**: Erdős–Rényi (18 configs), real backbones (GÉANT, Abilene),
2D regular lattice, scale-free Barabási–Albert, and small-world
Watts–Strogatz.

## Repository layout

```
emmet/
├── experiments/          Live scripts that reproduce the paper
│   ├── emmet_budget.py              Network builders, baselines (SP, LASP)
│   ├── emmet_momentum_dp.py         Algorithm 1: Mass-Aware DP routing
│   ├── momentum_clean.py            Simulation infrastructure (own warmup)
│   ├── momentum_clean_full.py       Full battery → headline results
│   ├── momentum_clean_kappa_sweep.py    Justifies κ=1.0
│   ├── topology_builders.py         Grid, BA, WS topologies
│   ├── topology_extended_battery.py     Generalization across 5 topology families
│   ├── hostile_audit_momentum_v2.py     Self-audit (7 suspicions tested)
│   └── archive/         Superseded scripts (preserved for traceability)
├── data/                 JSONs cited in the paper
│   ├── momentum_clean_full_*.json   Headline battery (20 ER + 2 real)
│   ├── momentum_clean_kappa_sweep_*.json    κ sweep
│   ├── topology_extended_*.json     5-family generalization
│   └── archive/         Older experimental runs
├── paper/                LaTeX sources for the paper
│   ├── abstract.tex
│   ├── introduction.tex
│   ├── section3_model.tex
│   ├── algorithm1.tex
│   ├── figure1_concept.tex (+ .pdf)
│   ├── paper_main.tex               Assembles the above into preview
│   └── archive/         Earlier paper versions
├── docs/
│   ├── AUDIT_LOG.md      Internal hostile-suspicion checks and external code-audit history
│   ├── DEVELOPMENT_NOTE.md   Note on the condensed commit history
│   └── internal/         Working notes (not part of the public claim surface)
├── requirements.txt
├── LICENSE
├── CITATION.cff
├── REPRODUCIBILITY.md
├── RESULTS_MANIFEST.md
└── README.md
```

## Note on archived material

Superseded scripts, intermediate data files, and earlier versions of
the paper are preserved under `archive/`, `experiments/archive/`,
`data/archive/`, and `paper/archive/` for traceability. **None of the
claims in the current paper depend on archived material**: the
mapping from each headline number to the script that produced it and
the JSON file it lives in is given explicitly in
[`RESULTS_MANIFEST.md`](RESULTS_MANIFEST.md). The archived files
exist so that an interested reader can see the development trajectory
(EMMET-thermal → EMMET-budget → mass-aware DP), not as evidence for
any claim.

## Reproducing the headline result

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Headline battery: 20 scenarios × 100 seeds, ~6 min on 28 cores
python3 experiments/momentum_clean_full.py
# Writes data/momentum_clean_full_{raw,summary}.json

# Verify GEANT loss reduction reproduces
python3 -c "
import json, statistics as st
raw = json.load(open('data/momentum_clean_full_raw.json'))
g = [r for r in raw if r['scenario'] == 'GEANT']
la = st.mean(r['lasp_aug']['losses'] for r in g)
mom = st.mean(r['momentum_dp']['losses'] for r in g)
print(f'LASP-aug: {la:.2f} | Momentum-DP: {mom:.2f} | reduction: {(la-mom)/la*100:.1f}%')
"
```

Expected output: `LASP-aug: 3.24 | Momentum-DP: 1.29 | reduction: 60.2%`

## Building the paper preview

```bash
cd paper
pdflatex -interaction=nonstopmode paper_main.tex
pdflatex -interaction=nonstopmode paper_main.tex   # second pass for refs
```

Requires TeX Live with `algorithm2e` (`apt install texlive-science` on
Ubuntu).

## Algorithm at a glance

The core routing decision for a packet with current mass `m_in`
crossing a candidate edge `(u,v)`:

```python
# Local edge cost, scaled by the packet's accumulated mass:
delta = m_in * edge_potential(u, v, snap)

# Mass update after crossing:
rho = load(u,v) / capacity(u,v)
m_out = min(m_in * (1 + kappa * rho), m_max)
```

This per-edge cost is fed into a constrained dynamic program over
`(node, hops_used, mass_bucket)` with hop budget
`H = ceil(α_budget · sp_hops)`. Delivery within budget is guaranteed
when a feasible path exists (no dead ends, no fallback). See
[`paper/algorithm1.tex`](paper/algorithm1.tex) for the full
formalization.

## Hyperparameters

Defaults used throughout the paper:

| Parameter | Value | Meaning |
|---|---|---|
| α | 1.0 | Latency coefficient |
| β | 3.0 | Congestion coefficient |
| γ | 2.0 | Loss-snapshot coefficient |
| θ_T | 5.0 | Global thermostat strength |
| κ | 1.0 | Mass growth rate. Module default is 0.3; paper experiments override to 1.0 (Pareto-optimal across battery; sweep over {0, 0.1, 0.3, 0.5, 1.0, 1.5}). |
| m_max | 3.0 | Mass saturation cap |
| B | 32 | Mass bucket count for DP. Module default is 8; paper experiments override to 32. |
| α_budget | 1.25 | Hop-budget multiplier over shortest path |
| d_λ | 0.9 | Per-step load decay |
| d_θ | 0.999 | Per-step loss-snapshot decay |

## Status

This is a preprint draft. The algorithm and its validation are
considered stable; the paper draft is feature-complete through the
Results section, with Discussion and full Related Work pending. See
[`docs/AUDIT_LOG.md`](docs/AUDIT_LOG.md) for the audit history.

## License

MIT License -- see [`LICENSE`](LICENSE) for details.

## Citation

If you use this work, please cite the Zenodo release:

```bibtex
@software{lopez2026emmet,
  author       = {Lopez, Carlos},
  title        = {EMMET: Effective-Mass Memory Edge Transport},
  year         = 2026,
  publisher    = {Zenodo},
  version      = {v1.0-preprint},
  doi          = {10.5281/zenodo.TBD},
  url          = {https://github.com/Carloscodix/EMMET}
}
```

An arXiv preprint with extended discussion is in preparation; this
README will be updated with the arXiv identifier when available.

---

*EMMET started as a Sunday-afternoon question — what if a ping packet
were a physical particle? — and one thing led to another.*
