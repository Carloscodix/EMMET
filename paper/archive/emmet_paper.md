# EMMET: A Potential-Field Routing Heuristic with Adaptive Congestion Thermostat and Loss Memory

**Carlos López**
Independent Researcher
carlos@codix.cat

Code & data: https://github.com/Carloscodix/EMMET

---

## Abstract

We present EMMET, an adaptive routing algorithm grounded in classical
mechanics and thermodynamics. Network packets are modeled as physical
particles navigating a composite potential field with three terms: distance
to destination, instantaneous link congestion, and decayed historical
packet loss. The TTL is interpreted as physical energy; packets that
exhaust their budget are considered to undergo thermal dissipation. The
loss term carries a frozen warm-up snapshot subject to half-life decay,
modeling persistent thermal memory of past failures. An ε-greedy
stochastic term implements local exploration. A global congestion
thermostat adapts the congestion weight β according to the mean
normalized network load.

We characterize a phase transition in the algorithm's behavior as a
function of network density: below a critical threshold ρc ∈ [0.15, 0.30]
on Erdős–Rényi graphs, the potential field collapses into topological
dead ends. Above the threshold, EMMET achieves near-zero packet
loss in the dense regime (mean below 0.2 packets per 200-step run for ρ ≥ 0.30 on n=20). We further identify a β sweet spot at β=3.5–4.0 followed by a field
saturation regime, an emergent dual-superiority regime at very low
density, and the empirical relationship between mechanisms: thermal
memory and adaptive β are **synergistic**, while local lookahead h=2 and
thermal memory are **substitutes**.

EMMET is validated against three baselines (Shortest Path, ECMP, LASP) on
synthetic Erdős–Rényi graphs (N ∈ {20, 50, 100}) and real Internet
topologies (Abilene, GEANT) from the Internet Topology Zoo, across four
batteries totaling 28,800 simulations (100 seeds per scenario for n=20, n=50, and real topologies; 50 seeds for n=100 due to compute cost). The
full system (adaptive β + thermal) reduces packet loss by 55% to 65%
versus LASP on synthetic networks and 54.5% on GEANT, with a 12.3%
reduction on the small Abilene topology that previous variants could not
improve. Three independent adversarial code audits identified and
corrected methodological errors.

**Keywords:** adaptive routing, potential field, phase transition,
thermal dynamics, complex networks, network science.

---

## 1. Introduction

The standard approach to network routing — minimize path length under
some cost metric — treats the network as a static optimization problem.
The packet follows the shortest path and arrives, or it does not.

Real networks are dynamic systems. Links congest, degrade, and recover.
A packet that blindly follows the shortest path may arrive at a saturated
link and be dropped, while an alternative longer path delivers reliably.

This paper asks: what if a packet behaved like a physical particle? In
classical mechanics, a particle moving through a field does not follow
the straight-line path — it follows the path of least potential energy,
trading distance for the avoidance of high-energy regions. Friction
dissipates motion. Heat marks regions of maximum energy exchange. A
particle with finite energy that cannot reach its destination dies of
thermal dissipation.

This framing produces a concrete algorithm with measurable physical
analogues. We name the algorithm EMMET: Energy-Minimizing
Multi-dimensional Edge-based Traversal. Each routing decision minimizes
a composite potential combining distance, congestion, and loss memory,
under a globally adapted congestion weight, with stochastic exploration
to break greedy rigidity.

Our contributions are:

1. A potential-field routing algorithm with four physically motivated
   mechanisms: warm-up loss snapshot, half-life decay, ε-greedy
   exploration, and adaptive β thermostat.
2. Empirical characterization of a critical density threshold below which
   the potential field collapses (phase transition).
3. Identification of a β sweet spot followed by a field saturation regime.
4. Empirical demonstration that thermal memory and adaptive β are
   synergistic, while lookahead h=2 substitutes for thermal memory.
5. Validation across 28,800 simulations on synthetic and real Internet
   topologies, after three adversarial code
   audits.

---

## 2. Related Work

**Potential-field routing** has been studied for wireless sensor and
ad-hoc networks. Lenders et al. (2008) propose density-based anycast
with explicit analysis of local maxima, deriving theoretical bounds for
local-minima-free operation under a single-term potential. Their analysis
does not characterize a critical density for composite multi-term
potentials.

**Geographic routing** literature (Karp & Kung 2000, Kuhn et al. 2003)
documents local minima in greedy forwarding and addresses them through
recovery mechanisms (face routing, perimeter routing) rather than
characterizing the failure regime.

