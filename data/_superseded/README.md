# Superseded data files

These equivalence JSONs predate the Abilene fix (audit, 9-10 June 2026):
before that fix, the `Abilene` topology entry fell through to the
`real` builder branch and silently constructed the GEANT graph twice
under two names. Their Abilene numbers are therefore a second copy of
GEANT, and the per-seed harness differed (14 seeds vs the 20 used in
the final run).

The equivalence tables in the paper are backed by
`data/equivalence_strict_{archimedes,newton,pascal}.json` (post-fix,
20 seeds/topo), not by these files. They are kept here only as a
provenance record of what the cross-implementation TOST audit caught.
Do not use them for any reported number.
