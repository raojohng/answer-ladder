"""Edit files with SEARCH/REPLACE blocks read from a quoted heredoc, so the whole edit is one run_command argument.

  python3 .git/tools/edit.py <<'EDIT'
  FILE: rich/markup.py
  <<<<<<< SEARCH
      return markup
  =======
      return escape(markup)
  >>>>>>> REPLACE
  EDIT

Several blocks, and several FILE: lines, may go in one call. Each block is matched against the file as it stands,
by the first rule that finds exactly one place: exact text; the same lines ignoring indentation (the replacement is
re-indented); the text with one level of JSON escaping undone; a near match (90%+ similar, and clearly the best).
When the SEARCH text has several identical copies, `<<<<<<< SEARCH ALL` changes every copy and `FILE: path:LINE`
changes the copy nearest LINE; otherwise the reply lists each copy's line and the class/function around it.
All blocks for one file apply together or not at all. A .py file that no longer compiles is not written. Every
reply says what happened and, on a failure, the closest lines and the likely cause. After an edit of a source file
the reply also says whether the repository's related tests still pass (check.py).
"""

from __future__ import annotations

import difflib
import hashlib
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check  # noqa: E402
import tools_common as tc  # noqa: E402

SEARCH = re.compile(r"^\s*<{3,}\s*SEARCH\s*(ALL)?\s*:?\s*$", re.IGNORECASE)
DIFF_CHARS_WITH_TESTS = 1500           # leave room in the reply for the test report
DIVIDER = re.compile(r"^\s*={3,}\s*$")
REPLACE = re.compile(r"^\s*>{3,}\s*REPLACE\s*:?\s*$", re.IGNORECASE)
FILE = re.compile(r"^\s*(?:FILE|PATH)\s*:\s*(.+?)(?::(\d+))?\s*$", re.IGNORECASE)
ESCAPES = (("\\n", "\n"), ("\\t", "\t"), ('\\"', '"'), ("\\'", "'"), ("\\\\", "\\"))


def last_read_path() -> str:
    for call in reversed(tc.load_state().get("calls", [])):
        if call["tool"] == "read":
            return call["key"].split("|")[0]
    return ""


def parse(text: str) -> tuple[list[dict], list[str]]:
    """Blocks as {file, search, replace}; notes about anything the parser had to guess."""
    blocks, notes, current, near, every, state, search, replace = [], [], "", None, False, "out", [], []

    def close():
        blocks.append({"file": current, "search": "\n".join(search), "replace": "\n".join(replace), "all": every,
                       "near": near})

    for line in text.splitlines():
        if state == "out":
            m = FILE.match(line)
            if m:
                current, near = tc.clean_path(m.group(1)), int(m.group(2)) if m.group(2) else None
            elif SEARCH.match(line):
                state, search, replace, every = "search", [], [], bool(SEARCH.match(line).group(1))
        elif state == "search":
            if DIVIDER.match(line):
                state = "replace"
            else:
                search.append(line)
        elif state == "replace":
            if REPLACE.match(line):
                close()
                state = "out"
            elif SEARCH.match(line):          # a new block began without closing this one
                close()
                notes.append("a block had no >>>>>>> REPLACE line; it ended where the next SEARCH began")
                state, search, replace, every = "search", [], [], bool(SEARCH.match(line).group(1))
            else:
                replace.append(line)
    if state == "replace":
        close()
        notes.append("the last block had no >>>>>>> REPLACE line; it ran to the end")
    elif state == "search":
        notes.append("a SEARCH block had no ======= line and was ignored")
    fallback = last_read_path()
    for b in blocks:
        if not b["file"]:
            b["file"] = fallback
            notes.append(f"no FILE: line; used the file you read last ({fallback or 'none'})")
    return blocks, notes


def sandbox_paths(text: str) -> str:
    """Kaggle's no-Docker sandbox rewrites /workspace and /tmp inside commands; put the originals back."""
    root = str(tc.REPO).rstrip("/")
    if root != "/workspace":
        text = text.replace(root, "/workspace")
    tmp = os.environ.get("TMPDIR", "").rstrip("/")
    if tmp and tmp != "/tmp":
        text = text.replace(tmp, "/tmp")
    return text


def unescape(text: str) -> str:
    for a, b in ESCAPES:
        text = text.replace(a, b)
    return text


def indent_of(line: str) -> int:
    return len(line) - len(line.lstrip(" \t"))


