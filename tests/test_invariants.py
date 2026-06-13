"""
Invariant test suite for the EMMET simulator (code audit, method 2).

These are properties that must hold regardless of policy, topology or seed.
A failure here means a published number could be wrong. Run with pytest.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "experiments"))

import flowsim as FS
from equivalence import TOPOS, build_topo, N_SEEDS
from emmet_budget import reset

POLICIES = {
    "shortest": FS.policy_shortest,
    "drill":    FS.policy_drill,
    "emmet":    FS.policy_emmet,
}

def _run(name, builder, dsrc, pol, seed):
    G, dem = build_topo(name, builder, dsrc, seed)
    sched = FS.gen_flows(dem, 200, seed + 9000)
    reset(G)
    return FS.simulate_flows(G, sched, 200, pol)


def _cases(n_topos=4, n_seeds=2):
    out = []
    for t in TOPOS[:n_topos]:
        for pname, pol in POLICIES.items():
            for s in range(min(n_seeds, N_SEEDS)):
                out.append((t[0], t[1], t[2], pname, pol, s))
    return out

def test_conservation():
    """served + drop must equal total, and total must equal the sum."""
    for name, b, d, pname, pol, s in _cases():
        r = _run(name, b, d, pol, s)
        assert r["served_ticks"] + r["drop_ticks"] == r["total_ticks"], (name, pname, s)


def test_drop_rate_in_range():
    """drop_rate is a probability: it lives in [0, 1]."""
    for name, b, d, pname, pol, s in _cases():
        r = _run(name, b, d, pol, s)
        assert 0.0 <= r["drop_rate"] <= 1.0, (name, pname, s, r["drop_rate"])


def test_drop_rate_matches_counts():
    """drop_rate must equal drop_ticks / total_ticks exactly."""
    for name, b, d, pname, pol, s in _cases():
        r = _run(name, b, d, pol, s)
        if r["total_ticks"] > 0:
            assert abs(r["drop_rate"] - r["drop_ticks"]/r["total_ticks"]) < 1e-12, (name, pname)

def test_determinism():
    """Same graph, same schedule, same policy -> identical result."""
    for name, b, d, pname, pol, s in _cases():
        r1 = _run(name, b, d, pol, s)
        r2 = _run(name, b, d, pol, s)
        assert r1 == r2, (name, pname, s)


def test_reset_clears_load():
    """After reset(G), every edge load is exactly zero."""
    for name, b, d, pname, pol, s in _cases(n_topos=3, n_seeds=1):
        G, dem = build_topo(name, b, d, s)
        sched = FS.gen_flows(dem, 200, s + 9000)
        reset(G); FS.simulate_flows(G, sched, 200, pol)
        reset(G)
        assert all(G[u][v]["load"] == 0 for u, v in G.edges()), name

def test_born_bounded_by_schedule():
    """No more flows can be born than there are entries in the schedule."""
    for name, b, d, pname, pol, s in _cases(n_topos=3, n_seeds=1):
        G, dem = build_topo(name, b, d, s)
        sched = FS.gen_flows(dem, 200, s + 9000)
        n_entries = sum(len(v) for v in sched.values())
        reset(G)
        r = FS.simulate_flows(G, sched, 200, pol)
        assert r["born"] <= n_entries, (name, pname, r["born"], n_entries)

def test_load_reset_each_tick():
    """_apply_flow_load zeroes load before summing: no ghost accumulation."""
    name, b, d = TOPOS[0][0], TOPOS[0][1], TOPOS[0][2]
    G, _ = build_topo(name, b, d, 0)
    for u, v in G.edges():
        G[u][v]["load"] = 999.0
    FS._apply_flow_load(G, [])
    assert all(G[u][v]["load"] == 0 for u, v in G.edges())

if __name__ == "__main__":
    import traceback
    tests = [v for k, v in sorted(globals().items())
             if k.startswith("test_") and callable(v)]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS  {t.__name__}")
        except Exception:
            failed += 1
            print(f"FAIL  {t.__name__}")
            traceback.print_exc()
    print("-" * 40)
    print(f"{len(tests)-failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)