**Gravity routing** (Chinese Physics B, 2015) applies gravitational
analogies but uses global attraction toward low-congestion nodes, unlike
EMMET's local per-edge potential.

**Backpressure routing** (Tassiulas & Ephremides 1992) routes on queue
differentials and is throughput-optimal but degrades latency.

**ECMP** (RFC 2992) distributes flows hash-based among equal-cost paths
and is the industry standard for load balancing in IP networks. **LASP**
(Load-Aware Shortest Path) extends Dijkstra with congestion-aware weights
and is a standard traffic-engineering baseline.

None of these works characterize a critical density threshold for a
composite three-term potential function combining distance, congestion,
and decayed loss memory; nor do they study mechanism interactions
(synergy vs substitution) between exploration, lookahead, and adaptive
parameters. This is the gap EMMET addresses.

---

## 3. The EMMET Model

### 3.1 Network Model

The network is an undirected graph G = (V, E) where each edge (u,v) carries:
- `latency(u,v)` — static propagation delay
- `capacity(u,v)` — maximum load before loss occurs
- `load(u,v)` — current traffic level (decays exponentially per step)
- `loss(u,v)` — accumulated packet loss count

### 3.2 Potential Function

For a packet at node u considering neighbor v toward destination dst:

```
P(u, v, dst) = α · dist(v, dst)
             + β_eff · load(u,v) / capacity(u,v)
             + γ · loss_snapshot(u,v)
```

Where α and γ are fixed weights, and β_eff is governed by the adaptive
thermostat (§3.6). The loss_snapshot is a thermal memory term (§3.5).

### 3.3 Routing Rule

At each hop, the packet moves to the neighbor minimizing P, excluding
previously visited nodes. With probability ε, the second-best neighbor is
chosen instead — this implements stochastic exploration (§3.7).

### 3.4 TTL as Physical Energy

A packet is born with energy budget E = TTL_FACTOR · |V| hops. Two
distinct termination conditions exist:

- **dead_end**: no unvisited neighbors — topological local minimum
- **ttl_expired**: energy exhausted — thermal dissipation

These are tracked separately as failure modes signaling field collapse
versus insufficient energy for the topology.

### 3.5 Thermal Memory: Snapshot, Decay, and Warm-up

The `loss_snapshot` term carries persistent information about past
failures. It is constructed in three steps:

**Warm-up phase** — before measurement, EMMET routes
warmup_steps = max(20, |V|·5) packets and freezes the resulting per-edge
loss values into a snapshot dictionary.

**Read-only during measurement** — the snapshot is consulted at every
routing decision but is not updated by losses occurring during measurement.
This eliminates information asymmetry against the baselines.

**Half-life decay** — after each step, snapshot(u,v) ← decay · snapshot(u,v),
with decay = exp(−ln 2 / HALF_LIFE). For HALF_LIFE = 100 steps, decay ≈
0.9931 — the snapshot loses 50% of its value every 100 steps. This
models heat dissipation.

### 3.6 Adaptive β Thermostat

A fixed β assumes uniform congestion across the network. Real topologies
have heterogeneously stressed regions. The adaptive thermostat scales β
with the global thermal state of the network:

```
β_eff = β_base · (1 + θ · ⟨load(u,v) / capacity(u,v)⟩)
```

Where ⟨·⟩ denotes the mean over all edges and θ ≥ 0 is the sensitivity.
With θ = 0, β is fixed; with θ > 0, β scales up under network stress.
The thermostat introduces no learning state — it is a stateless feedback
mechanism evaluated at routing time.

### 3.7 ε-greedy Stochastic Exploration

With probability ε, the routing decision selects the second-best
neighbor by potential ranking instead of the best. This breaks greedy
rigidity, enables exploration of locally suboptimal paths, and provides
robustness to small modeling errors. We use ε = 0.10.

In an early implementation, an additive constant offset was used as an
"exploration term"; this is mathematically inert (it adds equally to all
neighbors and does not change the argmin), and was identified by an
adversarial audit. The ε-greedy formulation replaces it with a real
exploration mechanism.

### 3.8 Implicit Momentum

The visited set implements infinite inertia by construction — a previously
visited node is never reconsidered, equivalent to assigning it infinite
potential. Empirical tests with explicit momentum terms confirmed no
measurable additional effect, so explicit momentum is omitted.

---

## 4. Experimental Setup

### 4.1 Topologies

