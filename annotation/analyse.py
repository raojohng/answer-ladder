"""Results of the annotation study (GUIDE.md). Run after both annotators finished:  python3 analyse.py   (from annotation/)

Inputs: labels_A/<task>.json (annotator A, all 20 tasks), labels_B.json (annotator B, 8 tasks), locations_mechanical.json
(function of the first changed line of each final-patch hunk), key_DO_NOT_READ_until_labelled.json (verdicts).
Writes results.json and prints the tables."""
import collections, glob, itertools, json, os, random

A = {os.path.basename(f)[:-5]: json.load(open(f)) for f in glob.glob("labels_A/*.json")}
B = json.load(open("labels_B.json"))
LOC = json.load(open("locations_mechanical.json"))
KEY = json.load(open("key_DO_NOT_READ_until_labelled.json"))
ORDER = ["no patch", "different location", "same location, different diagnosis",
         "same location and diagnosis, different implementation", "unclear"]


def category(task, f, s, labels):
    lf, ls = set(LOC[task][f]), set(LOC[task][s])
    if not lf:
        return "no patch"
    if not lf & ls:
        return "different location"
    df, ds = labels[f]["diagnosis_id"], labels[s]["diagnosis_id"]
    if "unknown" in (df, ds) or df.startswith("unknown") or ds.startswith("unknown"):
        return "unclear"
    if df != ds:
        return "same location, different diagnosis"
    if labels[f]["implementation_id"] != labels[s]["implementation_id"]:
        return "same location and diagnosis, different implementation"
    return "unclear"


def pairs(task):
    k = KEY[task]
    return [(f, s) for f in k for s in k if not k[f]["solved"] and k[s]["solved"]]


def shares(labels_by_task, tasks):
    out = {}
    for t in tasks:
        ps = pairs(t)
        c = collections.Counter(category(t, f, s, labels_by_task[t]) for f, s in ps)
        out[t] = {cat: c[cat] / len(ps) for cat in ORDER}
    return out


def summary(per_task, seed=1):
    tasks = sorted(per_task)
    random.seed(seed)
    res = {}
    for cat in ORDER:
        vals = [per_task[t][cat] for t in tasks]
        boots = sorted(sum(random.choice(vals) for _ in vals) / len(vals) for _ in range(4000))
        res[cat] = (sum(vals) / len(vals), boots[100], boots[3899])
    return res


tasks = sorted(A)
n_pairs = sum(len(pairs(t)) for t in tasks)
print(f"{len(tasks)} tasks, {sum(len(KEY[t]) for t in tasks)} tries "
      f"({sum(v['solved'] for t in tasks for v in KEY[t].values())} solved), {n_pairs} failed-solved pairs")
main = summary(shares(A, tasks))
print("\nPrimary: failed-solved pairs by category, task-weighted (annotator A, 20 tasks; 95% task bootstrap)")
for cat in ORDER:
    m, lo, hi = main[cat]
    print(f"  {cat:56s} {100 * m:5.1f}%  ({100 * lo:.0f} to {100 * hi:.0f})")

# Agreement on the 8 double-labelled tasks: the pair category, and the same/different decision on diagnoses and implementations
both = sorted(B)
cats_a, cats_b = [], []
for t in both:
    for f, s in pairs(t):
        cats_a.append(category(t, f, s, A[t])); cats_b.append(category(t, f, s, B[t]))
agree = sum(a == b for a, b in zip(cats_a, cats_b)) / len(cats_a)
pa, pb = collections.Counter(cats_a), collections.Counter(cats_b)
expected = sum(pa[c] * pb[c] for c in ORDER) / len(cats_a) ** 2
kappa = (agree - expected) / (1 - expected) if expected < 1 else float("nan")
same_dx = same_im = n_dx = 0
for t in both:
    for x, y in itertools.combinations(sorted(KEY[t]), 2):
        if LOC[t][x] and LOC[t][y]:
            n_dx += 1
            same_dx += (A[t][x]["diagnosis_id"] == A[t][y]["diagnosis_id"]) == (B[t][x]["diagnosis_id"] == B[t][y]["diagnosis_id"])
            same_im += (A[t][x]["implementation_id"] == A[t][y]["implementation_id"]) == (B[t][x]["implementation_id"] == B[t][y]["implementation_id"])
print(f"\nAgreement, {len(both)} tasks, {len(cats_a)} pairs: pair category {100 * agree:.0f}% (Cohen's kappa {kappa:.2f}); "
      f"same-or-different diagnosis for two tries with a patch {100 * same_dx / n_dx:.0f}% of {n_dx}; "
      f"same-or-different implementation {100 * same_im / n_dx:.0f}%")
