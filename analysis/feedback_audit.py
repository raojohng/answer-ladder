"""Idea 2 / plan 2.2: what feedback did each untrained v8 try get after its edits, and what did it do with it?
Tool calls and results are collected from every request of the session (compaction drops old results from later requests);
a result that comes back as status "error" is read from details.stdout as well."""
import json, glob, collections, multiprocessing, os, sys
def text(content):
    t = content if isinstance(content, str) else json.dumps(content)
    try:
        d = json.loads(t)
        if isinstance(d, dict):
            return str(d.get("stdout") or (d.get("details") or {}).get("stdout") or t)
    except Exception:
        pass
    return t
def one(d):
    try:
        res = json.loads(open(d + "/task_results.jsonl").readline())
        rows = [json.loads(l) for l in open(d + "/llm_calls.jsonl")]
    except Exception:
        return None
    task = os.path.basename(d).rsplit("_t", 1)[0]
    rows = [r for r in rows if r.get("instance_id") == task and any(t["function"]["name"] == "run_command" for t in r.get("tools") or [])]
    if not rows:
        return None
    order, cmds, results = [], {}, {}
    for r in rows:
        for m in r["messages"]:
            if m.get("role") == "tool" and m.get("tool_call_id"):
                results[m["tool_call_id"]] = text(m["content"])
        for c in r["response"]["choices"][0]["message"].get("tool_calls") or []:
            try:
                cmd = json.loads(c["function"]["arguments"]).get("command", "") or c["function"]["name"]
            except Exception:
                cmd = c["function"]["name"]
            order.append(c.get("id")); cmds[c.get("id")] = cmd
    events, own = [], False
    for cid in order:
        cmd, out = cmds[cid], results.get(cid, "")
        if "edit.py" in cmd and ": edited" in out:
            events.append("broken" if "TESTS BROKEN" in out else "ok" if "no existing test broke" in out else "none")
        elif "check.py" in cmd and events:
            events.append("check_broken" if "TESTS BROKEN" in out else "check_other")
        elif events and ("python" in cmd or "pytest" in cmd) and not any(x in cmd for x in (".git/tools/",)):
            own = True
        elif cmd == "submit_patch":
            events.append("submit")
    applied = [e for e in events if e in ("broken", "ok", "none")]
    last_evidence = next((e for e in reversed(events) if e in ("broken", "ok", "none", "check_broken")), None)
    return dict(solved=bool(res.get("resolved")), patch=bool(res.get("agent_patch_size")), applied=len(applied), last=last_evidence,
                own=own, crash="No LlmAgent model" in str(res.get("error")), missing=sum(cid not in results for cid in order))
dirs = [d for run in ("v8_sweep", "fresh_v8_p1") for d in glob.glob(f"runs/{run}/*_t[0-9]*")]
with multiprocessing.Pool(24) as p:
    out = [x for x in p.map(one, dirs, chunksize=16) if x and not x["crash"]]
print(f"{len(out)} sessions; tool results missing for {sum(x['missing'] > 0 for x in out)} (calls without any recorded result)")
for lab, sel in (("solved", lambda x: x["solved"]), ("failed with a patch", lambda x: not x["solved"] and x["patch"])):
    s = [x for x in out if sel(x) and x["applied"]]
    n = len(s)
    last = collections.Counter("broken" if x["last"] in ("broken", "check_broken") else x["last"] for x in s)
    edits = collections.Counter(min(x["applied"], 3) for x in s)
    print(f"{lab}: {n} tries with an applied edit | applied edits 1: {100*edits[1]/n:.0f}%, 2: {100*edits[2]/n:.0f}%, 3+: {100*edits[3]/n:.0f}% | "
          f"last test evidence before submitting: no existing test broke {100*last['ok']/n:.0f}%, tests broken {100*last['broken']/n:.0f}%, "
          f"none ran {100*last['none']/n:.0f}% | own python/pytest check after editing {100*sum(x['own'] for x in s)/n:.0f}%")
