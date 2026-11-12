"""Graph arms split by whether the graph hint's five symbols cover the reference lines (25 tasks) or not (52); the reference is
used only to classify. Solves per pass and first applied edit on the reference lines per arm; paired 95% task-bootstrap intervals
(2,000 resamples, seed 1) for graph hint minus control.
    python3 -I graph_split.py <ladder4_stages.csv> <nodes_test.jsonl>"""
import collections, csv, json, random, sys

hit = {r["task"]: any(r["hits"]) for r in map(json.loads, open(sys.argv[2]))}
by = collections.defaultdict(lambda: collections.defaultdict(list))
for r in csv.DictReader(open(sys.argv[1])):
    by[r["arm"]][r["task"]].append(r)
ARMS = {"control": "e4b_loc_ctrl_v1", "graph tools": "e4b_gpull_v1", "graph hint": "e4b_ghint_v1", "reference lines": "e4b_loc_hint_v1"}
solved = lambda r: r["solved"] == "1"
first = lambda r: r["first_applied_gold_lines"] == "1"
per = lambda a, f, ts: sum(sum(map(f, by[a][t])) / len(by[a][t]) for t in ts)
for group, ts in (("hint covers the reference lines", [t for t in hit if hit[t]]), ("hint misses them", [t for t in hit if not hit[t]])):
    print(f"{group}: {len(ts)} tasks")
    for k, a in ARMS.items():
        print(f"  {k:16s} solved {per(a, solved, ts):4.1f}/pass | first applied edit on the reference lines {per(a, first, ts):4.1f}/pass")
    random.seed(1)
    smp = [[random.choice(ts) for _ in ts] for _ in range(2000)]
    for name, f in (("solved", solved), ("first applied edit on the reference lines", first)):
        d = sorted(per(ARMS["graph hint"], f, x) - per(ARMS["control"], f, x) for x in smp)
        print(f"  graph hint - control, {name}: {per(ARMS['graph hint'], f, ts) - per(ARMS['control'], f, ts):+.1f} ({d[50]:+.1f} to {d[1949]:+.1f})")
print("GRAPH_SPLIT_DONE")
