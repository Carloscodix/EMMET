"""
Bench H: electrical baseline -- a fourth independent physical witness.

If a current-flow (Ohm's-law) router lands in the attractor basin -- high
cosine with the momentum cores, near the phys-phys level and well above the
blind ECMP floor -- then the attractor is not a quirk of one mechanism but a
structural pull that an unrelated physical family also obeys.

Positive control: phys-phys cosine must reproduce its known ~0.98 in this
pipeline before we trust the electrical numbers.
"""
import sys, json, math
sys.path.insert(0, "/home/clopez/emmet/experiments")
import numpy as np
import flowsim as FS
import physics_cores as PC
from electrical_policy import policy_electrical
from equivalence import build_topo, TOPOS
from attractor_full import cosine, l1_sim
from sweep_topologies import tube_sp
from emmet_budget import reset

PHYS = ["newton", "archimedes", "pascal"]
N_SEEDS = 8


def get_policy(name):
    if name == "electrical":
        return policy_electrical
    if name == "ecmp":
        return FS.policy_ecmp
    return PC.make_physics_policy(name)


def util_for(name, builder, dsrc, seed, router, sched):
    G, _ = build_topo(name, builder, dsrc, seed); reset(G)
    fs = router in PHYS
    return FS.simulate_flows_util(G, sched, 200, get_policy(router), feed_scar=fs)["util"]


def run_topo(name, builder, dsrc):
    routers = PHYS + ["electrical", "ecmp"]
    util = {r: [] for r in routers}
    tubes = []
    for s in range(N_SEEDS):
        G0, dem = build_topo(name, builder, dsrc, s)
        tubes.append(tube_sp(G0))
        sched = FS.gen_flows(dem, 200, s + 9000, birth_rate=0.8, dur_lo=4, dur_hi=12, rate=1)
        for r in routers:
            util[r].append(util_for(name, builder, dsrc, s, r, sched))
    return util, float(np.mean(tubes))


def cosines(util):
    def pm(ra, rb):
        v = [cosine(util[ra][s], util[rb][s]) for s in range(N_SEEDS)]
        v = [x for x in v if not math.isnan(x)]
        return float(np.mean(v)) if v else float("nan")
    pp = np.mean([pm(a, b) for i, a in enumerate(PHYS) for b in PHYS[i+1:]])
    pelec = np.mean([pm(a, "electrical") for a in PHYS])
    pecmp = np.mean([pm(a, "ecmp") for a in PHYS])
    return float(pp), float(pelec), float(pecmp)


def main():
    rows = []
    print(f"{'topo':<12}{'phys-phys':>10}{'phys-elec':>10}{'phys-ecmp':>10}")
    for name, builder, bargs in TOPOS:
        util, tube = run_topo(name, builder, bargs)
        pp, pe, pc = cosines(util)
        rows.append({"topo": name, "tube_sp": tube, "phys_phys": pp,
                     "phys_elec": pe, "phys_ecmp": pc})
        print(f"{name:<12}{pp:>10.3f}{pe:>10.3f}{pc:>10.3f}", flush=True)
    pp_mean = np.mean([r["phys_phys"] for r in rows])
    pe_mean = np.mean([r["phys_elec"] for r in rows])
    pc_mean = np.mean([r["phys_ecmp"] for r in rows])
    print(f"\n[control] phys-phys mean = {pp_mean:.3f} (gate >0.9: {'PASS' if pp_mean>0.9 else 'FAIL'})")
    print(f"electrical cosine with cores: {pe_mean:.3f}")
    print(f"blind ECMP floor:             {pc_mean:.3f}")
    midpoint = (pp_mean + pc_mean) / 2
    verdict = "IN the attractor basin" if pe_mean > midpoint else "closer to blind floor"
    print(f"\nverdict: electrical is {verdict} (midpoint {midpoint:.3f})")
    json.dump({"rows": rows, "phys_phys": pp_mean, "phys_elec": pe_mean,
               "phys_ecmp": pc_mean}, open("/home/clopez/emmet/data/bench_h.json", "w"), indent=2)


if __name__ == "__main__":
    main()
