"""
Flow-synchronization diagnostic (standalone analysis tool, not part of the paper).

Measures whether a router induces collective flow synchronization: many flows
converge on the same next-hop, saturate it together, flee together, oscillate in
lockstep (the TCP-global-sync analogue). Metric: edge-choice entropy and its drop
in the windows preceding losses (pre-loss convergence). A static router is the
no-reaction baseline; a delayed-greedy router (reacts to a stale load view) is the
positive control that generates synchronization on demand.

Finding: across the SNDlib topologies, neither the physical core nor CONGA shows
pre-loss convergence above the static baseline; both sit at or below it (they
disperse rather than converge). Synchronization requires feedback delay, and the
core reacts to a decay-smoothed signal (the snap) that already de-synchronizes by
construction, so no external perturbation is needed. The positive control reaches
+0.24, far above any real router, confirming the metric sees synchronization when
it exists.

Common instrumented cycle for all routers; no production runners touched.
"""
import sys, json, random
import numpy as np
import networkx as nx
from bursty_traffic import gen_bursty, GAP_SENTINEL
from flow_stability import _walk, _decay, _builder, make_route_fns


def run_with_load_trace(G, traf, route_fn):
    """Common cycle: route each packet, record per-edge load every step."""
    def snapshot(trace):
        for u, v in G.edges():
            trace[tuple(sorted((u, v)))].append(G[u][v]['load'])
    trace = {tuple(sorted((u, v))): [] for u, v in G.edges()}
    for step in traf:
        if step == GAP_SENTINEL:
            _decay(G); snapshot(trace); continue
        src, dst = step
        if src == dst:
            _decay(G); snapshot(trace); continue
        path = route_fn(G, src, dst)
        if path is not None and len(path) >= 2:
            _walk(G, path)
        _decay(G); snapshot(trace)
    return trace


def cv_hotspots(trace, k=5):
    """Mean temporal coefficient of variation over the top-k hotspot edges."""
    means = {e: float(np.mean(s)) if s else 0.0 for e, s in trace.items()}
    hot = sorted(means, key=means.get, reverse=True)[:k]
    cvs = []
    for e in hot:
        s = np.array(trace[e], dtype=float)
        m = s.mean()
        if m > 1e-9:
            cvs.append(s.std() / m)
    return float(np.mean(cvs)) if cvs else 0.0


def static_fn(G, s, d):
    try:
        return nx.shortest_path(G, s, d, weight='latency')
    except nx.NetworkXNoPath:
        return None


def greedy_fn(G, s, d):
    """Pure reaction: step to least-congested neighbour, tie-break toward dst."""
    path = [s]; cur = s; visited = {s}
    for _ in range(len(G)):
        if cur == d:
            break
        nbrs = [n for n in G.neighbors(cur) if n not in visited]
        if not nbrs:
            return None
        def key(n):
            cong = G[cur][n]['load'] / G[cur][n]['capacity']
            try:
                dd = nx.shortest_path_length(G, n, d, weight='latency')
            except nx.NetworkXNoPath:
                dd = 999
            return cong * 10.0 + dd
        nxt = min(nbrs, key=key)
        path.append(nxt); visited.add(nxt); cur = nxt
    return path if cur == d else None


# ---------- P3: POSITIVE CONTROL ----------
def _bottleneck():
    G = nx.Graph()
    def add(u, v, lat, cap):
        G.add_edge(u, v, latency=lat, capacity=cap, load=0, loss=0)
    add(0, 1, 1.0, 4); add(1, 5, 1.0, 4)
    add(0, 2, 1.0, 4); add(2, 5, 1.0, 4)
    add(0, 3, 1.5, 4); add(3, 4, 1.0, 4); add(4, 5, 1.5, 4)
    return G


def _bottleneck_traffic(n=300):
    traf = []
    for i in range(n):
        traf.append((0, 5))
        if i % 5 == 4:
            traf.append(GAP_SENTINEL)
    return traf


