"""
Flow-stability instrumentation (gap B). Pre-registered in
PREREG_flow_stability.md (committed before this file).

Measures path_change_rate: within each burst (a maximal run of packets to the
same (src,dst) = one flow), the fraction of consecutive intra-flow packet
transitions where the chosen route changes. Stable router -> low; per-packet
reshuffler (DRILL) -> high. The simulator-level analogue of TCP reordering.

The production runners (run_bursty_*) are NOT touched; these are parallel
instrumented versions so published loss numbers are unaffected.
"""
import sys, json, random
import numpy as np
import networkx as nx
from bursty_traffic import gen_bursty, GAP_SENTINEL
from emmet_budget import reset


def _path_key(path):
    return tuple(path) if path else None


# ---------- P3: POSITIVE CONTROL (runs first) ----------
def _diamond():
    """src=0 -> {1,2} -> dst=3. Two parallel routes 0-1-3 and 0-2-3."""
    G = nx.Graph()
    for u, v in [(0, 1), (0, 2), (1, 3), (2, 3)]:
        G.add_edge(u, v, latency=1.0, capacity=100, load=0, loss=0)
    return G


def _measure_pcr(route_seq):
    """route_seq: list of path-keys for consecutive packets of ONE flow.
    Returns (changes, transitions)."""
    changes = transitions = 0
    for a, b in zip(route_seq, route_seq[1:]):
        transitions += 1
        if a != b:
            changes += 1
    return changes, transitions


def positive_control():
    flow = [(0, 3)] * 50
    stable = [(0, 1, 3) for _ in flow]
    sc, st = _measure_pcr(stable)
    rng = random.Random(0)
    unstable = [rng.choice([(0, 1, 3), (0, 2, 3)]) for _ in flow]
    uc, ut = _measure_pcr(unstable)
    s_pcr = sc / st if st else 0
    u_pcr = uc / ut if ut else 0
    passed = s_pcr < 0.05 and u_pcr > 0.30
    print(f"P3 CONTROL: stable_pcr={s_pcr:.3f} (want ~0), "
          f"unstable_pcr={u_pcr:.3f} (want high) -> "
          f"{'PASS' if passed else 'FAIL'}")
    return passed


# ---------- instrumented runner (losses + path_change_rate) ----------
def _walk(G, path):
    hops = 0
    for i in range(len(path) - 1):
        e = G[path[i]][path[i + 1]]
        e['load'] += 1; hops += 1
        if e['load'] > e['capacity']:
            e['loss'] += 1
            return False
    return True


def _decay(G):
    for u, v in G.edges():
        G[u][v]['load'] *= 0.9


def run_instrumented(G, traf, route_fn):
    losses = delivered = 0
    changes = transitions = 0
    cur_pair = None
    prev_path = None
    for step in traf:
        if step == GAP_SENTINEL:
            _decay(G); cur_pair = None; prev_path = None; continue
        src, dst = step
        if src == dst:
            _decay(G); continue
        path = route_fn(G, src, dst)
        if step != cur_pair:
            cur_pair = step; prev_path = None
        if path is not None and len(path) >= 2:
            pk = tuple(path)
            if prev_path is not None:
                transitions += 1
                if pk != prev_path:
                    changes += 1
            prev_path = pk
            if _walk(G, path): delivered += 1
            else: losses += 1
        _decay(G)
    pcr = changes / transitions if transitions else 0.0
    return {"losses": losses, "delivered": delivered,
            "path_change_rate": pcr, "transitions": transitions}


