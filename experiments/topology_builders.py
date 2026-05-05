"""Topology builders beyond Erdos-Renyi."""
import random
import networkx as nx


def _populate_edges(G, seed):
    rng = random.Random(seed)
    for u, v in G.edges():
        G[u][v]["latency"] = rng.uniform(1, 5)
        G[u][v]["capacity"] = rng.randint(3, 6)
        G[u][v]["load"] = 0
        G[u][v]["loss"] = 0
    return G


def build_grid(side, seed):
    G = nx.grid_2d_graph(side, side)
    G = nx.Graph(G)
    G = nx.relabel_nodes(G, {n: i for i, n in enumerate(G.nodes())})
    return _populate_edges(G, seed)


def build_barabasi_albert(n, m, seed):
    G = nx.barabasi_albert_graph(n, m, seed=seed)
    return _populate_edges(G, seed)


def build_watts_strogatz(n, k, p, seed):
    G = nx.watts_strogatz_graph(n, k, p, seed=seed)
    return _populate_edges(G, seed)
