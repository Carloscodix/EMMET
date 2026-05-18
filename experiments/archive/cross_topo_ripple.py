"""Cross-topology bursty test with RIPPLE arms.

Adds RIPPLE_def and RIPPLE_opt to the standard cross-topo test.
RIPPLE = Archimedes-scaled blood + temporal wave (ripple=0.3, steps=3).
Same seeds and warmup as cross_topo_save.py for paired comparison.
"""
import sys, json, time
from pathlib import Path
sys.path.insert(0, '/home/clopez/emmet/experiments')
import emmet_budget
from emmet_budget import build_real, reset
from topology_builders import build_grid, build_watts_strogatz
from bursty_traffic import gen_bursty
from bursty_warmup import warmup_bursty_lasp, warmup_bursty_momentum
from bursty_runner import (run_bursty_lasp, run_bursty_conga,
                            run_bursty_emmet, run_bursty_emmet_live,
                            run_bursty_emmet_live_delayed,
                            run_bursty_emmet_live_ripple)

STEPS = 200
N = 30
GAMMA_OPT = 0.5
BR_OPT = 10.0
BR_DEF = 5.0
RIPPLE = 0.3
RIPPLE_STEPS = 3

TOPOS = [
    ('GEANT',   lambda s: build_real('Geant.graphml', s)),
    ('Abilene', lambda s: build_real('Abilene.graphml', s)),
    ('Grid7x7', lambda s: build_grid(7, s)),
    ('WS_n50',  lambda s: build_watts_strogatz(50, 4, 0.1, s)),
    ('Grid10',  lambda s: build_grid(10, s)),
]

def run_one_seed(builder, s):
    out = {}
    emmet_budget.GAMMA = 2.0
    ws = max(20, builder(s).number_of_nodes() * 5)

    # GAMMA=2.0 family
    G4 = builder(s); reset(G4)
    wt4 = gen_bursty(list(G4.nodes()), ws, s + 700000)
    snap_m = warmup_bursty_momentum(G4, wt4, 1.0, 32)

    G6 = builder(s); reset(G6)
    traf6 = gen_bursty(list(G6.nodes()), STEPS, s + 100000)
    out['DELAY_def'] = run_bursty_emmet_live_delayed(G6, traf6, snap_m, 1.0, 32, blood_rate=BR_DEF)['losses']

    G7 = builder(s); reset(G7)
    traf7 = gen_bursty(list(G7.nodes()), STEPS, s + 100000)
    out['RIPPLE_def'] = run_bursty_emmet_live_ripple(G7, traf7, snap_m, 1.0, 32, blood_rate=BR_DEF, ripple=RIPPLE, ripple_steps=RIPPLE_STEPS)['losses']

    # GAMMA=0.5 family (Lopt regime)
    emmet_budget.GAMMA = GAMMA_OPT
    G8 = builder(s); reset(G8)
    wt8 = gen_bursty(list(G8.nodes()), ws, s + 700000)
    snap_o = warmup_bursty_momentum(G8, wt8, 1.0, 32)

    G10 = builder(s); reset(G10)
    traf10 = gen_bursty(list(G10.nodes()), STEPS, s + 100000)
    out['DELAY_opt'] = run_bursty_emmet_live_delayed(G10, traf10, snap_o, 1.0, 32, blood_rate=BR_OPT)['losses']

    G11 = builder(s); reset(G11)
    traf11 = gen_bursty(list(G11.nodes()), STEPS, s + 100000)
    out['RIPPLE_opt'] = run_bursty_emmet_live_ripple(G11, traf11, snap_o, 1.0, 32, blood_rate=BR_OPT, ripple=RIPPLE, ripple_steps=RIPPLE_STEPS)['losses']

    emmet_budget.GAMMA = 2.0  # restore
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
    out_path = Path('/home/clopez/emmet/data/cross_topo_ripple_raw.json')
    json.dump(results, open(out_path, 'w'), indent=2)
    print(f"Saved {out_path}")
    print(f"Total elapsed: {(time.time()-t0)/60:.1f} min")


if __name__ == '__main__':
    main()
