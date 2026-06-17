# PRE-REGISTRATION: Flow stability as the hidden axis (gap B)
## Date: 2026-06-17 (committed BEFORE instrumenting or running)

## The question (the coyote and the canyon)
In LOW tube/sp topologies the physical core LOSES to CONGA on drop rate
(nobel-us -24.7%, atlanta, polska, zib54 in bench_a_realdemand_v2). Gap-B
hypothesis: the core may lose on packet loss yet WIN on flow stability -- it
keeps a flow on one path while DRILL/CONGA reshuffle per packet -- and the
current simulator cannot see this because it only counts losses.

## What we instrument (falsifiable metric)
Per burst (maximal run of packets to same (src,dst) between gaps = one flow),
count route changes between consecutive packets of that flow.
  path_change_rate = route changes within flows / intra-flow transitions
Stable router keeps the path; unstable one flips it. Analogue of TCP reorder.

## PRE-COMMITTED PREDICTIONS
P1 (interesting): in LOW tube/sp (tube/sp < 3.5, where core loses on drop),
   core path_change_rate LOWER than DRILL by >= 0.10 absolute. Core trades loss
   for stability.
P2: DRILL has HIGHEST path_change_rate of the three (identity check on metric).
P3 (POSITIVE CONTROL, FIRST): metric must separate a stable router from an
   unstable one on a trivial diamond. Static-shortest ~0, random-next-hop high.
   Else instrument broken, voided.

## Falsification / honesty
- If P1 fails (core NOT more stable where it loses on drop): no hidden axis on
  the loss-region topologies. We report the core simply loses there. Honest.
- If P2 fails: metric suspect; fix before interpreting.
- If P3 fails: voided, repair first (yesterday's lesson).
- Whatever comes out goes in the paper. Gap-closing, not cheerleading.

## Confound (addressed in analysis, not assumed away)
A route change within a burst can be (a) mechanism instability (bad) or (b)
correct reaction to self-induced congestion (good). We also report
path_change_rate in the HIGH tube/sp region as contrast: if the core is stable
everywhere and DRILL unstable everywhere, the axis is about mechanism, not
congestion reaction. No victory claimed from stability alone without contrast.
