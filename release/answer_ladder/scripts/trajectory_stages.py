"""One row per session: the stages it passed on the way to a fix, and what its first five tool calls looked like.

    taskset -c 24-47 nice python3 -I trajectory_stages.py <out.csv> <workers> <runs dir>=<tasks.jsonl>[,<tasks.jsonl>] [...]
    (runs where the raw records live; no GPU, no model; needs placement_census.py beside it)

Stages (privileged: they use the reference patch; 1-based index of the solver's tool call, empty = never):
  i_gold_file_seen   first call whose command or result names a reference file
  i_gold_read        first read.py call covering reference lines (within 3 lines)
  i_first_edit       first edit.py call;  first_edit_gold_file = it names a reference file
  i_first_applied    first edit.py call that changed a file; first_applied_gold_lines = one of its hunks is on reference lines
  ever_gold_edit     any applied edit landed on reference lines (final patch may still be elsewhere: see `place`)
Early features (not privileged: only what the agent did in its first EARLY tool calls, and the task statement):
  e_find, e_read, e_edit, e_other   calls by kind;  e_distinct, e_repeat   distinct and repeated commands
  e_nomatch   searches with no match;  e_errors   failed commands or rejected edits;  e_files_read   distinct files read
  e_find_hits   largest match count of a search;  e_issue_overlap   share of search terms that appear in the task statement
  e_think_chars   characters of thinking in those turns;  e_minute   the harness clock after the last of them
"""
import collections, csv, glob, json, multiprocessing, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import placement_census as pc

EARLY = 5
EDITED = re.compile(r"^(\S+): edited", re.MULTILINE)
HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+", re.MULTILINE)
MINUTE = re.compile(r"\[time: minute ([\d.]+) of")
MATCHES = re.compile(r"(\d+) matches in \d+ files")
QUOTED = re.compile(r"[\"']([^\"']+)[\"']")
FIELDS = ["run", "arm", "task", "try", "repo", "solved", "place", "gold_files", "gold_hunks", "calls", "crash", "error",
          "i_gold_file_seen", "i_gold_read", "i_first_edit", "first_edit_gold_file", "i_first_applied", "first_applied_gold_lines",
          "ever_gold_edit", "edits", "edits_applied", "i_submit", "minute_first_edit", "minutes", "issue_chars",
          "e_find", "e_read", "e_edit", "e_other", "e_distinct", "e_repeat", "e_nomatch", "e_errors", "e_files_read",
          "e_find_hits", "e_issue_overlap", "e_think_chars", "e_minute"]


def turns(folder, task):
    """[(tool name, command, result text, thinking chars)] of the solver stage, in order."""
    rows = [json.loads(l) for l in open(os.path.join(folder, "llm_calls.jsonl")) if l.strip()]
    rows = [r for r in rows if r.get("instance_id") == task and "run_command" in {t["function"]["name"] for t in r.get("tools") or []}]
    results, out = {}, []
    for r in rows:
        for m in r["messages"]:
            if m.get("role") == "tool" and m.get("tool_call_id"):
                c = m.get("content")
                results[m["tool_call_id"]] = c if isinstance(c, str) else json.dumps(c)
    for r in rows:
        msg = r["response"]["choices"][0]["message"]
        think = len(msg.get("reasoning_content") or msg.get("reasoning") or "") + len(msg.get("content") or "")
        for j, c in enumerate(msg.get("tool_calls") or []):
            try:
                command = json.loads(c["function"]["arguments"]).get("command", "") or ""
            except (ValueError, AttributeError):
                command = ""
            out.append((c["function"]["name"], command, results.get(c.get("id"), ""), think if j == 0 else 0))
    return out


def stdout(result):
    """A command that exits non-zero after an applied edit (e.g. a heredoc followed by a malformed extra line) comes back as
    status "error" with the real output under details.stdout; read it there too (extraction audit, 2026-11-11: 114 sessions
    with a patch had no detected applied edit for this reason)."""
    try:
        d = json.loads(result)
        out = d.get("stdout")
        if out is None and isinstance(d.get("details"), dict):
            out = d["details"].get("stdout")
        return str(out or ""), d.get("status"), d.get("exit_code")
    except (ValueError, AttributeError):
        return result, None, None


def near(a, b, hunks):
    return any(a <= d + pc.NEAR and c <= b + pc.NEAR for c, d in hunks)


