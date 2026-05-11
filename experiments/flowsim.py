"""FLOW simulator — the 'flight field' for wake/Blob/flocking ideas.

Key difference vs the packet-bullet model: a FLOW is an entity that is
born, LIVES for D steps injecting load r on its current route each step,
then dies and releases its load. Flows create corridors that PERSIST,
giving directional-wake / Blob / flocking the substrate they need.

A flow: {src, dst, rate, ttl_left, route}. Each tick:
  - new flows may be born (demand-weighted)
  - each live flow injects `rate` onto each edge of its route
  - congestion = load/capacity as usual; overloaded edges drop (count loss)
  - flows age; dead flows release their load
Routing policy decides each flow's route at birth (and optionally re-routes).
"""
import sys, random, math
sys.path.insert(0, '/home/clopez/emmet/experiments')
import networkx as nx


def gen_flows(idx_demand, n_ticks, seed, birth_rate=0.8, dur_lo=4, dur_hi=12,
              rate=1):
    """Schedule of flow births. Returns dict tick -> list of (src,dst,dur,rate).
    Pairs sampled proportional to real demand (like gen_bursty_real)."""
    pairs = list(idx_demand.keys())
    weights = [idx_demand[p] for p in pairs]
    rng = random.Random(seed)
    sched = {}
    for t in range(n_ticks):
        # number of flows born this tick ~ Poisson-ish via birth_rate
        n_born = 0
        x = birth_rate
        while x > 0:
            if rng.random() < min(x, 1.0):
                n_born += 1
            x -= 1.0
        births = []
        for _ in range(n_born):
            s, d = rng.choices(pairs, weights=weights, k=1)[0]
            dur = rng.randint(dur_lo, dur_hi)
            births.append((s, d, dur, rate))
        if births:
            sched[t] = births
    return sched


def _apply_flow_load(G, flows):
    """Reset edge load, then sum the rate of every live flow on its route."""
    for u, v in G.edges():
        G[u][v]['load'] = 0
    for fl in flows:
        r = fl['route']
        for i in range(len(r) - 1):
            G[r[i]][r[i+1]]['load'] += fl['rate']


def simulate_flows(G, sched, n_ticks, route_fn, reroute=False):
    """Run the flow simulation.
    route_fn(G, src, dst, state) -> path (state = mutable dict for memory).
    reroute=True lets live flows recompute path each tick (flow-following)."""
    flows = []
    state = {}
    served_ticks = 0
    drop_ticks = 0
    born = 0
    for t in range(n_ticks):
        for (s, d, dur, rate) in sched.get(t, []):
            path = route_fn(G, s, d, state)
            if path and len(path) >= 2:
                flows.append({'src': s, 'dst': d, 'rate': rate,
                              'ttl': dur, 'route': path})
                born += 1
        if reroute:
            for fl in flows:
                p = route_fn(G, fl['src'], fl['dst'], state)
                if p and len(p) >= 2:
                    fl['route'] = p
        _apply_flow_load(G, flows)
        for fl in flows:
            r = fl['route']; hit = False
            for i in range(len(r) - 1):
                if G[r[i]][r[i+1]]['load'] > G[r[i]][r[i+1]]['capacity']:
                    hit = True; break
            if hit: drop_ticks += 1
            else:    served_ticks += 1
        for fl in flows:
            fl['ttl'] -= 1
        flows = [fl for fl in flows if fl['ttl'] > 0]
    total = served_ticks + drop_ticks
    return {'born': born, 'served_ticks': served_ticks,
            'drop_ticks': drop_ticks, 'total_ticks': total,
            'drop_rate': drop_ticks / total if total else 0.0}


# ---- routing policies wrapped as route_fn(G, src, dst, state) ----

def policy_shortest(G, src, dst, state):
    try:
        return nx.shortest_path(G, src, dst, weight='latency')
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return None

