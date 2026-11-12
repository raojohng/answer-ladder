"""Apply-tool use per model on the official loop (rung 5), from the released sessions. Per try: did any tool call mention
apply_fix in its arguments; did a run_command actually run it (`-m apply_fix`); did the tool report FIX APPLIED; was the try
solved, and did it end without a patch. Tries are split by whether the fix was applied.
    mkdir runs && for r in ladder3 ladder5 ladder8; do tar -xzf sessions/$r.tar.gz -C runs; done
    python3 -I tool_use_models.py runs"""
import collections, glob, json, os, sys

runs = sys.argv[1]
MODELS = {"E4B": ("ladder3", "e4b_off_apply_v1"), "Qwen3.5-4B": ("ladder5", "q4b_off_apply_v1"), "E2B": ("ladder8", "e2b_off_apply_v1")}
for model, (run, arm) in MODELS.items():
    c = collections.Counter()
    for d in sorted(set(glob.glob(f"{runs}/**/{run}/{arm}_*_t[0-9]", recursive=True))):   # any depth (Kaggle: sessions/<run>/<run>/)
        res = json.loads(open(d + "/task_results.jsonl").readline())
        calls = [json.loads(l) for l in open(d + "/tool_calls.jsonl")]
        mentioned = any("apply_fix" in r["arguments"] for r in calls)
        ran = any(r["name"] == "run_command" and "-m apply_fix" in r["arguments"] for r in calls)
        applied = "FIX APPLIED" in open(d + "/adk_events.jsonl").read()
        solved = res["resolved"] in (True, "True")
        no_patch = not res.get("agent_patch_size")
        c["tries"] += 1; c["mentioned"] += mentioned; c["ran"] += ran; c["applied"] += applied
        c["applied, solved"] += applied and solved
        c["not applied"] += not applied; c["not applied, solved"] += (not applied) and solved
        c["not applied, failed without a patch"] += (not applied) and (not solved) and no_patch
    print(f"{model}: " + ", ".join(f"{k} {v}" for k, v in c.items()))
print("TOOL_USE_MODELS_DONE")
