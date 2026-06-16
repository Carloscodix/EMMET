"""
Bench G: alternative structural predictors.

Is tube/sp the best structural predictor of where the physical core gains, or
do standard graph metrics (betweenness, Fiedler, mean degree, density, a
hub-aware ratio) predict it better? If tube/sp wins or ties, our choice is
justified; if another wins, we say so and switch.

Positive control: tube/sp must reproduce its known in-sample correlation with
reduction% through this pipeline before we trust the comparison.
"""
import sys, json
sys.path.insert(0, "/home/clopez/emmet/experiments")
import numpy as np
import networkx as nx
from scipy import stats
from collections import defaultdict
from equivalence import build_topo, TOPOS
from sweep_topologies import tube_sp


def load_target():
    d = json.load(open("/home/clopez/emmet/data/sweep_topologies_raw.json"))
    agg = defaultdict(lambda: {"C": 0, "R": 0})
    for r in d["runs"]:
        agg[r["topo"]]["C"] += r["CONGA"]; agg[r["topo"]]["R"] += r["RIPPLE"]
    red = {}
    for topo in d["tube"]:
        c, rr = agg[topo]["C"], agg[topo]["R"]
        red[topo] = (c - rr) / c * 100 if c > 0 else 0
    return red


def predictors(G):
    n = G.number_of_nodes(); m = G.number_of_edges()
    bet = np.mean(list(nx.betweenness_centrality(G).values()))
    lap = nx.normalized_laplacian_matrix(G).toarray()
    ev = np.sort(np.linalg.eigvalsh(lap))
    fiedler = float(ev[1])
    deg = 2 * m / n
    dens = m / (n * (n - 1) / 2)
    degs = [d for _, d in G.degree()]
    hub = float(np.max(degs) / np.mean(degs))
    return {"betweenness": bet, "fiedler": fiedler, "mean_degree": deg,
            "density": dens, "hub_ratio": hub}


def main():
    red = load_target()
    names = [n for n, _, _ in TOPOS]
    tube = {}; preds = defaultdict(dict)
    for name, builder, bargs in TOPOS:
        G = build_topo(name, builder, bargs, 0)[0]
        tube[name] = tube_sp(G)
        for k, v in predictors(G).items():
            preds[k][name] = v
    use = [n for n in names if n != "Abilene"]
    y = np.array([red[n] for n in use])
    x_tube = np.array([tube[n] for n in use])
    r_tube, p_tube = stats.pearsonr(x_tube, y)
    s_tube, _ = stats.spearmanr(x_tube, y)
    print(f"[control] tube/sp ~ reduction: Pearson {r_tube:+.3f} (p={p_tube:.4f}) Spearman {s_tube:+.3f}")
    gate = abs(r_tube) > 0.5
    print(f"[control] gate (|r|>0.5): {'PASS' if gate else 'FAIL'}\n")
    rows = [("tube_sp", r_tube, s_tube)]
    for k in preds:
        xk = np.array([preds[k][n] for n in use])
        rk, _ = stats.pearsonr(xk, y); sk, _ = stats.spearmanr(xk, y)
        rows.append((k, rk, sk))
    rows.sort(key=lambda t: -abs(t[1]))
    print(f"{'predictor':<14}{'Pearson':>10}{'Spearman':>10}")
    for k, rk, sk in rows:
        star = "  <-- tube/sp" if k == "tube_sp" else ""
        print(f"{k:<14}{rk:>+10.3f}{sk:>+10.3f}{star}")
    winner = rows[0][0]
    print(f"\nbest |Pearson|: {winner}")
    ym, tubem, fiedm = multivariate_check()
    base = loo_rmse([tubem], ym); biv = loo_rmse([tubem, fiedm], ym)
    print(f"[multivariate] LOO-RMSE tube {base:.2f} | tube+fiedler {biv:.2f} ({'generalizes' if biv<base else 'overfit'})")
    json.dump({"control_r": r_tube, "winner": winner,
               "ranking": [(k, rk, sk) for k, rk, sk in rows]},
              open("/home/clopez/emmet/data/bench_g.json", "w"), indent=2)



def multivariate_check():
    red = load_target()
    use = [n for n, _, _ in TOPOS if n != "Abilene"]
    y = np.array([red[n] for n in use])
    data = {}
    for name, builder, bargs in TOPOS:
        if name == "Abilene":
            continue
        G = build_topo(name, builder, bargs, 0)[0]
        data.setdefault("tube", {})[name] = tube_sp(G)
        for k, v in predictors(G).items():
            data.setdefault(k, {})[name] = v
    tube = np.array([data["tube"][n] for n in use])
    fied = np.array([data["fiedler"][n] for n in use])
    return y, tube, fied


def loo_rmse(cols, y):
    n = len(y); errs = []
    for i in range(n):
        tr = [j for j in range(n) if j != i]
        X = np.column_stack([np.ones(n)] + cols)
        beta, *_ = np.linalg.lstsq(X[tr], y[tr], rcond=None)
        errs.append((y[i] - X[i] @ beta) ** 2)
    return float(np.sqrt(np.mean(errs)))


if __name__ == "__main__":
    main()
