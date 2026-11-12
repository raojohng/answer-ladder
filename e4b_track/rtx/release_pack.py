"""Pack the ladder release (the paper's resource): task files of every rung on both scaffolds (77 tasks only), the apply tool and
its wheel, the agent bundles, and every ladder session's results, events, final patch and a compact tool_calls.jsonl (name and
arguments of every model tool call, from the raw LLM request log, which is not shipped because it repeats the full prompt at
every call). Home paths and archive owners are scrubbed.
    python3 -I release_pack.py -> work/release/answer_ladder/"""
import io, json, shutil, tarfile
from pathlib import Path

W = Path.home() / "workspace/Gemma4/work"
OUT = W / "release/answer_ladder"
HOME = str(Path.home()).encode()
shutil.rmtree(OUT, ignore_errors=True); (OUT / "tasks").mkdir(parents=True)
ids = set(open(W / "ladder2/ids.txt").read().split())
RUNS = {  # run folder -> (what it is, session-name prefixes kept or None for all)
    "loc1": ("first run, rungs 1-2 (our scaffold)", ("e4b_loc_ctrl_v1", "e4b_loc_hint_v1")),
    "diff1": ("first run, rung 3", ("e4b_diff_v1",)),
    "d2_e4b_diff_blocks_v1": ("first run, rung 4", ("e4b_diff_blocks_v1",)),
    "d2_e4b_diff_apply_v2": ("first run, rung 5", ("e4b_diff_apply_v2",)),
    "ladder2": ("replication, rungs 1-5 (our scaffold)", None),
    "ladder3": ("official loop, rungs 1-5, Gemma 4 E4B", None),
    "ladder5": ("official loop, rungs 1-5, Qwen3.5-4B (qwen3_coder tool parser)", None),
    "ladder8": ("official loop, rungs 1-5, Gemma 4 E2B", None),
    "ladder4": ("graph arms (our scaffold): control, graph tools, graph hint, reference lines", None),
    "ladder6": ("graph arms, second run: control, text-only hint, graph hint, graph tools with an instruction", None),
}
TASKDIRS = (("our_scaffold", W / "ladder2"), ("official_loop", W / "ladder3"), ("official_loop_qwen", W / "ladder5"), ("official_loop_e2b", W / "ladder8"),
            ("graph_arms", W / "ladder4"), ("graph_arms_2", W / "ladder6"))
for name, src in TASKDIRS:
    (OUT / "tasks" / name).mkdir()
    for f in sorted(src.glob("tasks_*.jsonl")):
        rows = [l for l in open(f) if json.loads(l)["instance_id"] in ids]
        assert len(rows) == 77, (f, len(rows))
        open(OUT / "tasks" / name / f.name, "w").write("".join(rows))
shutil.copy(W / "ladder2/ids.txt", OUT / "tasks/ids_77.txt")
shutil.copytree(W / "ladder3/fixtool", OUT / "apply_tool", ignore=shutil.ignore_patterns("__pycache__"))
shutil.copy(W / "wheels_rich_fix/swe_fixtool-1.0-py3-none-any.whl", OUT / "apply_tool/")
shutil.copy(W / "rtx_test/apply_fix.py", OUT / "apply_tool/apply_fix_skill_script.py")
shutil.copy(W / "diff2/fixes_data.py", OUT / "apply_tool/fixes_data_skill_script.py")
(OUT / "bundles").mkdir()
for b in ("e4b_loc_ctrl_v1", "e4b_loc_hint_v1", "e4b_diff_v1", "e4b_diff_blocks_v1", "e4b_diff_apply_v2", "e4b_gpull_v1", "e4b_gpull2_v1",
          "e4b_ghint_v1", "e4b_thint_v1", "e4b_off_ctrl_v1", "e4b_off_apply_v1", "q4b_off_ctrl_v1", "e2b_off_ctrl_v1"):
    shutil.copytree(W / "bundles" / b / "agent", OUT / "bundles" / b, ignore=shutil.ignore_patterns("__pycache__"))


def scrub(data):
    return data.replace(HOME, b"/home/user").replace(HOME.split(b"/")[-1], b"user")


def add(tar, name, data):
    data = scrub(data)
    info = tarfile.TarInfo(name); info.size = len(data); info.mtime = 0
    tar.addfile(info, io.BytesIO(data))


(OUT / "sessions").mkdir()
index = []
for run, (what, keep) in RUNS.items():
    n = 0
    with tarfile.open(OUT / "sessions" / f"{run}.tar.gz", "w:gz") as tar:
        for d in sorted((W / "rtx_test/runs" / run).glob("*_t[0-9]")):
            r = d / "task_results.jsonl"
            if not r.exists():
                continue
            res = json.loads(open(r).readline())
            if res["instance_id"] not in ids or (keep and not d.name.startswith(keep)):
                continue
            for f in ["task_results.jsonl", "adk_events.jsonl"] + [p.relative_to(d).as_posix() for p in (d / "patches").glob("*")]:
                if (d / f).exists():
                    add(tar, f"{run}/{d.name}/{f}", (d / f).read_bytes())
            calls = []
            if (d / "llm_calls.jsonl").exists():
                for k, line in enumerate(open(d / "llm_calls.jsonl")):
                    try:
                        c = json.loads(line)
                    except ValueError:
                        continue
                    for ch in (c.get("response") or {}).get("choices", []):
                        for t in ch["message"].get("tool_calls") or []:
                            calls.append({"call": k, "name": t["function"]["name"], "arguments": t["function"]["arguments"]})
            add(tar, f"{run}/{d.name}/tool_calls.jsonl", "".join(json.dumps(x) + "\n" for x in calls).encode())
            index.append({"run": run, "session": d.name, "task": res["instance_id"], "resolved": res["resolved"] in (True, "True")})
            n += 1
    print(run, what, n, "sessions")
open(OUT / "sessions/index.jsonl", "w").write("".join(json.dumps(x) + "\n" for x in index))
print(len(index), "sessions; RELEASE_PACK_DONE")