def reindent(lines: list[str], delta: int) -> list[str]:
    out = []
    for line in lines:
        if not line.strip():
            out.append(line)
        elif delta >= 0:
            out.append(" " * delta + line)
        else:
            out.append(line[min(-delta, indent_of(line)):])
    return out


def scope_of(lines: list[str], i: int) -> str:
    """The class and function around line i ("Body.__init__"), for telling identical copies apart."""
    names, limit = [], indent_of(lines[i]) if lines[i].strip() else 10 ** 6
    for j in range(i - 1, -1, -1):
        m = re.match(r"^(\s*)(?:async\s+)?(?:def|class)\s+(\w+)", lines[j])
        if m and len(m.group(1)) < limit:
            names.insert(0, m.group(2))
            limit = len(m.group(1))
            if limit == 0:
                break
    return ".".join(names) or "module level"


def ambiguous(lines: list[str], starts: list[int], path: str) -> str:
    """Where each copy is, and the two ways to choose: every copy, or the copy at a line."""
    places = ", ".join(f"line {i + 1} ({scope_of(lines, i)})" for i in starts)
    return (f"ambiguous: the SEARCH text appears {len(starts)} times, at {places}. Adding lines will not help if the "
            f"copies are identical. To change every copy, start the block with <<<<<<< SEARCH ALL. To change one "
            f"copy, put its line on the FILE line, e.g. FILE: {path or '<path>'}:{starts[-1] + 1}")


def pick(starts: list[int], near: int | None) -> int | None:
    """The copy nearest line `near` (1-based), if one is clearly nearest."""
    if near is None:
        return None
    gaps = sorted((abs(i + 1 - near), i) for i in starts)
    return gaps[0][1] if len(gaps) == 1 or gaps[0][0] < gaps[1][0] else None


def find_place(text: str, search: str, replace: str, every: bool = False, near: int | None = None,
               path: str = "") -> tuple[str | None, str]:
    """The new text and the rule that matched, or (None, reason) when no single place matches. `every` changes all
    copies of the SEARCH text; `near` (a line number) picks the copy nearest it."""
    if not search.strip():
        return None, "empty SEARCH"
    n = text.count(search)
    if n == 1:
        return text.replace(search, replace, 1), "exact"
    if n > 1:
        offsets = [m.start() for m in re.finditer(re.escape(search), text)]
        starts = [text.count("\n", 0, o) for o in offsets]
        if every:
            return text.replace(search, replace), f"exact, all {n} copies (lines {', '.join(str(i + 1) for i in starts)})"
        chosen = pick(starts, near)
        if chosen is not None:
            o = offsets[starts.index(chosen)]
            return text[:o] + replace + text[o + len(search):], f"exact, the copy at line {chosen + 1}"
        return None, ambiguous(text.split("\n"), starts, path)
    lines, want = text.split("\n"), search.split("\n")
    while want and not want[-1].strip():
        want.pop()
    while want and not want[0].strip():
        want.pop(0)
    if not want:
        return None, "empty SEARCH"
    key = [w.strip() for w in want]
    hits = [i for i in range(len(lines) - len(want) + 1) if [l.strip() for l in lines[i:i + len(want)]] == key]
    first = next((j for j, w in enumerate(want) if w.strip()), 0)
    if len(hits) > 1 and not every:
        chosen = pick(hits, near)
        if chosen is None:
            return None, ambiguous(lines, hits, path)
        hits = [chosen]
    if hits:
        for i in reversed(hits):                    # bottom first, so earlier line numbers stay valid
            delta = indent_of(lines[i + first]) - indent_of(want[first])
            lines = lines[:i] + reindent(replace.split("\n"), delta) + lines[i + len(want):]
        rule = "same lines, indentation adjusted"
        return "\n".join(lines), rule + (f", all {len(hits)} copies" if len(hits) > 1 else "")
    if any(a in search for a, _ in ESCAPES):
        new, rule = find_place(text, unescape(search), unescape(replace), every, near, path)
        if new is not None:
            return new, rule + ", after undoing \\n / \\\" escaping"
    best, second, at = 0.0, 0.0, -1
    joined = "\n".join(key)
    for i in range(len(lines) - len(want) + 1):
        r = difflib.SequenceMatcher(None, joined, "\n".join(l.strip() for l in lines[i:i + len(want)])).ratio()
        if r > best:
            best, second, at = r, best, i
        elif r > second:
            second = r
    if best >= 0.9 and best - second >= 0.05:
        first = next((j for j, w in enumerate(want) if w.strip()), 0)
        delta = indent_of(lines[at + first]) - indent_of(want[first])
        new = reindent(replace.split("\n"), delta)
        return "\n".join(lines[:at] + new + lines[at + len(want):]), f"near match ({best:.0%} similar), lines {at + 1}-{at + len(want)}"
    return None, "not found"


