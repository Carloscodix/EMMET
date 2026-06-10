"""Generate paper tables from the definitive JSON summaries.

Reads:
  - data/momentum_clean_full_summary.json  (headline + ER + Real)
  - data/topology_extended_summary.json    (Grid, BA, WS)
  - data/momentum_clean_kappa_sweep_summary.json  (kappa sweep)

Writes LaTeX tabulars to:
  - paper/table1_headline.tex
  - paper/table2_battery.tex
  - paper/table3_kappa_sweep.tex
"""
import json
from pathlib import Path

REPO = Path('/home/clopez/emmet')
DATA = REPO / 'data'
PAPER = REPO / 'paper'

# =====================================================================
# Table 1: GEANT headline metrics
# =====================================================================
full = json.load(open(DATA / 'momentum_clean_full_summary.json'))
geant = next(r for r in full if r['scenario'] == 'GEANT')

t1 = r"""% Auto-generated from data/momentum_clean_full_summary.json
\begin{tabular}{lrrr}
\toprule
Metric & LASP-aug & EMMET-DP & $\Delta$ \\
\midrule
"""
def fmt_pct_diff(la, mom, lower_is_better=True):
    if la == 0:
        return "--"
    d = (la - mom) / la * 100
    sign = '-' if (lower_is_better and d > 0) else ('+' if d != 0 else '')
    return f"{sign}{abs(d):.1f}\\%"

la_loss = geant['lasp_aug_losses_mean']
mom_loss = geant['momentum_dp_losses_mean']
la_dr = geant['lasp_aug_delivery_rate_mean']
mom_dr = geant['momentum_dp_delivery_rate_mean']
la_cap = geant['lasp_aug_cap_per_routed_attempt_mean']
mom_cap = geant['momentum_dp_cap_per_routed_attempt_mean']
la_capdel = geant['lasp_aug_cap_per_delivery_mean']
mom_capdel = geant['momentum_dp_cap_per_delivery_mean']
la_caplost = geant['lasp_aug_cap_consumed_lost_mean']
mom_caplost = geant['momentum_dp_cap_consumed_lost_mean']

t1 += f"Congestion losses (mean) & {la_loss:.2f} & {mom_loss:.2f} & "
t1 += fmt_pct_diff(la_loss, mom_loss, lower_is_better=True) + r" \\" + "\n"
t1 += f"Delivery rate            & {la_dr:.2f}\\% & {mom_dr:.2f}\\% & "
t1 += f"+{mom_dr - la_dr:.2f}\\,pp \\\\" + "\n"
t1 += f"Cap.\\ per routed attempt (hops) & {la_cap:.2f} & {mom_cap:.2f} & "
t1 += f"+{mom_cap - la_cap:.2f} \\\\" + "\n"
t1 += f"Cap.\\ per delivery (hops) & {la_capdel:.2f} & {mom_capdel:.2f} & "
t1 += f"+{mom_capdel - la_capdel:.2f} \\\\" + "\n"
t1 += f"Cap.\\ wasted on losses (mean) & {la_caplost:.2f} & {mom_caplost:.2f} & "
t1 += fmt_pct_diff(la_caplost, mom_caplost, lower_is_better=True) + r" \\" + "\n"
t1 += r"""\bottomrule
\end{tabular}
"""
(PAPER / 'table1_headline.tex').write_text(t1)
print(f"Table 1 written ({len(t1)} chars)")

# =====================================================================
# Table 2: Generalization across all 22 scenarios + 5 topology families
# =====================================================================
topo = json.load(open(DATA / 'topology_extended_summary.json'))

# Map scenario to family
def family(sc):
    if sc.startswith('GEANT') or sc.startswith('Abilene'):
        return 'Real'
    if sc.startswith('ER_'):
        return 'ER'
    if sc.startswith('Grid'):
        return 'Grid'
    if sc.startswith('BA'):
        return 'BA'
    if sc.startswith('WS'):
        return 'WS'
    return '??'

