"""Reinforcement round 1 against the concurrent untrained control, on the 234 frontier tasks (run on the RTX in rtx_test/runs).
    python3 -I rl1_summary.py <runs dir> <frontier.txt>"""
import collections, glob, json, sys
runs, ft = sys.argv[1], set(open(sys.argv[2]).read().split())
for run, what in (("rl1_r1", "reinforcement adapter, round 1"), ("rl1_plain", "untrained, concurrent control")):
    n = s = 0
    for d in glob.glob(f"{runs}/{run}/*_t[0-9]"):
        try:
            r = json.loads(open(d + "/task_results.jsonl").readline())
        except (OSError, ValueError):
            continue
        if r["instance_id"] in ft:
            n += 1; s += r["resolved"] in (True, "True")
    print(f"{run} ({what}): {s} of {n} frontier tries solved ({100 * s / n:.1f}%)")
