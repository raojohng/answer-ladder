"""Location test loc1, result: hint arm against control arm on the same tasks, 95% task-bootstrap intervals (2,000 resamples).
    python3 -I loc1_summary.py <stages.csv>
'per pass' = sum over tasks of the per-task rate (solves expected from one try of every task)."""
import collections, csv, random, sys
rows = [r for r in csv.DictReader(open(sys.argv[1])) if r["run"] == "loc1"]
arms = {"hint": "e4b_loc_hint_v1", "control": "e4b_loc_ctrl_v1"}
by = {k: collections.defaultdict(list) for k in arms}
for r in rows:
    for k, b in arms.items():
        if r["arm"] == b:
            by[k][r["task"]].append(r)
tasks = sorted(set(by["hint"]) & set(by["control"]))
MEASURES = {"solved": lambda r: r["solved"] == "1", "first applied edit on the reference lines": lambda r: r["first_applied_gold_lines"] == "1",
            "final patch on the reference lines": lambda r: r["place"] == "gold lines", "no patch": lambda r: r["place"] == "no patch"}
print(f"{len(tasks)} tasks; tries: hint {sum(len(by['hint'][t]) for t in tasks)}, control {sum(len(by['control'][t]) for t in tasks)}")
random.seed(1)
for name, f in MEASURES.items():
    per = lambda k, ts: sum(sum(map(f, by[k][t])) / len(by[k][t]) for t in ts)
    diffs = sorted(per("hint", s) - per("control", s) for s in ([random.choice(tasks) for _ in tasks] for _ in range(2000)))
    n = len(tasks)
    print(f"  {name:42s} hint {per('hint', tasks):5.1f} per pass ({100 * per('hint', tasks) / n:4.1f}%) | control {per('control', tasks):5.1f} "
          f"({100 * per('control', tasks) / n:4.1f}%) | difference {per('hint', tasks) - per('control', tasks):+5.1f} per pass (95% interval {diffs[50]:+.1f} to {diffs[1949]:+.1f})")
ever = lambda k: {t for t in tasks if any(r["solved"] == "1" for r in by[k][t])}
print(f"  tasks solved at least once: hint {len(ever('hint'))}, control {len(ever('control'))}, either {len(ever('hint') | ever('control'))}")
single = [t for t in tasks if by["hint"][t][0]["gold_files"] == "1"]
per = lambda k, ts: sum(sum(r["solved"] == "1" for r in by[k][t]) / len(by[k][t]) for t in ts)
print(f"  single-file reference ({len(single)} tasks): solved per pass hint {per('hint', single):.1f}, control {per('control', single):.1f}")
print("LOC1_SUMMARY_DONE")
