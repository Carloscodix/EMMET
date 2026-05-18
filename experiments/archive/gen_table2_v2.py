"""Generate table2_battery.tex v2 with effect sizes."""
import json
from pathlib import Path

REPO = Path('/home/clopez/emmet')
boot = {r['scenario']: r for r in json.load(open(REPO / 'data/v2_bootstrap_ci.json'))}

FAMILY = [
    ('Real', ['Abilene', 'GEANT']),
    ('ER',   sorted(s for s in boot if s.startswith('ER_'))),
    ('Grid', ['Grid_7x7']),
    ('BA',   sorted(s for s in boot if s.startswith('BA_'))),
    ('WS',   sorted(s for s in boot if s.startswith('WS_'))),
]

esc = lambda s: s.replace('_', r'\_')

def fmt_p(p):
    if p is None: return '---'
    if p < 1e-6: return f'{p:.1e}'
    if p < 0.001: return f'{p:.1e}'
    if p < 0.05: return f'{p:.3f}'
    return f'{p:.2f}'

out = []
out.append('% Auto-generated v2 by experiments/gen_table2_v2.py')
out.append('% Source: data/v2_bootstrap_ci.json (kappa=1.0 results)')
out.append(r'\begin{tabular}{llrrrrrr}')
out.append(r'\toprule')
out.append(r'Family & Scenario & LASP & EMMET & $\Delta$ losses & 95\% CI & $d$ & $r$ \\')
out.append(r'\midrule')

for fam, scens in FAMILY:
    for i, sc in enumerate(s for s in scens if s in boot):
        b = boot[sc]
        n = b['n_seeds']
        l_lasp = b['sum_lasp'] / n
        l_dp = b['sum_dp'] / n
        if l_lasp > 0:
            rel_str = f'$-{b["rel_total_pct"]:.1f}\\%$'
        else:
            rel_str = '---'
        if b['rel_ci95']:
            lo, hi = -b['rel_ci95'][1], -b['rel_ci95'][0]
            ci = f'$[{lo:+.1f}, {hi:+.1f}]\\%$'
        else:
            ci = '---'
        d = f'{b["cohens_d"]:+.2f}'
        r = f'{b["wilcoxon_r"]:.2f}' if b['wilcoxon_r'] is not None else '---'
        first = fam if i == 0 else ''
        out.append(f' {first} & {esc(sc)} & {l_lasp:.2f} & {l_dp:.2f} & {rel_str} & {ci} & {d} & {r} \\\\')
    out.append(r'\midrule')

out[-1] = r'\bottomrule'
out.append(r'\end{tabular}')

result = '\n'.join(out)
with open(REPO / 'paper/table2_battery.tex', 'w') as f:
    f.write(result)

print('Wrote table2_battery.tex v2')
print(f'Lines: {len(out)}')
