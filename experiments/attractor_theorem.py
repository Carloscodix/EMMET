"""
Analytic derivation check for the pinned-component theorem.

Claim: the pinned component of the load distribution -- the part any two
routers share regardless of their rule -- equals, per demand pair, the
inverse of that pair's near-shortest-path multiplicity. Aggregated over
demand, this gives a STRUCTURE-ONLY predictor (no simulation) of the
physics-vs-blind similarity.

  pinned_hat = sum_ij w_ij * (sp_ij / tube_ij) / sum_ij w_ij,  w_ij = sp_ij

where tube_ij = edges within the alpha-stretch tube of (i,j). This script
confirms pinned_hat predicts the measured phys-ECMP cosine.
"""
import json, math
import numpy as np
import networkx as nx
from scipy import stats
import sys
sys.path.insert(0, '/home/clopez/emmet/experiments')
from sweep_topologies import TOPOS, build_grid, build_watts_strogatz, build_barabasi_albert, build_real

ALPHA = 1.5

def pinned_hat(G, max_pairs=300, seed=0):
    """Structure-only estimate of the pinned component: flow-weighted mean
    of sp/tube over demand pairs. No simulation."""
    nodes = list(G.nodes()); rng = np.random.default_rng(seed)
    pairs = [(a, b) for i, a in enumerate(nodes) for b in nodes[i+1:]]
    if len(pairs) > max_pairs:
        idx = rng.choice(len(pairs), max_pairs, replace=False)
        pairs = [pairs[i] for i in idx]
    edges = list(G.edges()); num = den = 0.0
    for s, t in pairs:
        ds = nx.single_source_shortest_path_length(G, s)
        dt = nx.single_source_shortest_path_length(G, t)
        if t not in ds: continue
        sp = ds[t]
        if sp == 0: continue
        cut = math.ceil(ALPHA * sp); tube = 0
        for u, v in edges:
            if (ds.get(u, 9e9)+1+dt.get(v, 9e9) <= cut) or (ds.get(v, 9e9)+1+dt.get(u, 9e9) <= cut):
                tube += 1
        num += sp * (sp / max(tube, sp)); den += sp
    return num/den if den else 0.0

if __name__ == "__main__":
    meas = {r['topo']: r for r in json.load(open('/home/clopez/emmet/data/attractor_full.json'))}
    ph, pe = [], []
    for name, builder, bargs in TOPOS:
        if name not in meas: continue
        ph.append(pinned_hat(builder(*bargs, seed=0)))
        pe.append(meas[name]['pe_cos'])
    ph, pe = np.array(ph), np.array(pe)
    r, p = stats.pearsonr(ph, pe)
    sr, sp = stats.spearmanr(ph, pe)
    print(f"n={len(ph)}")
    print(f"pinned_hat (structure only) ~ phys-ECMP (measured): "
          f"Pearson {r:+.3f} (p={p:.4f}), Spearman {sr:+.3f}")
    sl, ic, rr, pv, se = stats.linregress(ph, pe)
    print(f"fit: phys-ECMP = {sl:.3f}*pinned_hat + {ic:.3f}, R^2={rr**2:.3f}")
