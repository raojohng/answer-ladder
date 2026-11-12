"""Graph arms (ladder4): control, graph tools (pull), graph hint (push), reference lines (oracle); 77 tasks, 3 tries, interleaved.
Solved share, tasks solved at least once / in all three tries, first applied edit on the reference lines, paired 95% task-bootstrap
intervals (2,000 resamples, seed 1) for the differences that answer the question, and how often the pull arm called a graph tool.
    python3 -I graph_arms_summary.py <stages.csv> <runs/ladder4 dir>"""
import collections, csv, glob, json, random, sys


def tool_calls(d):
    """[(name, arguments)] of every tool call in a session folder: the raw llm_calls.jsonl when present, else the
    release's tool_calls.jsonl (the same calls, extracted from the raw file by release_pack.py)."""
    import os
    if os.path.exists(d + "/llm_calls.jsonl"):
        return [(t["function"]["name"], t["function"]["arguments"]) for k in map(json.loads, open(d + "/llm_calls.jsonl"))
                for ch in (k.get("response") or {}).get("choices", []) for t in (ch["message"].get("tool_calls") or [])]
    return [(r["name"], r["arguments"]) for r in map(json.loads, open(d + "/tool_calls.jsonl"))]

stages, rundir = sys.argv[1], sys.argv[2]
ARMS = {"control": "e4b_loc_ctrl_v1", "graph tools": "e4b_gpull_v1", "graph hint": "e4b_ghint_v1", "reference lines": "e4b_loc_hint_v1"}
by = {k: collections.defaultdict(list) for k in ARMS}
for r in csv.DictReader(open(stages)):
    for k, b in ARMS.items():
        if r["run"] == "ladder4" and r["arm"] == b:
            by[k][r["task"]].append(r)
tasks = sorted(set.intersection(*(set(v) for v in by.values())))
per = lambda k, f, ts: sum(sum(map(f, by[k][t])) / len(by[k][t]) for t in ts)
solved = lambda r: r["solved"] == "1"
first = lambda r: r["first_applied_gold_lines"] == "1"
random.seed(1)
samples = [[random.choice(tasks) for _ in tasks] for _ in range(2000)]
print(f"{len(tasks)} tasks; tries " + ", ".join(f"{k} {sum(len(by[k][t]) for t in tasks)}" for k in ARMS))
for name, f in (("solved", solved), ("first applied edit on the reference lines", first)):
    print(f"  {name}: " + " | ".join(f"{k} {per(k, f, tasks):.1f}/pass ({100 * per(k, f, tasks) / len(tasks):.1f}%)" for k in ARMS))
    for a, b in (("graph tools", "control"), ("graph hint", "control"), ("graph hint", "graph tools"), ("reference lines", "graph hint")):
        d = sorted(per(a, f, s) - per(b, f, s) for s in samples)
        print(f"    {a} - {b}: {per(a, f, tasks) - per(b, f, tasks):+.1f} ({d[50]:+.1f} to {d[1949]:+.1f})")
print("  tasks solved at least once / in all 3 tries: " + ", ".join(
    f"{k} {sum(any(map(solved, by[k][t])) for t in tasks)}/{sum(all(map(solved, by[k][t])) for t in tasks)}" for k in ARMS))
# graph tool use in the pull arm
GRAPH = ("search_similar_code", "get_code_neighbors", "get_code_subgraph")
use, calls, errors, solved_use = collections.Counter(), collections.Counter(), 0, collections.Counter()
for d in sorted(glob.glob(f"{rundir}/{ARMS['graph tools']}_*_t[0-9]")):
    res = json.loads(open(d + "/task_results.jsonl").readline())
    names = [name for name, _ in tool_calls(d)]
    n = sum(x in GRAPH for x in names)
    for x in names:
        if x in GRAPH:
            calls[x] += 1
    used = n > 0
    use[used] += 1
    solved_use[(used, res["resolved"] in (True, "True"))] += 1
    errors += open(d + "/adk_events.jsonl").read().count('"status": "error"') if used else 0
print(f"  graph-tools arm: tries calling a graph tool {use[True]} of {use[True] + use[False]}; calls {dict(calls)}; "
      f"solved when used {solved_use[(True, True)]}/{use[True]}, when not {solved_use[(False, True)]}/{use[False]}")
print("GRAPH_ARMS_DONE")
