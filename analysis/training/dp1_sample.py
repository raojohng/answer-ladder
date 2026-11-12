"""Decision points dp1 (John's go, 2026-11-11): many samples of the next step from one fixed context, each scored at once.

    dp1_sample.py <port> <model name> <out.jsonl> <train|held|all> [K=8] [contexts per task=6]

Why: one reward per try, spread over thousands of thinking tokens, taught wording and not the choice (probe, 2026-11-11).
Here the context is fixed and only the next step varies, so what separates rewarded from unrewarded samples is the choice.

Contexts: for each frontier task, the recorded requests of plain E4B's solver turns 2 to its first edit, from its 4 tries
(identical requests once; up to N per task, taken turn by turn across the tries). Tasks: train = frontier minus the 60
held-out tasks of tr1, held = those 60.
Samples: the recorded request again, n=K, with its recorded sampler (temperature 1, top-p 0.95, top-k 40, thinking 3,072).
Reward of a sample, from the reference patch (needs no run):
  read  = a read.py call on the reference file whose range covers reference lines (within 3 lines)
  edit  = an edit.py call on the reference file whose first SEARCH block sits on reference lines in the untouched file
  anything else = 0.   Resumes: contexts already in the output are skipped.
"""
import collections, hashlib, json, re, sys, tarfile, threading, time, urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

W = Path.home() / "workspace/Gemma4/work"
sys.path.insert(0, str(W / "rtx_test"))
import placement_census as pc

PORT, MODEL, OUT, PART = int(sys.argv[1]), sys.argv[2], Path(sys.argv[3]), sys.argv[4]
K = int(sys.argv[5]) if len(sys.argv) > 5 else 8
PER_TASK = int(sys.argv[6]) if len(sys.argv) > 6 else 6
E = W / "extra_tasks"
SETS = {"r1": (E / "r1/tasks.jsonl", E / "r1/snapshots"), "r2": (E / "r2/tasks.jsonl", E / "r2/snapshots"),
        "fresh": (E / "public/freshswe-py/data/tasks.jsonl", E / "public/freshswe-py/data/snapshots")}
SEARCH = re.compile(r"^\s*<{3,}\s*SEARCH\s*(?:ALL)?\s*:?\s*$", re.IGNORECASE)
DIVIDER = re.compile(r"^\s*={3,}\s*$")


def contexts(task, kind):
    run = W / "rtx_test/runs" / ("fresh_v8_p1" if kind == "fresh" else "v8_sweep")
    per_try = []
    for k in range(1, 5):
        f = run / f"{task}_t{k}/llm_calls.jsonl"
        if not f.exists():
            continue
        rows = [r for r in map(json.loads, open(f)) if r["instance_id"] == task]
        solver = [r for r in rows if any(t["function"]["name"] == "run_command" for t in r.get("tools") or [])]
        turns = []
        for j, r in enumerate(solver, 1):
            calls = r["response"]["choices"][0]["message"].get("tool_calls") or []
            if not calls or len(r["messages"]) > 60:
                break
            turns.append((k, j, r))
            if "edit.py" in calls[0]["function"]["arguments"] or calls[0]["function"]["name"] == "submit_patch":
                break
        per_try.append(turns)
    out, seen = [], set()
    for j in range(1, 14):                                # turn by turn across the tries; the first turn has nothing to go on yet
        for turns in per_try:
            if j < len(turns) and len(out) < PER_TASK:
                k, turn, r = turns[j]
                key = hashlib.sha1(json.dumps(r["messages"], sort_keys=True).encode()).hexdigest()
                if key not in seen:
                    seen.add(key)
                    out.append({"id": f"{task}:t{k}:{turn}", "task": task, "messages": r["messages"], "tools": r["tools"], "params": r["params"]})
    return out


def block_lines(command):
    """Lines of the first SEARCH block of an edit.py call, and the LINE hint of its FILE line."""
    lines, inside, block = command.splitlines(), False, []
    for line in lines:
        if SEARCH.match(line):
            inside = True
        elif inside and DIVIDER.match(line):
            break
        elif inside:
            block.append(line)
    return block


