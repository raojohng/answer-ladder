"""Numbers that come from the extra data files (not from sessions.csv): Table 3, the FreshSWE-Py replication,
the single-agent curve with the three passes of Section 6, and the Gemma 4 31B comparison.
    python3 analysis/make_extra_tables.py        (run in this folder; needs only data/)
Placement columns were written by analysis/test_census.py and analysis/placement_census.py from the raw session records."""
import collections, csv, math

def rows(name): return list(csv.DictReader(open(f"data/{name}")))
def by_task(rs, key="solved"):
    t = collections.defaultdict(list)
    for r in rs: t[r["task"]].append(int(r[key]))
    return t
def curve(t, k, tasks=None): return sum(1 - math.comb(len(t[x]) - sum(t[x]), k) / math.comb(len(t[x]), k) for x in (tasks or t))

main, test = rows("sessions.csv"), rows("place1_test86.csv")
ever = {r["task"] for r in main if r["solved"] == "1"}
print("Table 3")
for arm in ("e4b_edit_fair_v1", "e4b_place1a_v1", "e4b_place1b_v1"):
    R = [r for r in test if r["arm"] == arm]; E = [r for r in R if r["task"] in ever]
    g = lambda X: sum(r["place"] == "gold lines" for r in X)
    print(f"  {arm}: per pass {[sum(int(r['solved']) for r in R if r['try'] == k) for k in '123']}, on the {len(ever)} tasks "
          f"{sum(int(r['solved']) for r in E)} of {len(E)}, gold lines {g(R)/len(R):.0%} all, {g(E)/len(E):.0%} on the {len(ever)}, "
          f"read gold lines before the first edit {sum(r['read_gold_before'] == '1' for r in R)/len(R):.0%}")
v8 = by_task([r for r in main if r["arm"] == "e4b_edit_fair_v1"] + [r for r in test if r["arm"] == "e4b_edit_fair_v1"])
print("untrained v8 scaffold, 11 tries:", {k: round(curve(v8, k), 1) for k in (1, 2, 4, 6, 8, 11)})
off = by_task([r for r in main if r["arm"] == "e4b_official_v1"])
print("untrained official loop, 10 tries:", {k: round(curve(off, k), 1) for k in (1, 4, 8, 10)})
big = by_task(rows("gemma31b_sessions.csv")); common = sorted(set(big) & set(v8))
print(f"31B against E4B on {len(common)} common tasks:", {k: (round(curve(big, k, common), 1), round(curve(v8, k, common), 1)) for k in (1, 3, 6)})
for name in ("freshswe_sessions.csv", "training_tasks_sessions.csv"):
    R = rows(name); t = by_task(R); c = collections.Counter(sum(v) for v in t.values() if len(v) == 4)
    place = collections.defaultdict(list)
    for r in R: place[sum(t[r["task"]])].append(r["place"] == "gold lines")
    print(name, len(R), "sessions,", len(t), "tasks; per try", [sum(int(r["solved"]) for r in R if r["try"] == k) for k in "1234"],
          "; tasks by solves in 4:", dict(sorted(c.items())), "; gold lines when solved 4 of 4:",
          f"{sum(place[4])/max(1,len(place[4])):.0%}", ", 1 to 3:", f"{sum(sum(place[k]) for k in (1,2,3))/sum(len(place[k]) for k in (1,2,3)):.0%}")
passes = collections.defaultdict(int)
for r in main:
    if r["arm"] in ("e4b_official_v1", "e4b_edit_fair_v1"): passes[(r["arm"], r["run"], r["try"])] += int(r["solved"])
import statistics
for a in ("e4b_official_v1", "e4b_edit_fair_v1"):
    v = [n for (arm, _, _), n in passes.items() if arm == a]; print(a, "passes", sorted(v), "sd", round(statistics.stdev(v), 2))
print("passes per arm to detect a gain d (two-sided 5%, power 80%, sd 2.2):", {d: math.ceil(2 * (2.8 * 2.2 / d) ** 2) for d in (2, 4, 6)})
