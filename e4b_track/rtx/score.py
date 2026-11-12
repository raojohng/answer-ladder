"""Score an agent on the Answer Ladder.

Your runs: one harness results folder per rung (searched recursively for task_results.jsonl; every line is one try):
    python3 score.py --rung control=runs/ctrl --rung lines=runs/loc --rung patch=runs/diff --rung commands=runs/edits --rung apply=runs/apply
The released sessions (reproduces the paper's ladder and graph tables; no GPU, a few seconds):
    python3 score.py --release sessions/
Prints, per rung: tries, share of tries solved, solves per pass (expected tasks solved by one try of every task), tasks solved at
least once and in every try; then each rung minus the rung before it with a paired 95% task-bootstrap interval (2,000 resamples,
seed 1). Only tasks present in every rung are scored; --ids restricts them further (default: tasks/ids_77.txt beside this script
when it exists). Standard library only.
"""
import argparse, collections, io, json, random, sys, tarfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
# released runs: run -> [(rung, session-name prefix)]
RELEASE = {
    "Our scaffold, first run (E4B)": [("control", "loc1", "e4b_loc_ctrl_v1"), ("reference lines", "loc1", "e4b_loc_hint_v1"),
                                       ("reference patch", "diff1", "e4b_diff_v1"), ("edit commands", "d2_e4b_diff_blocks_v1", "e4b_diff_blocks_v1"),
                                       ("apply tool", "d2_e4b_diff_apply_v2", "e4b_diff_apply_v2")],
    "Our scaffold, replication (E4B)": [(r, "ladder2", b) for r, b in (("control", "e4b_loc_ctrl_v1"), ("reference lines", "e4b_loc_hint_v1"),
                                         ("reference patch", "e4b_diff_v1"), ("edit commands", "e4b_diff_blocks_v1"), ("apply tool", "e4b_diff_apply_v2"))],
    "Official loop (E4B)": [(r, "ladder3", f"e4b_off_{b}_v1") for r, b in (("control", "ctrl"), ("reference lines", "loc"),
                             ("reference patch", "diff"), ("edit commands", "edits"), ("apply tool", "apply"))],
    "Official loop (Qwen3.5-4B)": [(r, "ladder5", f"q4b_off_{b}_v1") for r, b in (("control", "ctrl"), ("reference lines", "loc"),
                                    ("reference patch", "diff"), ("edit commands", "edits"), ("apply tool", "apply"))],
    "Official loop (Gemma 4 E2B)": [(r, "ladder8", f"e2b_off_{b}_v1") for r, b in (("control", "ctrl"), ("reference lines", "loc"),
                                     ("reference patch", "diff"), ("edit commands", "edits"), ("apply tool", "apply"))],
    "Graph arms (E4B, our scaffold)": [(r, "ladder4", b) for r, b in (("control", "e4b_loc_ctrl_v1"), ("graph tools", "e4b_gpull_v1"),
                                        ("graph hint", "e4b_ghint_v1"), ("reference lines", "e4b_loc_hint_v1"))],
    "Graph arms, second run (E4B, our scaffold)": [(r, "ladder6", b) for r, b in (("control", "e4b_loc_ctrl_v1"), ("text-only hint", "e4b_thint_v1"),
                                                    ("graph hint", "e4b_ghint_v1"), ("graph tools + instruction", "e4b_gpull2_v1"))],
}


def report(name, rungs, ids):
    """rungs: [(rung, {task: [solved, ...]})] in ladder order."""
    tasks = set.intersection(*(set(r) for _, r in rungs))
    if ids:
        tasks &= ids
    tasks = sorted(tasks)
    if not tasks:
        print(f"{name}: no task present in every rung"); return
    per = lambda r, ts: sum(sum(r[t]) / len(r[t]) for t in ts)
    print(f"\n{name}: {len(tasks)} tasks")
    print(f"  {'rung':28s} {'tries':>6s} {'solved':>8s} {'per pass':>9s} {'once':>5s} {'every try':>10s}")
    for rung, r in rungs:
        n = sum(len(r[t]) for t in tasks); s = sum(sum(r[t]) for t in tasks)
        print(f"  {rung:28s} {n:6d} {100 * per(r, tasks) / len(tasks):7.1f}% {per(r, tasks):9.1f} "
              f"{sum(any(r[t]) for t in tasks):5d} {sum(all(r[t]) for t in tasks):10d}")
    random.seed(1)
    samples = [[random.choice(tasks) for _ in tasks] for _ in range(2000)]
    for (ra, a), (rb, b) in zip(rungs[1:], rungs[:-1]):
        d = sorted(per(a, s) - per(b, s) for s in samples)
        print(f"  {ra} - {rb}: {per(a, tasks) - per(b, tasks):+.1f} solves per pass ({d[50]:+.1f} to {d[1949]:+.1f})")
    names = [r for r, _ in rungs]
    if "apply tool" in names and "reference patch" in names:   # execution help beyond the patch (the paper's tool-over-patch)
        a, b = rungs[names.index("apply tool")][1], rungs[names.index("reference patch")][1]
        d = sorted(per(a, s) - per(b, s) for s in samples)
        print(f"  apply tool - reference patch: {per(a, tasks) - per(b, tasks):+.1f} solves per pass ({d[50]:+.1f} to {d[1949]:+.1f})")


def from_dirs(paths):
    r = collections.defaultdict(list)
    for p in paths:
        for f in Path(p).rglob("task_results.jsonl"):
            for line in open(f):
                if line.strip():
                    x = json.loads(line); r[x["instance_id"]].append(x["resolved"] in (True, "True", "true", 1))
    return r


def from_release(sessions):
    """Reads <run>.tar.gz archives, or the same sessions unpacked (Kaggle unpacks archives on upload, giving
    sessions/<run>/<run>/<session>/; a local `tar -xzf` gives <dir>/<run>/<session>/)."""
    by = collections.defaultdict(lambda: collections.defaultdict(list))   # (run, session prefix) -> task -> [solved]

    def add(run, sess, line):
        x = json.loads(line)
        prefix = sess[: -len(f"_{x['instance_id']}_t1")]
        by[(run, prefix)][x["instance_id"]].append(x["resolved"] in (True, "True"))

    archives = sorted(Path(sessions).glob("*.tar.gz"))
    for tgz in archives:
        with tarfile.open(tgz) as tar:
            for m in tar:
                if m.name.endswith("/task_results.jsonl"):
                    run, sess = m.name.split("/")[:2]
                    add(run, sess, tar.extractfile(m).readline())
    if not archives:
        for f in sorted(Path(sessions).rglob("task_results.jsonl")):
            sess, run = f.parent.name, f.parent.parent.name
            add(run, sess, open(f).readline())
    return by


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rung", action="append", default=[], help="name=results folder (repeat, in ladder order)")
    ap.add_argument("--release", help="folder of the released session archives")
    ap.add_argument("--ids", help="file of task ids to score (default tasks/ids_77.txt beside this script)")
    a = ap.parse_args()
    idfile = Path(a.ids) if a.ids else HERE.parent / "tasks/ids_77.txt"
    ids = set(idfile.read_text().split()) if idfile.exists() else None
    if a.release:
        by = from_release(a.release)
        for name, spec in RELEASE.items():
            if all((run, prefix) in by for _, run, prefix in spec):
                report(name, [(rung, by[(run, prefix)]) for rung, run, prefix in spec], ids)
    elif a.rung:
        report("Your agent", [(x.split("=", 1)[0], from_dirs([x.split("=", 1)[1]])) for x in a.rung], ids)
    else:
        ap.print_help(); sys.exit(1)
