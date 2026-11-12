"""col1 (John, 2026-11-12 02:55 IST: "get training data using the highest solved method ... train on both with two different methods,
test on all 86"): collection tasks = training tasks (r1, r2: the gold-checked ids in valid_rtx.json) and FreshSWE-Py, never the
official repositories; each task statement gets the reference fix as the exact edit.py commands (the ladder's 'edit commands' arm,
John's choice over the apply tool, whose successful tries consist of a call that does not exist without the answer).
Kept: patch at most 10,000 chars, no created files, every SEARCH text found exactly once in sequence on the task's snapshot.
    python3 -I col1_prep.py <out folder>   -> tasks_<set>.jsonl (statement + commands), hints.json {task: appended text}, ids.txt ("set id")
"""
import json, sys, tarfile, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from diff2_prep_lib import files_of

W = Path.home() / "workspace/Gemma4/work"; E = W / "extra_tasks"
OUT = Path(sys.argv[1]); OUT.mkdir(parents=True, exist_ok=True)
valid = json.load(open(W / "rtx_test/valid_rtx.json"))
SETS = {"r1": (E / "r1/tasks.jsonl", E / "r1/snapshots", set(valid["r1"])),
        "r2": (E / "r2/tasks.jsonl", E / "r2/snapshots", set(valid["r2"])),
        "fresh": (E / "public/freshswe-py/data/tasks.jsonl", E / "public/freshswe-py/data/snapshots", None)}
OFFICIAL_REPOS = {"fastapi/fastapi", "Textualize/rich", "textualize/rich", "willmcgugan/rich"}
hints, ids, why = {}, [], {}
for s, (tf, snaps, keep) in SETS.items():
    rows = []
    for t in map(json.loads, open(tf)):
        tid = t["instance_id"]
        if (keep is not None and tid not in keep) or t.get("repo") in OFFICIAL_REPOS or tid in hints:
            continue
        if len(t["patch"]) > 10_000:
            why[tid] = "long"; continue
        fs = files_of(t["patch"])
        snap = snaps / f"{tid}.tgz"
        if not snap.exists() or any(new for _, new, _ in fs):
            why[tid] = "no snapshot" if not snap.exists() else "creates a file"; continue
        ok = True
        with tempfile.TemporaryDirectory() as d:
            with tarfile.open(snap) as tar:
                tar.extractall(d, filter="data")
            for path, _, hunks in fs:
                p = Path(d) / path
                if not p.is_file():
                    ok = False; break
                text = p.read_text(errors="replace")
                for old, new in hunks:
                    a, b = "\n".join(old) + "\n", "\n".join(new) + "\n"
                    if text.count(a) != 1:
                        ok = False; break
                    text = text.replace(a, b)
                if not ok:
                    break
        if not ok:
            why[tid] = "search text not unique"; continue
        cmds = []
        for path, _, hunks in fs:
            blocks = "".join("<<<<<<< SEARCH\n" + "\n".join(o) + "\n=======\n" + "\n".join(n) + "\n>>>>>>> REPLACE\n" for o, n in hunks)
            cmds.append(f"python3 .git/tools/edit.py <<'EDIT'\nFILE: {path}\n{blocks}EDIT")
        hint = "\n\nThe fix is this change to the repository, written as the edit command(s) to run:\n```\n" + "\n\n".join(cmds) + "\n```\n"
        hints[tid] = hint
        rows.append({**t, "problem_statement": t["problem_statement"].rstrip() + hint})
        ids.append(f"{s} {tid}")
    open(OUT / f"tasks_{s}.jsonl", "w").write("".join(json.dumps(r) + "\n" for r in rows))
    print(f"{s}: {len(rows)} tasks kept", flush=True)
json.dump(hints, open(OUT / "hints.json", "w"))
open(OUT / "ids.txt", "w").write("\n".join(ids) + "\n")
import collections
print(f"total {len(ids)} tasks; left out: {dict(collections.Counter(why.values()))}")
print("COL1_PREP_DONE")
