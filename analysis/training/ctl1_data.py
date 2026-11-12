"""Positive control (astra's training review, 2026-11-11): the four prefixes to memorise, and the requests to replay.

    ctl1_data.py        (on the RTX machine, no GPU) -> work/ctl1/{a_train,a_held_out}.jsonl, a_manifest.json, replay.json, ids.txt

Rows come from the rl1 round 1 set (plain E4B's own tries, cut after the first edit): solved, patch on the reference lines,
task where plain landed there in 1 of 4 tries. Astra asked for at most 4,096 tokens; only one such task exists with a mixed
record, so the limit here is 5,500. The space token the server puts before the tool declarations is inserted (parity check).
"""
import json
from pathlib import Path

W = Path.home() / "workspace/Gemma4/work"
PICK = ["toolz_551:t2:nav", "boltons_403:t4:nav", "sqlite_utils_88b48fa167:t3:nav", "more_itertools_1200:t2:nav"]
SPACE, TOOL, CLOSE = 236743, 46, 101          # CLOSE is checked below against the tokenizer
from tokenizers import Tokenizer
tok = Tokenizer.from_file(str(W.parent / "models/gemma-4-e4b-it-qat-w4a16-ct/tokenizer.json"))
CLOSE = tok.token_to_id("<channel|>")
valid = json.load(open(W / "rtx_test/valid_rtx.json"))
out = W / "ctl1"
out.mkdir(exist_ok=True)
rows, replay, ids = [], [], []
for line in open(W / "rl1/r1/a_train.jsonl"):
    r = json.loads(line)
    if r["id"] not in PICK:
        continue
    assert r["reward"] == 1 and r["solved"] and r["tokens"] <= 5500 and not r.get("masked_turns"), (r["id"], r.get("masked_turns"))
    at = r["input_ids"].index(TOOL)
    assert r["input_ids"][at - 1] != SPACE and at < r["targets"][0][0]
    r["input_ids"] = r["input_ids"][:at] + [SPACE] + r["input_ids"][at:]
    r["targets"] = [[a + 1, b + 1] for a, b in r["targets"]]
    r["tokens"] += 1
    r["weights"] = []                          # per target span: [thinking tokens (weight 1), action tokens (weight 4)]
    for a, b in r["targets"]:
        span = r["input_ids"][a:b]
        cut = span.index(CLOSE) + 1 if CLOSE in span else 0
        r["weights"].append([cut, b - a - cut])
    rows.append(r)
    task, k = r["task"], r["id"].split(":")[1][1:]
    calls = [c for c in map(json.loads, open(W / f"rtx_test/runs/{r['source']}/{task}_t{k}/llm_calls.jsonl")) if c["instance_id"] == task]
    solver = [c for c in calls if any(t["function"]["name"] == "run_command" for t in c.get("tools") or [])][:r["calls"]]
    assert len(solver) == len(r["targets"]), (len(solver), len(r["targets"]))
    for n, (c, (a, b)) in enumerate(zip(solver, r["targets"])):
        call = c["response"]["choices"][0]["message"]["tool_calls"][0]["function"]
        replay.append({"id": r["id"], "turn": n + 1, "of": len(solver), "messages": c["messages"], "tools": c["tools"], "params": c["params"],
                       "want_name": call["name"], "want_arguments": json.loads(call["arguments"]), "prompt_ids": r["input_ids"][:a]})
    ids.append(("fresh" if r["source"].startswith("fresh") else "r1" if task in valid["r1"] else "r2") + " " + task)
    print(r["id"], r["source"], "tokens", r["tokens"], "spans (thinking, action):", r["weights"], "advantage", r["advantage"])
assert len(rows) == len(PICK)
open(out / "a_train.jsonl", "w").write("".join(json.dumps(r) + "\n" for r in rows))
open(out / "a_held_out.jsonl", "w").write("")
json.dump({"control": "ctl1", "rows": PICK, "space_token_inserted": True, "weights": {"thinking": 1, "action": 4}}, open(out / "a_manifest.json", "w"))
json.dump(replay, open(out / "replay.json", "w"))
open(out / "ids.txt", "w").write("\n".join(ids) + "\n")
print(len(replay), "requests to replay;", ids)
