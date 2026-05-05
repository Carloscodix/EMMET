# Note on the Repository History

The visible commit history of this repository is intentionally
condensed. The work documented here was developed iteratively over
several weeks, with a substantially larger number of intermediate
commits, experiments that did not pan out, and refactors. To keep
the public history focused on the algorithm and its validation, the
development was squashed into a small number of thematic commits
when the repository was prepared for public release.

The intermediate state of the project — including:

- Discarded algorithmic variants (EMMET-thermal, EMMET-budget without
  per-packet state, EMMET-fb with shortest-path fallback, and
  ablations of mechanisms ultimately removed)
- Earlier versions of the paper, with different positioning and
  partially-superseded claims
- Per-experiment iteration logs and intermediate JSON outputs

is preserved in the `archive/` subdirectories and remains under
version control. None of these archived files supports any claim in
the current paper; the explicit mapping from each headline number to
the script and data file that produced it is given in
[`RESULTS_MANIFEST.md`](../RESULTS_MANIFEST.md).

If you are reviewing this work and want access to the granular
development history (individual commits, decisions made along the
way, audit findings and how each was addressed), please contact the
maintainer directly. The full history is available on request.
