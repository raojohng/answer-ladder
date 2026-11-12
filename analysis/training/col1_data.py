"""col1 training data (John, 2026-11-12): from the collection run (runs/col1: training and FreshSWE-Py tasks, each statement
followed by the reference fix as exact edit.py commands), one solved try per task (the shortest that builds, at most 9,000 tokens),
cut after its first edit as in tr1/tr2. The appended commands are REMOVED from every recorded request before the rows are rebuilt on
the server's own token ids, so the model is trained to produce the try from the plain task statement. Thinking may still mention
the given commands; the action-only method gives thinking tokens no weight.

    col1_data.py <port>   (a plain server must be running) -> work/col1/{a_train,a_held_out}.jsonl, a_manifest.json
"""
import collections, importlib.util, json, multiprocessing, os, random, sys, urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

PORT = int(sys.argv[1])
W = Path.home() / "workspace/Gemma4/work"
REPO = W / "v8con/repo"
RUNS = {"col1": W / "rtx_test/runs/col1"}
HINTS = json.load(open(W / "col1/hints.json"))
# lines the fix adds (from the REPLACE side, not in the SEARCH side), at least 12 characters: none may appear in the context
ADDED = {}
for _t, _h in HINTS.items():
    _old = set(l.strip() for b in _h.split("<<<<<<< SEARCH\n")[1:] for l in b.split("\n=======\n")[0].splitlines())
    ADDED[_t] = [l for b in _h.split("\n=======\n")[1:] for l in b.split("\n>>>>>>> REPLACE")[0].splitlines()
                 if len(l.strip()) >= 12 and l.strip() not in _old]
# what the setup stage says in a plain session (identical across tasks): taken from a recorded plain session
_ref = [json.loads(l) for l in open(W / "rtx_test/runs/loc1/e4b_loc_ctrl_v1_fastapi_11355_t1/llm_calls.jsonl")]
SETUP_SAID = next(p["text"] for r in _ref for m in r["messages"] if isinstance(m.get("content"), list)
                  for p in m["content"] if isinstance(p, dict) and str(p.get("text", "")).startswith("[setup] said:"))
PLAIN, MAX_TOKENS, TRAIN, SEED = "gemma-4-e4b-it-qat-w4a16-ct", 9000, 400, 20261112
os.environ["SOURCES"] = "x"; os.environ.setdefault("RUNS", "."); os.environ.setdefault("OUT", "/tmp/unused")
os.chdir(REPO)
spec = importlib.util.spec_from_file_location("rl", REPO / "e4b_track/train/make_rl_dataset.py")
rl = importlib.util.module_from_spec(spec); spec.loader.exec_module(rl)
renderer = None


def build(job):
    """One solved session -> its row cut after the first edit, with the recorded requests of its solver turns."""
    global renderer
    if renderer is None:
        renderer = rl.own.renderer_class()(rl.ROOT / "post_training/render/model_files/e4b")
    run, task, k = job
    folder = RUNS[run] / f"{task}_t{k}"
    try:
        item, calls = rl.nav(folder, task, renderer)
    except rl.Reject as error:
        return job, None, str(error)
    if item.get("masked_turns"):
        return job, None, "masked turn"
    rows = [c for c in map(json.loads, open(folder / "llm_calls.jsonl")) if c["instance_id"] == task]
    solver = [c for c in rows if any(t["function"]["name"] == "run_command" for t in c.get("tools") or [])][:calls]
    if len(solver) != len(item["targets"]):
        return job, None, "turn count"
    hint = HINTS[task]

    def clean(text):
        text = text.replace(hint, "").replace(hint.strip(), "")
        if text.startswith("[setup] said:") and ("SEARCH" in text or "edit.py" in text):
            text = SETUP_SAID          # the setup stage tried the given commands; show what it says in a plain session
        return text

    def strip(m):
        m = dict(m)
        if isinstance(m.get("content"), str):
            m["content"] = clean(m["content"])
        elif isinstance(m.get("content"), list):
            m["content"] = [{**p, "text": clean(p["text"])} if isinstance(p, dict) and isinstance(p.get("text"), str) else p for p in m["content"]]
        return m
    item["requests"] = [{"messages": [strip(m) for m in c["messages"]], "tools": c["tools"], **(c["params"].get("extra_body") or {})} for c in solver]
    context = json.dumps([m for r in item["requests"] for m in r["messages"] if m.get("role") in ("system", "user")])
    if "written as the edit command(s) to run" in context or any(json.dumps(line)[1:-1] in context for line in ADDED[task]):
        return job, None, "hint left in the context"
    return job, item, None


