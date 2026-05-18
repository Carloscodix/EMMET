"""Topology sweep: tube/sp vs Ripple-over-CONGA advantage."""
import sys, json, time, math, random
from pathlib import Path
from multiprocessing import Pool, cpu_count
sys.path.insert(0, '/home/clopez/emmet/experiments')
import networkx as nx
import emmet_budget
from emmet_budget import build_real, reset
from topology_builders import build_grid, build_barabasi_albert, build_watts_strogatz
from bursty_traffic import gen_bursty
from bursty_warmup import warmup_bursty_momentum
from bursty_runner import run_bursty_conga, run_bursty_emmet_live_ripple

N_SEEDS = 20
GAMMA_OPT = 0.5
BR_OPT = 10.0
RIPPLE = 0.3
RIPPLE_STEPS = 3
ALPHA = 1.25

# (name, builder, args) -- builder called as builder(*args, seed)
TOPOS = [
    ('Grid5',     build_grid, (5,)),
    ('Grid6',     build_grid, (6,)),
    ('Grid7',     build_grid, (7,)),
    ('Grid8',     build_grid, (8,)),
    ('Grid10',    build_grid, (10,)),
    ('Grid12',    build_grid, (12,)),
    ('WS_n30_k4', build_watts_strogatz, (30, 4, 0.1)),
    ('WS_n50_k4', build_watts_strogatz, (50, 4, 0.1)),
    ('WS_n50_k6', build_watts_strogatz, (50, 6, 0.1)),
    ('WS_n80_k4', build_watts_strogatz, (80, 4, 0.1)),
    ('BA_n50_m2', build_barabasi_albert, (50, 2)),
    ('BA_n50_m3', build_barabasi_albert, (50, 3)),
    ('BA_n80_m2', build_barabasi_albert, (80, 2)),
    ('GEANT',     build_real, ('Geant.graphml',)),
    ('Abilene',   build_real, ('Abilene.graphml',)),
]

def tube_sp(G, max_pairs=400, seed=0):
    """Mean (tube width / shortest-path length) over sampled pairs."""
    nodes = list(G.nodes())
    rng = random.Random(seed)
    pairs = [(a, b) for i, a in enumerate(nodes) for b in nodes[i+1:]]
    if len(pairs) > max_pairs:
        pairs = rng.sample(pairs, max_pairs)
    ratios = []
    edges = list(G.edges())
    for s, t in pairs:
        ds = nx.single_source_shortest_path_length(G, s)
        dt = nx.single_source_shortest_path_length(G, t)
        if t not in ds:
            continue
        sp = ds[t]
        cutoff = math.ceil(ALPHA * sp)
        w = 0
        for u, v in edges:
            if (ds[u] + 1 + dt[v] <= cutoff) or (ds[v] + 1 + dt[u] <= cutoff):
                w += 1
        ratios.append(w / max(sp, 1))
    return sum(ratios) / len(ratios) if ratios else 0.0

def run_seed(args):
    name, builder, bargs, seed = args
    out = {'topo': name, 'seed': seed}
    G = builder(*bargs, seed=seed)
    ws = max(20, G.number_of_nodes() * 5)
    G1 = builder(*bargs, seed=seed); reset(G1)
    tr1 = gen_bursty(list(G1.nodes()), 200, seed + 100000)
    out['CONGA'] = run_bursty_conga(G1, tr1)['losses']
    emmet_budget.GAMMA = GAMMA_OPT
    G2 = builder(*bargs, seed=seed); reset(G2)
    wt = gen_bursty(list(G2.nodes()), ws, seed + 700000)
    snap = warmup_bursty_momentum(G2, wt, 1.0, 32)
    G3 = builder(*bargs, seed=seed); reset(G3)
    tr3 = gen_bursty(list(G3.nodes()), 200, seed + 100000)
    out['RIPPLE'] = run_bursty_emmet_live_ripple(G3, tr3, snap, 1.0, 32, blood_rate=BR_OPT, ripple=RIPPLE, ripple_steps=RIPPLE_STEPS)['losses']
    emmet_budget.GAMMA = 2.0
    return out

def main():
    t0 = time.time()
    print("Computing tube/sp...", flush=True)
    tube = {}; meta = {}
    for name, builder, bargs in TOPOS:
        G = builder(*bargs, seed=0)
        tube[name] = tube_sp(G)
        meta[name] = {'n': G.number_of_nodes(), 'edges': G.number_of_edges()}
        print(f"  {name}: tube/sp={tube[name]:.2f} n={meta[name]['n']}", flush=True)
    jobs = [(name, builder, bargs, s) for name, builder, bargs in TOPOS for s in range(N_SEEDS)]
    print(f"Running {len(jobs)} bursty jobs...", flush=True)
    with Pool(max(1, cpu_count() - 4)) as pool:
        results = pool.map(run_seed, jobs)
    out = {'tube': tube, 'meta': meta, 'runs': results, 'n_seeds': N_SEEDS}
    Path('/home/clopez/emmet/data/sweep_topologies_raw.json').write_text(json.dumps(out, indent=2))
    print(f"Saved. Total {(time.time()-t0)/60:.1f} min", flush=True)

if __name__ == '__main__':
    main()
