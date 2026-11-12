"""One row per session of an arm_test run (folders <bundle>_<task>_t<k>): python3 -I test_census.py <out.csv> <runs dir> <tasks.jsonl>..."""
import csv, glob, json, os, re, sys, importlib.util
spec = importlib.util.spec_from_file_location("pc", os.path.join(os.path.dirname(os.path.abspath(__file__)), "placement_census.py"))
pc = importlib.util.module_from_spec(spec); spec.loader.exec_module(pc)
out, runs, *files = sys.argv[1:]
gold = {}
for f in files:
    for l in open(f):
        t = json.loads(l); gold[t["instance_id"]] = pc.hunks(t["patch"])
rows = []
for f in sorted(glob.glob(os.path.join(runs, "*_t[0-9]*", "task_results.jsonl"))):
    d = os.path.dirname(f); name, k = os.path.basename(d).rsplit("_t", 1)
    task = next((t for t in gold if name.endswith("_" + t)), None)
    if not task: continue
    arm = name[:-len(task) - 1]
    r = [json.loads(l) for l in open(f) if l.strip()][-1]
    patch = "".join(open(p, errors="replace").read() for p in glob.glob(os.path.join(d, "patches", "*")))
    row = {"arm": arm, "task": task, "try": int(k), "solved": int(bool(r.get("resolved"))), "place": pc.place(pc.hunks(patch), gold[task]),
           "gold_files": len(gold[task]), "error": str(r.get("error"))[:60], "crash": int(pc.CRASH in str(r.get("error")))}
    row.update(pc.trace(d, task, gold[task]))
    # summaries before the first edit: llm calls without tools in the solver stage are not visible here; count summary markers
    rows.append(row)
fields = ["arm", "task", "try", "solved", "place", "gold_files", "error", "crash", "solver_calls", "first_edit", "first_edit_gold", "read_gold_before", "found_gold_file_before"]
w = csv.DictWriter(open(out, "w", newline=""), fieldnames=fields); w.writeheader(); w.writerows(rows)
print(len(rows), "rows")