# ---------- router wrappers as route_fn(G, src, dst) ----------
def make_route_fns(G_nodes):
    from conga_wan import conga_wan_route
    from baselines_extra import drill_route
    from emmet_momentum_dp import emmet_momentum_dp_route, M_MAX, ALPHA_BUDGET, KAPPA
    rng = random.Random(12345)
    snap = {}

    def core_fn(G, s, d):
        p, _ = emmet_momentum_dp_route(G, s, d, snap, kappa=KAPPA,
            m_max=M_MAX, alpha_budget=ALPHA_BUDGET, n_buckets=8)
        return p

    def conga_fn(G, s, d):
        p, _ = conga_wan_route(G, s, d)
        return p

    def drill_fn(G, s, d):
        p, _ = drill_route(G, s, d, rng, m=2)
        return p

    return {"core": core_fn, "conga": conga_fn, "drill": drill_fn}


def measure_topo(builder, seed, n_steps=200):
    """Run the three routers on one topology, same traffic, return
    losses and path_change_rate for each."""
    out = {}
    fns = make_route_fns(None)
    for label in ["core", "conga", "drill"]:
        G = builder(seed); reset(G)
        nodes = list(G.nodes())
        traf = gen_bursty(nodes, n_steps, seed + 100000)
        r = run_instrumented(G, traf, fns[label])
        out[label] = r
    return out


# ---------- main: stability across SNDlib topologies ----------
LOW = ["nobel-us", "polska", "atlanta", "nobel-eu", "cost266", "janos-us", "zib54"]
HIGH = ["india35", "pioro40", "giul39", "newyork", "di-yuan", "dfn-gwin"]
N_SEEDS = 5


def _builder(topo):
    import sndlib_parse as SND
    G0, _ = SND.load(topo)
    mapping = {n: i for i, n in enumerate(G0.nodes())}
    def builder(seed):
        G = nx.Graph(G0); rng = random.Random(seed)
        for u, v in G.edges():
            G[u][v]['latency'] = rng.uniform(1, 5)
            G[u][v]['capacity'] = rng.randint(2, 4)
            G[u][v]['load'] = 0; G[u][v]['loss'] = 0
        return nx.relabel_nodes(G, mapping)
    return builder


def run_band(topos, label):
    print(f"\n--- {label} tube/sp ---")
    print(f"{'topo':<11}{'core':>8}{'conga':>8}{'drill':>8}")
    rows = []
    for topo in topos:
        b = _builder(topo)
        acc = {"core": 0.0, "conga": 0.0, "drill": 0.0}
        for s in range(N_SEEDS):
            r = measure_topo(b, s)
            for k in acc:
                acc[k] += r[k]["path_change_rate"]
        for k in acc:
            acc[k] /= N_SEEDS
        rows.append({"topo": topo, **acc})
        print(f"{topo:<11}{acc['core']:>8.3f}{acc['conga']:>8.3f}{acc['drill']:>8.3f}")
    return rows


if __name__ == "__main__":
    print("=== P3 POSITIVE CONTROL (first) ===")
    if not positive_control():
        print("Control failed -- voided."); sys.exit(0)
    low = run_band(LOW, "LOW (core loses on drop)")
    high = run_band(HIGH, "HIGH (core wins on drop)")
    def bmean(rows):
        return {k: float(np.mean([r[k] for r in rows]))
                for k in ["core", "conga", "drill"]}
    lm, hm = bmean(low), bmean(high)
    print("\n=== VERDICT vs pre-registered predictions ===")
    print(f"LOW  pcr: core={lm['core']:.3f} conga={lm['conga']:.3f} drill={lm['drill']:.3f}")
    print(f"HIGH pcr: core={hm['core']:.3f} conga={hm['conga']:.3f} drill={hm['drill']:.3f}")
    print(f"P1 core<DRILL in LOW by>=0.10: diff={lm['drill']-lm['core']:+.3f} "
          f"-> {'PASS' if lm['drill']-lm['core']>=0.10 else 'FAIL'}")
    print(f"core vs CONGA in LOW: core-conga={lm['core']-lm['conga']:+.3f}")
    out = {"control": True, "low": low, "high": high, "low_mean": lm, "high_mean": hm}
    json.dump(out, open("/home/clopez/emmet/data/flow_stability.json","w"), indent=2)
    print("\nsaved data/flow_stability.json")
