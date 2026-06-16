# PRE-REGISTRATION: Bench A with REAL SNDlib demand matrices
## Date: 2026-06-16 (committed BEFORE running the experiment)

## Motivation
bench_a_v3 generalizes the two-factor law across TOPOLOGY but feeds every
SNDlib graph the same SYNTHETIC harness. A reviewer flagged this is
topological generalization, not demand generalization. The parser CAN read the
real demand matrix shipped with each instance, but the bench discarded it
(G0, _ = SND.load). We now run the law with REAL demand.

## What changes
Same graphs, same capacity/latency scheme. Demand: each pair weighted by the
REAL SNDlib volume instead of uniform. gen_flows already samples proportional
to real demand.

## PRE-COMMITTED PREDICTIONS
P1. tube/sp -> loss-reduction stays POSITIVE. Pearson r >= +0.45 (in-sample
    +0.59; allow attenuation because real demand is lumpier).
P2. Direction preserved per-topology. Spearman rho >= +0.50.
P3. POSITIVE CONTROL first: same real-demand pipeline on bench topos must
    reproduce the in-sample sign before any SNDlib number counts.

## Falsification
If r < +0.45 OR Spearman < +0.50 OR sign flips on a majority: the law is
demand-fragile. Report THAT honestly -- generalizes topologically but not to
real demand. If control fails: experiment voided, instrument repaired first.

## Honesty clause
Whatever comes out goes in the paper. A negative is a real finding about the
scope of the law, not a failure to hide.
