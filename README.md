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
small-world, scale-free, and the real GEANT and Abilene backbones), the physics cores uncovered **two empirical laws, a channel taxonomy, and a
measured deployment envelope** for when the choice of load-balancing
mechanism matters at all.

Every quantitative claim below maps to a script and a JSON in this
repository. Nothing is reported that was not stress-tested first.

## The six findings

**1. A load-distribution attractor.** All congestion-aware rules produce
near-identical per-edge load distributions (cosine 0.979 between physics
cores vs 0.867 for blind ECMP; Wilcoxon p = 1e-4 on two independent
metrics). Topology and demand fix most of the outcome; any sensible rule
descends into the same basin. The attractor now has a geometric lemma
(the physics-vs-blind cosine equals the cut-pinned fraction f, verified
to <0.01) and a structure-only derivation of f predicting the measured
similarity (Spearman +0.86).
`experiments/attractor_full.py`, `experiments/attractor_pinned.py`,
`experiments/attractor_theorem.py` -> `data/attractor_full.json`

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
matters (partial r = +0.92). The structural law holds out of sample on
18 unseen SNDlib backbones (r = 0.85), survives shaking the traffic bench
(7/7 variants), and beats five standard graph predictors.
`experiments/abilene_relief_sweep.py`, `experiments/partial_perf.py`,
`experiments/bench_a_v3.py`, `experiments/bench_b.py`, `experiments/bench_g.py`

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

**6. The deployment assumptions, priced.** The two most-cited limitations
(idealized global state; flow-level granularity) converted into
measurements. Routing on a load view refreshed every T ticks degrades
*gracefully*: +0.44pp at half telemetry frequency, +2.5pp at one fifth,
+7.7pp at one twentieth -- monotone, and with **no resonance** (oscillation
ratio <= 1.29 across the sweep: stale state makes the core blind, not
unstable; the predicted oscillatory failure mode did not appear). Decision
cost in a common substrate: 0.07-2.3 ms per *flow*, ~10x cheaper than
evaluating CONGA's K=16 catalogue, 5-26x dearer than DRILL's local
sampling. Flow-level bursts open +0.59pp for DRILL (its territory,
quantified at half a point); 13/15 topologies stay within the 2pp margin. The spatial axis, also measured: with true load visible only within k hops (zero beyond), k=1 recovers 36% of the blind-to-global gap, k=2 63%, k=3 77% -- at three hops the core sits +1.75pp from the global view, inside the equivalence margin. The physics needs a neighbourhood, not a god's eye.
`experiments/stale_state.py`, `experiments/cpu_bench.py`,
`experiments/bursty_bench.py` -> `data/{stale_state,cpu_bench,bursty_bench}.json`

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
| Staleness would cost <0.5pp at T=20 (our pre-registered guess) | Missed badly: +7.7pp, reported as-is; the resonance a reviewer predicted did not appear either -- stale state blinds, it does not destabilize |

Full trail in [`docs/AUDIT_LOG.md`](docs/AUDIT_LOG.md) and the commit
history.

## Repository map

```text
experiments/   every experiment as a standalone script (python3 experiments/X.py)
data/          raw per-seed JSONs behind every number in the paper
paper/         LaTeX sources (paper_v5.tex = current master, v6 draft)
docs/          audit log
```

## Reproduce

```bash
pip install -r requirements.txt      # networkx, numpy, scipy
python3 experiments/attractor_full.py        # ~10 min
python3 experiments/ablation_redux.py        # ~8 min
python3 experiments/causal_capacity_sweep.py # ~6 min
python3 experiments/newton_redemption.py     # ~8 min
```

The deployment-envelope battery (v6):

```bash
python3 experiments/stale_state.py           # ~3 min  staleness sweep
python3 experiments/khop_visibility.py       # ~4 min  k-hop visibility
python3 experiments/bursty_bench.py          # ~5 min  bursty arrivals
python3 experiments/cpu_bench.py             # ~1 min  per-decision cost
python3 experiments/jain_fairness.py         # ~8 min  fairness / attractor
```

The validation battery (out-of-sample, robustness, attractor theory):

```bash
python3 experiments/bench_a_v3.py            # ~5 min  law holds on 18 SNDlib backbones (r=0.85)
python3 experiments/bench_b.py               # ~15 min harness-sensitivity (7/7 variants hold)
python3 experiments/bench_g.py               # ~1 min  tube/sp beats 5 standard predictors
python3 experiments/bench_h.py               # ~6 min  electrical baseline (negative, congestion-specific)
python3 experiments/attractor_pinned.py      # <1 min  pinned-fraction prediction (r=-0.94)
python3 experiments/attractor_lemma_check.py # <1 min  geometric lemma cos=f
python3 experiments/attractor_theorem.py     # <1 min  pinned component from structure alone
python3 experiments/attractor_form.py        # <1 min  hyperbolic functional form of f
```


The code-audit suite (harness integrity):

```bash
python3 experiments/negative_control.py      # ~8 min  identical-routers control
```

Method, scope and findings of the code audit: [`docs/CODE_AUDIT.md`](docs/CODE_AUDIT.md).

Exact commands, runtimes and expected outputs for every claim:
[`REPRODUCIBILITY.md`](REPRODUCIBILITY.md). Claim-to-data mapping:
[`RESULTS_MANIFEST.md`](RESULTS_MANIFEST.md).

## Paper

*When Does the Router Matter? A Two-Factor Law and a Structural Attractor
in Graph Load Balancing, Found Through Classical-Physics Heuristics.*
Twenty-nine pages: six findings, a complexity analysis, the attractor
theory (a geometric lemma plus a structure-only derivation of its
strength), out-of-sample and harness-robustness validation, a formal
appendix on the tube/sp metric, and an operator decision diagram
distilled from the law. LaTeX sources in [`paper/`](paper/) (master:
`paper_v5.tex`). Preprint: arXiv link upcoming.

## Cite

See [`CITATION.cff`](CITATION.cff).

## License

MIT.
