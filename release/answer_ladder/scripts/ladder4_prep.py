"""Graph arms on the main scaffold (John 2026-11-12: one paper that also covers a new application and a new resource).
Same 77 tasks as the ladder, interleaved, 3 tries:
  e4b_loc_ctrl_v1  control        "Where to change: find this in the repository yourself."
  e4b_gpull_v1     graph tools    control text; the agent also has the harness's search_similar_code, get_code_neighbors and
                                  get_code_subgraph (the harness appends its own "Code Intelligence Tools" note)
  e4b_ghint_v1     graph hint     the line becomes the top-5 nodes from graph_hint.py (text + call graph + embeddings, no answer)
  e4b_loc_hint_v1  oracle         the reference files and lines
    python3 -I ladder4_prep.py <hints.json>  -> work/ladder4/{tasks_<bundle>.jsonl, ids.txt, graphs, embeddings}; bundles
"""
import json, os, shutil, sys
from pathlib import Path

W = Path(os.environ.get("LADDER_WORK", Path.home() / "workspace/Gemma4/work"))   # folder holding ladder*/, bundles/, rtx_test/
L2, OUT, B = W / "ladder2", W / "ladder4", W / "bundles"
OUT.mkdir(exist_ok=True)
hints = json.load(open(sys.argv[1]))["hints"]
CTRL = "Where to change: find this in the repository yourself."
ids = open(L2 / "ids.txt").read().split()
load = lambda b: {t["instance_id"]: t for t in map(json.loads, open(L2 / f"tasks_{b}.jsonl"))}
ctrl, loc = load("e4b_loc_ctrl_v1"), load("e4b_loc_hint_v1")
rows = {"e4b_loc_ctrl_v1": [], "e4b_gpull_v1": [], "e4b_ghint_v1": [], "e4b_loc_hint_v1": []}
for tid in ids:
    s = ctrl[tid]["problem_statement"]
    assert s.count(CTRL) == 1, tid
    rows["e4b_loc_ctrl_v1"].append(ctrl[tid]); rows["e4b_gpull_v1"].append(ctrl[tid]); rows["e4b_loc_hint_v1"].append(loc[tid])
    rows["e4b_ghint_v1"].append({**ctrl[tid], "problem_statement": s.replace(
        CTRL, "Where to look first (suggested by the repository's code graph; it may be wrong): " + hints[tid] + ".")})
for b, r in rows.items():
    open(OUT / f"tasks_{b}.jsonl", "w").write("".join(json.dumps(x) + "\n" for x in r))
open(OUT / "ids.txt", "w").write("\n".join(ids) + "\n")
for d in ("graphs", "embeddings"):      # the harness looks beside the tasks file
    if not (OUT / d).exists():
        os.symlink(W.parent / "competition_data" / d, OUT / d)
for b in ("e4b_gpull_v1", "e4b_ghint_v1"):
    shutil.rmtree(B / b, ignore_errors=True); shutil.copytree(B / "e4b_loc_ctrl_v1", B / b)
y = B / "e4b_gpull_v1/agent/sub_agents/swe_agent.yaml"
text = y.read_text()
assert "  - submit_patch\n" in text
y.write_text(text.replace("  - submit_patch\n", "  - submit_patch\n  - search_similar_code\n  - get_code_neighbors\n  - get_code_subgraph\n"))
print(f"{len(ids)} tasks; example hint: {rows['e4b_ghint_v1'][0]['problem_statement'][-400:]}")
print("LADDER4_PREP_DONE")