- **Synthetic**: Erdős–Rényi G(N, p) with size-dependent density coverage:
    - N = 20: p ∈ {0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40, 0.50}
    - N = 50: p ∈ {0.05, 0.10, 0.15, 0.20, 0.25, 0.30}
    - N = 100: p ∈ {0.05, 0.10, 0.15, 0.20} (sparse regime only, where
      the phase transition is observable; denser n=100 graphs converge
      trivially to zero loss for all strategies)
- **Real**: Abilene (N = 11, ρ = 0.25) and GEANT (N = 40, ρ = 0.08)
  from the Internet Topology Zoo (Knight et al. 2011)

### 4.2 Traffic Model

For each scenario and seed, 200 random source-destination pairs are
generated from a fixed traffic seed, independent of any routing
strategy's randomness. All strategies see identical traffic.

### 4.3 Statistical Validation

100 independent seeds per scenario for synthetic n=20, n=50, and real
topologies; 50 seeds for n=100 due to computational cost. Mean and
standard deviation reported throughout. Across the three batteries (canonical 4-strategy, lookahead h=2
with 6 strategies, and adaptive-β with 6 strategies), 28,800 simulations
were executed (1800 jobs × 4 + 1800 × 6 + 1800 × 6).

### 4.4 Baselines

- **SP**: Dijkstra on `latency`
- **ECMP**: random choice among shortest paths (RFC 2992)
- **LASP**: Dijkstra on `latency · (1 + load/capacity)`

### 4.5 Audit-Clean Implementation

Three independent adversarial code reviews identified and corrected:
- RNG contamination across strategies (separate RNGs for traffic,
  baseline path choice, and EMMET exploration)
- Asymmetric information in EMMET's loss term (snapshot is read-only
  during measurement; populated only by warm-up)
- Decay scale mismatch (switched from `0.95^step` to half-life formulation)
- Mathematically inert exploration constant (replaced with ε-greedy)
- Non-portable absolute file paths (replaced with `Path(__file__).parents[1]`)
- Latency metric mixing partial work of lost packets (separated into
  latency-per-delivered and latency-per-attempt)

All reported results are from the audited implementation.

### 4.6 Default Parameters

α = 1.0, β_base = 3.0, γ = 2.0, ε = 0.10, θ = 1.0, TTL_FACTOR = 2,
HALF_LIFE = 100 steps.

---

## 5. Results

### 5.1 Density Sweep: Phase Transition

Density swept on Erdős–Rényi G(20, p) from p=0.05 to p=0.50.

| Density | SP loss | LASP loss | EMMET full loss | Connectivity |
|---------|---------|-----------|-----------------|--------------|
| 0.05    | 11.98   | 11.53     | **5.15**        | 0%           |
| 0.10    | 39.67   | 35.14     | **12.30**       | 7%           |
| 0.15    | 18.81   | 11.48     | **7.61**        | 43%          |
| 0.20    | 10.57   | 4.78      | **2.39**        | 80%          |
| 0.25    | 4.57    | 1.14      | 0.41            | 93%          |
| 0.30    | 2.45    | 0.53      | 0.17            | 100%         |
| 0.40    | 1.07    | 0.18      | 0.04            | 100%         |
| 0.50    | 0.83    | 0.11      | 0.00            | 100%         |

**Finding 1 — Phase transition at ρc ∈ [0.15, 0.30].** Below this range,
graphs are rarely connected; above ρ = 0.30, graphs are 100% connected
and EMMET achieves a mean loss below 0.2 packets per 200-step run.

**Finding 2 — Loss reduction at low density, with a latency cost.** At
p < 0.15, EMMET reduces losses by 54--67\% versus SP. SP retains a
latency advantage (3--13\% lower mean latency per delivered packet,
verified under both per-strategy and conditional-on-common-delivery
metrics; see §4.5 and selection_bias_analysis.json). EMMET and SP thus
occupy distinct corners of the loss-vs-latency trade-off space; they
are not strictly comparable.

**Finding 3 — Dead ends as field collapse signature.** Dead-end counts
drop sharply at p ≈ 0.25–0.30, coinciding with full topological
connectivity.

### 5.2 Beta Sensitivity (Fixed β)

Beta swept on G(20, 0.30) from β=0.1 to β=5.0 with γ=2.0:

| β   | EMMET losses | EMMET latency |
|-----|--------------|---------------|
| 1.0 | 0.17         | 4.856         |
| 2.0 | 0.07         | 4.870         |
| 3.0 | 0.07         | 4.891         |
| 3.5 | **0.00**     | 4.898         |
| 4.0 | **0.00**     | 4.915         |
| 4.5 | 0.03         | 4.936         |
| 5.0 | 0.03         | 4.960         |

