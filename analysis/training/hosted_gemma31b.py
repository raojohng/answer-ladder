"""Gemma 4 31B on all five rungs, hosted on Kaggle Benchmarks (one try per task and rung), beside the three local models.
Tries that failed for a platform reason (a model service, sandbox or budget error) are reported and left out; agent
outcomes (timeouts, no submit) count as unsolved, as in the competition; the rungs are compared on the tasks every rung completed. Steps: rung minus the rung below, paired
95% task-bootstrap interval (2,000 resamples, seed 1). Local models: solves per pass on the same tasks (mean of 3 tries).
    python3 -I hosted_gemma31b.py <report.json> <ladder3_stages.csv> <ladder5_stages.csv> <ladder8_stages.csv>"""
import collections, csv, json, random, sys

report = json.load(open(sys.argv[1]))
RUNGS = [("ctrl", "control"), ("loc", "reference lines"), ("diff", "reference patch"), ("edits", "edit commands"), ("apply", "apply tool")]
solved, errors = {}, collections.Counter()
for key, _ in RUNGS:
    solved[key] = {}
    for t, res in report["rungs"][key]["results"].items():
        for task, r in res.items():
            # Agent outcomes (session timeout, finishing without submit_patch, ...) count as unsolved, as in the competition and our
            # local runs; only infrastructure errors (model service, sandbox, budget) are platform failures, left out.
            platform = ("sandbox", "worker error", "quota", "429", "rate limit", "proxy", "apierror", "api error", "connection")
            if r.get("error") and any(k in r["error"].lower() for k in platform):
                errors[(key, r["error"][:60])] += 1
                continue
            solved[key][task] = bool(r.get("resolved"))
tasks = sorted(set.intersection(*(set(solved[k]) for k, _ in RUNGS)))
print(f"Gemma 4 31B (hosted): {len(tasks)} tasks completed in every rung; platform errors: {sum(errors.values())}")
for (k, e), n in errors.most_common(8):
    print(f"  {k:6s} {n:3d}  {e}")
local = {}
for name, path, run, pat in (("E4B", sys.argv[2], "ladder3", "e4b_off_{}_v1"), ("Qwen3.5-4B", sys.argv[3], "ladder5", "q4b_off_{}_v1"),
                             ("E2B", sys.argv[4], "ladder8", "e2b_off_{}_v1")):
    by = collections.defaultdict(lambda: collections.defaultdict(list))
    for r in csv.DictReader(open(path)):
        for key, _ in RUNGS:
            if r["run"] == run and r["arm"] == pat.format(key):
                by[key][r["task"]].append(r["solved"] == "1")
    local[name] = {k: sum(sum(by[k][t]) / len(by[k][t]) for t in tasks) for k, _ in RUNGS}
print(f"  {'rung':16s} {'Gemma 4 31B':>12s} " + " ".join(f"{n:>11s}" for n in local))
for key, label in RUNGS:
    g = sum(solved[key][t] for t in tasks)
    print(f"  {label:16s} {g:5d} ({100 * g / len(tasks):3.0f}%) " + " ".join(f"{local[n][key]:5.1f} ({100 * local[n][key] / len(tasks):3.0f}%)" for n in local))
random.seed(1)
smp = [[random.choice(tasks) for _ in tasks] for _ in range(2000)]
per = lambda k, ts: sum(solved[k][t] for t in ts)
for (lo, ll), (hi, hl) in list(zip(RUNGS, RUNGS[1:])) + [(RUNGS[2], RUNGS[4])]:
    d = sorted(per(hi, s) - per(lo, s) for s in smp)
    print(f"  {hl} - {ll}: {per(hi, tasks) - per(lo, tasks):+d} ({d[50]:+d} to {d[1949]:+d})")
print("HOSTED_GEMMA31B_DONE")
