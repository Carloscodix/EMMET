# Reproducibility Guide

This document gives exact commands, expected runtimes, and expected
output for every quantitative claim in the paper.

## Environment

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

The codebase requires `numpy`, `networkx>=3.0`, `matplotlib>=3.5`,
and `scipy>=1.10`. Python 3.10+ is recommended.

For paper compilation, also install TeX Live with `algorithm2e`:

```bash
sudo apt install texlive-science  # Ubuntu/Debian
```

## Headline result: GÉANT loss reduction

**Claim (paper §6.1, Table 1):** EMMET-DP reduces congestion losses
on GÉANT by 60.2 % vs. LASP-aug.

**Reproduce:**
```bash
python3 experiments/momentum_clean_full.py
```

**Expected runtime:** ~6 minutes on 28 cores.

**Expected output:** `data/momentum_clean_full_raw.json` and
`data/momentum_clean_full_summary.json`.

**Verify the headline:**
```bash
python3 -c "
import json, statistics as st
raw = json.load(open('data/momentum_clean_full_raw.json'))
g = [r for r in raw if r['scenario'] == 'GEANT']
la = st.mean(r['lasp_aug']['losses'] for r in g)
mom = st.mean(r['momentum_dp']['losses'] for r in g)
print(f'LASP-aug: {la:.2f} | EMMET-DP: {mom:.2f} | Δ: {(la-mom)/la*100:.1f}%')
"
```

**Expected output:** `LASP-aug: 3.24 | EMMET-DP: 1.29 | Δ: 60.2%`

## Generalization across topology families (Figure 4, Table 2)

**Reproduce:**
```bash
python3 experiments/topology_extended_battery.py
```

**Expected runtime:** ~5 minutes on 28 cores.

**Expected output:** `data/topology_extended_raw.json` and
`data/topology_extended_summary.json` covering 6 scenarios:
Grid_7x7, BA_n50_m{2,3}, WS_n50_k4_p{0.05, 0.10, 0.30}.

## Hyperparameter sweep: κ (Figure 5, Table 3)

**Reproduce:**
```bash
python3 experiments/momentum_clean_kappa_sweep.py
```

**Expected runtime:** ~4 minutes on 28 cores.

**Expected output:** `data/momentum_clean_kappa_sweep_raw.json` and
`data/momentum_clean_kappa_sweep_summary.json`. Confirms κ=1.0 as
Pareto-optimal across the 5 representative scenarios.

## Self-audit (hostile suspicions)

**Reproduce:**
```bash
python3 experiments/hostile_audit_momentum_v2.py
```

**Expected runtime:** ~2 minutes.

**Expected output:** seven suspicion checks, all passing or with
diagnostics matching those documented in `docs/AUDIT_LOG.md`.

## Paper compilation

```bash
cd paper
pdflatex -interaction=nonstopmode paper_main.tex
pdflatex -interaction=nonstopmode paper_main.tex   # second pass for refs
```

**Expected output:** `paper/paper_main.pdf`, ~12 pages.

## Manifest

The full claim → script → JSON → paper-section mapping is in
[`RESULTS_MANIFEST.md`](RESULTS_MANIFEST.md). What follows is a
quick summary.

| Claim | Script | Output | Paper |
|---|---|---|---|
| GÉANT −60.2 % | `momentum_clean_full.py` | `momentum_clean_full_summary.json` | §6.1, Table 1 |
| 26-scenario generalization | `momentum_clean_full.py` + `topology_extended_battery.py` | `*_summary.json` | §6.2, Table 2, Figure 4 |
| κ=1.0 Pareto-optimal | `momentum_clean_kappa_sweep.py` | `momentum_clean_kappa_sweep_summary.json` | §6.3, Table 3, Figure 5 |
| t = 5.21, Wilcoxon p = 1.1×10⁻⁸ | `hostile_audit_momentum_v2.py` | stdout | §5.6, §6.1 |
