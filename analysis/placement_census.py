"""Placement census of v8-scaffold sessions: where each session's patch landed against the reference patch, and what
the session did before its first edit. No GPU, no model; sizes the placement training set.

    python3 -I placement_census.py <out.csv> <runs dir> <tasks.jsonl> [<tasks.jsonl> ...]

One row per session folder <task>_t<k> in the runs dir. Columns:
  place               where the submitted patch landed (same rule as paper_track/analysis/extract_sessions.py)
  solver_calls        tool calls made by the solver stage
  first_edit          1-based index of the first edit.py call among the solver's calls (empty: never edited)
  first_edit_gold     1 when that first edit names a file of the reference patch
  read_gold_before    1 when a read.py call before the first edit covered reference lines (within NEAR lines)
  found_gold_file_before  1 when a gold file path appeared in any tool result before the first edit
"""
import collections, csv, glob, json, os, re, sys

NEAR = 3
FIELDS = ["task", "try", "repo", "solved", "place", "gold_files", "gold_hunks", "solver_calls", "first_edit",
          "first_edit_gold", "read_gold_before", "found_gold_file_before", "crash"]
FILE = re.compile(r"^\s*(?:FILE|PATH)\s*:\s*(.+?)(?::(\d+))?\s*$", re.IGNORECASE | re.MULTILINE)
READ = re.compile(r"read\.py\s+[\"']?([^\s\"']+)(?:\s+(\d+)\s*-\s*(\d+))?")
CRASH = "No LlmAgent model available for event compaction summarizer"


def hunks(patch):
    out, cur = collections.defaultdict(list), None
    for line in patch.splitlines():
        if line.startswith("+++ "):
            cur = line[4:].strip()
            cur = cur[2:] if cur.startswith(("a/", "b/")) else cur
            continue
        m = re.match(r"@@ -(\d+)(?:,(\d+))? \+", line)
        if m and cur and cur != "/dev/null":
            a, n = int(m.group(1)), int(m.group(2) or 1)
            out[cur].append((a, a + max(n, 1) - 1))
    return out


def place(agent, gold):
    if not agent:
        return "no patch"
    src = {f: h for f, h in agent.items() if f.endswith(".py") and "test" not in f.lower()}
    common = set(src) & set(gold)
    if not common:
        return "another file"
    for f in common:
        for a, b in src[f]:
            for c, d in gold[f]:
                if a <= d + NEAR and c <= b + NEAR:
                    return "gold lines" if set(gold) <= set(src) else "gold lines, misses a gold file"
    return "right file, other lines"


def norm(path):
    path = path.strip().strip("\"'")
    for prefix in ("/workspace/", "./"):
        if path.startswith(prefix):
            path = path[len(prefix):]
    return path


def solver_calls(folder, task):
    """[(command or tool name, result text)] of the solver stage, in order."""
    rows = [json.loads(l) for l in open(os.path.join(folder, "llm_calls.jsonl")) if l.strip()]
    rows = [r for r in rows if r.get("instance_id") == task and
            "run_command" in {t["function"]["name"] for t in r.get("tools") or []}]
    results, calls = {}, []
    for r in rows:
        for m in r["messages"]:
            if m.get("role") == "tool" and m.get("tool_call_id"):
                c = m.get("content")
                results[m["tool_call_id"]] = c if isinstance(c, str) else json.dumps(c)
    for r in rows:
        for c in r["response"]["choices"][0]["message"].get("tool_calls") or []:
            try:
                command = json.loads(c["function"]["arguments"]).get("command", "")
            except (ValueError, AttributeError):
                command = ""
            calls.append((c["function"]["name"], command or "", results.get(c.get("id"), "")))
    return calls


def trace(folder, task, gold):
    try:
        calls = solver_calls(folder, task)
    except (OSError, ValueError, KeyError):
        return {}
    out = {"solver_calls": len(calls), "first_edit": "", "first_edit_gold": "", "read_gold_before": 0,
           "found_gold_file_before": 0}
    for i, (name, command, result) in enumerate(calls, 1):
        if name == "run_command" and "edit.py" in command:
            files = {norm(m.group(1)) for m in FILE.finditer(command)}
            out["first_edit"] = i
            out["first_edit_gold"] = int(bool(files & set(gold)))
            break
        m = READ.search(command) if name == "run_command" else None
        if m and norm(m.group(1)) in gold:
            a, b = int(m.group(2) or 1), int(m.group(3) or 10 ** 9)
            if any(a <= d + NEAR and c <= b + NEAR for c, d in gold[norm(m.group(1))]):
                out["read_gold_before"] = 1
        if any(f in result or f in command for f in gold):
            out["found_gold_file_before"] = 1
    return out


def main(out, runs, *task_files):
    gold = {}
    for f in task_files:
        for line in open(f):
            t = json.loads(line)
            gold[t["instance_id"]] = hunks(t["patch"])
    rows = []
    for f in sorted(glob.glob(os.path.join(runs, "*_t[0-9]*", "task_results.jsonl"))):
        d = os.path.dirname(f)
        task, k = os.path.basename(d).rsplit("_t", 1)
        if task not in gold:
            continue
        try:
            r = [json.loads(l) for l in open(f) if l.strip()][-1]
        except (ValueError, IndexError):
            continue
        patch = ""
        for p in glob.glob(os.path.join(d, "patches", "*")):
            patch = open(p, errors="replace").read()
        g = gold[task]
        row = {"task": task, "try": int(k), "repo": task.rsplit("_", 1)[0], "solved": int(bool(r.get("resolved"))),
               "place": place(hunks(patch), g), "gold_files": len(g), "gold_hunks": sum(len(h) for h in g.values()),
               "crash": int(CRASH in str(r.get("error")))}
        row.update(trace(d, task, g))
        rows.append(row)
    with open(out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} sessions, {len({r['task'] for r in rows})} tasks, {sum(r['solved'] for r in rows)} solved -> {out}")


if __name__ == "__main__":
    main(*sys.argv[1:])
