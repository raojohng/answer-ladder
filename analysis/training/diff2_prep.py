"""Prepare the follow-up arms of the diff test (run only if diff1 falls well short; John's go 2026-11-11 23:35 IST).
  D1 apply  : same text as diff1, plus "It is saved in the repository: run python3 .git/tools/apply_fix.py <task id> to apply it exactly."
              The bundle carries every task's patch by task id; apply_fix.py runs git apply.
  D2 blocks : problem statement + the same fix written as the exact edit.py commands the scaffold accepts (one per file).
Checks every task offline on its snapshot: git apply --check for D1, and for D2 that every SEARCH text occurs exactly once
(in sequence) and that applying the blocks gives the same files as git apply.
    python3 -I diff2_prep.py <competition dir> <ids_diff.txt> <out folder>
"""
import json, os, re, subprocess, sys, tarfile, tempfile
from pathlib import Path

comp, ids_file, out = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3])
ids = open(ids_file).read().split()
tasks = {t["instance_id"]: t for t in map(json.loads, open(comp / "tasks.jsonl")) if t["instance_id"] in ids}
(out / "fixes").mkdir(parents=True, exist_ok=True)


def files_of(patch):
    """[(path, new_file, [(old_lines, new_lines), ...])] from a unified diff."""
    res, cur, hunk = [], None, None
    for line in patch.splitlines():
        if line.startswith("--- "):
            cur = None
        elif line.startswith("+++ "):
            path = line[4:].split("\t")[0]
            path = path[2:] if path.startswith("b/") else path
            cur = [path, False, []]
            res.append(cur)
        elif line.startswith("@@") and cur is not None:
            if re.match(r"@@ -0,0 ", line):
                cur[1] = True
            hunk = ([], [])
            cur[2].append(hunk)
        elif cur is not None and hunk is not None and line[:1] in (" ", "-", "+"):
            if line[0] in " -":
                hunk[0].append(line[1:])
            if line[0] in " +":
                hunk[1].append(line[1:])
        elif line.startswith("\\"):
            pass
    return res


rows_d1, rows_d2, report, keymap = [], [], [], {}
for tid in ids:
    t = tasks[tid]
    with tempfile.TemporaryDirectory() as d:
        with tarfile.open(comp / "snapshots" / f"{tid}.tgz") as tf:
            tf.extractall(d, filter="data")
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=d, capture_output=True, text=True).stdout.strip()
        pf = Path(d) / ".fix.patch"; pf.write_text(t["patch"] if t["patch"].endswith("\n") else t["patch"] + "\n")
        ok1 = subprocess.run(["git", "apply", "--check", str(pf)], cwd=d, capture_output=True, text=True).returncode == 0
        # D2 simulation
        fs = files_of(t["patch"]); ok2, why = True, ""
        sim = {}
        for path, new, hunks in fs:
            if new:
                ok2, why = False, f"creates {path}"; break
            p = Path(d) / path
            text = p.read_text() if p.is_file() else None
            if text is None:
                ok2, why = False, f"missing {path}"; break
            for old, newl in hunks:
                s, r = "\n".join(old) + "\n", "\n".join(newl) + "\n"
                if text.count(s) != 1:
                    ok2, why = False, f"SEARCH found {text.count(s)} times in {path}"; break
                text = text.replace(s, r)
            if not ok2:
                break
            sim[path] = text
        if ok1 and ok2:
            subprocess.run(["git", "apply", str(pf)], cwd=d, capture_output=True)
            for path, text in sim.items():
                if (Path(d) / path).read_text() != text:
                    ok2, why = False, f"blocks differ from git apply in {path}"
    keymap.setdefault(head, []).append(tid)
    (out / "fixes" / f"{tid}.patch").write_text(t["patch"] if t["patch"].endswith("\n") else t["patch"] + "\n")
    diff_text = "\n\nThe fix is this change to the repository:\n```diff\n" + t["patch"].rstrip() + "\n```\n"
    rows_d1.append({**t, "problem_statement": t["problem_statement"].rstrip() + diff_text +
                    f"It is saved in the repository: run `python3 .git/tools/apply_fix.py {tid}` to apply it exactly.\n"})
    if ok2:
        cmds = []
        for path, new, hunks in fs:
            blocks = "".join(f"<<<<<<< SEARCH\n" + "\n".join(o) + "\n=======\n" + "\n".join(n) + "\n>>>>>>> REPLACE\n" for o, n in hunks)
            cmds.append(f"python3 .git/tools/edit.py <<'EDIT'\nFILE: {path}\n{blocks}EDIT")
        text = ("\n\nThe fix is this change to the repository, written as the edit command(s) to run:\n```\n" + "\n\n".join(cmds) + "\n```\n")
        rows_d2.append({**t, "problem_statement": t["problem_statement"].rstrip() + text})
    report.append((tid, head[:10], ok1, ok2, why))
open(out / "tasks_e4b_diff_apply_v1.jsonl", "w").write("".join(json.dumps(r) + "\n" for r in rows_d1))
open(out / "tasks_e4b_diff_blocks_v1.jsonl", "w").write("".join(json.dumps(r) + "\n" for r in rows_d2))
open(out / "ids_d2.txt", "w").write("\n".join(r[0] for r in report if r[3]) + "\n")
json.dump(keymap, open(out / "fixes" / "index.json", "w"), indent=1)
open(out / "fixes_data.py", "w").write("FIXES = " + repr({tid: (tasks[tid]["patch"] if tasks[tid]["patch"].endswith("\n") else tasks[tid]["patch"] + "\n") for tid in ids}) + "\n")
print(f"{len(report)} tasks; git apply --check ok {sum(r[2] for r in report)}; D2 blocks valid {sum(r[3] for r in report)}; "
      f"distinct snapshot heads {len(keymap)}")
for r in report:
    if not (r[2] and r[3]):
        print("  ", r)
