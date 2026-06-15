"""
Baseline fidelity audit (code audit, method 5).

Checks that policy_drill and the CONGA policy implement the behaviours
the paper claims for them, and that those claims match the published
algorithms (Ghorbani 2017 for DRILL, Alizadeh 2014 for CONGA). This is
the defence against the "your baselines are straw men" objection.

The paper describes DRILL as a near-stateless per-hop balancer and CONGA
as a K-shortest-path congestion-aware selector. These tests verify the
code matches those descriptions, behaviourally.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "experiments"))
import networkx as nx
import random
import flowsim as FS
from baselines_extra import drill_route
from conga_wan import conga_wan_route, k_shortest_paths, path_congestion

def _line_graph_with_loads():
    """Small graph where the least-loaded next hop is unambiguous."""
    G = nx.Graph()
    # diamond: 0 -> {1,2,3} -> 4, each edge capacity 10
    for n in (1, 2, 3):
        G.add_edge(0, n, latency=1.0, capacity=10, load=0, loss=0)
        G.add_edge(n, 4, latency=1.0, capacity=10, load=0, loss=0)
    return G


def test_drill_picks_least_loaded_when_m_covers_all():
    """With m >= #candidates, DRILL must pick the least-loaded next hop."""
    G = _line_graph_with_loads()
    G[0][1]["load"] = 9; G[0][2]["load"] = 1; G[0][3]["load"] = 5
    rng = random.Random(0)
    # m=3 covers all three first-hop candidates: choice is deterministic
    p, status = drill_route(G, 0, 4, rng, m=3)
    assert status == "delivered", status
    assert p[1] == 2, f"expected hop via node 2 (load 1), got {p[1]}"

def test_drill_respects_sample_size():
    """DRILL[m] samples at most m candidates (plus the remembered best):
    it is NOT a global argmin. With m=1 and a fixed rng, the pick must be
    one of the sampled candidates, not necessarily the global least-loaded."""
    G = _line_graph_with_loads()
    G[0][1]["load"] = 9; G[0][2]["load"] = 1; G[0][3]["load"] = 5
    # Force m=1: only one random candidate is examined each step.
    seen = set()
    for s in range(30):
        rng = random.Random(s)
        p, st = drill_route(G, 0, 4, rng, m=1)
        if st == "delivered":
            seen.add(p[1])
    # Across seeds the first hop varies (sampling), proving it is not a
    # deterministic global argmin masquerading as DRILL.
    assert len(seen) >= 2, f"m=1 should explore via sampling, saw only {seen}"

def _two_path_graph():
    """Two disjoint paths 0->...->3 of equal length, different congestion."""
    G = nx.Graph()
    # path A: 0-1-3 ; path B: 0-2-3
    G.add_edge(0, 1, latency=1.0, capacity=10, load=8, loss=0)
    G.add_edge(1, 3, latency=1.0, capacity=10, load=8, loss=0)
    G.add_edge(0, 2, latency=1.0, capacity=10, load=1, loss=0)
    G.add_edge(2, 3, latency=1.0, capacity=10, load=1, loss=0)
    return G


def test_conga_picks_least_congested_path():
    """CONGA must select the less congested of the K candidate paths."""
    G = _two_path_graph()
    p, st = conga_wan_route(G, 0, 3, k=4)
    assert st == "delivered", st
    assert 2 in p, f"expected the low-load path via node 2, got {p}"

def test_conga_k_bounds_candidate_set():
    """CONGA considers at most K shortest paths. K=1 cannot avoid
    congestion (no choice). This is the K=4 artefact lesson as a test."""
    G = _two_path_graph()
    paths_k1 = k_shortest_paths(G, 0, 3, k=1)
    assert len(paths_k1) == 1
    paths_k4 = k_shortest_paths(G, 0, 3, k=4)
    assert len(paths_k4) >= 2, "k=4 must expose both disjoint paths"

def test_conga_congestion_metric_monotone():
    """path_congestion increases with edge load: the scoring is sane."""
    G = _two_path_graph()
    cong_A = path_congestion(G, [0, 1, 3])
    cong_B = path_congestion(G, [0, 2, 3])
    assert cong_A > cong_B, (cong_A, cong_B)

if __name__ == "__main__":
    import traceback
    tests = [v for k, v in sorted(globals().items())
             if k.startswith("test_") and callable(v)]
    failed = 0
    for t in tests:
        try:
            t(); print(f"PASS  {t.__name__}")
        except Exception:
            failed += 1; print(f"FAIL  {t.__name__}"); traceback.print_exc()
    print("-" * 40)
    print(f"{len(tests)-failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)
