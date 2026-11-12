"""Ladder on a second scaffold (John's go 2026-11-12, after astra review 9): the competition's official single-agent scaffold
(e4b_official_v1: run_command, read_file, edit_file, write_file, submit_patch; no setup stage, no helper scripts), same 77 tasks,
same five rungs. Rungs 1-3 reuse the ladder2 task text unchanged (it names no tool). Rung 4 writes the fix as the scaffold's own
edit_file calls (one per hunk, arguments as JSON); rung 5 adds a one-call apply script, run with run_command from a fixed path
outside the repository, so every arm has exactly the same tools.
Checks every rung-4 task on its snapshot: each old_string occurs exactly once when applied in order, and the result equals git apply.
    python3 -I ladder3_prep.py <competition dir> -> work/ladder3/{tasks_<bundle>.jsonl, ids.txt, fixtool/}
"""
import json, re, shutil, subprocess, sys, tarfile, tempfile
import os
from pathlib import Path

comp = Path(sys.argv[1])
W = Path(os.environ.get("LADDER_WORK", Path.home() / "workspace/Gemma4/work"))   # folder holding ladder*/, bundles/, rtx_test/
L2, OUT = W / "ladder2", W / "ladder3"
FIXDIR = OUT / "fixtool"
FIXDIR.mkdir(parents=True, exist_ok=True)
ids = open(L2 / "ids.txt").read().split()
load = lambda b: {t["instance_id"]: t for t in map(json.loads, open(L2 / f"tasks_{b}.jsonl"))}
ctrl, loc, diff = load("e4b_loc_ctrl_v1"), load("e4b_loc_hint_v1"), load("e4b_diff_v1")
gold = {t["instance_id"]: t for t in map(json.loads, open(comp / "tasks.jsonl"))}
MARK = "\n\nThe fix is this change to the repository:\n```diff\n"


def files_of(patch):
    """[(path, [(old_lines, new_lines), ...])] from a unified diff (no new files: those tasks are already excluded)."""
    res, cur, hunk = [], None, None
    for line in patch.splitlines():
        if line.startswith("--- "):
            cur = None
        elif line.startswith("+++ "):
            path = line[4:].split("\t")[0]
            cur = [path[2:] if path.startswith("b/") else path, []]; res.append(cur)
        elif line.startswith("@@") and cur is not None:
            hunk = ([], []); cur[1].append(hunk)
        elif cur is not None and hunk is not None and line[:1] in (" ", "-", "+"):
            if line[0] in " -":
                hunk[0].append(line[1:])
            if line[0] in " +":
                hunk[1].append(line[1:])
    return res


rows = {k: [] for k in ("ctrl", "loc", "diff", "edits", "apply")}
bad = []
for tid in ids:
    patch = gold[tid]["patch"] if gold[tid]["patch"].endswith("\n") else gold[tid]["patch"] + "\n"
    calls = [{"filepath": p, "old_string": "\n".join(o), "new_string": "\n".join(n)} for p, hunks in files_of(patch) for o, n in hunks]
    with tempfile.TemporaryDirectory() as d:
        with tarfile.open(comp / "snapshots" / f"{tid}.tgz") as tf:
            tf.extractall(d, filter="data")
        texts, why = {}, ""
        for c in calls:
            p = Path(d) / c["filepath"]
            text = texts.get(c["filepath"], p.read_text() if p.is_file() else None)
            if text is None or text.count(c["old_string"]) != 1:
                why = f"old_string found {0 if text is None else text.count(c['old_string'])} times in {c['filepath']}"; break
            texts[c["filepath"]] = text.replace(c["old_string"], c["new_string"])
        if not why:
            pf = Path(d) / ".fix.patch"; pf.write_text(patch)
            subprocess.run(["git", "apply", str(pf)], cwd=d, capture_output=True)
            why = next((f"differs from git apply in {f}" for f, t in texts.items() if (Path(d) / f).read_text() != t), "")
    if why:
        bad.append((tid, why)); continue
    base = diff[tid]["problem_statement"]
    assert MARK in base, tid
    rows["ctrl"].append(ctrl[tid]); rows["loc"].append(loc[tid]); rows["diff"].append(diff[tid])
    shown = "\n\n".join(json.dumps(c, indent=1) for c in calls)
    rows["edits"].append({**diff[tid], "problem_statement": base.split(MARK)[0].rstrip() +
                          "\n\nThe fix is this change to the repository, written as the edit_file call(s) to make, in order "
                          "(each one's arguments as JSON):\n```json\n" + shown + "\n```\n"})
    rows["apply"].append({**diff[tid], "problem_statement": base.rstrip() +
                          f"\nIt is saved as a script: run `python3 -m apply_fix {tid}` with run_command to apply it exactly.\n"})
names = {"ctrl": "e4b_off_ctrl_v1", "loc": "e4b_off_loc_v1", "diff": "e4b_off_diff_v1", "edits": "e4b_off_edits_v1", "apply": "e4b_off_apply_v1"}
for k, b in names.items():
    open(OUT / f"tasks_{b}.jsonl", "w").write("".join(json.dumps(r) + "\n" for r in rows[k]))
open(OUT / "ids.txt", "w").write("\n".join(r["instance_id"] for r in rows["edits"]) + "\n")
(FIXDIR / "apply_fix.py").write_text((W / "rtx_test/apply_fix.py").read_text().replace("python3 .git/tools/apply_fix.py", "python3 -m apply_fix"))
open(FIXDIR / "fixes_data.py", "w").write("FIXES = " + repr({tid: (gold[tid]["patch"] if gold[tid]["patch"].endswith("\n") else gold[tid]["patch"] + "\n") for tid in ids}) + "\n")
# The sandbox is Docker: the harness unpacks every small wheel of the task's wheels folder into the container's site-packages.
# The apply arm alone gets a copy of the wheels folder plus this wheel, so `python3 -m apply_fix <id>` works inside the container.
import base64, hashlib, zipfile
files = {"apply_fix.py": (FIXDIR / "apply_fix.py").read_bytes(), "fixes_data.py": (FIXDIR / "fixes_data.py").read_bytes(),
         "swe_fixtool-1.0.dist-info/METADATA": b"Metadata-Version: 2.1\nName: swe-fixtool\nVersion: 1.0\n",
         "swe_fixtool-1.0.dist-info/WHEEL": b"Wheel-Version: 1.0\nGenerator: ladder3_prep\nRoot-Is-Purelib: true\nTag: py3-none-any\n",
         "swe_fixtool-1.0.dist-info/top_level.txt": b"apply_fix\nfixes_data\n"}
rec = "".join(f"{n},sha256={base64.urlsafe_b64encode(hashlib.sha256(b).digest()).rstrip(b'=').decode()},{len(b)}\n" for n, b in files.items())
files["swe_fixtool-1.0.dist-info/RECORD"] = (rec + "swe_fixtool-1.0.dist-info/RECORD,,\n").encode()
for repo in ("fastapi", "rich"):
    dst = W / f"wheels_{repo}_fix"
    shutil.rmtree(dst, ignore_errors=True); shutil.copytree(W / f"wheels_{repo}", dst)
    with zipfile.ZipFile(dst / "swe_fixtool-1.0-py3-none-any.whl", "w") as z:
        for n, b in files.items():
            z.writestr(n, b)
print(f"{len(ids)} tasks; valid for every rung {len(rows['edits'])}; excluded {bad}")
print("LADDER3_PREP_DONE")
