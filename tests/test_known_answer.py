"""
Known-answer tests (code audit, method 7).

Tiny graphs and hand-built schedules where served/drop counts are worked
out by pencil, then checked against the simulator. If the arithmetic and
the code disagree, the code is wrong. No randomness, no policy black box:
routes are forced so the only thing under test is the load/drop mechanic.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "experiments"))
import networkx as nx
import flowsim as FS


def _fixed_route(route):
    """A policy that always returns the same pre-set path."""
    return lambda G, s, d, state: route

def test_single_flow_under_capacity():
    """One flow, rate 1, on an edge of capacity 5, for 3 ticks.
    load=1 <= 5 every tick -> 0 drops, 3 served ticks. born=1."""
    G = nx.Graph()
    G.add_edge(0, 1, latency=2.0, capacity=5, load=0, loss=0)
    sched = {0: [(0, 1, 3, 1)]}   # one flow born at t0, dur 3, rate 1
    r = FS.simulate_flows(G, sched, 5, _fixed_route([0, 1]))
    assert r["born"] == 1, r
    assert r["drop_ticks"] == 0, r
    assert r["served_ticks"] == 3, r
    assert r["total_ticks"] == 3, r

def test_overflow_all_drop():
    """Three rate-1 flows share an edge of capacity 2, for 2 ticks each.
    load=3 > 2 every tick -> every live flow drops. 3 flows x 2 ticks =
    6 drop_ticks, 0 served. born=3."""
    G = nx.Graph()
    G.add_edge(0, 1, latency=1.0, capacity=2, load=0, loss=0)
    sched = {0: [(0, 1, 2, 1), (0, 1, 2, 1), (0, 1, 2, 1)]}
    r = FS.simulate_flows(G, sched, 5, _fixed_route([0, 1]))
    assert r["born"] == 3, r
    assert r["drop_ticks"] == 6, r
    assert r["served_ticks"] == 0, r

def test_exactly_at_capacity_no_drop():
    """Two rate-1 flows on capacity-2 edge: load=2, which is NOT > 2.
    The drop condition is strict (>), so both are served. This pins down
    the boundary: 2 flows x 1 tick = 2 served, 0 drops."""
    G = nx.Graph()
    G.add_edge(0, 1, latency=1.0, capacity=2, load=0, loss=0)
    sched = {0: [(0, 1, 1, 1), (0, 1, 1, 1)]}
    r = FS.simulate_flows(G, sched, 3, _fixed_route([0, 1]))
    assert r["born"] == 2, r
    assert r["drop_ticks"] == 0, r
    assert r["served_ticks"] == 2, r

def test_bottleneck_on_second_hop():
    """Route 0-1-2. Edge (0,1) cap 10, edge (1,2) cap 1. Two rate-1 flows.
    (1,2) load=2 > 1 -> both drop, even though (0,1) is fine. Confirms the
    drop check scans every edge on the path. 2 flows x 1 tick = 2 drops."""
    G = nx.Graph()
    G.add_edge(0, 1, latency=1.0, capacity=10, load=0, loss=0)
    G.add_edge(1, 2, latency=1.0, capacity=1, load=0, loss=0)
    sched = {0: [(0, 2, 1, 1), (0, 2, 1, 1)]}
    r = FS.simulate_flows(G, sched, 3, _fixed_route([0, 1, 2]))
    assert r["born"] == 2, r
    assert r["drop_ticks"] == 2, r
    assert r["served_ticks"] == 0, r

def test_flow_lifetime_exact():
    """A flow with dur=2 contributes to exactly 2 ticks, then dies.
    Capacity is ample, so all served. Confirms TTL accounting: total=2,
    not 1 or 3, regardless of how many ticks the sim runs."""
    G = nx.Graph()
    G.add_edge(0, 1, latency=1.0, capacity=99, load=0, loss=0)
    sched = {0: [(0, 1, 2, 1)]}
    r = FS.simulate_flows(G, sched, 10, _fixed_route([0, 1]))
    assert r["born"] == 1, r
    assert r["served_ticks"] == 2, r
    assert r["total_ticks"] == 2, r

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
