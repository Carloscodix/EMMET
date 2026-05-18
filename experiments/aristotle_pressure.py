"""
aristotle_pressure.py - does the gear-mesh saving bite under saturation?

The smoke test said: Archimedes... no, Aristotle cuts wasted capacity but the
saving didn't convert to fewer drops, because the network was near-empty.

Hypothesis: capacity recovered by good mesh only matters when capacity is the
bottleneck. So we sweep increasing pressure (shrinking capacities) and watch
whether the drop gap (congestion - aristotle) grows as the network saturates.

Reuses the smoke's engine verbatim; only the harness changes.
"""
import numpy as np
import aristotle_smoke as A


def run_pressure(cap_scale, n_seeds=10, n_pkts=400):
    """Lower cap_scale = tighter capacities = more saturation."""
    out = {m: [] for m in ('shortest', 'congestion', 'aristotle')}
    waste = {m: [] for m in ('congestion', 'aristotle')}
    for seed in range(n_seeds):
        G = A.build_graph(30, seed)
        # squeeze the bottleneck: scale every capacity down
        for u, v in G.edges():
            G[u][v]['capacity'] = max(60, int(G[u][v]['capacity'] * cap_scale))
        dem = A.gen_demand(G, n_pkts, seed)
        for mode in ('shortest', 'congestion', 'aristotle'):
            r = A.simulate(G, dem, mode)
            out[mode].append(r['drop_rate'])
            if mode in waste:
                waste[mode].append(r['waste_frac'])
    return out, waste


if __name__ == '__main__':
    print("Pressure sweep: shrinking capacity until the network hurts.")
    print(f"{'cap_scale':>9} | {'short':>7} {'cong':>7} {'arist':>7} | "
          f"{'gap(c-a)':>9} | {'wasteCut':>8}")
    print('-' * 64)
    rows = []
    for cs in [1.0, 0.6, 0.45, 0.35, 0.28, 0.22, 0.18]:
        out, waste = run_pressure(cs)
        s = np.mean(out['shortest']); c = np.mean(out['congestion']); a = np.mean(out['aristotle'])
        gap = c - a
        wc = np.mean(waste['congestion']) - np.mean(waste['aristotle'])
        rows.append((cs, s, c, a, gap, wc))
        print(f"{cs:>9.2f} | {s:>7.4f} {c:>7.4f} {a:>7.4f} | {gap:>+9.4f} | {wc:>+8.4f}")
    print('-' * 64)
    # verdict: does the drop gap grow as we saturate?
    gaps = [r[4] for r in rows]
    drops_cong = [r[2] for r in rows]
    print("\n=== READING ===")
    print(f"max congestion drop_rate reached: {max(drops_cong):.3f} "
          f"({'saturated enough' if max(drops_cong) > 0.05 else 'STILL TOO EMPTY - push harder'})")
    print(f"drop gap (cong - arist): min {min(gaps):+.4f}, max {max(gaps):+.4f}")
    # is the gap meaningfully positive at high pressure (last 3 rows)?
    high = gaps[-3:]
    if max(drops_cong) <= 0.05:
        print("-> network never saturated; verdict inconclusive, need harder squeeze.")
    elif np.mean(high) > 0.01:
        print("-> under saturation Aristotle DOES cut drops: the mesh saving bites. REAL payoff.")
    elif np.mean(high) > 0.003:
        print("-> weak positive under saturation: marginal, needs the full bench to confirm.")
    else:
        print("-> even saturated, no drop payoff: HONEST NEGATIVE. Mesh saves waste, not drops.")
