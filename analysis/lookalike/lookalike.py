"""Look-alikes: do wrong edits land on code that looks like the right code, in the competition's embedding space?

Tries without help (control arms of the four ladder runs, and the graph-tools arm) on the 77 ladder tasks. For each failed try
whose final patch is not on the reference lines, the edited lines and the reference lines are mapped to graph nodes (functions,
classes) of the task's snapshot (graph_hint.locate). Measures, per try (first edited node against the reference nodes):
  sim        best cosine between an edited node and a reference node (precomputed 256-d node embeddings)
  rank       rank of the nearest reference node among all nodes of the repository, by cosine to the edited node (1 = nearest)
  same_name  the edited node and a reference node share their last name part (e.g. FastAPI.get / APIRouter.get)
Baseline: the same measures for every other node in the same file as the edited node (what an edit "near there" would give).
    python3 -I lookalike.py <competition data dir> <session archives dir> <stages dir> <ids file> <out dir>
"""
import collections, csv, json, multiprocessing, os, re, sys, tarfile, tempfile
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "graph_hint"))
sys.argv, ARGS = sys.argv[:2] + ["x", "x", "x"], sys.argv          # graph_hint reads argv at import (data dir first)
import graph_hint as gh
DATA, SESS, STAGES, IDS, OUT = Path(ARGS[1]), Path(ARGS[2]), Path(ARGS[3]), ARGS[4], Path(ARGS[5])
gh.DATA = DATA
tasks = {t["instance_id"]: t for t in map(json.loads, open(DATA / "tasks.jsonl"))}
ids = set(open(IDS).read().split())
ARMS = {("loc1", "e4b_loc_ctrl_v1"), ("ladder2", "e4b_loc_ctrl_v1"), ("ladder3", "e4b_off_ctrl_v1"), ("ladder4", "e4b_loc_ctrl_v1"),
        ("ladder4", "e4b_gpull_v1")}
STAGEFILES = ["first_run_stages.csv", "replication_stages.csv", "official_loop_stages.csv", "graph_arms_stages.csv"]


def changed_lines(patch):
    """{file: set of old-file line numbers touched}: removed lines, and the line before each insertion."""
    out, cur, line = collections.defaultdict(set), None, 0
    for l in patch.splitlines():
        if l.startswith("--- "):
            p = l[4:].split("\t")[0]; cur = p[2:] if p.startswith("a/") else None
        elif l.startswith("@@") and cur:
            line = int(re.match(r"@@ -(\d+)", l).group(1))
        elif cur and l[:1] in (" ", "-", "+") and not l.startswith(("+++", "---")):
            if l[0] == "-":
                out[cur].add(line)
            elif l[0] == "+":
                out[cur].add(max(line - 1, 1))
            if l[0] in " -":
                line += 1
    return out


def nodes_at(where, lines):
    """Smallest node spans containing any of the lines (methods rather than their class)."""
    hit = []
    for f, ls in lines.items():
        for n, (nf, a, b) in where.items():
            if nf == f and any(a <= x <= b for x in ls):
                hit.append((b - a, n))
    best = {}
    for size, n in sorted(hit):
        best.setdefault(n, size)
    return [n for n, _ in sorted(best.items(), key=lambda kv: kv[1])]


def prepare(tid):
    t = tasks[tid]
    stem = f"{t['repo'].split('/')[-1]}_{t['base_commit']}"
    g = json.load(open(DATA / "graphs" / f"{stem}.json"))
    emb = np.load(DATA / "embeddings" / f"{stem}.npz")
    with tempfile.TemporaryDirectory() as d:
        with tarfile.open(DATA / "snapshots" / f"{tid}.tgz") as tf:
            tf.extractall(d, filter="data")
        root = Path(d)
        if not (root / ".git").exists():
            sub = [p for p in root.iterdir() if p.is_dir()]
            root = sub[0] if len(sub) == 1 else root
        where = gh.locate(g["nodes"], root)
    names = [n for n in where if n in emb.files]
    E = np.array([emb[n] for n in names], dtype=np.float32)
    if os.environ.get("CENTER"):        # remove the repository's mean vector: the raw vectors share one dominant direction
        E -= E.mean(axis=0, keepdims=True)
    E /= np.maximum(np.linalg.norm(E, axis=1, keepdims=True), 1e-9)
    ref = nodes_at({n: where[n] for n in names}, changed_lines(t["patch"]))
    return tid, {"names": names, "where": {n: where[n] for n in names}, "E": E, "ref": ref}


