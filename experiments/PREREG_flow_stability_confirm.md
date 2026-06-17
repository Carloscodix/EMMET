# PRE-REGISTRATION (CONFIRMATORY): Flow stability, the right axis
## Date: 2026-06-17 (committed BEFORE running on fresh seeds)

## Why a second pre-registration
The first prereg predicted the core more stable than DRILL. That FAILED: DRILL
with m=2 is not the per-packet reshuffler I assumed. The exploratory run (seeds
0-4) instead showed the core far more stable than CONGA where it loses on drop
(LOW path_change_rate: core 0.584 vs CONGA 0.830, all 7 topos). That finding is
post-hoc -- HARKing unless confirmed. This pre-commits the corrected hypothesis
and test, on FRESH seeds (100-119) never used in exploration.

## The corrected, pre-committed hypothesis
H: In LOW tube/sp topologies (where the core loses to CONGA on drop), the core's
flow path_change_rate is LOWER than CONGA's. Pre-committed threshold:
CONGA - core >= 0.15 absolute in the band mean, AND core more stable than CONGA
in at least 6 of 7 LOW topos.

## Secondary, also pre-committed
S1: The gap shrinks in the HIGH band -- with slack all routers reshuffle, so
    core-vs-CONGA difference is smaller than in LOW (stability is a property of
    constrained topology, same place the attractor pins behaviour).
S2: Axis ORTHOGONAL to drop: in LOW the core loses on drop but wins on
    stability; report both, a trade-off, not a clean win.

## Method (frozen before running)
- Seeds: 100..119 (20 fresh; exploration used 0..4).
- Same metric (path_change_rate), engine, topologies (LOW/HIGH lists).
- Positive control (diamond) runs first; if it fails, voided.

## Falsification / honesty
- If CONGA - core < 0.15 in LOW, or core wins in < 6/7 LOW topos: effect did not
  confirm at pre-committed strength. Report the weaker truth.
- If HIGH-band contrast (S1) fails: stability is not specific to constrained
  topology; drop the attractor connection and say so.
- Fresh seeds replace exploratory numbers in the paper. No mixing seeds.