def policy_drill(G, src, dst, state):
    from baselines_extra import drill_route
    if 'rng' not in state:
        state['rng'] = random.Random(7777)
    p, _ = drill_route(G, src, dst, state['rng'], m=2)
    return p


def policy_emmet(G, src, dst, state):
    """Gradient + blood core (the proven EMMET). Blood lives in state['snap']."""
    from emmet_momentum_dp import emmet_momentum_dp_route, M_MAX, ALPHA_BUDGET
    if 'snap' not in state:
        state['snap'] = {}
    p, _ = emmet_momentum_dp_route(G, src, dst, state['snap'], kappa=0.3,
                                   m_max=M_MAX, alpha_budget=ALPHA_BUDGET,
                                   n_buckets=32)
    return p


def policy_ecmp(G, src, dst, state):
    from baselines_extra import ecmp_route
    if 'rng_e' not in state:
        state['rng_e'] = random.Random(5555)
    p, _ = ecmp_route(G, src, dst, state['rng_e'])
    return p

def policy_conga(G, src, dst, state):
    from conga_wan import conga_wan_route
    p = conga_wan_route(G, src, dst, k=4)
    return p[0] if isinstance(p, tuple) else p


def make_wake_policy(mode='evade', gain=1.0):
    """route_fn with directional-wake memory. mode='evade' routes AROUND
    others' wakes (parallel corridors); 'follow' routes ALONG them."""
    from emmet_momentum_dp import emmet_momentum_dp_route, M_MAX, ALPHA_BUDGET
    def route_fn(G, src, dst, state):
        wf = state.setdefault('wf', {})
        wb = state.setdefault('wb', {})
        snap = state.setdefault('snap', {})
        bias = dict(snap)
        for k in set(list(wf.keys()) + list(wb.keys())):
            mag = wf.get(k, 0.0) + wb.get(k, 0.0)
            bias[k] = bias.get(k, 0.0) + (gain*mag if mode=='evade' else -gain*mag)
        p, _ = emmet_momentum_dp_route(G, src, dst, bias, kappa=0.3,
                                       m_max=M_MAX, alpha_budget=ALPHA_BUDGET,
                                       n_buckets=32)
        return p
    return route_fn


def simulate_flows_wake(G, sched, n_ticks, route_fn, wake_decay=0.7, deposit=1.0):
    """Blob: live flows feed directional wake each tick, then re-route reading it."""
    flows = []; state = {}
    served = drop = born = 0
    for t in range(n_ticks):
        for (s, d, dur, rate) in sched.get(t, []):
            path = route_fn(G, s, d, state)
            if path and len(path) >= 2:
                flows.append({'src': s,'dst': d,'rate': rate,'ttl': dur,'route': path}); born += 1
        wf = state.setdefault('wf', {}); wb = state.setdefault('wb', {})
        for dd in (wf, wb):
            for k in list(dd.keys()): dd[k] *= wake_decay
        for fl in flows:
            r = fl['route']
            for i in range(len(r)-1):
                u,v = r[i], r[i+1]; k = tuple(sorted([u,v]))
                if u < v: wf[k] = wf.get(k,0.0)+deposit
                else:     wb[k] = wb.get(k,0.0)+deposit
        for fl in flows:
            p = route_fn(G, fl['src'], fl['dst'], state)
            if p and len(p) >= 2: fl['route'] = p
        _apply_flow_load(G, flows)
        for fl in flows:
            r = fl['route']; hit = any(G[r[i]][r[i+1]]['load'] > G[r[i]][r[i+1]]['capacity'] for i in range(len(r)-1))
            if hit: drop += 1
            else:   served += 1
        for fl in flows: fl['ttl'] -= 1
        flows = [fl for fl in flows if fl['ttl'] > 0]
    total = served + drop
    return {'born': born,'served_ticks': served,'drop_ticks': drop,
            'total_ticks': total,'drop_rate': drop/total if total else 0.0}


