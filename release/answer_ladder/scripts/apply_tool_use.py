"""Apply-tool arm: did a try invoke apply_fix.py at all (any tool call whose arguments name it), did the tool report
FIX APPLIED, and was the try solved. Separates never invoking the tool from invoking it without success (astra review 9).
    python3 -I apply_tool_use.py <runs dir>
Both runs are restricted to the 77 tasks of the interleaved replication (the ladder's common cohort)."""
import collections, glob, json, sys


def tool_calls(d):
    """[(name, arguments)] of every tool call in a session folder: the raw llm_calls.jsonl when present, else the
    release's tool_calls.jsonl (the same calls, extracted from the raw file by release_pack.py)."""
    import os
    if os.path.exists(d + "/llm_calls.jsonl"):
        return [(t["function"]["name"], t["function"]["arguments"]) for k in map(json.loads, open(d + "/llm_calls.jsonl"))
                for ch in (k.get("response") or {}).get("choices", []) for t in (ch["message"].get("tool_calls") or [])]
    return [(r["name"], r["arguments"]) for r in map(json.loads, open(d + "/tool_calls.jsonl"))]

runs = sys.argv[1]
# run folders at any depth: a local `tar -xzf` gives <runs>/<run>/, the Kaggle copy sessions/<run>/<run>/
ARMS = {"first run": f"{runs}/**/d2_e4b_diff_apply_v2/*_t[0-9]", "interleaved replication": f"{runs}/**/ladder2/e4b_diff_apply_v2_*_t[0-9]"}
ids = {json.loads(open(d + "/task_results.jsonl").readline())["instance_id"] for d in glob.glob(ARMS["interleaved replication"], recursive=True)}
print(f"{len(ids)} tasks")
for name, pattern in ARMS.items():
    c = collections.Counter()
    for d in sorted(set(glob.glob(pattern, recursive=True))):
        res = json.loads(open(d + "/task_results.jsonl").readline())
        if res["instance_id"] not in ids:
            continue
        invoked = any("apply_fix" in args for _, args in tool_calls(d))
        applied = "FIX APPLIED" in open(d + "/adk_events.jsonl").read()
        c[("invoked" if invoked else "never invoked", "FIX APPLIED" if applied else "not applied",
           "solved" if res["resolved"] in (True, "True") else "failed")] += 1
    print(f"{name}: {sum(c.values())} tries")
    for k, v in sorted(c.items()):
        print("  ", " / ".join(k), v)
    for state in ("invoked", "never invoked"):
        n = sum(v for k, v in c.items() if k[0] == state); s = sum(v for k, v in c.items() if k[0] == state and k[2] == "solved")
        print(f"  {state}: {n} tries, {s} solved")
print("APPLY_TOOL_USE_DONE")
