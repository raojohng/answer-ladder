"""Confidence-gated graph hint: push the hint only when the code graph and embeddings say it is coherent. No reference answer is
used to build or gate a hint; the reference only labels dev tasks (hint covers the reference lines or not) and scores test tasks.

Signals of the five hinted nodes (the graph hint of graph_hint.py, weights a = b = 0.25):
  graph_links   share of the 10 node pairs within two call-graph hops of each other
  emb_agree     mean pairwise cosine of the five nodes' embeddings, centred on the repository mean
  file_conc     share of the five nodes in their most common file
  margin        (score of node 1 - score of node 6) / score of node 1
  top_score     score of node 1
Selection on the 52 dev tasks only: the signal with the highest AUC for "hint covers the reference lines", then the threshold that
maximises (dev hints kept that are right - dev hints kept that are wrong). Then on the 77 test tasks: offline correctness of kept
hints, and the agent's solves per pass if each task gets the graph hint when gated in and the control text otherwise, taken from the
interleaved graph arms (control and graph-hint arms of each run given), with paired task-bootstrap intervals.
    python3 -I gate.py <competition data> <dev ids> <test ids> <out dir> <stages.csv>[,<stages.csv>...]
"""
import collections, csv, json, multiprocessing, random, sys
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
ARGS = sys.argv
sys.argv = ARGS[:5]
import graph_hint as gh

DEV, TEST, OUT = open(ARGS[2]).read().split(), open(ARGS[3]).read().split(), Path(ARGS[4])
STAGES = ARGS[5].split(",")
A = B = 0.25


def signals(item):
    tid, f = item
    top = gh.rank(f, A, B)
    s = f["text"] + A * np.array([np.mean(f["text"][f["nb"][i]]) if f["nb"].get(i) else 0.0 for i in range(len(f["text"]))])
    best = np.argsort(f["text"])[::-1][:gh.NEAR]; w = f["text"][best]
    if w.sum() > 0:
        s = s + B * (f["E"] @ (f["E"][best].T @ w)) / w.sum()
    order = [i for i in np.argsort(s)[::-1] if s[i] > 0]
    nb = {k: set(v) for k, v in f["nb"].items()}
    two = lambda i: nb.get(i, set()) | {m for n in nb.get(i, set()) for m in nb.get(n, set())}
    pairs = [(i, j) for k, i in enumerate(top) for j in top[k + 1:]]
    Ec = f["E"] - f["E"].mean(axis=0, keepdims=True)
    Ec /= np.maximum(np.linalg.norm(Ec, axis=1, keepdims=True), 1e-9)
    files = collections.Counter(f["where"][i][0] for i in top)
    sig = {"graph_links": np.mean([j in two(i) for i, j in pairs]) if pairs else 0.0,
           "emb_agree": float(np.mean([Ec[i] @ Ec[j] for i, j in pairs])) if pairs else 0.0,
           "file_conc": files.most_common(1)[0][1] / max(len(top), 1),
           "margin": float((s[order[0]] - s[order[5]]) / s[order[0]]) if len(order) > 5 else 1.0,
           "top_score": float(s[order[0]]) if order else 0.0}
    return tid, sig, bool(f["line_hit"][top].any()) if top else False


def auc(xs, ys):
    pos = [x for x, y in zip(xs, ys) if y]; neg = [x for x, y in zip(xs, ys) if not y]
    return np.mean([(p > n) + 0.5 * (p == n) for p in pos for n in neg]) if pos and neg else 0.5


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    with multiprocessing.Pool(8) as pool:
        feats = dict(pool.map(gh.features, DEV + TEST))
        rows = {tid: (sig, hit) for tid, sig, hit in pool.map(signals, feats.items())}
    lines = []
    say = lambda s: (print(s), lines.append(s))
    names = list(next(iter(rows.values()))[0])
    dev_y = [rows[t][1] for t in DEV]
    say(f"Dev {len(DEV)} tasks, hint right on {sum(dev_y)}; test {len(TEST)} tasks, hint right on {sum(rows[t][1] for t in TEST)}.")
    aucs = {n: auc([rows[t][0][n] for t in DEV], dev_y) for n in names}
    test_aucs = {n: auc([rows[t][0][n] for t in TEST], [rows[t][1] for t in TEST]) for n in names}
    for n in names:
        say(f"  {n:12s} AUC for 'hint is right': dev {aucs[n]:.2f} | test {test_aucs[n]:.2f}")
    pick = max(names, key=aucs.get)
    cands = sorted({rows[t][0][pick] for t in DEV})
    net = lambda th: sum((1 if rows[t][1] else -1) for t in DEV if rows[t][0][pick] >= th)
    th = max(cands, key=lambda c: (net(c), -c))
    kept = [t for t in TEST if rows[t][0][pick] >= th]
    say(f"Chosen on dev: {pick} >= {th:.3f} (dev: keeps {sum(rows[t][0][pick] >= th for t in DEV)} hints, "
        f"{sum(rows[t][1] for t in DEV if rows[t][0][pick] >= th)} right).")
    say(f"Test: keeps {len(kept)} of {len(TEST)} hints, {sum(rows[t][1] for t in kept)} right "
        f"({100 * np.mean([rows[t][1] for t in kept]):.0f}%; all hints: {100 * np.mean([rows[t][1] for t in TEST]):.0f}%).")
    json.dump({"signal": pick, "threshold": th, "kept": kept, "signals": {t: rows[t][0] for t in DEV + TEST},
               "right": {t: rows[t][1] for t in DEV + TEST}}, open(OUT / "gate.json", "w"), indent=1)
    # agent outcome, from interleaved control and graph-hint arms
    for path in STAGES:
        by = collections.defaultdict(lambda: collections.defaultdict(list))
        for r in csv.DictReader(open(path)):
            if r["arm"] in ("e4b_loc_ctrl_v1", "e4b_ghint_v1"):
                by[r["arm"]][r["task"]].append(r["solved"] == "1")
        ts = [t for t in TEST if t in by["e4b_loc_ctrl_v1"] and t in by["e4b_ghint_v1"]]
        if not ts:
            continue
        rate = lambda arm, t: np.mean(by[arm][t])
        ctrl = lambda T: sum(rate("e4b_loc_ctrl_v1", t) for t in T)
        always = lambda T: sum(rate("e4b_ghint_v1", t) for t in T)
        gated = lambda T: sum(rate("e4b_ghint_v1" if t in kept else "e4b_loc_ctrl_v1", t) for t in T)
        random.seed(1)
        smp = [[random.choice(ts) for _ in ts] for _ in range(2000)]
        say(f"{Path(path).name}: {len(ts)} tasks, solves per pass: control {ctrl(ts):.1f} | hint always {always(ts):.1f} | gated hint {gated(ts):.1f}")
        for name, a, b in (("gated - control", gated, ctrl), ("gated - always", gated, always), ("always - control", always, ctrl)):
            d = sorted(a(s) - b(s) for s in smp)
            say(f"    {name}: {a(ts) - b(ts):+.1f} ({d[50]:+.1f} to {d[1949]:+.1f})")
    open(OUT / "gate.txt", "w").write("\n".join(lines) + "\n")
    print("GATE_DONE")
