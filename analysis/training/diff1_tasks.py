"""Diff test diff1 (third rung of the ladder; John's go 2026-11-11 23:05 IST): the official tasks with the reference patch appended.
  diff arm: problem statement + "The fix is this change to the repository:" + the reference patch (the `patch` field: source only,
  never `test_patch`), for every gold-checked official task whose patch is at most 10,000 characters (fixed before the run).
  Control and location arms are loc1's (same 86 tasks, same machine, same harness); the summary compares all three on these tasks.
    python3 -I diff1_tasks.py <competition tasks.jsonl> <valid_rtx.json> <out folder>  -> tasks_e4b_diff_v1.jsonl, ids_diff.txt, excluded.txt
"""
import json, sys
from pathlib import Path
src, valid, out = sys.argv[1], sys.argv[2], Path(sys.argv[3])
MAX_CHARS = 10_000
out.mkdir(parents=True, exist_ok=True)
ids = set(json.load(open(valid))["official"])
rows, kept, excluded = [], [], []
for line in open(src):
    t = json.loads(line)
    if t["instance_id"] not in ids:
        continue
    if len(t["patch"]) > MAX_CHARS:
        excluded.append((t["instance_id"], len(t["patch"])))
        continue
    text = t["problem_statement"].rstrip() + "\n\nThe fix is this change to the repository:\n```diff\n" + t["patch"].rstrip() + "\n```\n"
    rows.append({**t, "problem_statement": text}); kept.append(t["instance_id"])
open(out / "tasks_e4b_diff_v1.jsonl", "w").write("".join(json.dumps(r) + "\n" for r in rows))
open(out / "ids_diff.txt", "w").write("\n".join(sorted(kept)) + "\n")
open(out / "excluded.txt", "w").write("".join(f"{i} {n}\n" for i, n in sorted(excluded)))
print(f"{len(kept)} tasks kept, {len(excluded)} excluded (patch over {MAX_CHARS} chars): {sorted(excluded)}")
