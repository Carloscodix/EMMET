"""
Quantitative test of the structural attractor argument.

The structural argument claims the attractor is the component of the load
distribution PINNED by cuts and demand, common to all routers including blind
ones. Falsifiable prediction: similarity between a physical core and a BLIND
router (ECMP) measures only the pinned component, so it must FALL as tube/sp
rises. The contrast with phys-phys (which also shares the congestion rule, and
so rises with tube/sp) is the signature of the mechanism.
"""
import json
import numpy as np
from scipy import stats

rows = json.load(open("/home/clopez/emmet/data/attractor_full.json"))
tube = np.array([r["tube_sp"] for r in rows])

print("=== structural attractor: pinned component vs tube/sp ===\n")
for label, key in [("phys-ECMP cosine", "pe_cos"), ("phys-ECMP 1-L1", "pe_l1"),
                   ("phys-phys cosine", "pp_cos")]:
    v = np.array([r[key] for r in rows])
    r, p = stats.pearsonr(tube, v)
    sr, sp = stats.spearmanr(tube, v)
    print(f"  tube/sp ~ {label:18s}: pearson {r:+.3f} (p={p:.4f})  spearman {sr:+.3f}")

print("\nPinned floor (phys-ECMP cosine) by topology, sorted by tube/sp:")
for i in np.argsort(tube):
    print("  %-12s tube/sp=%5.2f  pinned=%.3f" % (rows[i]["topo"], tube[i], rows[i]["pe_cos"]))
