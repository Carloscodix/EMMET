"""
SNDlib native-format parser for the out-of-sample benchmark (bench A).

Parses sndlib-instances-native topology files into a networkx graph plus
the real demand matrix shipped with each instance. This lets us test the
two-factor law on backbones never used to fit it, with their OWN demands
(attacking the demand-approximate caveat), not a synthetic proxy.
"""
import re
import zipfile
import networkx as nx

ZIP = "/home/clopez/emmet/data/real_traffic/sndlib.zip"
BASE = "sndlib-instances-native"


def _section(text, name):
    """Extract the body between NAME ( ... )."""
    m = re.search(name + r"\s*\((.*?)\n\)", text, re.S)
    return m.group(1) if m else ""

def load(topo):
    """Return (G, demand) for an SNDlib topology name.

    G: undirected networkx graph with latency/capacity/load/loss per edge.
    demand: dict {(u,v): volume} from the instance DEMANDS section.
    """
    with zipfile.ZipFile(ZIP) as z:
        text = z.read(f"{BASE}/{topo}/{topo}.txt").decode("utf-8", "replace")

    G = nx.Graph()
    for line in _section(text, "NODES").strip().splitlines():
        name = line.strip().split("(")[0].strip()
        if name:
            G.add_node(name)


    # LINKS: capture only the topology (which nodes connect). Capacity and
    # latency are assigned by the bench scheme (apply_bench_scheme), so the
    # ONLY thing that differs from the training bench is the structure --
    # exactly the variable the two-factor law is about.
    link_re = re.compile(r"^\s*\S+\s+\(\s*(\S+)\s+(\S+)\s*\)")
    for line in _section(text, "LINKS").strip().splitlines():
        m = link_re.match(line)
        if m and m.group(1) in G and m.group(2) in G:
            G.add_edge(m.group(1), m.group(2), latency=1.0, capacity=1, load=0, loss=0)

    # DEMANDS: Demand_x ( A B ) routing vol UNLIMITED
    demand = {}
    dem_re = re.compile(r"\(\s*(\S+)\s+(\S+)\s*\)\s+\d+\s+([\d.]+)")
    for line in _section(text, "DEMANDS").strip().splitlines():
        if not line.strip().startswith("Demand"):
            continue
        m = dem_re.search(line)
        if m and m.group(1) in G and m.group(2) in G:
            demand[(m.group(1), m.group(2))] = float(m.group(3))
    return G, demand

def apply_bench_scheme(G, seed, cap=(2, 4)):
    """Assign capacity/latency with the SAME scheme as the training bench
    (equivalence.build_topo): random integer capacity in cap, uniform
    latency. Relabel nodes to integers 0..n-1 to match bench conventions.
    Returns (G_int, mapping)."""
    import random as _r
    rng = _r.Random(seed)
    for u, v in G.edges():
        G[u][v]["latency"] = rng.uniform(1, 5)
        G[u][v]["capacity"] = rng.randint(cap[0], cap[1])
        G[u][v]["load"] = 0
        G[u][v]["loss"] = 0
    mapping = {n: i for i, n in enumerate(G.nodes())}
    import networkx as _nx
    return _nx.relabel_nodes(G, mapping), mapping
