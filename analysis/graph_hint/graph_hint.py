"""Graph hints: turn the competition's code graph and node embeddings into a location hint written into the task statement,
with no reference answer.

  Candidates: graph nodes (functions, classes) in source files (not tests, docs, examples, scripts), mapped to file and lines in
              the task's snapshot by dotted name and first code line.
  Text:       TF-IDF of the task statement against each node's name parts and code (identifiers split on _ and case).
  Graph:      one hop of propagation over call edges: s'(n) = s(n) + a * mean of s over n's callers and callees.
  Embedding:  smoothing over the precomputed vectors: s'(n) = s(n) + b * (text-weighted mean cosine of n to the 10 best text nodes).
  The top 5 nodes become the hint: "file: Class.method (defined at line n)"; the offline check uses each node's full line span.

Protocol: a, b in {0, 0.25, 0.5} are chosen on DEV tasks (public tasks outside the ladder: 52, incl. requests and httpx, which need
no sandbox here) by reference lines in the top 5; ties go to the smaller weights. The chosen setting is then scored once on the
77 ladder tasks and its hints are what the agent sees. The reference patch is used only to score.
A hit: a node on a reference file within 3 lines of a reference hunk (the paper's "reference lines" rule).

    python3 -I graph_hint.py <competition data dir> <dev ids> <test ids> <out dir>
      -> <out>/hints.json (test tasks), offline.txt, nodes_test.jsonl
"""
import collections, itertools, json, math, multiprocessing, os, re, sys, tarfile, tempfile
from pathlib import Path
import numpy as np

DATA, DEV, TEST, OUT = Path(sys.argv[1]), sys.argv[2], sys.argv[3], Path(sys.argv[4])
TOP, NEAR = 5, 10
SKIP = re.compile(r"(^|/)(tests?|docs|docs_src|examples|benchmarks|scripts)/|(^|/)test_[^/]*\.py$|conftest\.py$")
tasks = {t["instance_id"]: t for t in map(json.loads, open(DATA / "tasks.jsonl"))}


def words(text):
    out = []
    for tok in re.findall(r"[A-Za-z_][A-Za-z0-9_]*", text):
        for part in re.split(r"_+", tok):
            out += [p.lower() for p in re.findall(r"[A-Z]+(?![a-z])|[A-Z]?[a-z]+|[0-9]+", part) if len(p) > 1]
        if len(tok) > 2:
            out.append(tok.lower())
    return out


def reference_hunks(patch):
    """{file: [(start, end)]}: old-file line ranges of each hunk's changed lines."""
    res, cur, line = collections.defaultdict(list), None, 0
    for l in patch.splitlines():
        if l.startswith("--- "):
            p = l[4:].split("\t")[0]; cur = p[2:] if p.startswith("a/") else None
        elif l.startswith("@@") and cur:
            line = int(re.match(r"@@ -(\d+)", l).group(1))
        elif cur and l[:1] in (" ", "-", "+") and not l.startswith(("+++", "---")):
            if l[0] in "-+":
                at = line if l[0] == "-" else max(line - 1, 1)
                if res[cur] and res[cur][-1][1] >= at - 1:
                    res[cur][-1] = (res[cur][-1][0], max(res[cur][-1][1], at))
                else:
                    res[cur].append((at, at))
            if l[0] in " -":
                line += 1
    return res


def locate(nodes, root):
    """node id -> (file, start, end) by dotted module suffix and the node's first code line."""
    by_mod = collections.defaultdict(list)
    for p in root.rglob("*.py"):
        if ".git" in p.parts:
            continue
        rel = p.relative_to(root).as_posix()
        parts = rel[:-3].split("/")
        if parts[-1] == "__init__":
            parts = parts[:-1]
        for i in range(len(parts)):
            by_mod[".".join(parts[i:])].append(rel)
    texts, out = {}, {}
    for n in nodes:
        name, code = n["id"], n.get("text") or ""
        parts = name.split(".")
        head = code.strip().splitlines()[0].strip() if code.strip() else ""
        for i in range(len(parts) - 1, 0, -1):
            for rel in by_mod.get(".".join(parts[:i]), []):
                if SKIP.search(rel):
                    continue
                if rel not in texts:
                    texts[rel] = [l.strip() for l in (root / rel).read_text(errors="ignore").splitlines()]
                hit = next((k for k, l in enumerate(texts[rel]) if head and l == head), None)
                if hit is not None:
                    out[name] = (rel, hit + 1, hit + max(len(code.splitlines()), 1))
                    break
            if name in out:
                break
    return out


