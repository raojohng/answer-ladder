"""Idea 2, location part: within tasks with both solved and failed untrained v8 tries (single-file reference), how does each
failed try differ from each solved try of the same task? Task-weighted shares with a task bootstrap (2,000 resamples).
    python3 analysis/retry_pairs.py        (needs data/stages_all.csv)"""
import csv, collections, random
rows = [r for r in csv.DictReader(open("data/stages_all.csv")) if r["run"] in ("v8_sweep", "fresh_v8_p1") and r["gold_files"] == "1" and r["crash"] != "1"]
by = collections.defaultdict(list)
for r in rows:
    by[(r["run"], r["task"])].append(r)
mixed = {k: v for k, v in by.items() if any(x["solved"] == "1" for x in v) and any(x["solved"] == "0" for x in v)}
on = lambda r: r["place"] == "gold lines"
def cat(f, s):
    if not on(s): return "solved try not on reference lines"
    if f["place"] == "no patch": return "failed try: no patch"
    if not on(f): return "different location"
    return "same location, different fix"
share = collections.defaultdict(list)
for v in mixed.values():
    S = [x for x in v if x["solved"] == "1"]; F = [x for x in v if x["solved"] == "0"]
    c = collections.Counter(cat(f, s) for f in F for s in S); n = sum(c.values())
    for k in ("same location, different fix", "failed try: no patch", "different location", "solved try not on reference lines"):
        share[k].append(c[k] / n)
random.seed(1)
print(f"{len(mixed)} tasks with solved and failed tries")
for k, v in share.items():
    bs = sorted(sum(random.choice(v) for _ in v) / len(v) for _ in range(2000))
    print(f"  {k:36s} {100 * sum(v) / len(v):5.1f}% of failed-solved pairs (95% {100 * bs[50]:.1f} to {100 * bs[1949]:.1f})")
S = [x for v in mixed.values() for x in v if x["solved"] == "1"]
print("  solved tries whose first applied edit was elsewhere and final patch on the reference lines:",
      sum(x["first_applied_gold_lines"] == "0" and x["i_first_applied"] != "" and on(x) for x in S), "of", len(S))
