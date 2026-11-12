"""Compact view of one session: each solver call (command, first lines of its result), thinking excerpts, final patch hunks vs reference."""
import json, sys, re, glob, os
sys.path.insert(0, os.path.expanduser("~/workspace/Gemma4/work/rtx_test"))
import placement_census as pc
E = os.path.expanduser("~/workspace/Gemma4/work/extra_tasks")
REF = {}
for f in (E + "/r1/tasks.jsonl", E + "/r2/tasks.jsonl", E + "/public/freshswe-py/data/tasks.jsonl"):
    for l in open(f):
        t = json.loads(l); REF[t["instance_id"]] = t
run, task, k, think = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4]) if len(sys.argv) > 4 else 250
d = os.path.expanduser(f"~/workspace/Gemma4/work/rtx_test/runs/{run}/{task}_t{k}")
res = json.loads(open(d + "/task_results.jsonl").readline())
rows = [json.loads(l) for l in open(d + "/llm_calls.jsonl")]
rows = [r for r in rows if r["instance_id"] == task and any(t["function"]["name"] == "run_command" for t in r.get("tools") or [])]
print(f"### {run} {task} t{k}: resolved {res.get('resolved')}, patch bytes {res.get('agent_patch_size')}, {len(rows)} solver calls")
print("reference hunks:", dict(pc.hunks(REF[task]["patch"])))
print("issue:", REF[task]["problem_statement"][:300].replace("\n", " "))
msgs = rows[-1]["messages"]
results = {m.get("tool_call_id"): (m["content"] if isinstance(m["content"], str) else json.dumps(m["content"])) for m in msgs if m.get("role") == "tool"}
for i, r in enumerate(rows, 1):
    m = r["response"]["choices"][0]["message"]
    th = (m.get("reasoning_content") or m.get("reasoning") or "").replace("\n", " ")
    for c in m.get("tool_calls") or []:
        try: cmd = json.loads(c["function"]["arguments"]).get("command", "") or c["function"]["name"]
        except Exception: cmd = c["function"]["arguments"]
        out = results.get(c.get("id"), "")
        try: out = json.loads(out).get("stdout", out)
        except Exception: pass
        out = re.sub(r"\s+", " ", str(out))
        tag = ""
        if "edit.py" in cmd:
            tag = " [EDIT " + ("applied" if ": edited" in out else "NOT applied") + ("; TESTS BROKEN" if "TESTS BROKEN" in out else "; tests ok" if "no existing test broke" in out else "") + "]"
            cmd = re.sub(r"\s+", " ", cmd)[:260]
        print(f"{i:2d}. think[{len(th)}]: {th[:think]}")
        print(f"    $ {cmd[:260]}{tag}")
        print(f"    -> {out[:220]}")
    if not m.get("tool_calls"):
        print(f"{i:2d}. text: {(m.get('content') or '')[:200]}")
patch = "".join(open(p, errors="replace").read() for p in glob.glob(d + "/patches/*"))
print("final patch hunks:", dict(pc.hunks(patch)), "| place:", pc.place(pc.hunks(patch), pc.hunks(REF[task]["patch"])))
