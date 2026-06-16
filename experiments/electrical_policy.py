"""
Electrical / current-flow routing policy.

Treat each edge as a resistor (conductance = capacity/latency), inject unit
current at src, extract at dst, solve the Laplacian for node potentials, and
route greedily down the potential gradient -- how current chooses its path.
A fourth independent physical family: if it lands in the attractor basin
(high cosine with the momentum cores), it is another witness.
"""
import numpy as np
import networkx as nx


def policy_electrical(G, src, dst, state):
    if src == dst:
        return [src]
    nodes = list(G.nodes())
    idx = {u: i for i, u in enumerate(nodes)}
    n = len(nodes)
    L = np.zeros((n, n))
    for u, v, d in G.edges(data=True):
        cap = d.get("capacity", 1.0); lat = d.get("latency", 1.0)
        g = max(cap, 1e-6) / max(lat, 1e-6)
        i, j = idx[u], idx[v]
        L[i, i] += g; L[j, j] += g; L[i, j] -= g; L[j, i] -= g
    b = np.zeros(n); b[idx[src]] = 1.0; b[idx[dst]] = -1.0
    Lr = L.copy(); d_i = idx[dst]
    Lr[d_i, :] = 0; Lr[d_i, d_i] = 1.0; b[d_i] = 0.0
    try:
        pot = np.linalg.solve(Lr, b)
    except np.linalg.LinAlgError:
        return None
    path = [src]; cur = src; seen = {src}
    for _ in range(n):
        if cur == dst:
            return path
        nbrs = [w for w in G.neighbors(cur) if w not in seen]
        if not nbrs:
            return None
        nxt = max(nbrs, key=lambda w: pot[idx[cur]] - pot[idx[w]])
        if pot[idx[nxt]] >= pot[idx[cur]]:
            return None
        path.append(nxt); seen.add(nxt); cur = nxt
    return path if cur == dst else None
