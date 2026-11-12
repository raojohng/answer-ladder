"""Diff test: how each diff-arm try's final patch compares with the reference patch it was given, and whether it used git apply.
    python3 -I diff1_failures.py <run dir> <competition tasks.jsonl> [ids file: only these tasks]
Classes per try (changed lines compared as sets of '+'/'-' lines per file, ignoring context and whitespace at line ends):
  identical, missing changes only (a subset of the reference), extra changes (a superset), different changes, empty."""
import collections, glob, json, os, re, sys

run, tasks = sys.argv[1], {t["instance_id"]: t for t in map(json.loads, open(sys.argv[2]))}
only = set(open(sys.argv[3]).read().split()) if len(sys.argv) > 3 else None


def changes(patch):
    out, cur = set(), None
    for line in patch.splitlines():
        if line.startswith("+++ "):
            p = line[4:].split("\t")[0]; cur = p[2:] if p.startswith("b/") else p
        elif line.startswith("--- ") or line.startswith("diff --git") or line.startswith("@@"):
            continue
        elif cur and line[:1] in "+-" and not line.startswith(("+++", "---")):
            out.add((cur, line[0], line[1:].rstrip()))
    return out


cls = collections.Counter(); tool = collections.Counter(); by_solved = collections.defaultdict(collections.Counter); git_apply = collections.Counter()
for d in sorted(glob.glob(f"{run}/*_t[0-9]*")):
    try:
        res = json.loads(open(f"{d}/task_results.jsonl").readline())
    except (OSError, ValueError):
        continue
    tid = res["instance_id"]; solved = res["resolved"] in (True, "True")
    if only is not None and tid not in only:
        continue
    pf = glob.glob(f"{d}/patches/*")
    agent = open(pf[0]).read() if pf else ""
    ref, got = changes(tasks[tid]["patch"]), changes(agent)
    c = ("empty" if not got else "identical" if got == ref else "missing changes only" if got < ref
         else "extra changes" if got > ref else "different changes")
    cls[c] += 1; by_solved[solved][c] += 1
    # raw llm_calls.jsonl when present (searched whole, as in the paper); in the release, the tool calls' arguments
    calls = (open(f"{d}/llm_calls.jsonl").read() if os.path.exists(f"{d}/llm_calls.jsonl") else
             open(f"{d}/tool_calls.jsonl").read() if os.path.exists(f"{d}/tool_calls.jsonl") else "")
    git_apply[("git apply" in calls or "patch -p" in calls, solved)] += 1
    ev = open(f"{d}/adk_events.jsonl").read() if os.path.exists(f"{d}/adk_events.jsonl") else ""
    tool[("FIX APPLIED" in ev, solved)] += 1
print(f"{sum(cls.values())} tries:", dict(cls))
for s in (True, False):
    print(f"  {'solved' if s else 'failed'}:", dict(by_solved[s]))
print("  used git apply or patch (solved, failed):", git_apply[(True, True)], git_apply[(True, False)],
      "| did not:", git_apply[(False, True)], git_apply[(False, False)])
print("  apply tool reported FIX APPLIED (solved, failed):", tool[(True, True)], tool[(True, False)], "| not applied:", tool[(False, True)], tool[(False, False)])
