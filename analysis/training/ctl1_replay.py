"""Positive control, replay: from the fixed contexts of the four memorised prefixes, does the served adapter choose the
trained next action? Each recorded request is sent again N times with its recorded sampling settings, to the plain model
and to the adapter. Also checks that the server's token ids for each request equal the training row's prefix.

    ctl1_replay.py <port> <adapter name> <replay.json> <out.json> [N=10]
"""
import collections, json, sys, urllib.request
from concurrent.futures import ThreadPoolExecutor

PORT, ADAPTER, N = int(sys.argv[1]), sys.argv[2], int(sys.argv[5]) if len(sys.argv) > 5 else 10
PLAIN = "gemma-4-e4b-it-qat-w4a16-ct"
items = json.load(open(sys.argv[3]))


def post(path, body):
    request = urllib.request.Request(f"http://127.0.0.1:{PORT}{path}", json.dumps(body).encode(), {"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(request, timeout=900).read())


def body(item, model):
    p = item["params"]
    b = {"model": model, "messages": item["messages"], "tools": item["tools"]}
    b.update({k: p[k] for k in ("temperature", "top_p", "max_completion_tokens") if p.get(k) is not None})
    b.update(p.get("extra_body") or {})
    return b


def ask(job):
    item, model = job
    try:
        m = post("/v1/chat/completions", body(item, model))["choices"][0]["message"]
        calls = m.get("tool_calls") or []
        if not calls:
            return item["id"], item["turn"], model, "no call", None
        f = calls[0]["function"]
        args = json.loads(f["arguments"]) if isinstance(f["arguments"], str) else f["arguments"]
        same = f["name"] == item["want_name"] and args == item["want_arguments"]
        loose = same or (f["name"] == item["want_name"] and " ".join(str(args.get("command", "")).split()) == " ".join(str(item["want_arguments"].get("command", "")).split()))
        return item["id"], item["turn"], model, "exact" if same else "same but for spaces" if loose else "other", str(args.get("command", args))[:160]
    except Exception as error:
        return item["id"], item["turn"], model, f"error {error}"[:80], None


for item in items:
    got = post("/tokenize", {**{k: v for k, v in body(item, PLAIN).items() if k in ("model", "messages", "tools", "chat_template_kwargs")}, "add_generation_prompt": True})["tokens"]
    print(f"{item['id']} turn {item['turn']}: server prompt {len(got)} ids, training prefix {len(item['prompt_ids'])}: {'identical' if got == item['prompt_ids'] else 'DIFFERENT'}", flush=True)

jobs = [(item, model) for item in items for model in (PLAIN, ADAPTER) for _ in range(N)]
with ThreadPoolExecutor(16) as pool:
    results = list(pool.map(ask, jobs))
table = collections.defaultdict(collections.Counter)
for i, turn, model, kind, _ in results:
    table[(i, turn, model)][kind] += 1
    table[("all", 0, model)][kind] += 1
for (i, turn, model), c in sorted(table.items(), key=lambda kv: (kv[0][0] != "all", kv[0])):
    ok = c["exact"] + c["same but for spaces"]
    print(f"{i:36s} turn {turn} {'adapter' if model == ADAPTER else 'plain  '}: trained action {ok}/{sum(c.values())} ({100 * ok / sum(c.values()):.0f}%) {dict(c)}")
json.dump(results, open(sys.argv[4], "w"))
print("REPLAY_DONE")
