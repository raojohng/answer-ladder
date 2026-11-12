"""Control and graph hint pooled over ladder4 and ladder6 (77 tasks, 6 tries per arm per task), overall and split by whether the hint's
five symbols cover the reference lines (the reference is used only to classify). Solves and first applied edit on the reference lines
per pass of 77 tasks; paired 95% task-bootstrap intervals (2,000 resamples, seed 1); run-to-run change of each arm.
    python3 -I graph_pooled.py <ladder4_stages.csv> <ladder6_stages.csv> <nodes_test.jsonl>"""
import collections, csv, json, random, sys

ARMS = {"control": "e4b_loc_ctrl_v1", "graph hint": "e4b_ghint_v1"}
by = collections.defaultdict(lambda: collections.defaultdict(list))   # arm -> task -> rows (both runs)
run = collections.defaultdict(lambda: collections.defaultdict(list))  # (run, arm) -> task -> rows
for path in sys.argv[1:3]:
    for r in csv.DictReader(open(path)):
        if r["arm"] in ARMS.values():
            by[r["arm"]][r["task"]].append(r)
            run[(r["run"], r["arm"])][r["task"]].append(r)
hit = {r["task"]: any(r["hits"]) for r in map(json.loads, open(sys.argv[3]))}
solved = lambda r: r["solved"] == "1"
first = lambda r: r["first_applied_gold_lines"] == "1"
per = lambda b, a, f, ts: sum(sum(map(f, b[a][t])) / len(b[a][t]) for t in ts)
tasks = sorted(set(by[ARMS["control"]]) & set(by[ARMS["graph hint"]]))
print("tries per arm: " + ", ".join(f"{k} {sum(len(by[a][t]) for t in tasks)}" for k, a in ARMS.items()))
for (rn, a), b in sorted(run.items()):
    print(f"  {rn} {a}: solved {per(run, (rn, a), solved, tasks):.1f}/pass, first edit on reference lines {per(run, (rn, a), first, tasks):.1f}/pass")
for title, ts in (("All", tasks), ("Hint covers the reference lines", [t for t in tasks if hit[t]]), ("Hint misses them", [t for t in tasks if not hit[t]])):
    random.seed(1)
    smp = [[random.choice(ts) for _ in ts] for _ in range(2000)]
    print(f"{title}: {len(ts)} tasks")
    for name, f in (("solved", solved), ("first applied edit on the reference lines", first)):
        c, g = per(by, ARMS["control"], f, ts), per(by, ARMS["graph hint"], f, ts)
        d = sorted(per(by, ARMS["graph hint"], f, s) - per(by, ARMS["control"], f, s) for s in smp)
        print(f"  {name}: control {c:.1f}/pass, graph hint {g:.1f}/pass, difference {g - c:+.1f} ({d[50]:+.1f} to {d[1949]:+.1f})")
print("GRAPH_POOLED_DONE")