def one(job):
    run, folder, task, arm, k, gold, issue = job
    try:
        res = [json.loads(l) for l in open(os.path.join(folder, "task_results.jsonl")) if l.strip()][-1]
        calls = turns(folder, task)
    except (OSError, ValueError, KeyError, IndexError):
        return None
    patch = "".join(open(p, errors="replace").read() for p in glob.glob(os.path.join(folder, "patches", "*")))
    row = dict.fromkeys(FIELDS, "")
    row.update(run=run, arm=arm, task=task, repo=task.rsplit("_", 1)[0], solved=int(bool(res.get("resolved"))), place=pc.place(pc.hunks(patch), gold),
               gold_files=len(gold), gold_hunks=sum(len(h) for h in gold.values()), calls=len(calls),
               crash=int(pc.CRASH in str(res.get("error"))), error=str(res.get("error") or "")[:40],
               minutes=round((res.get("duration_seconds") or 0) / 60, 2), issue_chars=len(issue), ever_gold_edit=0, edits=0, edits_applied=0)
    row["try"] = k
    words = set(re.findall(r"[A-Za-z_][A-Za-z_0-9]{2,}", issue.lower()))
    seen, files_read, terms, hit = set(), set(), [], 0
    early = collections.Counter()
    for i, (name, command, result, think) in enumerate(calls, 1):
        out, status, code = stdout(result)
        kind = "other"
        if name == "submit_patch":
            row["i_submit"] = row["i_submit"] or i
        elif "edit.py" in command:
            kind = "edit"; row["edits"] += 1
            files = {pc.norm(m.group(1)) for m in pc.FILE.finditer(command)}
            if not row["i_first_edit"]:
                row["i_first_edit"] = i; row["first_edit_gold_file"] = int(bool(files & set(gold)))
                m = MINUTE.search(out); row["minute_first_edit"] = m.group(1) if m else ""
            applied, on_gold = False, False
            parts = EDITED.split(out)            # ['', path, text after it, path, text, ...]
            for path, text in zip(parts[1::2], parts[2::2]):
                applied = True; path = pc.norm(path)
                if path in gold:
                    for m in HUNK.finditer(text):
                        a, n = int(m.group(1)), int(m.group(2) or 1)
                        on_gold = on_gold or near(a, a + max(n, 1) - 1, gold[path])
            if applied:
                row["edits_applied"] += 1
                if not row["i_first_applied"]:
                    row["i_first_applied"] = i; row["first_applied_gold_lines"] = int(on_gold)
                row["ever_gold_edit"] = int(row["ever_gold_edit"] or on_gold)
        elif "read.py" in command:
            kind = "read"
            m = pc.READ.search(command)
            if m:
                path = pc.norm(m.group(1)); files_read.add(path)
                if path in gold and not row["i_gold_read"]:
                    a, b = int(m.group(2) or 1), int(m.group(3) or 10 ** 9)
                    if near(a, b, gold[path]):
                        row["i_gold_read"] = i
        elif "find.py" in command:
            kind = "find"
            m = MATCHES.search(out); hit = max(hit, int(m.group(1)) if m else 0)
            terms += [w.lower() for q in QUOTED.findall(command) for w in re.findall(r"[A-Za-z_][A-Za-z_0-9]{2,}", q)]
        if not row["i_gold_file_seen"] and any(f in command or f in out for f in gold):
            row["i_gold_file_seen"] = i
        if i <= EARLY:
            early[kind] += 1; early["think"] += think
            early["repeat"] += command in seen
            early["nomatch"] += "No match for" in out
            early["errors"] += (status not in (None, "ok")) or (code not in (None, 0)) or "NOT EDITED" in out
            m = MINUTE.search(out)
            if m: row["e_minute"] = m.group(1)
            if i == min(EARLY, len(calls)):
                row.update(e_files_read=len(files_read), e_find_hits=hit, e_distinct=len(seen | {command}),
                           e_issue_overlap=round(sum(t in words for t in terms) / len(terms), 3) if terms else "")
        seen.add(command)
    row.update(e_find=early["find"], e_read=early["read"], e_edit=early["edit"], e_other=early["other"], e_repeat=early["repeat"],
               e_nomatch=early["nomatch"], e_errors=early["errors"], e_think_chars=early["think"])
    return row


def main(out, workers, *sources):
    jobs = []
    for source in sources:
        runs, files = source.split("=")
        gold, issue = {}, {}
        for f in files.split(","):
            for line in open(f):
                t = json.loads(line)
                gold[t["instance_id"]] = dict(pc.hunks(t["patch"])); issue[t["instance_id"]] = t.get("problem_statement") or ""
        for f in sorted(glob.glob(os.path.join(runs, "*_t[0-9]*", "task_results.jsonl"))):
            d = os.path.dirname(f); name, k = os.path.basename(d).rsplit("_t", 1)
            task = name if name in gold else next((t for t in gold if name.endswith("_" + t)), None)
            if task:
                jobs.append((os.path.basename(runs.rstrip("/")), d, task, name[:-len(task) - 1] if name != task else "", k, gold[task], issue[task]))
    with multiprocessing.Pool(int(workers)) as pool:
        rows = [r for r in pool.imap_unordered(one, jobs, chunksize=8) if r]
    rows.sort(key=lambda r: (r["run"], r["arm"], r["task"], int(r["try"])))
    with open(out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS); w.writeheader(); w.writerows(rows)
    print(f"{len(rows)} of {len(jobs)} sessions -> {out}")


if __name__ == "__main__":
    main(*sys.argv[1:])
