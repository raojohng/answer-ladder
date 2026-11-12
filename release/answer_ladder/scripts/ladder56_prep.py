"""Two runs after the v10 reviews (John 2026-11-12: yes to all; GPU 0 for the paper, GPU 1 for the two awards).
ladder5 (GPU 0): the official-loop ladder (ladder3's five task files) with a second model, Qwen3.5-4B: bundles q4b_off_<rung>_v1
         are e4b_off_<rung>_v1 with only the model line changed.
ladder6 (GPU 1): the graph arms again on our scaffold, E4B, interleaved, new seeds:
         e4b_loc_ctrl_v1  control
         e4b_thint_v1     text-only hint: the same builder and format with graph and embedding weights 0 (FORCE_WEIGHTS=0,0)
         e4b_ghint_v1     graph hint (as in ladder4)
         e4b_gpull2_v1    graph tools offered AND an instruction in the task to use them first
    python3 -I ladder56_prep.py <text hints.json> <graph hints.json>
"""
import json, os, shutil, sys
from pathlib import Path

W = Path(os.environ.get("LADDER_WORK", Path.home() / "workspace/Gemma4/work"))   # folder holding ladder*/, bundles/, rtx_test/
B = W / "bundles"
# ladder5
L3, L5 = W / "ladder3", W / "ladder5"
L5.mkdir(exist_ok=True)
for rung in ("ctrl", "loc", "diff", "edits", "apply"):
    shutil.copy(L3 / f"tasks_e4b_off_{rung}_v1.jsonl", L5 / f"tasks_q4b_off_{rung}_v1.jsonl")
    dst = B / f"q4b_off_{rung}_v1"
    shutil.rmtree(dst, ignore_errors=True); shutil.copytree(B / f"e4b_off_{rung}_v1", dst)
    y = dst / "agent/agent.yaml"; t = y.read_text()
    assert "model: gemma-4-e4b-it-qat-w4a16-ct" in t
    y.write_text(t.replace("model: gemma-4-e4b-it-qat-w4a16-ct", "model: Qwen3.5-4B"))
shutil.copy(L3 / "ids.txt", L5 / "ids.txt")
# ladder6
text_hints, graph_hints = json.load(open(sys.argv[1]))["hints"], json.load(open(sys.argv[2]))["hints"]
L4, L6 = W / "ladder4", W / "ladder6"
L6.mkdir(exist_ok=True)
CTRL = "Where to change: find this in the repository yourself."
ctrl = {t["instance_id"]: t for t in map(json.loads, open(L4 / "tasks_e4b_loc_ctrl_v1.jsonl"))}
ids = open(L4 / "ids.txt").read().split()
PULL = ("Where to change: find this in the repository yourself. Start with the code graph tools: search_similar_code and "
        "get_code_neighbors find the functions related to this issue.")
rows = {"e4b_loc_ctrl_v1": [], "e4b_thint_v1": [], "e4b_ghint_v1": [], "e4b_gpull2_v1": []}
for tid in ids:
    s = ctrl[tid]["problem_statement"]; assert s.count(CTRL) == 1
    hint = lambda h: s.replace(CTRL, "Where to look first (suggested by the repository's code graph; it may be wrong): " + h + ".")
    rows["e4b_loc_ctrl_v1"].append(ctrl[tid])
    rows["e4b_thint_v1"].append({**ctrl[tid], "problem_statement": hint(text_hints[tid])})
    rows["e4b_ghint_v1"].append({**ctrl[tid], "problem_statement": hint(graph_hints[tid])})
    rows["e4b_gpull2_v1"].append({**ctrl[tid], "problem_statement": s.replace(CTRL, PULL)})
for b, r in rows.items():
    open(L6 / f"tasks_{b}.jsonl", "w").write("".join(json.dumps(x) + "\n" for x in r))
shutil.copy(L4 / "ids.txt", L6 / "ids.txt")
for d in ("graphs", "embeddings"):
    if not (L6 / d).exists():
        os.symlink(L4 / d, L6 / d)
for b, src in (("e4b_thint_v1", "e4b_loc_ctrl_v1"), ("e4b_gpull2_v1", "e4b_gpull_v1")):
    shutil.rmtree(B / b, ignore_errors=True); shutil.copytree(B / src, B / b)
print("ladder5:", len(ids), "tasks x 5 Qwen bundles; ladder6:", {b: len(r) for b, r in rows.items()})
print("LADDER56_PREP_DONE")
