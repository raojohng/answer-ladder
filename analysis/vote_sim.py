"""Offline: if k tries were made and the patch that most other tries agree with (same file, hunks within 3 lines) were
submitted, how many tasks would be solved? python3 -I vote_sim.py <runs dir> <tasks.jsonl,...> [k ...]. No model, no GPU."""
import glob, itertools, json, os, sys, collections, importlib.util
spec = importlib.util.spec_from_file_location("pc", os.path.join(os.path.dirname(os.path.abspath(__file__)), "placement_census.py"))
pc = importlib.util.module_from_spec(spec); spec.loader.exec_module(pc)
runs, files, *ks = sys.argv[1:]
ids = set()
for f in files.split(","):
    ids |= {json.loads(l)["instance_id"] for l in open(f)}
tries = collections.defaultdict(list)
for f in glob.glob(os.path.join(runs, "*_t[0-9]*", "task_results.jsonl")):
    d = os.path.dirname(f); name = os.path.basename(d).rsplit("_t", 1)[0]
    task = name if name in ids else next((t for t in ids if name.endswith("_" + t)), None)
    if not task: continue
    r = [json.loads(l) for l in open(f) if l.strip()][-1]
    patch = "".join(open(p, errors="replace").read() for p in glob.glob(os.path.join(d, "patches", "*")))
    h = {f: v for f, v in pc.hunks(patch).items() if f.endswith(".py") and "test" not in f.lower()}
    tries[task].append((bool(r.get("resolved")), h))
def agree(a, b):
    return any(x <= d + 3 and c <= y + 3 for f in set(a) & set(b) for x, y in a[f] for c, d in b[f])
n = len(tries); print(f"{runs}: {n} tasks, {sum(map(len, tries.values()))} tries")
single = sum(sum(s for s, _ in t) / len(t) for t in tries.values())
print(f"  one try: {single:.1f} ({single/n:.1%})")
for k in map(int, ks or [3]):
    vote = oracle = first = 0.0; used = 0
    for t in tries.values():
        if len(t) < k: continue
        used += 1; subs = list(itertools.combinations(range(len(t)), k))
        if len(subs) > 300:
            import random; random.seed(1); subs = random.sample(subs, 300)
        v = o = 0.0
        for sub in subs:
            score = [(-1 if not t[i][1] else sum(agree(t[i][1], t[j][1]) for j in sub if j != i)) for i in sub]
            best = [i for i, sc in zip(sub, score) if sc == max(score)]
            v += sum(t[i][0] for i in best) / len(best); o += any(t[i][0] for i in sub)
        vote += v / len(subs); oracle += o / len(subs)
    print(f"  k={k} ({used} tasks): vote {vote:.1f} ({vote/used:.1%}) | perfect pick {oracle:.1f} ({oracle/used:.1%})")
