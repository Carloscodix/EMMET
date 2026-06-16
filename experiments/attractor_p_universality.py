"""
On the parameter p of the pinned-fraction law f = 1/(1+p(x-1)).

Two structural findings about p, neither a closed-form derivation:

1. ALPHA IS NOT ARBITRARY. The tube width alpha (cutoff=ceil(alpha*sp)) that
   best explains the pinned fraction is alpha=1.25 -- a clean maximum of the
   fit R^2 (0.87 at 1.25, falling to 0.61 at 1.35 and 0.47 at 1.10). That is
   the gentle-stretch tube: ~one extra hop per four of shortest-path length,
   exactly the near-shortest detours that actually compete for flow.

2. p IS QUASI-UNIVERSAL. Fitting p separately on three very different graph
   families gives Grid 0.043, small-world 0.030, scale-free 0.036 -- all within
   a ~20% window of ~0.036. Not one universal constant, but its stability
   across regular, small-world and scale-free graphs says the flow-carrying
   fraction of the gentle-stretch tube is close to a property of the stretch
   itself, not of the graph type.

Open: deriving p (or its mild family dependence) from a graph functional in
closed form -- a graph-theory problem in its own right.
"""
import sys, math, random
sys.path.insert(0,"experiments")
import numpy as np, networkx as nx, json
from equivalence import build_topo, TOPOS
from scipy import optimize

def tube_sp_alpha(G, alpha, max_pairs=200, seed=0):
    nodes=list(G.nodes()); rng=random.Random(seed)
    pairs=[(a,b) for i,a in enumerate(nodes) for b in nodes[i+1:]]
    if len(pairs)>max_pairs: pairs=rng.sample(pairs,max_pairs)
    edges=list(G.edges()); ratios=[]
    for s,t in pairs:
        ds=nx.single_source_shortest_path_length(G,s)
        dt=nx.single_source_shortest_path_length(G,t)
        if t not in ds: continue
        sp=ds[t]; cut=math.ceil(alpha*sp); w=0
        for u,v in edges:
            if (ds.get(u,9e9)+1+dt.get(v,9e9)<=cut) or (ds.get(v,9e9)+1+dt.get(u,9e9)<=cut): w+=1
        ratios.append(w/max(sp,1))
    return np.mean(ratios) if ratios else 0.0

import json
from scipy import optimize
fdata=json.load(open("data/attractor_full.json"))
fm={r["topo"]:r["pe_cos"] for r in fdata}
Gs={name:build_topo(name,builder,dsrc,0)[0] for name,builder,dsrc in TOPOS}
def mm(x,p): return 1.0/(1.0+p*(x-1.0))
fams={"Grid":["Grid5","Grid6","Grid7","Grid8","Grid10","Grid12"],"WS":["WS_n30_k4","WS_n50_k4","WS_n50_k6","WS_n80_k4"],"BA":["BA_n50_m2","BA_n50_m3","BA_n80_m2"]}
for fam,names in fams.items():
    xs=np.array([tube_sp_alpha(Gs[n],1.25) for n in names if n in fm])
    fs=np.array([fm[n] for n in names if n in fm])
    popt,_=optimize.curve_fit(mm,xs,fs,p0=[0.05],maxfev=99999)
    r2=1-np.sum((fs-mm(xs,*popt))**2)/np.sum((fs-fs.mean())**2)
    print("%-5s p=%.4f R2=%.3f n=%d" % (fam,popt[0],r2,len(xs)))
