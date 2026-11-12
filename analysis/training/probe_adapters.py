"""What did training change? Score every row of a training set under the plain model and under trained adapters, on the
server (prompt_logprobs: the log-probability of every token given the ones before it), and split the change by kind of token.

    probe_adapters.py score <port> <train.jsonl> <out.jsonl> <model> [<model> ...]     (server running with the adapters)
    probe_adapters.py report <out.jsonl>

Kinds, inside each target span (one model reply): thinking = up to and including the thinking-channel close; action = the
rest (the tool call). The last span of an rl row is the first edit: its action tokens are "edit", earlier ones "navigation".
"""
import collections, json, sys, threading, time, urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import numpy as np

PLAIN = "gemma-4-e4b-it-qat-w4a16-ct"


def score():
    from tokenizers import Tokenizer
    port, data, out, models = int(sys.argv[2]), sys.argv[3], Path(sys.argv[4]), sys.argv[5:]
    tok = Tokenizer.from_file(str(Path.home() / "workspace/Gemma4/models" / PLAIN / "tokenizer.json"))
    close = tok.token_to_id("<channel|>")
    assert close is not None
    rows = [json.loads(l) for l in open(data)]
    done = {(r["id"], r["model"]) for r in map(json.loads, open(out))} if out.exists() else set()
    lock, started, count = threading.Lock(), time.time(), [0]

    def one(job):
        row, model = job
        ids = row["input_ids"]
        body = json.dumps({"model": model, "prompt": ids, "max_tokens": 1, "temperature": 1.0, "prompt_logprobs": 1}).encode()
        for attempt in range(4):
            try:
                request = urllib.request.Request(f"http://127.0.0.1:{port}/v1/completions", body, {"Content-Type": "application/json"})
                entries = json.loads(urllib.request.urlopen(request, timeout=900).read())["choices"][0]["prompt_logprobs"]
                break
            except Exception as error:
                if attempt == 3:
                    print("FAILED", row["id"], model, error, flush=True)
                    return
                time.sleep(20)
        spans = []
        for a, b in row["targets"]:
            lp = [entries[i][str(ids[i])]["logprob"] for i in range(a, b)]
            cut = (ids[a:b].index(close) + 1) if close in ids[a:b] else 0
            spans.append([cut, sum(lp[:cut]), b - a - cut, sum(lp[cut:])])      # thinking tokens, their sum, action tokens, their sum
        with lock:
            with open(out, "a") as f:
                f.write(json.dumps({"id": row["id"], "model": model, "task": row["task"], "reward": row["reward"], "solved": row["solved"],
                                    "advantage": row["advantage"], "tokens": row["tokens"], "spans": spans}) + "\n")
            count[0] += 1
            if count[0] % 100 == 0:
                print(f"{count[0]} of {len(jobs)} in {(time.time() - started) / 60:.1f} min", flush=True)

    jobs = [(r, m) for m in models for r in rows if (r["id"], m) not in done]
    print(f"{len(rows)} rows, {len(models)} models, {len(jobs)} requests to do", flush=True)
    with ThreadPoolExecutor(3) as pool:
        list(pool.map(one, jobs))
    print("SCORE_DONE", flush=True)


def report():
    by = collections.defaultdict(dict)
    for r in map(json.loads, open(sys.argv[2])):
        by[r["model"]][r["id"]] = r
    plain = by.pop(PLAIN)
    kinds = {"thinking": lambda s: (sum(x[0] for x in s), sum(x[1] for x in s)),
             "navigation calls": lambda s: (sum(x[2] for x in s[:-1]), sum(x[3] for x in s[:-1])),
             "first edit call": lambda s: (s[-1][2], s[-1][3])}
    print(f"plain: {len(plain)} rows. Change = adapter minus plain, in nats. 'per row' = summed over the row's tokens of that kind.")
    for model, rows in by.items():
        ids = sorted(set(rows) & set(plain))
        adv = np.array([plain[i]["advantage"] for i in ids])
        print(f"\n== {model}: {len(ids)} rows ({(adv > 0).sum()} with a positive advantage, {(adv < 0).sum()} negative) ==")
        for kind, f in kinds.items():
            n = np.array([f(plain[i]["spans"])[0] for i in ids], float)
            d = np.array([f(rows[i]["spans"])[1] - f(plain[i]["spans"])[1] for i in ids])
            base = np.array([f(plain[i]["spans"])[1] for i in ids])
            up, down = adv > 0, adv < 0
            print(f"  {kind:17s} tokens per row {n.mean():7.1f} | plain log-probability per row: positive {base[up].mean():+8.2f} negative {base[down].mean():+8.2f}")
            print(f"  {'':17s} change per token: positive {d[up].sum() / n[up].sum():+.4f} negative {d[down].sum() / n[down].sum():+.4f} | "
                  f"change per row: positive {d[up].mean():+.3f} (sd {d[up].std():.2f}) negative {d[down].mean():+.3f} (sd {d[down].std():.2f}) | "
                  f"gap {d[up].mean() - d[down].mean():+.3f} | correlation with the advantage {np.corrcoef(adv, d)[0, 1]:+.3f}")
        tasks = collections.defaultdict(list)             # within a task: does the adapter prefer the tries that landed on the reference lines?
        for i in ids:
            s = rows[i]["spans"], plain[i]["spans"]
            tasks[plain[i]["task"]].append((plain[i]["reward"], sum(x[1] + x[3] for x in s[0]) - sum(x[1] + x[3] for x in s[1])))
        gaps = [np.mean([d for r, d in v if r == 1]) - np.mean([d for r, d in v if r == 0]) for v in tasks.values()
                if any(r == 1 for r, _ in v) and any(r == 0 for r, _ in v)]
        print(f"  within a task, whole row: change on rewarded tries minus change on the others: mean {np.mean(gaps):+.3f} nats, "
              f"median {np.median(gaps):+.3f}, positive in {100 * np.mean(np.array(gaps) > 0):.0f}% of {len(gaps)} tasks")
    print("REPORT_DONE")


{"score": score, "report": report}[sys.argv[1]]()
