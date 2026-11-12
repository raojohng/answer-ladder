"""Build the blind annotation records (GUIDE.md) for the sampled tasks. Runs on the RTX machine where the raw sessions are.

    python3 -I make_records.py <sample.json> <out dir>     (from work/rtx_test; needs placement_census.py there)

Per task one file <out>/records/<task>.md with its tries in a shuffled order labelled A, B, C, ...; no verdict, no reference.
<out>/key.json maps labels to tries, verdicts and reference overlap; annotators must not read it.
"""
import ast, glob, json, os, random, re, sys, tarfile
sys.path.insert(0, os.getcwd())
import placement_census as pc

SAMPLE, OUT = json.load(open(sys.argv[1])), sys.argv[2]
E = os.path.expanduser("~/workspace/Gemma4/work/extra_tasks")
SETS = {"v8_sweep": [(E + "/r1/tasks.jsonl", E + "/r1/snapshots"), (E + "/r2/tasks.jsonl", E + "/r2/snapshots")],
        "fresh_v8_p1": [(E + "/public/freshswe-py/data/tasks.jsonl", E + "/public/freshswe-py/data/snapshots")]}
EDITED = re.compile(r"^(\S+): edited[^\n]*\n((?:(?!^\S+: (?:edited|NOT EDITED)).*\n?)*)", re.M)
HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+\d+(?:,\d+)? @@", re.M)


def text(content):
    t = content if isinstance(content, str) else json.dumps(content)
    try:
        d = json.loads(t)
        if isinstance(d, dict):
            return str(d.get("stdout") or (d.get("details") or {}).get("stdout") or t)
    except Exception:
        pass
    return t


def task_info(run, task):
    for tasks, snaps in SETS[run]:
        for line in open(tasks):
            t = json.loads(line)
            if t["instance_id"] == task:
                return t, snaps
    raise KeyError(task)


def functions(source):
    """[(start, end, qualified name)] of every def and class."""
    out = []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return out
    def walk(node, prefix):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                name = f"{prefix}{child.name}"
                out.append((child.lineno, child.end_lineno or child.lineno, name))
                walk(child, name + ".")
            else:
                walk(child, prefix)
    walk(tree, "")
    return out


def enclosing(funcs, line):
    inside = [f for f in funcs if f[0] <= line <= f[1]]
    return min(inside, key=lambda f: f[1] - f[0])[2] if inside else "<module level>"


def changed(diff, limit=40):
    lines = [l for l in diff.splitlines() if (l.startswith("+") or l.startswith("-")) and not l.startswith(("+++", "---"))]
    return "\n".join(lines[:limit]) + ("\n..." if len(lines) > limit else "")


def try_record(folder, task, sources):
    rows = [json.loads(l) for l in open(folder + "/llm_calls.jsonl")]
    rows = [r for r in rows if r.get("instance_id") == task and any(t["function"]["name"] == "run_command" for t in r.get("tools") or [])]
    results = {}
    for r in rows:
        for m in r["messages"]:
            if m.get("role") == "tool" and m.get("tool_call_id"):
                results[m["tool_call_id"]] = text(m["content"])
    parts, n_edit, calls = [], 0, 0
    for r in rows:
        msg = r["response"]["choices"][0]["message"]
        thought = (msg.get("reasoning_content") or msg.get("reasoning") or "") + ("\n" + msg["content"] if msg.get("content") else "")
        for c in msg.get("tool_calls") or []:
            calls += 1
            try:
                cmd = json.loads(c["function"]["arguments"]).get("command", "") or c["function"]["name"]
            except Exception:
                cmd = c["function"]["name"]
            out = results.get(c.get("id"), "")
            if "edit.py" not in cmd or ": edited" not in out:
                continue
            n_edit += 1
            keep = 1500 if n_edit == 1 else 600
            parts.append(f"**Applied edit {n_edit} (tool call {calls}).** Thinking before it (last {keep} characters):\n\n> " +
                         re.sub(r"\s+", " ", thought.strip())[-keep:] + "\n")
            for m in EDITED.finditer(out):
                path = pc.norm(m.group(1))
                for h in HUNK.finditer(m.group(2)):
                    parts.append(f"- `{path}` near line {h.group(1)}, in `{enclosing(sources.get(path, []), int(h.group(1)))}`")
                parts.append("```diff\n" + changed(m.group(2)) + "\n```")
            if "TESTS BROKEN" in out:
                parts.append("Tool report after this edit: existing tests broke.")
            elif "no existing test broke" in out:
                parts.append("Tool report after this edit: no existing test broke.")
    final_text = rows[-1]["response"]["choices"][0]["message"].get("content") or ""
    patch = "".join(open(p, errors="replace").read() for p in glob.glob(folder + "/patches/*"))
    final = []
    for path, hunks in pc.hunks(patch).items():
        for a, b in hunks:
            final.append(f"- `{path}` lines {a}-{b}, in `{enclosing(sources.get(path, []), a)}`")
    body = "\n".join(parts) if parts else "_No applied edit was detected._"
    return (f"{body}\n\n**Final patch** ({calls} tool calls):\n" + ("\n".join(final) if final else "_empty_") +
            ("\n```diff\n" + changed(patch, 60) + "\n```" if patch.strip() else "") +
            f"\n\n**Final message:** {re.sub(r'\\s+', ' ', final_text)[:400]}\n"), patch


os.makedirs(OUT + "/records", exist_ok=True)
key = {}
for item in SAMPLE["sample"]:
    run, task = item["run"], item["task"]
    info, snaps = task_info(run, task)
    sources = {}
    with tarfile.open(f"{snaps}/{task}.tgz") as tar:
        for member in tar.getmembers():
            name = member.name[2:] if member.name.startswith("./") else member.name
            if name.endswith(".py") and member.isfile():
                try:
                    sources[name] = functions(tar.extractfile(member).read().decode("utf-8", "replace"))
                except Exception:
                    pass
    tries = list(item["tries"])
    random.Random(f"{task}:order").shuffle(tries)
    labels = "ABCDEFGH"
    doc = [f"# {task}\n", "## Task statement (first 1,500 characters)\n", "> " + info["problem_statement"][:1500].replace("\n", "\n> ") + "\n"]
    key[task] = {}
    for label, k in zip(labels, tries):
        folder = f"runs/{run}/{task}_t{k}"
        record, patch = try_record(folder, task, sources)
        doc.append(f"\n---\n\n## Try {label}\n\n{record}")
        res = json.loads(open(folder + "/task_results.jsonl").readline())
        key[task][label] = {"try": k, "solved": bool(res.get("resolved")),
                            "place": pc.place(pc.hunks(patch), pc.hunks(info["patch"])), "reference": dict(pc.hunks(info["patch"]))}
    open(f"{OUT}/records/{task}.md", "w").write("\n".join(doc))
json.dump(key, open(OUT + "/key.json", "w"), indent=1)
print("RECORDS_DONE", len(key), "tasks")
