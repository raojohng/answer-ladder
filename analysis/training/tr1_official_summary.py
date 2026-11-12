"""tr1 adapters on the 86 official tasks (repositories in no training data) against the untrained v8 scaffold's recorded passes.
    python3 -I tr1_official_summary.py <stages of the adapter run> <stages_official.csv>
Plain = arm e4b_edit_fair_v1 in place1_test86, scaffold_test86, v8con_test86 (9 passes). 'per pass' = sum over tasks of the
per-task rate. Interval: 2,000 bootstrap resamples of tasks."""
import collections, csv, random, sys
new = list(csv.DictReader(open(sys.argv[1])))
plain = [r for r in csv.DictReader(open(sys.argv[2])) if r["arm"] == "e4b_edit_fair_v1" and r["run"] in ("place1_test86", "scaffold_test86", "v8con_test86")]
group = lambda rows: {k: [r for r in rows if r["task"] == k] for k in {r["task"] for r in rows}}
P = group(plain)
MEASURES = {"solved": lambda r: r["solved"] == "1", "first applied edit on the reference lines": lambda r: r["first_applied_gold_lines"] == "1",
            "final patch on the reference lines": lambda r: r["place"] == "gold lines", "no patch": lambda r: r["place"] == "no patch"}
random.seed(1)
for arm in sorted({r["arm"] for r in new}):
    A = group([r for r in new if r["arm"] == arm])
    tasks = sorted(set(A) & set(P))
    print(f"\n{arm}: {len(tasks)} tasks, {sum(len(A[t]) for t in tasks)} tries (plain {sum(len(P[t]) for t in tasks)} tries)")
    for name, f in MEASURES.items():
        per = lambda d, ts: sum(sum(map(f, d[t])) / len(d[t]) for t in ts)
        diffs = sorted(per(A, s) - per(P, s) for s in ([random.choice(tasks) for _ in tasks] for _ in range(2000)))
        print(f"  {name:42s} adapter {per(A, tasks):5.1f} per pass | plain {per(P, tasks):5.1f} | difference {per(A, tasks) - per(P, tasks):+5.1f} "
              f"(95% interval {diffs[50]:+.1f} to {diffs[1949]:+.1f})")
print("TR1_OFFICIAL_DONE")