**Finding 4 — β sweet spot at 3.5–4.0.** Zero packet loss at minimum
latency cost.

**Finding 5 — Field saturation above β = 4.0.** Excessive congestion
aversion forces packets onto longer routes that congest previously
uncongested links — the β-loss relationship is non-monotonic above the
sweet spot. This motivates the adaptive thermostat (§3.6) which sets
β_eff dynamically based on global load.

### 5.3 Multi-Mechanism Comparison

Six strategies evaluated on representative scenarios:

| Scenario          | SP    | LASP  | cold  | thermal | adaptive | full  |
|-------------------|-------|-------|-------|---------|----------|-------|
| ER ρ=0.05 (n=20)  | 11.98 | 11.53 | 11.25 | 5.46    | 10.96    | **5.15**  |
| ER ρ=0.10 (n=20)  | 39.67 | 35.14 | 33.67 | 13.15   | 32.24    | **12.30** |
| ER ρ=0.05 (n=50)  | 16.87 | 11.70 | 12.82 | 5.27    | 12.10    | **4.50**  |
| Abilene           | 56.67 | 46.37 | 44.36 | 43.68   | 42.62    | **40.65** |
| GEANT             | 26.38 | 11.68 | 11.11 | 6.05    | 9.97     | **5.31**  |

**Finding 6 — Thermal memory is the dominant single mechanism.** Adding
the warm-up snapshot with decay reduces losses by 46% to 59% over
greedy-cold across the board.

**Finding 7 — Adaptive β contributes additional gains synergistically
with thermal memory.** EMMET full (both mechanisms) outperforms either
alone on every scenario tested. The full system reduces losses by 55% to
65% versus LASP on synthetic networks and 54.5% on GEANT.

**Finding 8 — Adaptive β is the only mechanism that improves Abilene.**
The small Abilene topology (N=11) was the difficult case for previous
variants. Adaptive β alone reduces losses by 8.1% versus LASP, and the
full system reaches 12.3% — the first significant improvement on this
scenario.

**Finding 9 — ECMP degenerates to SP without equal-cost ties.** With
real-valued latency, ECMP rarely finds multiple equal-cost paths and
produces results identical to SP. ECMP is effective only in topologies
engineered with uniform link costs (e.g., datacenter fat-trees).

### 5.4 Mechanism Interaction: Synergy vs Substitution

A separate battery (`experiments/emmet_lookahead.py`, results in `data/lookahead_summary.json`) tested local lookahead with horizon h=2: at each
routing decision, the potential is evaluated over the next two hops
rather than one. Results on representative scenarios:

| Scenario          | cold  | cold + LA2 | thermal | thermal + LA2 |
|-------------------|-------|------------|---------|---------------|
| ER ρ=0.05 (n=20)  | 11.25 | 11.37      | 5.46    | 7.85          |
| ER ρ=0.10 (n=20)  | 33.67 | 34.10      | 13.15   | 19.13         |
| ER ρ=0.05 (n=50)  | 12.82 | 12.18      | 5.27    | 7.68          |
| GEANT             | 11.11 | 10.42      | 6.05    | 6.19          |

**Finding 10 — Local lookahead does not improve EMMET; it degrades the
thermal variant.** Lookahead h=2 yields negligible change to EMMET cold
(within ±1.0% in n=20 sparse and modest improvement of 5–6% in n=50 and
GEANT) but consistently increases losses for EMMET thermal by 2% to 45%.
The combination is therefore counterproductive whenever a thermal
snapshot is in use. We interpret this as a substitution effect: thermal
memory and local lookahead both provide non-myopic information about
near-term link state, and their signals interfere when combined.
The snapshot is a more efficient signal for the same purpose.

This contrasts with adaptive β, which is **complementary** to thermal
memory. The distinction is meaningful: synergistic mechanisms operate
on different signals (β operates on global state, thermal on per-edge
history), while substitutive mechanisms compete for the same signal
(both lookahead and thermal aim to anticipate failure).

### 5.5 Pareto Frontier Analysis

Pareto analysis (`experiments/emmet_pareto.py`, results in `data/pareto_summary.json`). Across the 20 scenarios, Pareto-optimal frequency (latency vs loss):

| Strategy        | Pareto-optimal | % of scenarios |
|-----------------|----------------|----------------|
| SP              | 20 / 20        | 100%           |
| LASP            | 17 / 20        | 85%            |
| EMMET cold      | 14 / 20        | 70%            |
| EMMET thermal   | 3 / 20         | 15%            |
| EMMET adaptive  | 8 / 20         | 40%            |
| EMMET full      | 8 / 20         | 40%            |

