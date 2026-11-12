"""Parity check, server side: what the vLLM server computes for tokens the trainer was trained on.

    parity_server.py <port> <adapter name> <out folder>        (server already running with the adapter loaded)

1. Log-probabilities: each picked training row's token ids go to /v1/completions as they are; prompt_logprobs returns the
   server's log-probability of every token given the ones before it, for the plain model and for the adapter.
2. Tokens: recorded solver requests are sent again unchanged (1 new token) with return_token_ids, so the exact ids the
   server builds from a chat request can be compared with the trainer's rendering (parity_compare.py).
"""
import json, sys, urllib.request
from pathlib import Path

PORT, ADAPTER, OUT = int(sys.argv[1]), sys.argv[2], Path(sys.argv[3])
W = Path.home() / "workspace/Gemma4/work"
PLAIN = "gemma-4-e4b-it-qat-w4a16-ct"
ROWS = ["arrow_1052:t1:nav", "arrow_1063:t1:nav", "click_2724:t1:nav"]      # short, about 8k, about 16k tokens
TOKEN_RUN, TOKEN_TASK = W / "rtx_test/runs/v8_sweep/arrow_1052_t1", "arrow_1052"


def post(path, body):
    request = urllib.request.Request(f"http://127.0.0.1:{PORT}{path}", json.dumps(body).encode(), {"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(request, timeout=1800).read())


OUT.mkdir(parents=True, exist_ok=True)
rows = {}
for line in open(W / "rl1/r1/a_train.jsonl"):
    r = json.loads(line)
    if r["id"] in ROWS:
        rows[r["id"]] = {"input_ids": r["input_ids"], "targets": r["targets"]}
assert len(rows) == len(ROWS), sorted(rows)
json.dump(rows, open(OUT / "rows.json", "w"))

result = {}
for name, row in rows.items():
    ids = row["input_ids"]
    for model in (PLAIN, ADAPTER):
        reply = post("/v1/completions", {"model": model, "prompt": ids, "max_tokens": 1, "temperature": 1.0, "prompt_logprobs": 1})
        entries = reply["choices"][0]["prompt_logprobs"]
        assert len(entries) == len(ids), (len(entries), len(ids))
        values = [None] + [(e.get(str(t)) or {}).get("logprob") for e, t in zip(entries[1:], ids[1:])]
        result[f"{name}|{'plain' if model == PLAIN else 'adapter'}"] = values
        print(name, model, len(ids), "tokens,", sum(v is None for v in values[1:]), "missing,", "prompt tokens", reply["usage"]["prompt_tokens"], flush=True)
json.dump(result, open(OUT / "server_logprobs.json", "w"))

calls = [r for r in map(json.loads, open(TOKEN_RUN / "llm_calls.jsonl")) if r["instance_id"] == TOKEN_TASK]
solver = [r for r in calls if any(t["function"]["name"] == "run_command" for t in r.get("tools") or [])]
tokens = []
for row in (solver[0], solver[min(4, len(solver) - 1)]):
    body = {"model": PLAIN, "messages": row["messages"], "tools": row["tools"], "max_tokens": 1, "return_token_ids": True}
    body.update(row["params"].get("extra_body") or {})
    reply = post("/v1/chat/completions", body)
    listed = post("/tokenize", {"model": PLAIN, "messages": row["messages"], "tools": row["tools"], "add_generation_prompt": True,
                                **(row["params"].get("extra_body") or {})})
    tokens.append({"turn": row["turn"], "messages": row["messages"], "tools": row["tools"], "extra_body": row["params"].get("extra_body"),
                   "recorded_prompt_tokens": row["response"]["usage"]["prompt_tokens"], "replay_prompt_tokens": reply["usage"]["prompt_tokens"],
                   "server_ids": reply.get("prompt_token_ids"), "tokenize_ids": listed.get("tokens")})
    print("turn", row["turn"], "recorded", tokens[-1]["recorded_prompt_tokens"], "replay", tokens[-1]["replay_prompt_tokens"],
          "ids from the reply", len(tokens[-1]["server_ids"] or []), "ids from /tokenize", len(tokens[-1]["tokenize_ids"] or []), flush=True)
json.dump(tokens, open(OUT / "server_tokens.json", "w"))
print("SERVER_PART_DONE")
