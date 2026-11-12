"""Graph ablation (ladder6): control, text-only hint (same builder and wording, graph weights 0), graph hint (rerun of ladder4's arm),
graph tools with an instruction to use them; 77 tasks, 3 tries, interleaved. Solves and first applied edit on the reference lines per
pass, paired 95% task-bootstrap intervals (2,000 resamples, seed 1), split by whether each hint's five symbols cover the reference
lines (the reference is used only to classify), and ladder4's control and graph-hint arms beside this run's for the replication.
    python3 -I ladder6_summary.py <ladder6_stages.csv> <ladder4_stages.csv> <graph nodes_test.jsonl> <text nodes_test.jsonl>"""
import collections, csv, json, random, sys

l6, l4, gnodes, tnodes = sys.argv[1:5]
ARMS = {"control": "e4b_loc_ctrl_v1", "text hint": "e4b_thint_v1", "graph hint": "e4b_ghint_v1", "graph tools+instr": "e4b_gpull2_v1"}
PAIRS = (("text hint", "control"), ("graph hint", "control"), ("graph hint", "text hint"), ("graph tools+instr", "control"))


def load(path):
    by = collections.defaultdict(lambda: collections.defaultdict(list))
    for r in csv.DictReader(open(path)):
        by[r["arm"]][r["task"]].append(r)
    return by


by, old = load(l6), load(l4)
solved = lambda r: r["solved"] == "1"
first = lambda r: r["first_applied_gold_lines"] == "1"
per = lambda b, a, f, ts: sum(sum(map(f, b[a][t])) / len(b[a][t]) for t in ts if b[a][t])
tasks = sorted(set.intersection(*(set(by[a]) for a in ARMS.values())))
ghit = {r["task"]: any(r["hits"]) for r in map(json.loads, open(gnodes))}
thit = {r["task"]: any(r["hits"]) for r in map(json.loads, open(tnodes))}


def block(title, ts, pairs=PAIRS):
    random.seed(1)
    smp = [[random.choice(ts) for _ in ts] for _ in range(2000)]
    print(f"{title}: {len(ts)} tasks; tries " + ", ".join(f"{k} {sum(len(by[a][t]) for t in ts)}" for k, a in ARMS.items()))
    for name, f in (("solved", solved), ("first applied edit on the reference lines", first)):
        print(f"  {name}: " + " | ".join(f"{k} {per(by, a, f, ts):.1f}/pass" for k, a in ARMS.items()))
        for x, y in pairs:
            d = sorted(per(by, ARMS[x], f, s) - per(by, ARMS[y], f, s) for s in smp)
            print(f"    {x} - {y}: {per(by, ARMS[x], f, ts) - per(by, ARMS[y], f, ts):+.1f} ({d[50]:+.1f} to {d[1949]:+.1f})")


block("All", tasks)
print("  tasks solved at least once / in all 3 tries: " + ", ".join(
    f"{k} {sum(any(map(solved, by[a][t])) for t in tasks)}/{sum(all(map(solved, by[a][t])) for t in tasks)}" for k, a in ARMS.items()))
both = [t for t in tasks if ghit.get(t) and thit.get(t)]
print(f"\nHint coverage: graph hint covers {sum(ghit.get(t, False) for t in tasks)}, text hint {sum(thit.get(t, False) for t in tasks)}, both {len(both)}")
for title, ts in (("Graph hint covers the reference lines", [t for t in tasks if ghit.get(t)]),
                  ("Graph hint misses them", [t for t in tasks if not ghit.get(t)]),
                  ("Text hint covers the reference lines", [t for t in tasks if thit.get(t)]),
                  ("Text hint misses them", [t for t in tasks if not thit.get(t)]),
                  ("Hints differ in coverage", [t for t in tasks if ghit.get(t) != thit.get(t)])):
    if ts:
        print()
        block(title, ts, PAIRS[:3])
common = [t for t in tasks if old["e4b_ghint_v1"][t] and old["e4b_loc_ctrl_v1"][t]]
print(f"\nReplication of ladder4 ({len(common)} tasks): solved/pass  ladder4 control {per(old, 'e4b_loc_ctrl_v1', solved, common):.1f}, "
      f"graph hint {per(old, 'e4b_ghint_v1', solved, common):.1f} | ladder6 control {per(by, ARMS['control'], solved, common):.1f}, "
      f"graph hint {per(by, ARMS['graph hint'], solved, common):.1f}")
print("LADDER6_DONE")