def _route_maxcong(G, route):
    """Max congestion along a route (for hysteresis comparison)."""
    if not route or len(route) < 2:
        return float('inf')
    return max(G[route[i]][route[i+1]]['load'] / G[route[i]][route[i+1]]['capacity']
               for i in range(len(route)-1))


def simulate_flows_wake_tamed(G, sched, n_ticks, route_fn, wake_decay=0.7,
                              deposit=1.0, reroute_frac=0.2, hysteresis=0.15,
                              seed=0):
    """Tamed Blob: async reroute (only a fraction of flows per tick) + hysteresis
    (a flow switches route only if the new one improves max-congestion by >=
    hysteresis). Cures the synchronous-oscillation epileptic-flock failure."""
    import random as _r
    rng = _r.Random(seed + 333)
    flows = []; state = {}
    served = drop = born = 0
    for t in range(n_ticks):
        for (s, d, dur, rate) in sched.get(t, []):
            path = route_fn(G, s, d, state)
            if path and len(path) >= 2:
                flows.append({'src': s,'dst': d,'rate': rate,'ttl': dur,'route': path}); born += 1
        wf = state.setdefault('wf', {}); wb = state.setdefault('wb', {})
        for dd in (wf, wb):
            for k in list(dd.keys()): dd[k] *= wake_decay
        for fl in flows:
            r = fl['route']
            for i in range(len(r)-1):
                u,v = r[i], r[i+1]; k = tuple(sorted([u,v]))
                if u < v: wf[k] = wf.get(k,0.0)+deposit
                else:     wb[k] = wb.get(k,0.0)+deposit
        _apply_flow_load(G, flows)   # current load, for hysteresis comparison
        for fl in flows:
            if rng.random() >= reroute_frac:
                continue   # async: this flow doesn't re-evaluate this tick
            p = route_fn(G, fl['src'], fl['dst'], state)
            if p and len(p) >= 2:
                old_c = _route_maxcong(G, fl['route'])
                new_c = _route_maxcong(G, p)
                if new_c <= old_c - hysteresis:   # only switch if real improvement
                    fl['route'] = p
        _apply_flow_load(G, flows)   # re-apply after the few reroutes
        for fl in flows:
            r = fl['route']; hit = any(G[r[i]][r[i+1]]['load'] > G[r[i]][r[i+1]]['capacity'] for i in range(len(r)-1))
            if hit: drop += 1
            else:   served += 1
        for fl in flows: fl['ttl'] -= 1
        flows = [fl for fl in flows if fl['ttl'] > 0]
    total = served + drop
    return {'born': born,'served_ticks': served,'drop_ticks': drop,
            'total_ticks': total,'drop_rate': drop/total if total else 0.0}


def simulate_flows_util(G, sched, n_ticks, route_fn, reroute=False,
                        feed_scar=False, scar_deposit=1.0, scar_decay=0.998):
    """Like simulate_flows but also returns per-edge mean utilization vector.

    feed_scar=True deposits/decays the Newton-III scar exactly like
    simulate_flows_scar, so a scar-reading core (newton) runs with its memory
    alive. Cores that do not read scars are unaffected. Default False preserves
    the original behaviour for all existing callers."""
    flows = []; state = {'scars': {}} if feed_scar else {}
    scars = state.get('scars') if feed_scar else None
    served = drop = born = 0
    edges = list(G.edges())
    util_sum = {tuple(sorted(e)): 0.0 for e in edges}
    nt = 0
    for t in range(n_ticks):
        for (s, d, dur, rate) in sched.get(t, []):
            path = route_fn(G, s, d, state)
            if path and len(path) >= 2:
                flows.append({'src': s,'dst': d,'rate': rate,'ttl': dur,'route': path}); born += 1
        if reroute:
            for fl in flows:
                p = route_fn(G, fl['src'], fl['dst'], state)
                if p and len(p) >= 2: fl['route'] = p
        _apply_flow_load(G, flows)
        for u, v in edges:
            util_sum[tuple(sorted((u,v)))] += G[u][v]['load'] / G[u][v]['capacity']
        nt += 1
        for fl in flows:
            r = fl['route']; bad = None
            for i in range(len(r)-1):
                if G[r[i]][r[i+1]]['load'] > G[r[i]][r[i+1]]['capacity']:
                    bad = (r[i], r[i+1]); break
            if bad is not None:
                drop += 1
                if feed_scar:
                    k = tuple(sorted(bad)); scars[k] = scars.get(k, 0.0) + scar_deposit
            else:
                served += 1
        if feed_scar:
            for k in list(scars.keys()):
                scars[k] *= scar_decay
                if scars[k] < 1e-6: del scars[k]
        for fl in flows: fl['ttl'] -= 1
        flows = [fl for fl in flows if fl['ttl'] > 0]
    total = served + drop
    util = {k: util_sum[k]/nt for k in util_sum}
    return {'drop_rate': drop/total if total else 0.0, 'util': util}


