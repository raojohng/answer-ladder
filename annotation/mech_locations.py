"""Function-level location of every final patch in the annotation sample, from the first changed line of each hunk
(GUIDE.md, change 2). Runs on the RTX machine from work/rtx_test:  python3 -I mech_locations.py <sample.json> <key.json> <out.json>"""
import ast, glob, json, os, re, sys, tarfile
sys.path.insert(0, os.getcwd())
import placement_census as pc
sample, key, out = json.load(open(sys.argv[1])), json.load(open(sys.argv[2])), sys.argv[3]
E = os.path.expanduser("~/workspace/Gemma4/work/extra_tasks")
SNAPS = {"v8_sweep": [E + "/r1/snapshots", E + "/r2/snapshots"], "fresh_v8_p1": [E + "/public/freshswe-py/data/snapshots"]}

def functions(source):
    out = []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return out
    def walk(node, prefix):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                name = prefix + child.name
                out.append((child.lineno, child.end_lineno or child.lineno, name))
                walk(child, name + ".")
            else:
                walk(child, prefix)
    walk(tree, "")
    return out

def enclosing(funcs, line):
    inside = [f for f in funcs if f[0] <= line <= f[1]]
    return min(inside, key=lambda f: f[1] - f[0])[2] if inside else "<module level>"

def first_changed(patch):
    """[(file, old-file line of the first changed line of each hunk)]"""
    res, path, old = [], None, None
    for line in patch.splitlines():
        if line.startswith("+++ "):
            path = line[4:].strip(); path = path[2:] if path.startswith(("a/", "b/")) else path; continue
        if line.startswith("--- "):
            continue
        m = re.match(r"@@ -(\d+)(?:,\d+)? \+", line)
        if m:
            old, found = int(m.group(1)), False; res.append([path, None]); continue
        if old is None or not res or res[-1][1] is not None:
            if old is not None and line[:1] in (" ", "-"):
                old += 1
            continue
        if line[:1] in ("+", "-"):
            res[-1][1] = old
        elif line[:1] == " ":
            old += 1
    return [(p, l) for p, l in res if l is not None]

result = {}
for item in sample["sample"]:
    run, task = item["run"], item["task"]
    snap = next(f"{d}/{task}.tgz" for d in SNAPS[run] if os.path.exists(f"{d}/{task}.tgz"))
    with tarfile.open(snap) as tar:
        src = {}
        for m in tar.getmembers():
            n = m.name[2:] if m.name.startswith("./") else m.name
            if n.endswith(".py") and m.isfile():
                src[n] = functions(tar.extractfile(m).read().decode("utf-8", "replace"))
    result[task] = {}
    for label, info in key[task].items():
        d = f"runs/{run}/{task}_t{info['try']}"
        patch = "".join(open(p, errors="replace").read() for p in glob.glob(d + "/patches/*"))
        locs = sorted({f"{p}::{enclosing(src.get(p, []), l)}" for p, l in first_changed(patch)
                       if p.endswith(".py") and "test" not in p.lower()})
        result[task][label] = locs
json.dump(result, open(out, "w"), indent=1)
print("MECH_DONE", sum(len(v) for v in result.values()), "tries")