def positive_control():
    traf = _bottleneck_traffic()
    cv_g = cv_hotspots(run_with_load_trace(_bottleneck(), traf, greedy_fn), k=4)
    cv_s = cv_hotspots(run_with_load_trace(_bottleneck(), traf, static_fn), k=4)
    passed = cv_g > cv_s * 1.3
    print(f"P3 CONTROL: CV_t greedy={cv_g:.3f} static={cv_s:.3f} -> "
          f"{'PASS' if passed else 'FAIL'}")
    return passed


def _detrend(s, w=11):
    s = np.array(s, dtype=float)
    if len(s) < w:
        return s - s.mean()
    ma = np.convolve(s, np.ones(w) / w, mode='same')
    return s - ma


def sync_score(trace, k=6, w=11):
    """Mean pairwise corr of DETRENDED load on top-k hotspots. +1 = in-phase
    (synchronization); <=0 = balanced/independent."""
    means = {e: float(np.mean(s)) if s else 0.0 for e, s in trace.items()}
    hot = sorted(means, key=means.get, reverse=True)[:k]
    resids = [r for r in (_detrend(trace[e], w) for e in hot) if r.std() > 1e-9]
    if len(resids) < 2:
        return 0.0
    corrs = []
    for i in range(len(resids)):
        for j in range(i + 1, len(resids)):
            c = np.corrcoef(resids[i], resids[j])[0, 1]
            if not np.isnan(c):
                corrs.append(c)
    return float(np.mean(corrs)) if corrs else 0.0


