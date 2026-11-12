"""Every step of a ladder run, paired on the same tasks (astra review 9: is each adjacent step, not only each step over the patch,
distinguishable?). Tasks are those present in every rung. Solves per pass and paired 95% task-bootstrap intervals (2,000 resamples,
seed 1) for each rung minus the rung below it, and for the answer rungs minus the patch rung.
    python3 -I ladder_steps.py <stages.csv> <name> run:bundle:rung [run:bundle:rung ...]   (rungs in ladder order)"""
import collections, csv, random, sys

stages, name, specs = sys.argv[1], sys.argv[2], [s.split(":") for s in sys.argv[3:]]
by = {rung: collections.defaultdict(list) for _, _, rung in specs}
for r in csv.DictReader(open(stages)):
    for run, bundle, rung in specs:
        if r["run"] == run and r["arm"] == bundle:
            by[rung][r["task"]].append(r["solved"] == "1")
tasks = sorted(set.intersection(*(set(v) for v in by.values())))
per = lambda rung, ts: sum(sum(by[rung][t]) / len(by[rung][t]) for t in ts)
random.seed(1)
samples = [[random.choice(tasks) for _ in tasks] for _ in range(2000)]
rungs = [rung for _, _, rung in specs]
print(f"{name}: {len(tasks)} tasks; tries " + ", ".join(f"{k} {sum(len(by[k][t]) for t in tasks)}" for k in rungs))
print("  solved per pass: " + ", ".join(f"{k} {per(k, tasks):.1f} ({100 * per(k, tasks) / len(tasks):.1f}%)" for k in rungs))
pairs = list(zip(rungs[1:], rungs[:-1])) + [(k, "patch") for k in rungs[rungs.index("patch") + 2:]] if "patch" in rungs else list(zip(rungs[1:], rungs[:-1]))
for a, b in pairs:
    d = sorted(per(a, s) - per(b, s) for s in samples)
    print(f"  {a} - {b}: {per(a, tasks) - per(b, tasks):+.1f} ({d[50]:+.1f} to {d[1949]:+.1f})")
print("LADDER_STEPS_DONE")
