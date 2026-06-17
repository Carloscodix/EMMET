# PRE-REGISTRATION: Where the law lives along the load axis (gap A)
## Date: 2026-06-17 (committed BEFORE running)

## The question (the canyon, finished)
The tube/sp law predicts WHEN the router matters. Gap A asks WHERE on the
traffic-pressure axis the law has signal at all. A probe (cost266, sweeping
capacity) confirms three regimes reachable with the faithful engine: drop-zero
(high cap, 0 losses), a middle band, and collapse (low cap).

## Hypothesis (bell-shaped law strength)
The law's strength -- correlation between tube/sp and the core's loss advantage
over CONGA across topologies -- peaks in the middle band and falls at both ends:
- DROP-ZERO: all routers tie at ~0 loss; no advantage to correlate -> r ~ 0.
- COLLAPSE: all routers lose heavily; router cannot rescue an overrun net -> r
  weakens.
- MIDDLE: congestion exists AND room to route around it -> r strongest.

## Pre-committed predictions
P1: Pearson r(tube/sp, advantage) in MIDDLE band >= +0.45 (matches the
    +0.59/+0.77 at the bench operating point).
P2: |r_dropzero| < |r_middle| - 0.20 (law mutes where nobody loses).
P3: |r_collapse| < |r_middle| - 0.15 (law weakens where everybody loses).
P4 (shape): r_middle is the maximum of the three bands.

## Positive control
The MIDDLE band IS the control: it must reproduce the known law (r >= +0.45).
If it does not, the pressure parameterization is broken and the experiment is
VOIDED before reading the extremes (yesterday's lesson).