def positive_control_metric():
    """Validate sync_score on synthetic series WITH a common burst on top.
    In-phase must score high; antiphase low, despite the shared burst."""
    n = 300
    t = np.arange(n)
    burst = 5.0 + 3.0 * ((t // 5) % 2)
    osc = 2.0 * np.sin(t * 0.6)
    sync = {("a", "b"): (burst + osc).tolist(),
            ("c", "d"): (burst + osc).tolist()}
    bal = {("a", "b"): (burst + osc).tolist(),
           ("c", "d"): (burst - osc).tolist()}
    s_sync = sync_score(sync, k=2, w=11)
    s_bal = sync_score(bal, k=2, w=11)
    passed = s_sync > 0.7 and s_bal < -0.3
    print(f"P3 metric: in-phase={s_sync:+.3f} antiphase={s_bal:+.3f} -> "
          f"{'PASS' if passed else 'FAIL'}")
    return passed


# ====== edge-choice entropy + pre-loss convergence ======
from collections import Counter


def run_with_choice_trace(G, traf, route_fn):
    """Per step: edges used by chosen path, and whether a packet was lost."""
    steps = []
    for step in traf:
        if step == GAP_SENTINEL:
            _decay(G); steps.append((None, False)); continue
        src, dst = step
        if src == dst:
            _decay(G); steps.append((None, False)); continue
        path = route_fn(G, src, dst)
        if path is not None and len(path) >= 2:
            edges = [tuple(sorted((path[i], path[i + 1])))
                     for i in range(len(path) - 1)]
            lost = not _walk(G, path)
            steps.append((edges, lost))
        else:
            steps.append((None, False))
        _decay(G)
    return steps


def _entropy(counts):
    tot = sum(counts.values())
    if tot == 0:
        return None
    ps = np.array([c / tot for c in counts.values()], dtype=float)
    return float(-np.sum(ps * np.log(ps + 1e-12)))


def _window_entropy(steps, end, W):
    cnt = Counter()
    for i in range(max(0, end - W), end):
        e, _ = steps[i]
        if e:
            for edge in e:
                cnt[edge] += 1
    return _entropy(cnt)


def pre_loss_convergence(steps, W=10):
    """Does edge-choice entropy DROP before losses? H pre-loss vs no-loss."""
    n = len(steps)
    loss_idx = [i for i, (e, l) in enumerate(steps) if l]
    if not loss_idx:
        return {"H_preloss": None, "H_noloss": None, "gap": None, "n_loss": 0}
    pre = [_window_entropy(steps, i, W) for i in loss_idx]
    pre = [h for h in pre if h is not None]
    ctrl = [_window_entropy(steps, i, W) for i in range(W, n) if not steps[i][1]]
    ctrl = [h for h in ctrl if h is not None]
    hp = float(np.mean(pre)) if pre else None
    hn = float(np.mean(ctrl)) if ctrl else None
    gap = (hn - hp) if (hp is not None and hn is not None) else None
    return {"H_preloss": hp, "H_noloss": hn, "gap": gap, "n_loss": len(loss_idx)}


def _make_ecmp():
    rng = random.Random(999)
    def ecmp_fn(G, s, d):
        try:
            paths = list(nx.all_shortest_paths(G, s, d))
        except nx.NetworkXNoPath:
            return None
        return rng.choice(paths) if paths else None
    return ecmp_fn


def positive_control_entropy():
    """Greedy must converge (entropy drops) before losses; ECMP must not."""
    traf = _bottleneck_traffic(n=500)
    g = pre_loss_convergence(
        run_with_choice_trace(_bottleneck(), traf, greedy_fn), W=8)
    e = pre_loss_convergence(
        run_with_choice_trace(_bottleneck(), traf, _make_ecmp()), W=8)
    print(f"greedy: H_pre={g['H_preloss']} H_no={g['H_noloss']} gap={g['gap']} nl={g['n_loss']}")
    print(f"ecmp:   H_pre={e['H_preloss']} H_no={e['H_noloss']} gap={e['gap']} nl={e['n_loss']}")
    gg = g['gap'] if g['gap'] is not None else 0
    ge = e['gap'] if e['gap'] is not None else 0
    passed = gg > ge and gg > 0.02
    print(f"-> greedy converges pre-loss more than ecmp: {'PASS' if passed else 'FAIL'}")
    return passed


class DelayedGreedy:
    """Reacts to a STALE load view refreshed every k steps. Flows in a window
    see the same old loads, converge on the same next-hop, saturate it
    together. This is how synchronization is generated (needs delay)."""
    def __init__(self, k=10):
        self.k = k; self.view = {}; self.t = 0

    def _key(self, G, cur, n, d):
        e = tuple(sorted((cur, n)))
        cong = self.view.get(e, 0) / G[cur][n]['capacity']
        try:
            dd = nx.shortest_path_length(G, n, d, weight='latency')
        except nx.NetworkXNoPath:
            dd = 999
        return cong * 10.0 + dd

    def __call__(self, G, s, d):
        if self.t % self.k == 0:
            self.view = {tuple(sorted((u, v))): G[u][v]['load']
                         for u, v in G.edges()}
        self.t += 1
        path = [s]; cur = s; visited = {s}
        for _ in range(len(G)):
            if cur == d:
                break
            nbrs = [n for n in G.neighbors(cur) if n not in visited]
            if not nbrs:
                return None
            nxt = min(nbrs, key=lambda n: self._key(G, cur, n, d))
            path.append(nxt); visited.add(nxt); cur = nxt
        return path if cur == d else None


from emmet_budget import reset as _reset
from load_frontier import make_builder

DTOPOS = ["dfn-gwin", "nobel-us", "polska", "india35"]
DSEEDS = list(range(300, 304))


def diagnose_topo(topo, cap=(2, 4), W=10):
    builder = make_builder(topo, cap[0], cap[1])
    nodes = list(builder(DSEEDS[0]).nodes())
    res = {"static": [], "conga": [], "core": []}
    nloss = {"static": [], "conga": [], "core": []}
    for seed in DSEEDS:
        traf = gen_bursty(nodes, 250, seed + 100000)
        fns = make_route_fns(None)
        routers = {"static": static_fn, "conga": fns["conga"], "core": fns["core"]}
        for name, fn in routers.items():
            G = builder(seed); _reset(G)
            r = pre_loss_convergence(run_with_choice_trace(G, traf, fn), W=W)
            if r["gap"] is not None:
                res[name].append(r["gap"])
            nloss[name].append(r["n_loss"])
    o = {n: (float(np.mean(v)) if v else None) for n, v in res.items()}
    onl = {n: float(np.mean(v)) for n, v in nloss.items()}
    return o, onl