def measure(f, edited):
    idx = {n: i for i, n in enumerate(f["names"])}
    R = [idx[r] for r in f["ref"] if r in idx]
    e = idx[edited]
    sims = f["E"] @ f["E"][e]
    sims[e] = -2
    order = np.argsort(-sims)
    rank_of = {int(i): k + 1 for k, i in enumerate(order)}
    short = lambda n: n.split(".")[-1]
    ref_short = {short(f["names"][r]) for r in R}
    # chance that a random repository node (not a reference node) shares a reference node's last name part
    chance = sum(short(n) in ref_short for n in f["names"] if n not in f["ref"]) / max(len(f["names"]) - len(R), 1)
    return {"sim": float(max(sims[r] for r in R)) if R else None, "rank": min(rank_of[r] for r in R) if R else None,
            "same_name": any(short(f["names"][r]) == short(edited) for r in R), "name_chance": chance, "n": len(f["names"])}


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for sf in STAGEFILES:
        for r in csv.DictReader(open(STAGES / sf)):
            if (r["run"], r["arm"]) in ARMS and r["task"] in ids:
                rows.append(r)
    wrong = [r for r in rows if r["solved"] != "1" and r["place"] in ("another file", "right file, other lines")]
    print(f"{len(rows)} tries without help; {len(wrong)} failed with a final patch off the reference lines")
    with multiprocessing.Pool(8) as pool:
        feats = dict(pool.map(prepare, sorted({r["task"] for r in wrong})))
    patches = {}
    for run in sorted({r["run"] for r in wrong}):
        with tarfile.open(SESS / f"{run}.tar.gz") as tar:
            for m in tar.getmembers():
                if "/patches/" in m.name:
                    patches[m.name.split("/")[1]] = tar.extractfile(m).read().decode(errors="ignore")
    out, base = [], []
    for r in wrong:
        f = feats[r["task"]]
        sess = f"{r['arm']}_{r['task']}_t{r['try']}"
        if sess not in patches or not f["ref"]:
            continue
        edited = nodes_at(f["where"], changed_lines(patches[sess]))
        if not edited:
            continue
        m = measure(f, edited[0])
        m.update(run=r["run"], arm=r["arm"], task=r["task"], session=sess, edited=edited[0], ref=f["ref"][:3], place=r["place"])
        out.append(m)
        ef = f["where"][edited[0]][0]
        for n, (nf, _, _) in f["where"].items():         # baseline: other nodes of the same file
            if nf == ef and n != edited[0] and n not in f["ref"]:
                base.append(measure(f, n))
    open(OUT / "wrong_edits.jsonl", "w").write("".join(json.dumps(x) + "\n" for x in out))
    q = lambda xs, p: float(np.percentile(xs, p))
    with open(OUT / "summary.txt", "w") as fh:
        def say(s):
            print(s); print(s, file=fh)
        say(f"Look-alikes. {len(rows)} tries without help on {len(ids)} tasks; {len(wrong)} failed off the reference lines; "
            f"{len(out)} mapped to graph nodes ({len({o['task'] for o in out})} tasks). Baseline: {len(base)} other nodes in the same files.")
        for name, xs in (("wrong edits", out), ("same-file baseline", base)):
            s = [x["sim"] for x in xs]; k = [x["rank"] for x in xs]
            say(f"  {name:20s} cosine to the nearest reference node: median {np.median(s):.3f} (IQR {q(s, 25):.3f}-{q(s, 75):.3f}) | "
                f"reference node among the 10 nearest: {sum(x <= 10 for x in k)}/{len(k)} ({100 * np.mean([x <= 10 for x in k]):.0f}%), "
                f"among the 3 nearest: {100 * np.mean([x <= 3 for x in k]):.0f}% | same name: {100 * np.mean([x['same_name'] for x in xs]):.0f}% "
                f"(random repository node: {100 * np.mean([x['name_chance'] for x in xs]):.1f}%) | "
                f"median nodes per repo {int(np.median([x['n'] for x in xs]))}")
        by_task = collections.defaultdict(list)
        for o in out:
            by_task[o["task"]].append(o["rank"] <= 10)
        say(f"  task-weighted share of wrong edits with the reference node among their 10 nearest: "
            f"{100 * np.mean([np.mean(v) for v in by_task.values()]):.0f}% over {len(by_task)} tasks")
        top = collections.Counter((o["edited"].split(".")[-1], o["ref"][0].split(".")[-1]) for o in out if o["rank"] <= 3)
        say("  most common look-alike pairs (edited -> reference): " + "; ".join(f"{a} -> {b} x{c}" for (a, b), c in top.most_common(8)))
    print("LOOKALIKE_DONE")
