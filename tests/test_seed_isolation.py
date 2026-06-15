"""
Seed and pairing-isolation audit (code audit, method 6).

The equivalence comparisons are paired: for each seed, all routers must
see the SAME flow schedule on the SAME topology, and one policy\047s
internal RNG must not perturb another run\047s inputs. These tests pin
that down at the mechanism level (the negative control already proved
it at the result level).
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "experiments"))
import flowsim as FS
from equivalence import TOPOS, build_topo, N_SEEDS
from emmet_budget import reset

def _demand():
    name, b, d = TOPOS[0]
    _, dem = build_topo(name, b, d, 0)
    return dem


def test_gen_flows_deterministic():
    """Same seed -> byte-identical schedule."""
    dem = _demand()
    s1 = FS.gen_flows(dem, 200, 12345)
    s2 = FS.gen_flows(dem, 200, 12345)
    assert s1 == s2


def test_gen_flows_seed_sensitive():
    """Different seeds -> different schedules (seed is actually used)."""
    dem = _demand()
    s1 = FS.gen_flows(dem, 200, 1)
    s2 = FS.gen_flows(dem, 200, 2)
    assert s1 != s2

def test_schedule_not_mutated_by_simulation():
    """simulate_flows must not mutate the shared schedule: the paired
    routers that run after must see the same input. We snapshot and
    compare."""
    name, b, d = TOPOS[0]
    G, dem = build_topo(name, b, d, 0)
    sched = FS.gen_flows(dem, 200, 9000)
    import copy
    snap = copy.deepcopy(sched)
    reset(G)
    FS.simulate_flows(G, sched, 200, FS.policy_drill)
    assert sched == snap, "simulation mutated the shared schedule"

def test_rng_isolation_across_runs():
    """A DRILL run (which draws RNG) before a measured run must not
    perturb it: each run rebuilds the graph fresh and DRILL seeds its own
    Random. DRILL after an interleaved run must reproduce solo DRILL."""
    name, b, d = TOPOS[0]
    _, dem = build_topo(name, b, d, 0)
    sched = FS.gen_flows(dem, 200, 9000)
    G,_ = build_topo(name, b, d, 0); reset(G)
    solo = FS.simulate_flows(G, sched, 200, FS.policy_drill)["drop_rate"]
    G,_ = build_topo(name, b, d, 0); reset(G)
    FS.simulate_flows(G, sched, 200, FS.policy_emmet_core)
    G,_ = build_topo(name, b, d, 0); reset(G)
    after = FS.simulate_flows(G, sched, 200, FS.policy_drill)["drop_rate"]
    assert solo == after, (solo, after)

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