def policy_emmet_core(G, src, dst, state):
    """PURE physical core: gradient + Newton-III (blood), NO mass (kappa=0).
    The two-term claim. P = alpha*dist + beta*cong + gamma*blood."""
    from emmet_momentum_dp import emmet_momentum_dp_route, M_MAX, ALPHA_BUDGET
    if 'snap' not in state:
        state['snap'] = {}
    p, _ = emmet_momentum_dp_route(G, src, dst, state['snap'], kappa=0.0,
                                   m_max=M_MAX, alpha_budget=ALPHA_BUDGET,
                                   n_buckets=32)
    return p


def make_conga_policy(k=4):
    """CONGA with configurable path budget K (for fair-comparison audit)."""
    from conga_wan import conga_wan_route
    def route_fn(G, src, dst, state):
        p = conga_wan_route(G, src, dst, k=k)
        return p[0] if isinstance(p, tuple) else p
    return route_fn


# ---------------------------------------------------------------------------
# simulate_flows_scar: like simulate_flows, but feeds a Newton-III scar field
# in state['scars'] on every dropped tick (and decays it each tick), so a
# physics_cores 'newton' core runs with its memory ALIVE - the fair way to put
# Newton on the same K16 bench as Archimedes/Pascal.
# ---------------------------------------------------------------------------
def simulate_flows_scar(G, sched, n_ticks, route_fn, scar_deposit=1.0,
                        scar_decay=0.998):
    flows = []
    state = {'scars': {}}
    scars = state['scars']
    served_ticks = drop_ticks = born = 0
    for t in range(n_ticks):
        for (s, d, dur, rate) in sched.get(t, []):
            path = route_fn(G, s, d, state)
            if path and len(path) >= 2:
                flows.append({'src': s, 'dst': d, 'rate': rate,
                              'ttl': dur, 'route': path})
                born += 1
        _apply_flow_load(G, flows)
        for fl in flows:
            r = fl['route']; hit = False; bad = None
            for i in range(len(r) - 1):
                if G[r[i]][r[i+1]]['load'] > G[r[i]][r[i+1]]['capacity']:
                    hit = True; bad = (r[i], r[i+1]); break
            if hit:
                drop_ticks += 1
                k = tuple(sorted(bad))
                scars[k] = scars.get(k, 0.0) + scar_deposit  # Newton III reaction
            else:
                served_ticks += 1
        # decay scars once per tick (fade when not refreshed)
        for k in list(scars.keys()):
            scars[k] *= scar_decay
            if scars[k] < 1e-6:
                del scars[k]
        for fl in flows:
            fl['ttl'] -= 1
        flows = [fl for fl in flows if fl['ttl'] > 0]
    total = served_ticks + drop_ticks
    return {'born': born, 'served_ticks': served_ticks,
            'drop_ticks': drop_ticks, 'total_ticks': total,
            'drop_rate': drop_ticks / total if total else 0.0}
