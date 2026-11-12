"""Diff test diff1, result: the three rungs on the same tasks (the 80 official tasks whose reference patch is at most 10,000 chars).
    control  = loc1 control arm ("Where to change: find this in the repository yourself.")
    location = loc1 hint arm (reference files and line ranges)
    diff     = diff1 (the reference patch itself)
All three: plain E4B, v8 scaffold, 3 tries per task, GPU 1 of the same machine. 95% task-bootstrap intervals (2,000 resamples).
    python3 -I diff1_summary.py <stages.csv with runs loc1 and diff1> <ids_diff.txt>
'per pass' = expected solves from one try of every task; % = share of tries, task-weighted."""
import collections, csv, random, sys

ids = set(open(sys.argv[2]).read().split())
rows = [r for r in csv.DictReader(open(sys.argv[1])) if r["task"] in ids]
arms = {"control": ("loc1", "e4b_loc_ctrl_v1"), "location": ("loc1", "e4b_loc_hint_v1"), "diff": ("diff1", "e4b_diff_v1")}
by = {k: collections.defaultdict(list) for k in arms}
for r in rows:
    for k, (run, b) in arms.items():
        if r["run"] == run and r["arm"] == b:
            by[k][r["task"]].append(r)
tasks = sorted(set.intersection(*(set(by[k]) for k in arms)))
n = len(tasks)
print(f"{n} tasks in all three arms; tries: " + ", ".join(f"{k} {sum(len(by[k][t]) for t in tasks)}" for k in arms))
capped = lambda r: int(r["calls"] or 0) >= 50 or float(r["minutes"] or 0) >= 7.9
MEASURES = {"solved": lambda r: r["solved"] == "1",
            "first applied edit on the reference lines": lambda r: r["first_applied_gold_lines"] == "1",
            "final patch on the reference lines": lambda r: r["place"] == "gold lines",
            "no patch": lambda r: r["place"] == "no patch",
            "harness crash": lambda r: r["crash"] == "1",
            "hit the 50-call or 8-minute limit": capped}
per = lambda k, f, ts: sum(sum(map(f, by[k][t])) / len(by[k][t]) for t in ts)
random.seed(1)
samples = [[random.choice(tasks) for _ in tasks] for _ in range(2000)]
for name, f in MEASURES.items():
    line = f"  {name:42s} " + " | ".join(f"{k} {per(k, f, tasks):5.1f} ({100 * per(k, f, tasks) / n:4.1f}%)" for k in arms)
    for a, b in (("diff", "location"), ("diff", "control")):
        d = sorted(per(a, f, s) - per(b, f, s) for s in samples)
        line += f" | {a}-{b} {per(a, f, tasks) - per(b, f, tasks):+5.1f} ({d[50]:+.1f} to {d[1949]:+.1f})"
    print(line)
ever = lambda k: {t for t in tasks if any(r["solved"] == "1" for r in by[k][t])}
allk = lambda k: {t for t in tasks if all(r["solved"] == "1" for r in by[k][t])}
print("  tasks solved at least once: " + ", ".join(f"{k} {len(ever(k))}" for k in arms) + f"; solved in all 3 tries: " + ", ".join(f"{k} {len(allk(k))}" for k in arms))
print(f"  tasks never solved with the diff given: {len(set(tasks) - ever('diff'))}")
# Why diff-arm tries fail (each failed try once, first matching reason)
reasons = collections.Counter()
for t in tasks:
    for r in by["diff"][t]:
        if r["solved"] == "1":
            continue
        reasons["harness crash" if r["crash"] == "1" else "no patch" if r["place"] == "no patch" else
                "final patch off the reference lines" if r["place"] != "gold lines" else "on the reference lines, tests fail"] += 1
        if capped(r):
            reasons["  (of these, hit a limit)"] += 1
print("  failed diff tries by reason:", dict(reasons))
single = [t for t in tasks if by["diff"][t][0]["gold_files"] == "1"]
print(f"  single-file reference ({len(single)} tasks), solved per pass: " + ", ".join(f"{k} {per(k, MEASURES['solved'], single):.1f}" for k in arms))
multi = [t for t in tasks if t not in single]
print(f"  multi-file reference ({len(multi)} tasks), solved per pass: " + ", ".join(f"{k} {per(k, MEASURES['solved'], multi):.1f}" for k in arms))
print("DIFF1_SUMMARY_DONE")
