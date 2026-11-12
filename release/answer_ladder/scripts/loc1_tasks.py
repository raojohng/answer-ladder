"""Location test loc1 (judge's top request; John's go 2026-11-11 19:00 IST): two copies of the official task file that differ
only in one paragraph appended to each problem statement.
  hint arm:    "Where to change: <file> lines a-b, c-d; <file> lines ..."   (the reference patch's hunks, old-file lines)
  control arm: "Where to change: find this in the repository yourself."
    python3 -I loc1_tasks.py <competition tasks.jsonl> <out folder>   -> tasks_e4b_loc_hint_v1.jsonl, tasks_e4b_loc_ctrl_v1.jsonl
"""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import placement_census as pc

src, out = sys.argv[1], Path(sys.argv[2])
out.mkdir(parents=True, exist_ok=True)
hint_rows, ctrl_rows, lengths = [], [], []
for line in open(src):
    t = json.loads(line)
    files = pc.hunks(t["patch"])
    parts = []
    order = sorted(files, key=lambda f: (f.split('/')[0] in ('docs', 'docs_src', 'tests', 'scripts'), not f.endswith('.py')))   # library code first
    for f, h in [(f, files[f]) for f in order[:5]]:
        if all(a == 0 for a, _ in h):               # @@ -0,0: the file does not exist yet
            parts.append(f"{f} (a new file)")
            continue
        spans = ", ".join(f"{a}-{b}" if b > a else f"{a}" for a, b in sorted(h)[:4] if a > 0) + (", ..." if len(h) > 4 else "")
        parts.append(f"{f} lines {spans}")
    hint = "Where to change: " + "; ".join(parts) + (f"; and {len(files) - 5} more files" if len(files) > 5 else "") + "."
    ctrl = "Where to change: find this in the repository yourself."
    lengths.append(len(hint))
    hint_rows.append({**t, "problem_statement": t["problem_statement"].rstrip() + "\n\n" + hint + "\n"})
    ctrl_rows.append({**t, "problem_statement": t["problem_statement"].rstrip() + "\n\n" + ctrl + "\n"})
for name, rows in (("e4b_loc_hint_v1", hint_rows), ("e4b_loc_ctrl_v1", ctrl_rows)):
    open(out / f"tasks_{name}.jsonl", "w").write("".join(json.dumps(r) + "\n" for r in rows))
lengths.sort()
print(f"{len(hint_rows)} tasks; hint length median {lengths[len(lengths) // 2]} chars, max {lengths[-1]}; example: {hint_rows[0]['problem_statement'][-160:]!r}")