def similarity(text: str, search: str) -> float:
    lines, want = text.split("\n"), [w for w in search.split("\n") if w.strip()] or [""]
    joined = "\n".join(w.strip() for w in want)
    return max((difflib.SequenceMatcher(None, joined, "\n".join(l.strip() for l in lines[i:i + len(want)])).ratio()
                for i in range(max(1, len(lines) - len(want) + 1))), default=0.0)


def closest(text: str, search: str) -> str:
    lines, want = text.split("\n"), [w for w in search.split("\n") if w.strip()] or [""]
    joined = "\n".join(w.strip() for w in want)
    best, at = 0.0, 0
    for i in range(max(1, len(lines) - len(want) + 1)):
        r = difflib.SequenceMatcher(None, joined, "\n".join(l.strip() for l in lines[i:i + len(want)])).ratio()
        if r > best:
            best, at = r, i
    lo, hi = max(0, at - 2), min(len(lines), at + len(want) + 2)
    shown = "\n".join(f"{n + 1:>5}| {lines[n]}" for n in range(lo, hi))
    return f"Closest lines ({best:.0%} similar), {lo + 1}-{hi}:\n{shown}"


def cause(text: str, search: str, path: str) -> str:
    if "\\n" in search and "\\n" not in text:
        return "Your SEARCH text has \\n where the file has line breaks: write the lines one under another, as they are."
    best = similarity(text, search)
    if best < 0.7:
        return (f"These lines are not in the file (the closest is only {best:.0%} similar): read the region with read.py "
                "and copy the lines exactly; do not write them from memory.")
    for call in reversed(tc.load_state().get("calls", [])):
        if call["tool"] == "edit-ok" and call["key"].startswith(path + "|"):
            return f"The file changed at call {call['n']} (your earlier edit). Read it again before editing."
        if call["tool"] == "read" and call["key"].startswith(path + "|"):
            break
    if not any(c["tool"] == "read" and c["key"].startswith(path + "|") for c in tc.load_state().get("calls", [])):
        return "You have not read this file in this session: read the lines first, then copy them exactly."
    return "Copy the SEARCH lines exactly from the closest lines below (without the line numbers)."


def compiles(path: str, text: str) -> str:
    if not path.endswith(".py"):
        return ""
    try:
        compile(text, path, "exec")
        return ""
    except SyntaxError as e:
        lines = text.split("\n")
        n = e.lineno or 1
        around = "\n".join(f"{i + 1:>5}| {lines[i]}" for i in range(max(0, n - 3), min(len(lines), n + 2)))
        return f"line {n}: {e.msg}\n{around}"


HEADER = re.compile(r"^\s*(async\s+)?(with|for|while|if|elif|else|try|except|finally|def|class)\b.*:\s*(#.*)?$")


def block_end(lines: list[str], i: int) -> int:
    """The last line of the block that line i opens (by indentation)."""
    end = i
    for j in range(i + 1, len(lines)):
        if lines[j].strip():
            if indent_of(lines[j]) <= indent_of(lines[i]):
                break
            end = j
    return end


def structure_hint(path: str, old: list[str], new: list[str], error: str) -> str:
    """When the compile error sits in lines the edit did not change, say which structure the edit broke: a block
    whose indentation was changed only in part, or a try: left without except/finally."""
    ops = [op for op in difflib.SequenceMatcher(None, old, new, autojunk=False).get_opcodes() if op[0] != "equal"]
    m = re.match(r"line (\d+)", error)
    if not ops or not m:
        return ""
    i1, i2, j1, j2 = ops[0][1], ops[-1][2], ops[0][3], ops[-1][4]
    if int(m.group(1)) <= j2:                      # Python stopped inside the edited lines: the usual reply is enough
        return ""
    where = f"Python stopped below the lines your edit changes (line {m.group(1)} of the edited result). "
    if "'except' or 'finally'" in error:
        opened = next((j + 1 for j in range(j2 - 1, j1 - 1, -1) if re.match(r"^\s*try\s*:", new[j])), None)
        if opened:
            return where + (f"Your edit opens try: (line {opened} of the edited result) but no except: or finally: "
                            "follows its block. "
                            "Put the except: or finally: part in the same edit.")
    for i in range(i1, i2):
        if HEADER.match(old[i]) and block_end(old, i) >= i2:
            end = block_end(old, i) + 1
            return where + (f"In the file now, line {i + 1} ({old[i].strip()[:60]}) opens a block that runs to line "
                            f"{end}; your edit changes only lines {i + 1}-{i2} of it, and the lines below no longer fit "
                            f"the new indentation. Put the whole block, lines {i + 1}-{end}, in SEARCH and REPLACE "
                            f"(read.py \"{path} {i + 1}-{end}\").")
    return where + "The lines after your edit no longer fit its indentation or structure."


