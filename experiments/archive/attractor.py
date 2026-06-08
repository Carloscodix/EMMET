"""ATTRACTOR experiment: do different routers converge to the SAME per-edge
utilization vector, set by topology rather than algorithm?

Falsifiable: if smart routers (CONGA/DRILL/EMMET) produce highly-correlated
utilization vectors while the non-balancing control (shortest-path) diverges,
there is a load-balancing attractor. If even SP correlates equally, the
similarity is just the demand, not an attractor.
"""
import sys, json, itertools
from pathlib import Path
import numpy as np
sys.path.insert(0, '/home/clopez/emmet/experiments')
import emmet_budget
from emmet_budget import reset
from real_traffic import build_geant_real
import flowsim as FS

FAIL = (0, 2)
N_SEEDS = 12
POLICIES = [('SP', FS.policy_shortest), ('ECMP', FS.policy_ecmp),
            ('CONGA', FS.policy_conga), ('DRILL', FS.policy_drill),
            ('EMMET', FS.policy_emmet)]


def mk(seed, cap=(2,4)):
    G, dem = build_geant_real(seed, cap_lo=cap[0], cap_hi=cap[1])
    if G.has_edge(*FAIL):
        G.remove_edge(*FAIL)
    return G, dem

def util_vec(util, edge_order):
    return np.array([util[e] for e in edge_order])

def cosine(a, b):
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    return float(a.dot(b) / (na * nb)) if na > 0 and nb > 0 else 0.0


def main():
    emmet_budget.GAMMA = 2.0
    names = [p[0] for p in POLICIES]
    PP = {f'{a}-{b}': [] for a, b in itertools.combinations(names, 2)}
    PC = {f'{a}-{b}': [] for a, b in itertools.combinations(names, 2)}
    for s in range(N_SEEDS):
        G0, dem = mk(s)
        eo = [tuple(sorted(e)) for e in G0.edges()]
        sched = FS.gen_flows(dem, 200, s+9000, birth_rate=0.8, dur_lo=4, dur_hi=12, rate=1)
        vecs = {}
        for name, fn in POLICIES:
            G, _ = mk(s); reset(G)
            r = FS.simulate_flows_util(G, sched, 200, fn)
            vecs[name] = util_vec(r['util'], eo)
        for a, b in itertools.combinations(names, 2):
            PP[f'{a}-{b}'].append(float(np.corrcoef(vecs[a], vecs[b])[0,1]))
            PC[f'{a}-{b}'].append(cosine(vecs[a], vecs[b]))
    out = {'pearson': {k: float(np.mean(v)) for k, v in PP.items()},
           'cosine':  {k: float(np.mean(v)) for k, v in PC.items()}}
    Path('/home/clopez/emmet/data/attractor_raw.json').write_text(json.dumps(out, indent=2))
    print("PEARSON (mean over seeds), sorted:")
    for k, v in sorted(out['pearson'].items(), key=lambda kv:-kv[1]):
        print(f"  {k:<14} {v:+.3f}")

if __name__ == '__main__':
    main()
