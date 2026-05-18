"""Generate table4_scalability.tex from Phase A bootstrap results."""
import json
from pathlib import Path

REPO = Path('/home/clopez/emmet')
boot_a = json.load(open(REPO / 'data/scalability_phaseA_bootstrap.json'))
boot_by_scen = {r['scenario']: r for r in boot_a}
PHASE_B_PATH = REPO / 'data/scalability_phaseB_bootstrap.json'
INCLUDE_PHASE_B = PHASE_B_PATH.exists()
if INCLUDE_PHASE_B:
    boot_b = json.load(open(PHASE_B_PATH))
    for r in boot_b:
        boot_by_scen[r['scenario']] = r
    print('INFO: Phase B bootstrap found, including n=1000 rows')
NS = [100, 250, 500, 1000] if INCLUDE_PHASE_B else [100, 250, 500]

ER_CONFIGS = [(n, p) for n in NS for p in [0.05, 0.10, 0.20]]
WS_CONFIGS = [n for n in NS]

esc = lambda s: s.replace('_', r'\_')

def fmt_p(p):
    if p is None: return '---'
    if p < 1e-3: return f'{p:.1e}'
    if p < 0.05: return f'{p:.3f}'
    return f'{p:.2f}'

out = []
out.append('% Auto-generated v2 by experiments/gen_table4_scalability.py')
phase_label = 'Phase A+B' if INCLUDE_PHASE_B else 'Phase A only'
out.append(f'% Source: scalability_phaseA{"+B" if INCLUDE_PHASE_B else ""}_bootstrap.json ({phase_label})')
out.append(r'\begin{tabular}{llrrrrrr}')
out.append(r'\toprule')
out.append(r'Family & Scenario & $n$ & LASP loss & EMMET loss & rel.\ red.\ & 95\% CI & $d$ \\')
out.append(r'\midrule')

# ER block
for i, (n, p) in enumerate(ER_CONFIGS):
    key = f'ER_n{n}_p{p:.2f}'
    b = boot_by_scen.get(key)
    if not b: continue
    ll = b['sum_lasp'] / b['n_seeds']
    dl = b['sum_dp'] / b['n_seeds']
    if ll <= 0.01:
        rel_str = r'$\approx 0$'
        ci_str = '---'
    else:
        rel_str = f'$-{b["rel_total_pct"]:.1f}\\%$'
        if b['rel_ci95']:
            lo, hi = -b['rel_ci95'][1], -b['rel_ci95'][0]
            ci_str = f'$[{lo:+.1f}, {hi:+.1f}]\\%$'
        else:
            ci_str = '---'
    d_str = f'{b["cohens_d"]:+.2f}'
    fam = 'ER' if i == 0 else ''
    out.append(f' {fam} & {esc(key)} & {n} & {ll:.3f} & {dl:.3f} & {rel_str} & {ci_str} & {d_str} \\\\')
out.append(r'\midrule')

# WS block
for i, n in enumerate(WS_CONFIGS):
    key = f'WS_n{n}_k4_p0.10'
    b = boot_by_scen.get(key)
    if not b: continue
    ll = b['sum_lasp'] / b['n_seeds']
    dl = b['sum_dp'] / b['n_seeds']
    rel_str = f'$-{b["rel_total_pct"]:.1f}\\%$'
    if b['rel_ci95']:
        lo, hi = -b['rel_ci95'][1], -b['rel_ci95'][0]
        ci_str = f'$[{lo:+.1f}, {hi:+.1f}]\\%$'
    else:
        ci_str = '---'
    d_str = f'{b["cohens_d"]:+.2f}'
    fam = 'WS' if i == 0 else ''
    out.append(f' {fam} & {esc(key)} & {n} & {ll:.3f} & {dl:.3f} & {rel_str} & {ci_str} & {d_str} \\\\')

out.append(r'\bottomrule')
out.append(r'\end{tabular}')
result = '\n'.join(out)
with open(REPO / 'paper/table4_scalability.tex', 'w') as f:
    f.write(result)
print('Wrote table4_scalability.tex')
print(f'Lines: {len(out)}')
