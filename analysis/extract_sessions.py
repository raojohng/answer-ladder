"""Step 1 of 3. Raw session records -> data/sessions.csv (one row per session).

Runs where the raw records live (the RTX machine, work/rtx_test). No GPU, no model: it reads each session's
test verdict and submitted patch, and compares the patch with the task's reference patch.

Usage: python3 extract_sessions.py <runs dir> <tasks.jsonl> <valid task list json> <out.csv>

Inputs
  runs dir          one folder per run (*test86), one folder per session inside: task_results.jsonl, patches/*.patch
  tasks.jsonl       the competition's task file (instance_id, patch = reference patch)
  valid task list   json with key "official": the 86 task ids that pass the gold check in our sandbox
"""
import collections, csv, glob, json, os, re, sys

NAME = re.compile(r"(.+?)_((?:fastapi|rich|requests|httpx)_\d+)(?:_t(\d+))?$")
NEAR = 3  # a hunk "reaches the gold lines" when it lies within this many lines of a reference hunk
FIELDS = ["run", "arm", "try", "task", "repo", "solved", "place", "patch_bytes", "tool_calls", "seconds",
          "test_exit_code", "error", "gold_files", "gold_hunks"]


def hunks(patch):
    """{file: [(first old line, last old line)]} of a unified diff."""
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
    """Where the submitted patch landed, against the reference patch."""
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


def main(runs, tasks_file, valid_file, out):
    gold = {}
    for line in open(tasks_file):
        t = json.loads(line)
        gold[t["instance_id"]] = hunks(t["patch"])
    official = set(json.load(open(valid_file))["official"])
    rows = []
    for f in sorted(glob.glob(os.path.join(runs, "*test86", "*", "task_results.jsonl"))):
        d = os.path.dirname(f)
        m = NAME.match(os.path.basename(d))
        if not m or m.group(2) not in official:
            continue
        try:
            r = [json.loads(l) for l in open(f) if l.strip()][-1]
        except (ValueError, IndexError):
            continue
        patch = ""
        for p in glob.glob(os.path.join(d, "patches", "*")):
            patch = open(p, errors="replace").read()
        g = gold[m.group(2)]
        rows.append({"run": d.split(os.sep)[-2], "arm": m.group(1), "try": int(m.group(3) or 1), "task": m.group(2),
                     "repo": m.group(2).rsplit("_", 1)[0], "solved": int(bool(r.get("resolved"))),
                     "place": place(hunks(patch), g), "patch_bytes": r.get("agent_patch_size") or 0,
                     "tool_calls": r.get("tool_calls"), "seconds": r.get("duration_seconds"),
                     "test_exit_code": r.get("test_exit_code"), "error": int(bool(r.get("error"))),
                     "gold_files": len(g), "gold_hunks": sum(len(h) for h in g.values())})
    with open(out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} sessions, {sum(r['solved'] for r in rows)} solved, {len({r['task'] for r in rows})} tasks -> {out}")


if __name__ == "__main__":
    main(*sys.argv[1:5])