def main() -> None:
    raw = sys.stdin.read() if not sys.stdin.isatty() else ""
    raw = sandbox_paths(raw)
    blocks, notes = parse(raw)
    if not blocks:
        tc.emit("edit.py found no edit block. Use exactly this form:\n"
                "python3 .git/tools/edit.py <<'EDIT'\nFILE: path/to/file.py\n<<<<<<< SEARCH\n(the current lines)\n"
                "=======\n(the new lines)\n>>>>>>> REPLACE\nEDIT")
        return
    digest = hashlib.sha1(raw.encode()).hexdigest()[:16]
    earlier = tc.record("edit", digest)
    out, by_file, written = [], {}, False
    for b in blocks:
        by_file.setdefault(b["file"], []).append(b)
    for path, group in by_file.items():
        target = tc.REPO / path
        if not path or not target.is_file():
            near = difflib.get_close_matches(path, tc.repo_files(), n=3, cutoff=0.5)
            out.append(f"{path or '(no file)'}: no such file." + (f" Closest: {', '.join(near)}." if near else ""))
            continue
        old = target.read_text()
        text, rules, failed = old, [], None
        for k, b in enumerate(group, 1):
            new, rule = find_place(text, b["search"], b["replace"], b.get("all", False), b.get("near"), path)
            if new is None:
                failed = (k, b, rule)
                break
            text, rules = new, rules + [rule]
        if failed:
            k, b, rule = failed
            head = f"{path}: NOT EDITED. Block {k} of {len(group)}: {rule}."
            hint = "" if rule.startswith("ambiguous") else " " + cause(old, b["search"], path) + "\n" + closest(old, b["search"])
            out.append(head + hint + ("\nNo block in this file was applied; fix that block and send them all again." if len(group) > 1 else ""))
            continue
        broken = compiles(path, text) if not compiles(path, old) else ""   # only guard files that compiled before
        if broken:
            a, b = old.split("\n"), text.split("\n")
            at = next((i for i, (x, y) in enumerate(zip(a, b)) if x != y), min(len(a), len(b)))
            mine = "\n".join(f"{i + 1:>5}| {b[i]}" for i in range(max(0, at - 1), min(len(b), at + 4)))
            hint = structure_hint(path, a, b, broken.splitlines()[0])
            out.append(f"{path}: NOT EDITED: the result would not compile ({broken.splitlines()[0]}). The file is unchanged.\n"
                       + (hint + "\n" if hint else "")
                       + f"Your edit starts at line {at + 1}:\n{mine}\nWhere Python stopped:\n" + "\n".join(broken.splitlines()[1:]))
            continue
        target.write_text(text)
        written = True
        tc.record("edit-ok", f"{path}|{digest}")
        diff = "\n".join(list(difflib.unified_diff(old.split("\n"), text.split("\n"), f"a/{path}", f"b/{path}", n=2, lineterm=""))[2:60])
        how = "; ".join(f"block {i}: {r}" for i, r in enumerate(rules, 1)) if len(rules) > 1 else rules[0]
        out.append(f"{path}: edited ({how}).\n{diff}")
    tests = check.report() if written else ""
    if tests:
        out = [o if len(o) <= DIFF_CHARS_WITH_TESTS else o[:DIFF_CHARS_WITH_TESTS].rsplit("\n", 1)[0] + "\n ..."
               for o in out] + [tests]
    if notes:
        out.insert(0, "Note: " + "; ".join(notes) + ".")
    repeat = ""
    if earlier and any("would not compile" in o for o in out):
        repeat = (f"REPEAT: this exact edit was refused at call {earlier['n']} because the result would not compile; "
                  "sending it again gives the same result. Change the edit as described below.")
    elif earlier and any("NOT EDITED" in o or "no such file" in o for o in out):
        repeat = f"REPEAT: this exact edit failed at call {earlier['n']} and nothing has changed since. Read the lines again and copy them exactly."
    tc.emit("\n".join(out), repeat)


if __name__ == "__main__":
    main()
