# EMMET: Effective-Mass Memory Edge Transport

[![DOI](https://zenodo.org/badge/1227928743.svg)](https://doi.org/10.5281/zenodo.20128310)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> *A ping packet, treated as a classical particle, turned out to be less
> interesting as a router — and far more interesting as an instrument.
> With a hat-tip to Dr. Emmett Brown.*

---

## What this is

EMMET began as a question: **how far does classical physics get you in
network load balancing, on its own?** Packets are treated as particles
descending a potential field; classical force laws — a Newton-III loss
reaction, an Archimedean buoyancy, a Pascalian pressure diffusion, a
Hookean spring — are candidate routing terms sharing one search substrate
and nothing else.

The answer turned out to be worth more than the router. Used as
*independent instruments* on a bench of fifteen topologies (grids,
small-world, scale-free, and the real GEANT and Abilene backbones), the
physics cores uncovered **two empirical laws and a taxonomy** about when
the choice of load-balancing mechanism matters at all.

Every quantitative claim below maps to a script and a JSON in this
repository. Nothing is reported that was not stress-tested first.

## The five findings

**1. A load-distribution attractor.** All congestion-aware rules produce
near-identical per-edge load distributions (cosine 0.979 between physics
cores vs 0.867 for blind ECMP; Wilcoxon p = 1e-4 on two independent
metrics). Topology and demand fix most of the outcome; any sensible rule
descends into the same basin.
`experiments/attractor_full.py` -> `data/attractor_full.json`

**2. Congestion *causes* mechanism divergence (shown by intervention).**
Scaling link capacities within fixed topologies — same graph, same demand,
one knob — divergence between mechanisms tracks the drop rate inside every
graph (Spearman +0.77 to +1.00). A squeezed scale-free graph diverges 21x;
a relieved backbone converges 8x. Divergence lives in the *contested band*
between free flow and gridlock.
`experiments/causal_capacity_sweep.py` -> `data/causal_sweep.json`

**3. Structure sets the ceiling.** The bench's most congested graph (the
real Abilene, drop rate 0.22) shows unremarkable divergence: with four
cycles there is no room to express it. Relieving it traces the same
inverted-U as every other graph — at one third the amplitude. Congestion
dictates the *shape* of the divergence curve; structure dictates its
*amplitude*. The two factors dissociate cleanly: a structural ratio
(tube/sp) predicts the *gains* of congestion-aware rerouting (partial
r = +0.59), congestion predicts how much the *mechanism's identity*
matters (partial r = +0.92).
`experiments/abilene_relief_sweep.py`, `experiments/partial_perf.py`,
`experiments/divergence_vs_congestion.py`

**4. The validated core: gradient + anticipatory threshold.** A force that
engages *before* loss, above a density threshold, beats the bare substrate
on **15/15 topologies in every regime** (p <= 1e-4), across a 14/14
parameter plateau, for two functional forms (quadratic buoyancy, linear
spring). At matched thresholds the forms tie: the active ingredient is the
threshold, not the curvature. The reactive scar of our own earlier work
does **not** replicate on the modern bench — a verdict our re-audit
inverted, reported in full.
`experiments/ablation_redux.py`, `experiments/sensitivity_sweep.py`,
`experiments/hooke_quick.py`

**5. The temporal channel.** On a non-stationary bench (links failing in
episodes, healthy in between), the retired Newton-III scar returns to beat
every memoryless core *including the stationary champions* (p <= 1e-3),
identifying flaky edges with precision 0.69-0.80 where load statistics
reach 0.20. Each physics owns an information channel: **threshold = the
nonlinear present, Pascal = space, Newton = time.** The regime decides
which channel pays.
`experiments/newton_redemption.py` -> `data/newton_redemption.json`

**The boundary, stated plainly:** in saturation (real Abilene, >20%
drops) no physical core reaches TOST equivalence with the engineered
balancers CONGA and DRILL at any margin. Engineering matters exactly where
the laws say it must.
`experiments/equivalence_strict.py` -> `data/equivalence_strict_*.json`

## The router that survived

```text
phi(u,v) = alpha * latency(u,v)
         + beta  * load(u,v) / capacity(u,v)      # substrate: the gradient
         + g * max(0, rho(u,v) - rho0)^p          # anticipatory threshold (p = 1 or 2)
       [ + gamma * scar(u,v) ]                    # temporal term: add on infrastructure
                                                  # known to flap, half-life matched
                                                  # to the failure timescale
```

Local decisions only: no central controller, no per-flow state, no
precomputed path tables. Statistically equivalent (TOST, delta = 2pp) to
CONGA (K=16) and DRILL on 9-12 of 15 topologies — the equivalences
concentrating exactly where the attractor predicts.

## Self-correction record

The inversions are part of the result, not painted over:

| What we believed | What the audit found |
|---|---|
| Physics beats CONGA on grids | Artifact of CONGA at K=4; corrected to K=16/32 |
| Keep the scar, drop the buoyancy (original ablation) | Inverted on the modern bench: buoyancy 15/15, scar retired |
| A min-cut theory of the attractor | Predicted the wrong sign; retracted |
| Attractor cosine 0.992 | An experiment starved the scar field; fixed, re-run: 0.979, p improved |
| 15-topology bench | The harness loaded GEANT twice under the "Abilene" label; fixed, 15 genuine |
| The scar is dead | Mis-calibrated (half-life > simulation) and benched in the wrong regime; redeemed on the flaky bench |

Full trail in [`docs/AUDIT_LOG.md`](docs/AUDIT_LOG.md) and the commit
history.

## Repository map

```text
experiments/   every experiment as a standalone script (python3 experiments/X.py)
data/          raw per-seed JSONs behind every number in the paper
paper/         LaTeX sources (paper_v5.tex = current)
docs/          audit log, development notes
archive/       historical material
```

## Reproduce

```bash
pip install -r requirements.txt      # networkx, numpy, scipy
python3 experiments/attractor_full.py        # ~10 min
python3 experiments/ablation_redux.py        # ~8 min
python3 experiments/causal_capacity_sweep.py # ~6 min
python3 experiments/newton_redemption.py     # ~8 min
```

Exact commands, runtimes and expected outputs for every claim:
[`REPRODUCIBILITY.md`](REPRODUCIBILITY.md). Claim-to-data mapping:
[`RESULTS_MANIFEST.md`](RESULTS_MANIFEST.md).

## Paper

*When Does the Router Matter? A Two-Factor Law and a Structural Attractor
in Graph Load Balancing, Found Through Classical-Physics Heuristics.*
LaTeX sources in [`paper/`](paper/). Preprint: arXiv link upcoming.

## Cite

See [`CITATION.cff`](CITATION.cff).

## License

MIT.