def score(command, name, gold, source):
    """(kind, reward). gold = {file: [(a, b)]} of the reference patch, source = the reference file's lines before the patch."""
    near = lambda a, b, f: any(a <= d + pc.NEAR and c <= b + pc.NEAR for c, d in gold[f])
    if name != "run_command":
        return name, 0
    if "edit.py" in command:
        m = pc.FILE.search(command)
        path = pc.norm(m.group(1)) if m else ""
        if path not in gold:
            return "edit", 0
        block = [l.strip() for l in block_lines(command)]
        while block and not block[-1]:
            block.pop()
        while block and not block[0]:
            block.pop(0)
        if not block:
            return "edit", 0
        stripped = [l.strip() for l in source.get(path, [])]
        starts = [i for i in range(len(stripped) - len(block) + 1) if stripped[i:i + len(block)] == block]
        return "edit", int(any(near(i + 1, i + len(block), path) for i in starts))
    if "read.py" in command:
        m = pc.READ.search(command)
        if not m:
            return "read", 0
        path = pc.norm(m.group(1))
        return "read", int(path in gold and near(int(m.group(2) or 1), int(m.group(3) or 10 ** 9), path))
    return ("find" if "find.py" in command else "other"), 0


def sample(ctx):
    p = ctx["params"]
    body = {"model": MODEL, "messages": ctx["messages"], "tools": ctx["tools"], "n": K, "return_token_ids": True}
    body.update({k: p[k] for k in ("temperature", "top_p", "max_completion_tokens") if p.get(k) is not None})
    if p.get("top_k") is not None:
        body["top_k"] = int(p["top_k"])
    body.update(p.get("extra_body") or {})
    for attempt in range(3):
        try:
            r = urllib.request.Request(f"http://127.0.0.1:{PORT}/v1/chat/completions", json.dumps(body).encode(), {"Content-Type": "application/json"})
            d = json.loads(urllib.request.urlopen(r, timeout=1800).read())
            break
        except Exception as error:
            if attempt == 2:
                print("FAILED", ctx["id"], str(error)[:100], flush=True)
                return
            time.sleep(15)
    samples = []
    for c in d["choices"]:
        calls = c["message"].get("tool_calls") or []
        name, command = "no call", ""
        if calls:
            name = calls[0]["function"]["name"]
            try:
                command = json.loads(calls[0]["function"]["arguments"]).get("command", "") or ""
            except (ValueError, AttributeError):
                name = "bad call"
        kind, reward = score(command, name, ctx["gold"], ctx["source"])
        samples.append({"kind": kind, "reward": reward, "command": command[:2000], "finish": c["finish_reason"], "calls": len(calls), "token_ids": c["token_ids"]})
    with lock:
        with open(OUT, "a") as f:
            f.write(json.dumps({"id": ctx["id"], "task": ctx["task"], "model": MODEL, "prompt_ids": d["prompt_token_ids"], "samples": samples}) + "\n")
        count[0] += 1
        if count[0] % 50 == 0:
            print(f"{count[0]} of {len(todo)} contexts in {(time.time() - started) / 60:.1f} min", flush=True)


frontier = {t: s for s, t in (l.split() for l in open(W / "rl1/frontier.txt") if l.strip())}
held = set(json.load(open(W / "tr1/a_manifest.json"))["held_out_tasks"])
tasks = sorted(t for t in frontier if PART == "all" or (t in held) == (PART == "held"))
patches = {}
for kind, (file, _) in SETS.items():
    for line in open(file):
        t = json.loads(line)
        if frontier.get(t["instance_id"]) == kind:
            patches[t["instance_id"]] = t["patch"]
done = {json.loads(l)["id"] for l in open(OUT)} if OUT.exists() else set()
todo = []
for task in tasks:
    gold = {f: h for f, h in pc.hunks(patches[task]).items()}
    source = {}
    with tarfile.open(SETS[frontier[task]][1] / f"{task}.tgz") as tar:
        for f in gold:
            try:
                source[f] = tar.extractfile("./" + f).read().decode("utf-8", "replace").splitlines()
            except (KeyError, AttributeError):
                source[f] = []
    for ctx in contexts(task, frontier[task]):
        if ctx["id"] not in done:
            todo.append({**ctx, "gold": gold, "source": source})
print(f"{len(tasks)} tasks ({PART}), {len(todo)} contexts to sample, {K} samples each, model {MODEL}", flush=True)
lock, count, started = threading.Lock(), [0], time.time()
with ThreadPoolExecutor(6) as pool:
    list(pool.map(sample, todo))
print("DP1_SAMPLED", flush=True)
