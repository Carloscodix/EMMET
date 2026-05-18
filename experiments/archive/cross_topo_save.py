"""Cross-topology bursty test POST-CODEX with per-seed raw data save.

Same logic as blood_session/blood_final_v2.py but stores losses per
seed (not sums) so we can compute bootstrap CI 95% later.
"""
import sys, json, time
from pathlib import Path
sys.path.insert(0, '/home/clopez/emmet/experiments')
import emmet_budget
from emmet_budget import build_real, reset
from topology_builders import build_grid, build_watts_strogatz
from bursty_traffic import gen_bursty
from bursty_warmup import (warmup_bursty_lasp, warmup_bursty_momentum)
from bursty_runner import (run_bursty_lasp, run_bursty_conga,
                            run_bursty_emmet, run_bursty_emmet_live,
                            run_bursty_emmet_live_delayed)

STEPS = 200
N = 30
GAMMA_OPT = 0.5
BR_OPT = 10.0
BR_DEF = 5.0

TOPOS = [
    ('GEANT',   lambda s: build_real('Geant.graphml', s)),
    ('Abilene', lambda s: build_real('Abilene.graphml', s)),
    ('Grid7x7', lambda s: build_grid(7, s)),
    ('WS_n50',  lambda s: build_watts_strogatz(50, 4, 0.1, s)),
    ('Grid10',  lambda s: build_grid(10, s)),
]

ARMS = ['LASP', 'CONGA', 'v1', 'LIVE_def', 'DELAY_def', 'LIVE_opt', 'DELAY_opt']

def run_one_seed(builder, s):
    out = {}
    # Reset GAMMA at start of each seed
    emmet_budget.GAMMA = 2.0
    ws = max(20, builder(s).number_of_nodes() * 5)

    # LASP (GAMMA=2.0)
    G = builder(s); reset(G)
    wt = gen_bursty(list(G.nodes()), ws, s + 700000)
    snap_l = warmup_bursty_lasp(G, wt)
    G2 = builder(s); reset(G2)
    traf = gen_bursty(list(G2.nodes()), STEPS, s + 100000)
    out['LASP'] = run_bursty_lasp(G2, traf, snap_l)['losses']

    # CONGA (no snap)
    G3 = builder(s); reset(G3)
    traf3 = gen_bursty(list(G3.nodes()), STEPS, s + 100000)
    out['CONGA'] = run_bursty_conga(G3, traf3)['losses']

    # GAMMA=2.0 family: v1, LIVE_def, DELAY_def
    G4 = builder(s); reset(G4)
    wt4 = gen_bursty(list(G4.nodes()), ws, s + 700000)
    snap_m = warmup_bursty_momentum(G4, wt4, 1.0, 32)
    G5 = builder(s); reset(G5)
    traf5 = gen_bursty(list(G5.nodes()), STEPS, s + 100000)
    out['v1'] = run_bursty_emmet(G5, traf5, snap_m, 1.0, 32)['losses']
    G6 = builder(s); reset(G6)
    traf6 = gen_bursty(list(G6.nodes()), STEPS, s + 100000)
    out['LIVE_def'] = run_bursty_emmet_live(G6, traf6, snap_m, 1.0, 32, blood_rate=BR_DEF)['losses']
    G7 = builder(s); reset(G7)
    traf7 = gen_bursty(list(G7.nodes()), STEPS, s + 100000)
    out['DELAY_def'] = run_bursty_emmet_live_delayed(G7, traf7, snap_m, 1.0, 32, blood_rate=BR_DEF)['losses']

    # GAMMA=0.5 family: LIVE_opt, DELAY_opt
    emmet_budget.GAMMA = GAMMA_OPT
    G8 = builder(s); reset(G8)
    wt8 = gen_bursty(list(G8.nodes()), ws, s + 700000)
    snap_o = warmup_bursty_momentum(G8, wt8, 1.0, 32)
    G9 = builder(s); reset(G9)
    traf9 = gen_bursty(list(G9.nodes()), STEPS, s + 100000)
    out['LIVE_opt'] = run_bursty_emmet_live(G9, traf9, snap_o, 1.0, 32, blood_rate=BR_OPT)['losses']
    G10 = builder(s); reset(G10)
    traf10 = gen_bursty(list(G10.nodes()), STEPS, s + 100000)
    out['DELAY_opt'] = run_bursty_emmet_live_delayed(G10, traf10, snap_o, 1.0, 32, blood_rate=BR_OPT)['losses']
    emmet_budget.GAMMA = 2.0  # RESTORE
    return out


def main():
    results = []
    t0 = time.time()
    for topo_name, builder in TOPOS:
        print(f"--- {topo_name} ---", flush=True)
        for s in range(N):
            r = run_one_seed(builder, s)
            r['topo'] = topo_name
            r['seed'] = s
            results.append(r)
            if (s + 1) % 5 == 0:
                el = (time.time() - t0) / 60
                print(f"  seed {s+1}/{N} | elapsed {el:.1f}m", flush=True)
    out_path = Path('/home/clopez/emmet/data/cross_topo_bursty_raw.json')
    json.dump(results, open(out_path, 'w'), indent=2)
    print(f"Saved {out_path}")
    print(f"Total elapsed: {(time.time()-t0)/60:.1f} min")


if __name__ == '__main__':
    main()