disagree = [(t, f, s, a, b) for t in both for (f, s), a, b in zip(pairs(t), [category(t, f, s, A[t]) for f, s in pairs(t)],
                                                                    [category(t, f, s, B[t]) for f, s in pairs(t)]) if a != b]
for d in disagree:
    print("   disagreement:", d)
b_shares = summary(shares(B, both)); a8 = summary(shares(A, both))
print("  on these 8 tasks, category shares A vs B:", {c: (round(100 * a8[c][0]), round(100 * b_shares[c][0])) for c in ORDER})

# Secondary
tries = [(t, l) for t in tasks for l in KEY[t]]
unknown = sum(A[t][l]["diagnosis_id"] == "unknown" and bool(LOC[t][l]) for t, l in tries)
print(f"\nSecondary: tries with a patch but no stated cause: {unknown} of {sum(bool(LOC[t][l]) for t, l in tries)}")
for group, sel in (("solved", True), ("failed", False)):
    g = [(t, l) for t, l in tries if KEY[t][l]["solved"] == sel]
    rev = collections.Counter(A[t][l]["revised"] for t, l in g)
    nopatch = sum(not LOC[t][l] for t, l in g)
    claims = sum(not LOC[t][l] and ("claim" in A[t][l]["diagnosis"] or "describes" in A[t][l]["diagnosis"]) for t, l in g)
    print(f"  {group} tries: {len(g)} | revised after the first applied edit: {dict(rev)} | no patch: {nopatch}, of which the final message still claims or describes a fix: {claims}")
mixed_same = [t for t in tasks if any(category(t, f, s, A[t]) == 'unclear' and LOC[t][f] and A[t][f]['diagnosis_id'] not in ('unknown',) for f, s in pairs(t))]
print("  tasks with a pair whose labels are identical but outcomes differ:", mixed_same)
json.dump({"tasks": len(tasks), "pairs": n_pairs, "primary": main, "agreement": {"pairs": len(cats_a), "raw": agree, "kappa": kappa,
           "diagnosis_same_different": same_dx / n_dx, "implementation_same_different": same_im / n_dx}, "disagreements": disagree},
          open("results.json", "w"), indent=1)

# Added after the independent review (GUIDE.md, corrections 6): robustness of the headline
print("\nRobustness (added after review)")
MERGED = ["no patch", "different location", "same function, different change", "unclear"]
def merged(c):
    return "same function, different change" if c.startswith("same location") else c
def summary_cats(per, cats, seed=1):
    tasks_ = sorted(per); random.seed(seed); res = {}
    for cat in cats:
        vals = [per[t][cat] for t in tasks_]
        boots = sorted(sum(random.choice(vals) for _ in vals) / len(vals) for _ in range(4000))
        res[cat] = (sum(vals) / len(vals), boots[100], boots[3899])
    return res
def shares_with(catfn, cats, labels_by_task, tasks_):
    out = {}
    for t in tasks_:
        ps = pairs(t); c = collections.Counter(catfn(t, f, s, labels_by_task[t]) for f, s in ps)
        out[t] = {cat: c[cat] / len(ps) for cat in cats}
    return out
m = summary_cats(shares_with(lambda t, f, s, L: merged(category(t, f, s, L)), MERGED, A, tasks), MERGED)
print("  merged categories (annotator A, 20 tasks):", {c: f"{100*v[0]:.1f}% ({100*v[1]:.0f} to {100*v[2]:.0f})" for c, v in m.items()})
# line-level location: a failed try whose final patch is off the reference lines, paired with a solved try on them, is a different location
def line_cat(t, f, s, L):
    c = merged(category(t, f, s, L))
    if c == "same function, different change" and KEY[t][f]["place"] != "gold lines" and KEY[t][s]["place"] == "gold lines":
        return "different location"
    return c
m2 = summary_cats(shares_with(line_cat, MERGED, A, tasks), MERGED)
print("  with line-level location:", {c: f"{100*v[0]:.1f}% ({100*v[1]:.0f} to {100*v[2]:.0f})" for c, v in m2.items()})
judged = [(a, b) for a, b in zip(cats_a, cats_b) if a not in ("no patch", "different location")]
print(f"  agreement on pairs decided by labels, not by mechanical location: {sum(a == b for a, b in judged)} of {len(judged)}")
task_stated = sum("task" in A[t][l]["diagnosis"] for t in tasks for l in A[t] if LOC[t][l])
print(f"  patched tries whose diagnosis A marks as stated by the task: {task_stated} of {sum(bool(LOC[t][l]) for t in tasks for l in A[t])}")
subset = sum(1 for t in tasks for f, s in pairs(t) if merged(category(t, f, s, A[t])) == "same function, different change"
             and set(LOC[t][f]) < set(LOC[t][s]))
print(f"  same-function pairs where the solved patch also changes a function the failed one never touches: {subset}")
