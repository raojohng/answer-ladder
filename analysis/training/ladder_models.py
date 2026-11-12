"""Does a ladder step differ between models? Official loop, 77 tasks, 3 tries per rung and model. For each step (rung minus the
rung below), the difference between two models' steps in solves per pass, with a paired 95% task-bootstrap interval (2,000
resamples, seed 1): tasks are resampled jointly, so each model's step is paired on the same tasks.
    python3 -I ladder_models.py <ladder3_stages> <ladder5_stages> <ladder8_stages>"""
import collections, csv, random, sys

MODELS = {"E4B": ("ladder3", "e4b_off_{}_v1"), "Qwen3.5-4B": ("ladder5", "q4b_off_{}_v1"), "E2B": ("ladder8", "e2b_off_{}_v1")}
RUNGS = ["ctrl", "loc", "diff", "edits", "apply"]
by = {m: {r: collections.defaultdict(list) for r in RUNGS} for m in MODELS}
for path in sys.argv[1:4]:
    for row in csv.DictReader(open(path)):
        for m, (run, pat) in MODELS.items():
            for r in RUNGS:
                if row["run"] == run and row["arm"] == pat.format(r):
                    by[m][r][row["task"]].append(row["solved"] == "1")
tasks = sorted(set.intersection(*(set(by[m][r]) for m in MODELS for r in RUNGS)))
per = lambda m, r, ts: sum(sum(by[m][r][t]) / len(by[m][r][t]) for t in ts)
step = lambda m, lo, hi, ts: per(m, hi, ts) - per(m, lo, ts)
random.seed(1)
smp = [[random.choice(tasks) for _ in tasks] for _ in range(2000)]
print(f"{len(tasks)} tasks")
for lo, hi, name in (("ctrl", "loc", "lines - control"), ("loc", "diff", "patch - lines"), ("diff", "edits", "commands - patch"),
                     ("edits", "apply", "tool - commands"), ("diff", "apply", "tool - patch")):
    print(f"{name}: " + ", ".join(f"{m} {step(m, lo, hi, tasks):+.1f}" for m in MODELS))
    for a, b in (("E2B", "E4B"), ("Qwen3.5-4B", "E4B"), ("E2B", "Qwen3.5-4B")):
        d = sorted(step(a, lo, hi, s) - step(b, lo, hi, s) for s in smp)
        print(f"    {a} - {b}: {step(a, lo, hi, tasks) - step(b, lo, hi, tasks):+.1f} ({d[50]:+.1f} to {d[1949]:+.1f})")
print("LADDER_MODELS_DONE")
