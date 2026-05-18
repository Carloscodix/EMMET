"""EQUIVALENCE experiment — the heart of the reframed paper.

Falsifiable claim: the pure physical core (gradient + Newton-III, two terms,
no mass) is STATISTICALLY EQUIVALENT to engineered routers (CONGA, DRILL)
across a span of topologies, and tube/sp predicts when equivalence holds.

Equivalence tested with TOST (two one-sided tests), margin delta = 2pp drop-rate.
NOT mere interval overlap. Flow world (flowsim).
"""
import sys, json, itertools
from pathlib import Path
import numpy as np
from scipy import stats
sys.path.insert(0, '/home/clopez/emmet/experiments')
import emmet_budget
from emmet_budget import reset
from topology_builders import build_grid, build_barabasi_albert, build_watts_strogatz
from real_traffic import build_geant_real
import flowsim as FS

N_SEEDS = 20
DELTA = 0.02   # equivalence margin: 2 percentage points of drop-rate


TOPOS = [
    ('Grid5', lambda s: build_grid(5, s), 'unif'),
    ('Grid6', lambda s: build_grid(6, s), 'unif'),
    ('Grid7', lambda s: build_grid(7, s), 'unif'),
    ('Grid8', lambda s: build_grid(8, s), 'unif'),
    ('Grid10', lambda s: build_grid(10, s), 'unif'),
    ('Grid12', lambda s: build_grid(12, s), 'unif'),
    ('WS_n30_k4', lambda s: build_watts_strogatz(30, 4, 0.1, s), 'unif'),
    ('WS_n50_k4', lambda s: build_watts_strogatz(50, 4, 0.1, s), 'unif'),
    ('WS_n50_k6', lambda s: build_watts_strogatz(50, 6, 0.1, s), 'unif'),
    ('WS_n80_k4', lambda s: build_watts_strogatz(80, 4, 0.1, s), 'unif'),
    ('BA_n50_m2', lambda s: build_barabasi_albert(50, 2, s), 'unif'),
    ('BA_n50_m3', lambda s: build_barabasi_albert(50, 3, s), 'unif'),
    ('BA_n80_m2', lambda s: build_barabasi_albert(80, 2, s), 'unif'),
    ('GEANT', None, 'real'),
    ('Abilene', None, 'abilene'),
]


def unif_demand(G):
    """Uniform demand: every ordered node pair weight 1."""
    nodes = list(G.nodes())
    return {(a, b): 1.0 for a in nodes for b in nodes if a != b}

def build_topo(name, builder, dsrc, seed, cap=(2, 4)):
    """Return (G, idx_demand) with capacity scheme applied."""
    import random as _r
    if dsrc == 'real':
        G, dem = build_geant_real(seed, cap_lo=cap[0], cap_hi=cap[1])
        # fail the trunk link to create stress, as in the resilience study
        if G.has_edge(0, 2): G.remove_edge(0, 2)
        return G, dem
    if dsrc == 'abilene':
        # FIX (audit 9-jun): this entry used to fall into the dsrc=='real'
        # branch above, so the bench built GEANT twice under two names.
        # Load the real Abilene graph; same capacity scheme as the bench.
        import networkx as _nx
        from emmet_budget import TOPO as _TOPO
        G = _nx.Graph(_nx.read_graphml(str(_TOPO / 'Abilene.graphml')))
        G = _nx.relabel_nodes(G, {n: i for i, n in enumerate(G.nodes())})
        rng = _r.Random(seed)
        for u, v in G.edges():
            G[u][v]['latency'] = rng.uniform(1, 5)
            G[u][v]['capacity'] = rng.randint(cap[0], cap[1])
            G[u][v]['load'] = 0; G[u][v]['loss'] = 0
        return G, unif_demand(G)
    G = builder(seed)
    rng = _r.Random(seed)
    for u, v in G.edges():
        G[u][v]['latency'] = rng.uniform(1, 5)
        G[u][v]['capacity'] = rng.randint(cap[0], cap[1])
        G[u][v]['load'] = 0; G[u][v]['loss'] = 0
    return G, unif_demand(G)


def tost(a, b, delta):
    """Two One-Sided Tests for equivalence of two paired samples a,b.
    Returns (equivalent_bool, p_value). Equivalent if mean diff within +-delta
    at 95%. Uses paired differences."""
    d = np.array(a) - np.array(b)
    n = len(d)
    md = d.mean(); sd = d.std(ddof=1)
    if sd == 0:
        return (abs(md) < delta, 0.0)
    se = sd / np.sqrt(n)
    # H0a: diff <= -delta ; H0b: diff >= +delta. Reject both => equivalent.
    t_lower = (md - (-delta)) / se
    t_upper = (md - delta) / se
    p_lower = 1 - stats.t.cdf(t_lower, n-1)   # P(T > t_lower)
    p_upper = stats.t.cdf(t_upper, n-1)        # P(T < t_upper)
    p = max(p_lower, p_upper)
    return (p < 0.05, float(p))


def run_topo(args):
    name, builder, dsrc = args
    core, conga, drill = [], [], []
    for s in range(N_SEEDS):
        G, dem = build_topo(name, builder, dsrc, s)
        sched = FS.gen_flows(dem, 200, s+9000, birth_rate=0.8, dur_lo=4, dur_hi=12, rate=1)
        G, _ = build_topo(name, builder, dsrc, s); reset(G)
        core.append(FS.simulate_flows(G, sched, 200, FS.policy_emmet_core)['drop_rate'])
        G, _ = build_topo(name, builder, dsrc, s); reset(G)
        conga.append(FS.simulate_flows(G, sched, 200, FS.policy_conga)['drop_rate'])
        G, _ = build_topo(name, builder, dsrc, s); reset(G)
        drill.append(FS.simulate_flows(G, sched, 200, FS.policy_drill)['drop_rate'])
    ec, pc = tost(core, conga, DELTA)
    ed, pd = tost(core, drill, DELTA)
    return {'topo': name, 'core': float(np.mean(core)), 'conga': float(np.mean(conga)), 'drill': float(np.mean(drill)), 'eq_conga': ec, 'p_conga': pc, 'eq_drill': ed, 'p_drill': pd}


def main():
    emmet_budget.GAMMA = 2.0
    results = [run_topo(t) for t in TOPOS]
    Path('/home/clopez/emmet/data/equivalence_raw.json').write_text(json.dumps(results, indent=2))
    print(f"{'topo':<11}{'core':>7}{'CONGA':>7}{'DRILL':>7}  {'eqCONGA':>8}{'eqDRILL':>8}")
    print('-'*52)
    nc = nd = 0
    for r in results:
        ec = 'YES' if r['eq_conga'] else 'no'
        ed = 'YES' if r['eq_drill'] else 'no'
        nc += r['eq_conga']; nd += r['eq_drill']
        print(f"{r['topo']:<11}{r['core']:>7.3f}{r['conga']:>7.3f}{r['drill']:>7.3f}  {ec:>8}{ed:>8}")
    print('-'*52)
    print(f"Equivalent (TOST, delta={DELTA}): {nc}/{len(results)} vs CONGA, {nd}/{len(results)} vs DRILL")

if __name__ == '__main__':
    main()
