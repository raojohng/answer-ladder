"""Does what the agent does in its first five tool calls predict the outcome of the try?

    python3 analysis/early_predictor.py          (needs numpy and data/stages_all.csv; no GPU)

Features are not privileged: counts from the first five calls plus the length of the task statement (see trajectory_stages.py).
Fitted on the plain v8 scaffold's tries on training and FreshSWE-Py tasks (runs v8_sweep, fresh_v8_p1). Two checks:
  1. leave-repositories-out: 5 folds, every repository wholly in one fold;
  2. frozen model on the untrained scaffold's 258 tries on the 86 official tasks (other repositories, run later).
Reported per target (solved; first applied edit on the reference lines): AUC, Brier score against a constant-rate predictor,
an issue-length-only model, and the within-task AUC (solved against failed tries of the same task only), which removes task difficulty.
"""
import collections, csv, random
import numpy as np

FEATURES = ["e_find", "e_read", "e_edit", "e_other", "e_distinct", "e_repeat", "e_nomatch", "e_errors", "e_files_read",
            "e_find_hits", "e_issue_overlap", "e_think_chars", "e_minute", "issue_chars", "calls_lt5"]
LOG = {"e_find_hits", "e_think_chars", "issue_chars"}

def load():
    rows = [r for r in csv.DictReader(open("data/stages_all.csv")) if r["crash"] == "0"]
    for r in rows:
        r["calls_lt5"] = int(int(r["calls"]) < 5)
        r["y_solved"] = int(r["solved"]); r["y_first"] = int(r["first_applied_gold_lines"] == "1")
    return rows

def matrix(rows, names, stats=None):
    X = np.array([[float(r[n]) if r[n] != "" else np.nan for n in names] for r in rows])
    for j, n in enumerate(names):
        if n in LOG: X[:, j] = np.log1p(X[:, j])
    if stats is None:
        med = np.nanmedian(X, axis=0); X = np.where(np.isnan(X), med, X)
        stats = (med, X.mean(axis=0), X.std(axis=0) + 1e-9)
    med, mean, sd = stats
    X = np.where(np.isnan(X), med, X)
    return np.c_[np.ones(len(X)), (X - mean) / sd], stats

def fit(X, y, l2=1.0, steps=400):
    w = np.zeros(X.shape[1])
    for _ in range(steps):                               # Newton steps for L2 logistic regression
        p = 1 / (1 + np.exp(-X @ w)); g = X.T @ (p - y) + l2 * np.r_[0, w[1:]]
        H = (X * (p * (1 - p))[:, None]).T @ X + l2 * np.diag(np.r_[0, np.ones(len(w) - 1)])
        step = np.linalg.solve(H, g); w -= step
        if np.abs(step).max() < 1e-8: break
    return w

def auc(p, y):
    order = np.argsort(p); ranks = np.empty(len(p)); ranks[order] = np.arange(1, len(p) + 1)
    for v in np.unique(p):                                # average ranks of ties
        m = p == v; ranks[m] = ranks[m].mean()
    n1 = y.sum(); n0 = len(y) - n1
    return float((ranks[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)) if n1 and n0 else float("nan")

def within(p, y, tasks):
    wins = pairs = 0.0
    groups = collections.defaultdict(list)
    for i, t in enumerate(tasks): groups[t].append(i)
    for idx in groups.values():
        pos = [i for i in idx if y[i] == 1]; neg = [i for i in idx if y[i] == 0]
        for a in pos:
            for b in neg:
                pairs += 1; wins += 1.0 if p[a] > p[b] else 0.5 if p[a] == p[b] else 0.0
    return wins / pairs if pairs else float("nan"), int(pairs)

def report(label, p, y, tasks, base):
    w, n = within(p, y, tasks)
    print(f"  {label:28s} AUC {auc(p, y):.3f} | Brier {np.mean((p - y) ** 2):.4f} (constant {np.mean((base - y) ** 2):.4f}) | within-task AUC {w:.3f} over {n} pairs")

def main():
    rows = load()
    train = [r for r in rows if r["run"] in ("v8_sweep", "fresh_v8_p1")]
    test = [r for r in rows if r["run"] == "place1_test86" and r["arm"] == "e4b_edit_fair_v1"]
    repos = sorted({r["repo"] for r in train}); random.Random(20261111).shuffle(repos)
    fold = {repo: i % 5 for i, repo in enumerate(repos)}
    print(f"train {len(train)} tries, {len({r['task'] for r in train})} tasks, {len(repos)} repositories; official test {len(test)} tries, {len({r['task'] for r in test})} tasks")
    for target, name in (("y_solved", "the try is solved"), ("y_first", "the first applied edit is on the reference lines")):
        y = np.array([r[target] for r in train], float); tasks = [r["task"] for r in train]
        print(f"\nTarget: {name} (train rate {y.mean():.1%})")
        for label, names in (("issue length only", ["issue_chars"]), ("first five calls", FEATURES)):
            p = np.zeros(len(train))
            for f in range(5):
                tr = np.array([fold[r["repo"]] != f for r in train]); te = ~tr
                Xtr, stats = matrix([r for r, m in zip(train, tr) if m], names)
                Xte, _ = matrix([r for r, m in zip(train, te) if m], names, stats)
                p[te] = 1 / (1 + np.exp(-Xte @ fit(Xtr, y[tr])))
            report(f"held-out repositories, {label}", p, y, tasks, np.full(len(y), y.mean()))
        X, stats = matrix(train, FEATURES); w = fit(X, y)
        Xt, _ = matrix(test, FEATURES, stats); yt = np.array([r[target] for r in test], float)
        pt = 1 / (1 + np.exp(-Xt @ w))
        report("official tasks, frozen model", pt, yt, [r["task"] for r in test], np.full(len(yt), y.mean()))
        top = np.argsort(-np.abs(w[1:]))[:6]
        print("  largest standardised weights:", ", ".join(f"{FEATURES[j]} {w[1 + j]:+.2f}" for j in top))
        q = np.quantile(pt, [1 / 3, 2 / 3])
        for lab, m in (("lowest third", pt <= q[0]), ("middle third", (pt > q[0]) & (pt <= q[1])), ("highest third", pt > q[1])):
            print(f"    official tries, {lab} of predicted chance: {int(m.sum())} tries, actual {yt[m].mean():.0%}")

if __name__ == "__main__":
    main()