def features(tid):
    t = tasks[tid]
    stem = f"{tid.split('_')[0]}_{t['base_commit']}"
    g = json.load(open(DATA / "graphs" / f"{stem}.json"))
    emb = np.load(DATA / "embeddings" / f"{stem}.npz")
    with tempfile.TemporaryDirectory() as d:
        with tarfile.open(DATA / "snapshots" / f"{tid}.tgz") as tf:
            tf.extractall(d, filter="data")
        root = Path(d)
        if not (root / ".git").exists():
            sub = [p for p in root.iterdir() if p.is_dir()]
            root = sub[0] if len(sub) == 1 else root
        where = locate(g["nodes"], root)
    nodes = [n for n in g["nodes"] if n["id"] in where]
    names = [n["id"] for n in nodes]
    index = {n: i for i, n in enumerate(names)}
    docs = [collections.Counter(words(n["id"].replace(".", " ")) * 2 + words(n.get("text") or "")) for n in nodes]
    df = collections.Counter(w for d_ in docs for w in d_)
    idf = {w: math.log((1 + len(docs)) / (1 + c)) + 1 for w, c in df.items()}

    def vec(c):
        v = {w: (1 + math.log(x)) * idf.get(w, 0) for w, x in c.items()}
        s = math.sqrt(sum(x * x for x in v.values())) or 1
        return {w: x / s for w, x in v.items()}
    qv = vec(collections.Counter(words(t["problem_statement"])))
    text = np.array([sum(qv.get(w, 0) * x for w, x in vec(d_).items()) for d_ in docs])
    nb = collections.defaultdict(set)
    for e in g["edges"]:
        if e["source"] in index and e["target"] in index and e["source"] != e["target"]:
            nb[index[e["source"]]].add(index[e["target"]]); nb[index[e["target"]]].add(index[e["source"]])
    E = np.array([emb[n] if n in emb.files else np.zeros(emb[emb.files[0]].shape) for n in names], dtype=np.float32)
    E /= np.maximum(np.linalg.norm(E, axis=1, keepdims=True), 1e-9)
    ref = reference_hunks(t["patch"])
    file_hit = np.array([where[n][0] in ref for n in names])
    line_hit = np.array([where[n][0] in ref and any(where[n][1] - 3 <= hb and where[n][2] + 3 >= ha for ha, hb in ref[where[n][0]]) for n in names])
    return tid, {"names": names, "where": [where[n] for n in names], "text": text, "nb": {k: sorted(v) for k, v in nb.items()},
                 "E": E, "file_hit": file_hit, "line_hit": line_hit, "any_line": bool(line_hit.any())}


def qual(name, path):
    """The symbol inside its module: the dotted name minus the module path (e.g. APIRouter.get)."""
    mod = path[:-3].replace("/", ".").removesuffix(".__init__")
    parts = name.split(".")
    for i in range(len(parts)):
        if mod.endswith(".".join(parts[:i + 1])) and i + 1 < len(parts):
            return ".".join(parts[i + 1:])
    return parts[-1]


def rank(f, a, b):
    s = f["text"].copy()
    if a:
        prop = np.array([np.mean(f["text"][f["nb"][i]]) if f["nb"].get(i) else 0.0 for i in range(len(s))])
        s = s + a * prop
    if b:
        best = np.argsort(f["text"])[::-1][:NEAR]
        w = f["text"][best]
        if w.sum() > 0:
            s = s + b * (f["E"] @ (f["E"][best].T @ w)) / w.sum()
    return [i for i in np.argsort(s)[::-1] if s[i] > 0][:TOP]


def score(feats, a, b):
    c = collections.Counter()
    for f in feats.values():
        top = rank(f, a, b)
        c["file@5"] += bool(f["file_hit"][top].any()) if top else 0
        c["lines@5"] += bool(f["line_hit"][top].any()) if top else 0
        c["lines@1"] += bool(top) and bool(f["line_hit"][top[0]])
    return c


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    dev, test = open(DEV).read().split(), open(TEST).read().split()
    with multiprocessing.Pool(8) as pool:
        feats = dict(pool.map(features, dev + test))
    D, T = {k: feats[k] for k in dev}, {k: feats[k] for k in test}
    grid = list(itertools.product((0, 0.25, 0.5), (0, 0.25, 0.5)))
    lines = [f"Graph hints, offline. Top {TOP} nodes; hit = reference file within 3 lines of a reference hunk.",
             f"Dev {len(D)} tasks (reachable: some node on the reference lines in {sum(f['any_line'] for f in D.values())}); "
             f"test {len(T)} ladder tasks (reachable in {sum(f['any_line'] for f in T.values())})."]
    res = {}
    for a, b in grid:
        res[(a, b)] = (score(D, a, b), score(T, a, b))
    chosen = max(grid, key=lambda ab: (res[ab][0]["lines@5"], -ab[0] - ab[1]))
    if os.environ.get("FORCE_WEIGHTS"):   # ablation: e.g. FORCE_WEIGHTS=0,0 gives the text-only hint in the same format
        chosen = tuple(float(x) for x in os.environ["FORCE_WEIGHTS"].split(","))
    lines.append("graph a, embedding b | DEV: ref file in top 5, ref lines in top 5, top 1 on ref lines | TEST: same")
    for ab in grid:
        d, t = res[ab]
        mark = "  <- used" if ab == chosen else ""
        lines.append(f"  a={ab[0]:.2f} b={ab[1]:.2f} | dev {d['file@5']:3d} {d['lines@5']:3d} {d['lines@1']:3d} | test {t['file@5']:3d} {t['lines@5']:3d} {t['lines@1']:3d}{mark}")
    open(OUT / "offline.txt", "w").write("\n".join(lines) + "\n")
    print("\n".join(lines))
    hints, rows = {}, []
    for tid, f in T.items():
        top = rank(f, *chosen)
        hints[tid] = "; ".join(f"{f['where'][i][0]}: {qual(f['names'][i], f['where'][i][0])} (defined at line {f['where'][i][1]})" for i in top)
        rows.append({"task": tid, "hint": hints[tid], "hits": [bool(f["line_hit"][i]) for i in top], "nodes": len(f["names"])})
    json.dump({"chosen": {"graph": chosen[0], "embedding": chosen[1]}, "hints": hints}, open(OUT / "hints.json", "w"), indent=1)
    open(OUT / "nodes_test.jsonl", "w").write("".join(json.dumps(r) + "\n" for r in rows))
    print("GRAPH_HINT_DONE")
