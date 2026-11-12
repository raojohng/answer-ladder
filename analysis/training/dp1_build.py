"""Decision points dp1, training rows: from contexts where plain's samples disagree, the rewarded samples.
    dp1_build.py <train samples.jsonl> <held samples.jsonl> <out folder> [rows per context=2] [token budget=2500000]
Row = the server's prompt ids + the sample's own generated ids (the target). Weights as in the control (thinking 1, action 4).
Rows of one context differ in command where possible. Contexts are taken shortest first until the token budget is spent."""
import json, random, sys
from pathlib import Path
from tokenizers import Tokenizer

TRAIN, HELD, OUT = sys.argv[1], sys.argv[2], Path(sys.argv[3])
PER = int(sys.argv[4]) if len(sys.argv) > 4 else 2
BUDGET = int(sys.argv[5]) if len(sys.argv) > 5 else 2_500_000
close = Tokenizer.from_file(str(Path.home() / "workspace/Gemma4/models/gemma-4-e4b-it-qat-w4a16-ct/tokenizer.json")).token_to_id("<channel|>")
random.seed(20261111)


def rows(path, budget):
    out, used, contexts = [], 0, 0
    mixed = [r for r in map(json.loads, open(path)) if 0 < sum(s["reward"] for s in r["samples"]) < len(r["samples"])]
    for r in sorted(mixed, key=lambda r: len(r["prompt_ids"])):
        good, picked, commands = [s for s in r["samples"] if s["reward"] and s["finish"] == "tool_calls" and s["calls"] == 1], [], set()
        random.shuffle(good)
        for s in good:                                   # distinct commands first
            if len(picked) < PER and s["command"] not in commands:
                picked.append(s); commands.add(s["command"])
        for s in good:
            if len(picked) < PER and s not in picked:
                picked.append(s)
        if not picked or used + sum(len(r["prompt_ids"]) + len(s["token_ids"]) for s in picked) > budget:
            continue
        contexts += 1
        for n, s in enumerate(picked):
            c, p = s["token_ids"], len(r["prompt_ids"])
            cut = c.index(close) + 1 if close in c else 0
            out.append({"id": f"{r['id']}:s{n}", "task": r["task"], "repo": r["task"].rsplit("_", 1)[0], "kind": s["kind"], "input_ids": r["prompt_ids"] + c,
                        "targets": [[p, p + len(c)]], "weights": [[cut, len(c) - cut]], "tokens": p + len(c), "target_tokens": len(c)})
            used += p + len(c)
    return out, len(mixed), contexts


OUT.mkdir(parents=True, exist_ok=True)
for name, path, budget in (("train", TRAIN, BUDGET), ("held_out", HELD, 300_000)):
    r, mixed, used = rows(path, budget)
    open(OUT / f"a_{name}.jsonl", "w").write("".join(json.dumps(x) + "\n" for x in r))
    kinds = {k: sum(x["kind"] == k for x in r) for k in ("read", "edit")}
    print(f"{name}: {len(r)} rows from {used} of {mixed} mixed contexts, {len({x['task'] for x in r})} tasks, {kinds}, {sum(x['tokens'] for x in r):,} tokens, "
          f"{sum(x['target_tokens'] for x in r):,} target tokens")
json.dump({"test": "dp1", "rows_per_context": PER, "token_budget": BUDGET, "weights": {"thinking": 1, "action": 4}}, open(OUT / "a_manifest.json", "w"))
print("DP1_BUILT")
