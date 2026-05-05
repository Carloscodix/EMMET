# EMMET: Energy-Minimizing Multi-dimensional Edge-based Traversal

> *"What if a network packet behaved like a physical particle?"*

**EMMET** is an adaptive routing algorithm grounded in classical mechanics
and thermodynamics. Network packets navigate a composite potential field
combining distance, congestion, and historical loss — avoiding high-energy
regions the way a physical particle avoids potential barriers.

---

## Core Idea

At each hop, the packet moves toward the neighbor with minimum potential:

```
P(u, v) = α · dist(v, dst) + β_eff · congestion(u,v) + γ · loss_snapshot(u,v)
```

Where:
- `dist(v, dst)` — shortest path length from neighbor to destination
- `congestion(u,v)` — current load / link capacity
- `loss_snapshot(u,v)` — historical loss with thermal decay
- `α, γ` — fixed weights
- `β_eff = β_base · (1 + θ · ⟨load/capacity⟩)` — adaptive congestion thermostat

Heat dissipates over time: `loss_snapshot(u,v) ← decay · loss_snapshot(u,v)`
with half-life of 100 steps. An ε-greedy exploration term breaks rigidity.

### Physical Analogies

| Network concept     | Physical analogue              |
|---------------------|--------------------------------|
| Congested link      | Friction / resistance          |
| Packet loss         | Thermal dissipation            |
| TTL expiry          | Energy depletion               |
| Routing decision    | Gradient descent on a field    |
| Dead end            | Topological local minimum      |
| Loss snapshot       | Persistent thermal memory      |
| Half-life decay     | Heat dissipation               |
| ε-greedy            | Stochastic exploration         |
| Adaptive β          | Global thermostat              |
| Visited set         | Infinite inertia               |

---

## Strategies Compared

The full battery compares six strategies sharing identical traffic per seed:

| Strategy        | Description                                              |
|-----------------|----------------------------------------------------------|
| SP              | Dijkstra on latency                                      |
| LASP            | Dijkstra on latency · (1 + load/capacity)                |
| EMMET cold      | Greedy potential field, no snapshot, fixed β             |
| EMMET thermal   | + warm-up snapshot + half-life decay + ε-greedy          |
| EMMET adaptive  | Greedy + adaptive β (no snapshot)                        |
| **EMMET full**  | **adaptive β + warm-up snapshot + decay + ε-greedy**     |

---

## Key Results

Full battery: 28,800 simulations across 3 batteries (canonical 4-strategy + lookahead h=2 + adaptive-β; 100 seeds for n=20/50/real, 50 seeds for n=100),
synthetic Erdős–Rényi (n=20, 50, 100) and real Internet topologies
(Abilene, GEANT) from the Internet Topology Zoo.

### Loss reduction vs LASP (EMMET full)

| Scenario          | LASP loss | EMMET full loss | Reduction |
|-------------------|-----------|-----------------|-----------|
| ER ρ=0.05 (n=20)  | 11.53     | 5.15            | **−55.3%** |
| ER ρ=0.10 (n=20)  | 35.14     | 12.30           | **−65.0%** |
| ER ρ=0.05 (n=50)  | 11.70     | 4.50            | **−61.5%** |
| Abilene           | 46.37     | 40.65           | **−12.3%** |
| GEANT             | 11.68     | 5.31            | **−54.5%** |

### Phase Transition

Density sweep reveals a critical threshold ρc ∈ [0.15, 0.30] below which
the potential field collapses into topological dead ends. Below ρc, EMMET
exhibits a clear loss-versus-latency trade-off: EMMET reduces losses
by 54–67% but at a latency cost of 3–13%. The two algorithms occupy
distinct corners of the trade-off space.

### Adaptive β + Thermal: Synergy, Not Substitution

Comparison of mechanism combinations:

| Mechanism        | Loss vs LASP (GEANT) | Loss vs LASP (Abilene) |
|------------------|----------------------|------------------------|
| Cold (none)      | −4.9%                | −4.3%                  |
| + Thermal        | −48.2%               | −5.8%                  |
| + Adaptive β     | −14.6%               | −8.1%                  |
| + Both (full)    | **−54.5%**           | **−12.3%**             |

