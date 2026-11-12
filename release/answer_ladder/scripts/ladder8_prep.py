"""ladder8 (GPU 1, after the graph ablation): the official-loop ladder (ladder3's five task files) with Gemma 4 E2B (4-bit), the competition's smaller model (third model of the benchmark; John 2026-11-12),
after Qwen3.5-4B was dropped (its tool-call JSON was malformed in 5 of its first 6 sessions, which the harness treats as fatal).
Bundles e2b_off_<rung>_v1 are e4b_off_<rung>_v1 with only the model line changed."""
import shutil
import os
from pathlib import Path
W = Path(os.environ.get("LADDER_WORK", Path.home() / "workspace/Gemma4/work"))   # folder holding ladder*/, bundles/, rtx_test/
B = W / "bundles"; L3, L8 = W / "ladder3", W / "ladder8"
L8.mkdir(exist_ok=True)
for rung in ("ctrl", "loc", "diff", "edits", "apply"):
    shutil.copy(L3 / f"tasks_e4b_off_{rung}_v1.jsonl", L8 / f"tasks_e2b_off_{rung}_v1.jsonl")
    dst = B / f"e2b_off_{rung}_v1"
    shutil.rmtree(dst, ignore_errors=True); shutil.copytree(B / f"e4b_off_{rung}_v1", dst)
    y = dst / "agent/agent.yaml"; t = y.read_text(); assert "model: gemma-4-e4b-it-qat-w4a16-ct" in t
    y.write_text(t.replace("model: gemma-4-e4b-it-qat-w4a16-ct", "model: gemma-4-e2b-it-qat-w4a16-ct"))
shutil.copy(L3 / "ids.txt", L8 / "ids.txt")
print("LADDER8_PREP_DONE")
