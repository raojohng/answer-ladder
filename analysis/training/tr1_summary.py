"""Transfer test tr1, result: the adapter's free runs against plain E4B's on the same tasks, held-out and trained tasks apart.
    python3 -I tr1_summary.py <stages.csv> <work/tr1> [<held-out run> [<trained-task run>]]
Plain = the 4 tries of v8_sweep / fresh_v8_p1 plus the 2 of rl1_plain. Interval: 2,000 bootstrap resamples of tasks."""
import collections, csv, json, random, sys
rows = list(csv.DictReader(open(sys.argv[1])))
m = json.load(open(sys.argv[2] + "/a_manifest.json"))
PLAIN = ("v8_sweep", "fresh_v8_p1", "rl1_plain")
MEASURES = {"solved": lambda r: r["solved"] == "1", "first applied edit on the reference lines": lambda r: r["first_applied_gold_lines"] == "1",
            "final patch on the reference lines": lambda r: r["place"] == "gold lines", "no patch": lambda r: r["place"] == "no patch"}
random.seed(1)
HELD_RUN = sys.argv[3] if len(sys.argv) > 3 else "tr1_held"
SEEN_RUN = sys.argv[4] if len(sys.argv) > 4 else "tr1_seen" if len(sys.argv) <= 3 else ""
for label, tasks, run in (("HELD-OUT tasks (never trained on)", m["held_out_tasks"], HELD_RUN), ("TRAINED tasks", m["trained_tasks"], SEEN_RUN)):
    if not run:
        continue
    a = collections.defaultdict(list); p = collections.defaultdict(list)
    for r in rows:
        if r["task"] in set(tasks):
            (a if r["run"] == run else p if r["run"] in PLAIN else collections.defaultdict(list))[r["task"]].append(r)
    both = sorted(set(a) & set(p))
    if not both:
        print(f"\n{label}: no sessions of run {run}")
        continue
    print(f"\n{label}: {len(both)} tasks, adapter {sum(len(a[t]) for t in both)} tries, plain {sum(len(p[t]) for t in both)} tries")
    for name, f in MEASURES.items():
        rate = lambda d, ts: sum(sum(map(f, d[t])) / len(d[t]) for t in ts) / len(ts)          # mean of per-task rates
        diffs = sorted(rate(a, s) - rate(p, s) for s in ([random.choice(both) for _ in both] for _ in range(2000)))
        print(f"  {name:42s} adapter {100 * rate(a, both):5.1f}% | plain {100 * rate(p, both):5.1f}% | difference {100 * (rate(a, both) - rate(p, both)):+5.1f} points "
              f"(95% interval {100 * diffs[50]:+.1f} to {100 * diffs[1949]:+.1f})")
print("TR1_SUMMARY_DONE")
