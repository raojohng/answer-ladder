"""Transfer test tr1 (John's go, 2026-11-11 15:10 IST): the positive control scaled up. Data step.

    tr1_data.py <port>     (on the RTX machine; a plain server must be running: its /tokenize gives the exact served ids)
    -> work/tr1/{a_train,a_held_out}.jsonl, a_manifest.json, ids_held.txt, ids_seen.txt

The 234 frontier tasks (solved in 1 to 3 of plain E4B's 4 tries) are split by a seeded shuffle: 60 held out, never trained
on. For up to 100 of the others: one solved plain try (the shortest that builds, at most 9,000 tokens), cut after its first
edit, as in the control. Each row is rebuilt on the server's own token ids for the recorded requests (this fixes the space
token and the "8.0 minutes" line); a row whose recorded replies are not found unchanged in the server's prompt is dropped.
Held-out rows (one solved try per held-out task) are only for the trainer's loss check.
"""
import collections, importlib.util, json, multiprocessing, os, random, sys, urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

PORT = int(sys.argv[1])
W = Path.home() / "workspace/Gemma4/work"
REPO = W / "v8con/repo"
RUNS = {"v8_sweep": W / "rtx_test/runs/v8_sweep", "fresh_v8_p1": W / "rtx_test/runs/fresh_v8_p1"}
PLAIN, MAX_TOKENS, HELD, TRAIN, SEED = "gemma-4-e4b-it-qat-w4a16-ct", 9000, 60, 100, 20261111
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
    item["requests"] = [{"messages": c["messages"], "tools": c["tools"], **(c["params"].get("extra_body") or {})} for c in solver]
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
    frontier = [l.split() for l in open(W / "rl1/frontier.txt") if l.strip()]
    sets = {t: s for s, t in frontier}
    tasks = sorted(sets)
    random.seed(SEED); random.shuffle(tasks)
    held, rest = tasks[:HELD], tasks[HELD:]
    jobs = []
    for task in tasks:
        run = "fresh_v8_p1" if sets[task] == "fresh" else "v8_sweep"
        for k in range(1, 5):
            f = RUNS[run] / f"{task}_t{k}/task_results.jsonl"
            if f.exists() and json.loads(open(f).readline()).get("resolved"):
                jobs.append((run, task, k))
    with multiprocessing.Pool(24) as pool:
        built = pool.map(build, jobs, chunksize=4)
    reasons = collections.Counter(r for _, item, r in built if item is None)
    by_task = collections.defaultdict(list)
    for (run, task, k), item, _ in built:
        if item is not None and item["tokens"] <= MAX_TOKENS:
            by_task[task].append((item["tokens"], k, run, item))
    print(f"{len(jobs)} solved tries of {len(tasks)} frontier tasks; rows built for {len(by_task)} tasks; not built: {dict(reasons)}", flush=True)
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
    held_rows = [done[t] for t in held if done.get(t)]
    out = W / "tr1"; out.mkdir(exist_ok=True)
    for name, rows in (("train", train), ("held_out", held_rows)):
        open(out / f"a_{name}.jsonl", "w").write("".join(json.dumps(r) + "\n" for r in rows))
        tokens = sorted(r["tokens"] for r in rows)
        print(f"{name}: {len(rows)} rows, {len({r['repo'] for r in rows})} repos, {sum(tokens):,} tokens, median {tokens[len(tokens) // 2]:,}, max {tokens[-1]:,}, "
              f"thinking {sum(w[0] for r in rows for w in r['weights']):,}, action {sum(w[1] for r in rows for w in r['weights']):,} target tokens")
    seen = [r["task"] for r in train]
    open(out / "ids_held.txt", "w").write("".join(f"{sets[t]} {t}\n" for t in held))
    open(out / "ids_seen.txt", "w").write("".join(f"{sets[t]} {t}\n" for t in seen))
    repos = {r["repo"] for r in train}
    json.dump({"test": "tr1", "seed": SEED, "max_tokens": MAX_TOKENS, "held_out_tasks": held, "trained_tasks": seen, "rows_dropped_by_the_server_check": dropped,
               "held_out_tasks_in_a_trained_repo": sum(t.rsplit("_", 1)[0] in repos for t in held), "weights": {"thinking": 1, "action": 4}},
              open(out / "a_manifest.json", "w"), indent=1)
    print(f"held out {len(held)} tasks ({sum(t.rsplit('_', 1)[0] in repos for t in held)} in a repo that is trained on); trained {len(seen)}; "
          f"dropped by the server check: {len(dropped)}")
    print("TR1_DATA_DONE")