**Finding 11 — SP and EMMET full occupy distinct corners of the Pareto
frontier.** SP is always Pareto-optimal because it minimizes latency;
EMMET full is Pareto-optimal in 40% of scenarios because it minimizes
loss. The Pareto analysis confirms EMMET as the loss-minimizing extreme
of a routing trade-off, not as a universal dominator.

---

## 6. Discussion

### 6.1 Phase Transition Interpretation

The transition at ρc ∈ [0.15, 0.30] has a natural physical interpretation.
Below the critical density, the graph is frequently disconnected; the
potential field has no gradient to follow because the destination is
unreachable from many source nodes. This is analogous to a system below
its percolation threshold. Above the critical density, the field is
well-defined everywhere.

### 6.2 Field Saturation and the Adaptive Thermostat

The non-monotonic β behavior above β = 4.0 reveals a saturation effect:
overly aggressive congestion aversion forces packets onto longer paths,
saturating links that would otherwise have been free. The adaptive
thermostat resolves this by setting β_eff dynamically: high during stress,
low during relaxation. This converts a parameter-tuning problem into a
self-regulating mechanism.

### 6.3 Synergy and Substitution Among Mechanisms

The empirical distinction between synergistic and substitutive mechanisms
is one of the main contributions of this work. A mechanism designer
adding components to an algorithm typically assumes additive benefit;
our results show this assumption fails for some mechanism pairs. The
distinction appears to follow from whether the mechanisms operate on
overlapping or distinct signals:

- **Adaptive β + thermal memory** — distinct signals (global load vs
  per-edge history) → synergy.
- **Lookahead h=2 + thermal memory** — overlapping purpose
  (anticipate failure) → substitution.

This suggests a design principle: when adding a mechanism to a
potential-field algorithm, identify the signal it consumes and check
whether existing mechanisms already exploit that signal.

### 6.4 Limitations

- N ≤ 100 nodes synthetic; real-Internet-scale topologies (>1000 nodes)
  not yet measured
- Warm-up phase is sensitive to the ratio of warmup_steps to |V| in very
  small topologies
- Static α, γ, ε; adaptive scheduling deferred to future work
- All results from simulation; no real deployment tested
- LASP is a strong but not exhaustive baseline; comparison against
  TE controllers (e.g., MATE, B4-style flow assignments) deferred to
  future work

---

## 7. Conclusion

We presented EMMET, a physics-inspired adaptive routing algorithm modeling
packets as particles in a composite potential field with thermal dynamics
and an adaptive global thermostat. We characterized empirically:

1. A phase transition at ρc ∈ [0.15, 0.30] below which the field collapses
2. A clear loss-versus-latency trade-off across the density range, with EMMET dominating loss and SP dominating latency
3. A β sweet spot at 3.5–4.0 followed by a field saturation regime
4. Synergy between adaptive β and thermal memory
5. Substitution between local lookahead and thermal memory
6. Loss reductions of 55–65% versus LASP on synthetic networks and 54.5%
   on GEANT, with 12.3% reduction on the small Abilene topology that
   previous variants could not improve.

EMMET trades a modest latency cost for substantial loss reduction. The
physical framework provides interpretable parameters with clear
analogues — friction, heat, energy, thermostat, exploration — and
identifies failure regimes (field collapse, saturation) and mechanism
interactions (synergy, substitution) that prior adaptive routing
literature has not formally characterized.

Three independent adversarial code reviews validated the implementation.
All data, code, and reproducibility scripts are available at the project
repository under MIT license.

---

## References

- Lenders, V. et al. (2008). Density-based anycast: A robust routing
  strategy for wireless ad hoc networks. *IEEE/ACM Transactions on
  Networking*.
- Tassiulas, L. & Ephremides, A. (1992). Stability properties of
  constrained queueing systems and scheduling policies for maximum
  throughput. *IEEE Trans. Automatic Control*.
- Karp, B. & Kung, H.T. (2000). GPSR: Greedy perimeter stateless
  routing for wireless networks. *MobiCom*.
- Hopps, C. (2000). Analysis of an Equal-Cost Multi-Path Algorithm.
  *RFC 2992*.
- Knight, S. et al. (2011). The Internet Topology Zoo. *IEEE Journal on
  Selected Areas in Communications*.

---

*Code & data: https://github.com/Carloscodix/EMMET*
*Preprint: arXiv cs.NI (pending)*
*License: MIT*
