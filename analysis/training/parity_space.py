"""Parity follow-up: does the one space token the server puts before the tool declarations (and the trainer's rendering
lacks) change the probabilities of the target tokens? Server only, plain model.   parity_space.py <port> <out folder>"""
import json, sys, urllib.request
from pathlib import Path
import numpy as np

PORT, OUT = int(sys.argv[1]), Path(sys.argv[2])
PLAIN, SPACE, TOOL = "gemma-4-e4b-it-qat-w4a16-ct", 236743, 46


def score(ids):
    body = {"model": PLAIN, "prompt": ids, "max_tokens": 1, "temperature": 1.0, "prompt_logprobs": 1}
    request = urllib.request.Request(f"http://127.0.0.1:{PORT}/v1/completions", json.dumps(body).encode(), {"Content-Type": "application/json"})
    entries = json.loads(urllib.request.urlopen(request, timeout=1800).read())["choices"][0]["prompt_logprobs"]
    return np.array([np.nan] + [e[str(t)]["logprob"] for e, t in zip(entries[1:], ids[1:])])


advantage = {}
for line in open(Path.home() / "workspace/Gemma4/work/rl1/r1/a_train.jsonl"):
    r = json.loads(line)
    advantage[r["id"]] = r["advantage"]
for name, row in json.load(open(OUT / "rows.json")).items():
    ids = row["input_ids"]
    at = ids.index(TOOL)
    assert ids[at - 1] != SPACE
    a, again, b = score(ids), score(ids), score(ids[:at] + [SPACE] + ids[at:])
    b = np.delete(b, at)                               # drop the added token: the rest lines up again
    target = np.zeros(len(ids), bool)
    for s, e in row["targets"]:
        target[s:e] = True
    d, noise = (b - a)[target], (again - a)[target]
    print(f"{name} (advantage {advantage[name]:+.2f}): space added at {at}; on {target.sum()} targets: mean change {d.mean():+.4f}, abs mean "
          f"{np.abs(d).mean():.4f}, p99 {np.percentile(np.abs(d), 99):.3f}, max {np.abs(d).max():.3f} | same request twice: abs mean {np.abs(noise).mean():.4f}")
print("SPACE_DONE")
