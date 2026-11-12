"""Call-graph distance from each wrong edit (data/lookalike/wrong_edits.jsonl) to the nearest reference node, against the same-file
baseline nodes: are the agent's misses one call away from the fix (a caller or callee), or unrelated?
    python3 -I graph_distance.py <competition data dir> <wrong_edits.jsonl> <ids file>"""
import collections, json, sys
from pathlib import Path
import numpy as np
DATA, W = Path(sys.argv[1]), [json.loads(l) for l in open(sys.argv[2])]
tasks = {t["instance_id"]: t for t in map(json.loads, open(DATA / "tasks.jsonl"))}
nodes_jsonl = Path(sys.argv[2]).parent
cache = {}
def graph(tid):
    if tid not in cache:
        t = tasks[tid]; g = json.load(open(DATA / "graphs" / f"{t['repo'].split('/')[-1]}_{t['base_commit']}.json"))
        nb = collections.defaultdict(set)
        for e in g["edges"]:
            nb[e["source"]].add(e["target"]); nb[e["target"]].add(e["source"])
        cache[tid] = nb
    return cache[tid]
def dist(nb, a, targets, cap=4):
    seen, frontier = {a}, {a}
    for d in range(cap + 1):
        if frontier & targets:
            return d
        frontier = {m for n in frontier for m in nb[n]} - seen; seen |= frontier
    return None
c = collections.Counter(); per_task = collections.defaultdict(list)
for x in W:
    if x["edited"] in x["ref"]:
        continue
    d = dist(graph(x["task"]), x["edited"], set(x["ref"]))
    k = "1 hop" if d == 1 else "2 hops" if d == 2 else "3-4 hops" if d in (3, 4) else "not within 4 hops"
    c[k] += 1; per_task[x["task"]].append(d in (1, 2))
n = sum(c.values())
print(f"{n} wrong edits in another function: " + ", ".join(f"{k} {v} ({100*v/n:.0f}%)" for k, v in sorted(c.items())))
print(f"task-weighted share within 2 hops: {100*np.mean([np.mean(v) for v in per_task.values()]):.0f}% over {len(per_task)} tasks")
# baseline: every graph node (and the nodes in the edited node's module) at the same distances from the same reference nodes
import random
random.seed(1)
base, same_mod = collections.Counter(), collections.Counter()
for x in W:
    if x["edited"] in x["ref"]:
        continue
    nb = graph(x["task"]); refs = set(x["ref"])
    # BFS from the reference nodes once
    dmap, frontier, seen = {}, set(refs), set(refs)
    for d in range(5):
        for n in frontier: dmap[n] = d
        frontier = {m for n in frontier for m in nb[n]} - seen; seen |= frontier
    allnodes = [n for n in nb if n not in refs]
    for n in random.sample(allnodes, min(50, len(allnodes))):
        d = dmap.get(n); base["1 hop" if d == 1 else "2 hops" if d == 2 else "3-4 hops" if d in (3, 4) else "not within 4 hops"] += 1
    mod = x["edited"].rsplit(".", 1)[0]
    for n in [n for n in allnodes if n.startswith(mod + ".") and n != x["edited"]][:50]:
        d = dmap.get(n); same_mod["1 hop" if d == 1 else "2 hops" if d == 2 else "3-4 hops" if d in (3, 4) else "not within 4 hops"] += 1
for name, cc in (("random graph node (baseline)", base), ("other nodes beside the edited one (baseline)", same_mod)):
    m = sum(cc.values())
    print(f"{name}: " + ", ".join(f"{k} {100*v/m:.0f}%" for k, v in sorted(cc.items())))