Adaptive β and thermal memory **complement each other**. Adding both
yields more than either alone. This contrasts with lookahead h=2 (tested
separately), which **substitutes** for thermal memory — combining them
degrades performance.

### Beta Sweet Spot

Beta sweep (with fixed β) identifies an optimal point at β = 3.5–4.0 with
zero packet loss at minimum latency cost. Above β = 4.0, **field
saturation** emerges — excessive congestion aversion forces packets onto
long paths that congest previously uncongested links.

---

## Repository Structure

```
EMMET/
  src/
    emmet_v1.py                       # Reference implementation
  experiments/
    emmet_battery.py                  # 4-strategy battery (canonical)
    emmet_beta_adaptive.py            # 6-strategy adaptive battery
    emmet_lookahead.py                # Lookahead h=2 experiment
    emmet_pareto.py                   # Pareto frontier analysis
    emmet_plot_battery.py             # Battery figures
    emmet_plot_full.py                # Full-stack figures (final)
    legacy/                           # Old buggy variants kept for history
  notebooks/                          # Reproduction figures
  paper/
    emmet_paper.md                    # Paper draft
    emmet_full_*.png                  # Final figures
  data/
    topologies/                       # Abilene + GEANT graphml
    *_summary.json                    # Per-battery summaries
    *_raw_results.json                # Per-seed raw data
```

---

## Quickstart

```bash
pip install -r requirements.txt

# Single demonstration run
python3 src/emmet_v1.py

# Full battery (28,800 simulations across 6 strategies, ~6 min on 28 cores)
python3 experiments/emmet_beta_adaptive.py
```

---

## Roadmap

- [x] Core algorithm with physics-inspired TTL
- [x] Statistical validation (100 runs per scenario)
- [x] Density sweep — phase transition at ρc ∈ [0.15, 0.30]
- [x] Beta sweep — sweet spot β=3.5–4.0, field saturation
- [x] Momentum analysis — visited set = implicit infinite inertia
- [x] Real Internet topologies — Abilene + GEANT
- [x] ECMP baseline — degenerates to SP without equal-cost paths
- [x] LASP baseline — congestion-aware Dijkstra
- [x] Warm-up phase + thermal decay (read-only snapshot)
- [x] ε-greedy exploration (real, not constant offset)
- [x] Lookahead h=2 — found to substitute for thermal memory
- [x] Adaptive β thermostat — synergistic with thermal memory
- [x] Pareto frontier analysis
- [x] Three independent code audits passed
- [ ] Paper draft (in progress)
- [ ] arXiv preprint

---

## Honest Limitations

- Tested on N ∈ {20, 50, 100} synthetic nodes plus real topologies
  (Abilene N=11, GEANT N=40). Scaling beyond N=100 not yet measured
- Thermal warm-up requires sufficient topology size; in very small
  topologies (Abilene, 11 nodes) the effect is modest
- All results from simulation; no real-world deployment tested
- Lookahead h=2 is computationally expensive on n=100 dense topologies
- ECMP is a poor baseline with real-valued link costs (degenerates to SP);
  alternative load-balancing baselines deferred to future work

---

## Prior Art & Positioning

- **Density-based anycast** (Lenders et al. 2008) — closest prior art;
  documents local minima qualitatively but does not characterize a
  critical density for composite three-term potential
- **Gravity routing** (Chinese Physics B, 2015) — global attraction
  rather than local per-edge potential
- **Backpressure routing** (Tassiulas & Ephremides, 1992) — queue-based,
  throughput-optimal but destroys latency
- **Physarum-inspired routing** (PLOS ONE, 2014) — biological metaphor

**Contribution:** Empirical characterization of a critical density
threshold for composite potential-field routing with thermal dynamics
(warm-up snapshot + half-life decay + ε-greedy exploration + adaptive β
thermostat). Identification of the loss-versus-latency trade-off, field saturation
effect, and synergy/substitution relationships between mechanisms.
Validation on real Internet topologies with 100 seeds per scenario.

---

## Author

Carlos López — independent researcher
*"A Sunday afternoon in the village, a question about friction in ping packets,
and one thing led to another."*

---

## License

MIT — open science, open code.