all_scenarios = []
for r in full:
    all_scenarios.append({
        'family': family(r['scenario']),
        'scenario': r['scenario'],
        'la_loss': r['lasp_aug_losses_mean'],
        'mom_loss': r['momentum_dp_losses_mean'],
        'la_dr': r['lasp_aug_delivery_rate_mean'],
        'mom_dr': r['momentum_dp_delivery_rate_mean'],
    })
for r in topo:
    all_scenarios.append({
        'family': family(r['scenario']),
        'scenario': r['scenario'],
        'la_loss': r['lasp_aug_losses_mean'],
        'mom_loss': r['momentum_dp_losses_mean'],
        'la_dr': r['lasp_aug_delivery_rate_mean'],
        'mom_dr': r['momentum_dp_delivery_rate_mean'],
    })

family_order = ['Real', 'ER', 'Grid', 'BA', 'WS']
all_scenarios.sort(key=lambda r: (family_order.index(r['family']),
                                    r['scenario']))

t2 = r"""% Auto-generated from data/momentum_clean_full_summary.json + topology_extended_summary.json
\begin{tabular}{llrrrrr}
\toprule
Family & Scenario & LASP-aug & EMMET-DP & $\Delta$ losses & LASP-aug & EMMET-DP \\
       &          & losses   & losses   &                 & delivery & delivery \\
\midrule
"""
prev_family = None
for r in all_scenarios:
    fam_label = r['family'] if r['family'] != prev_family else ''
    if r['family'] != prev_family and prev_family is not None:
        t2 += r"\midrule" + "\n"
    prev_family = r['family']
    sc = r['scenario'].replace('_', r'\_')
    delta = fmt_pct_diff(r['la_loss'], r['mom_loss'], lower_is_better=True)
    t2 += (f"{fam_label} & {sc} & "
           f"{r['la_loss']:.2f} & {r['mom_loss']:.2f} & "
           f"{delta} & {r['la_dr']:.1f}\\% & {r['mom_dr']:.1f}\\% \\\\\n")
t2 += r"""\bottomrule
\end{tabular}
"""
(PAPER / 'table2_battery.tex').write_text(t2)
print(f"Table 2 written ({len(t2)} chars, {len(all_scenarios)} scenarios)")

# =====================================================================
# Table 3: Kappa sweep
# =====================================================================
sweep = json.load(open(DATA / 'momentum_clean_kappa_sweep_summary.json'))

# Pivot: rows = scenario, cols = kappa value
scenarios_sw = sorted({r['scenario'] for r in sweep})
kappas = sorted({r['kappa'] for r in sweep})

t3 = r"""% Auto-generated from data/momentum_clean_kappa_sweep_summary.json
\begin{tabular}{l""" + "r" * len(kappas) + r"""}
\toprule
Scenario"""
for k in kappas:
    t3 += f" & $\\kappa{{=}}{k:g}$"
t3 += r" \\" + "\n"
t3 += r"\midrule" + "\n"

for sc in scenarios_sw:
    t3 += sc.replace('_', r'\_')
    for k in kappas:
        row = next(r for r in sweep if r['scenario'] == sc and r['kappa'] == k)
        la = row['lasp_aug_losses_mean']
        mom = row['momentum_dp_losses_mean']
        if la == 0:
            cell = "--"
        else:
            d = (la - mom) / la * 100
            sign = '-' if d > 0 else ('+' if d < 0 else '')
            cell = f"{sign}{abs(d):.1f}\\%"
        t3 += f" & {cell}"
    t3 += r" \\" + "\n"
t3 += r"""\bottomrule
\end{tabular}
"""
(PAPER / 'table3_kappa_sweep.tex').write_text(t3)
print(f"Table 3 written ({len(t3)} chars, {len(scenarios_sw)} scenarios x {len(kappas)} kappas)")