def tokenize(request):
    body = json.dumps({"model": PLAIN, "add_generation_prompt": True, **request}).encode()
    r = urllib.request.Request(f"http://127.0.0.1:{PORT}/tokenize", body, {"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(r, timeout=300).read())["tokens"]


def served(item, close):
    """The row on the server's ids: prompt of the last turn + its reply; every earlier reply must sit unchanged in that prompt."""
    replies = [item["input_ids"][a:b] for a, b in item["targets"]]
    prompts = [tokenize(q) for q in item["requests"]]
    ids, targets, weights = prompts[-1] + replies[-1], [], []
    for p, c in zip(prompts, replies):
        if ids[:len(p)] != p or ids[len(p):len(p) + len(c)] != c:
            return None
        targets.append([len(p), len(p) + len(c)])
        cut = c.index(close) + 1 if close in c else 0
        weights.append([cut, len(c) - cut])
    return {"input_ids": ids, "targets": targets, "weights": weights, "tokens": len(ids), "target_tokens": sum(b - a for a, b in targets)}


if __name__ == "__main__":
    from tokenizers import Tokenizer
    close = Tokenizer.from_file(str(W.parent / "models" / PLAIN / "tokenizer.json")).token_to_id("<channel|>")
    sets = dict(l.split()[::-1] for l in open(W / "col1/ids.txt") if l.strip())
    jobs = []
    for run, folder in RUNS.items():
        for d in sorted(folder.iterdir()):
            f = d / "task_results.jsonl"
            if "_t" not in d.name or not f.exists():
                continue
            task, k = d.name.rsplit("_t", 1)
            if task in sets and json.loads(open(f).readline()).get("resolved") in (True, "True"):
                jobs.append((run, task, int(k)))
    tasks = sorted({t for _, t, _ in jobs})
    random.seed(SEED); random.shuffle(tasks)
    rest = tasks
    with multiprocessing.Pool(24) as pool:
        built = pool.map(build, jobs, chunksize=4)
    reasons = collections.Counter(r for _, item, r in built if item is None)
    by_task = collections.defaultdict(list)
    for (run, task, k), item, _ in built:
        if item is not None and item["tokens"] <= MAX_TOKENS:
            by_task[task].append((item["tokens"], k, run, item))
    print(f"{len(jobs)} solved tries of {len(tasks)} collection tasks; rows built for {len(by_task)} tasks; not built: {dict(reasons)}", flush=True)
    picked = [(task, *min(by_task[task], key=lambda x: x[:2])) for task in tasks if task in by_task]

    def finish(p):
        task, _, k, run, item = p
        row = served(item, close)
        if row is None:
            return task, None
        row.update(id=f"{task}:t{k}", task=task, repo=task.rsplit("_", 1)[0], source=run, calls=len(row["targets"]))
        return task, row

    with ThreadPoolExecutor(8) as pool:
        done = dict(pool.map(finish, picked))
    dropped = [t for t, r in done.items() if r is None]
    train = [done[t] for t in rest if done.get(t)][:TRAIN]
    out = W / "col1"; out.mkdir(exist_ok=True)
    import shutil; shutil.copy(W / "tr1/a_held_out.jsonl", out / "a_held_out.jsonl")    # tr1 held-out rows, for the loss check only
    held_rows = [json.loads(l) for l in open(out / "a_held_out.jsonl")]
    for name, rows in (("train", train),):
        open(out / f"a_{name}.jsonl", "w").write("".join(json.dumps(r) + "\n" for r in rows))
        tokens = sorted(r["tokens"] for r in rows)
        print(f"{name}: {len(rows)} rows, {len({r['repo'] for r in rows})} repos, {sum(tokens):,} tokens, median {tokens[len(tokens) // 2]:,}, max {tokens[-1]:,}, "
              f"thinking {sum(w[0] for r in rows for w in r['weights']):,}, action {sum(w[1] for r in rows for w in r['weights']):,} target tokens")
    seen = [r["task"] for r in train]
    json.dump({"test": "col1", "seed": SEED, "max_tokens": MAX_TOKENS, "trained_tasks": seen, "rows_dropped_by_the_server_check": dropped,
               "hint": "removed from every request"}, open(out / "a_manifest.json", "w"), indent=1)
    print(f"trained {len(seen)} tasks; dropped by the server check: {len(dropped)}")
    print("COL1_DATA_DONE")
