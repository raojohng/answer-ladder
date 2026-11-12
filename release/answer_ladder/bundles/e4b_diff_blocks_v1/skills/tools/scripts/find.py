"""Search the repository for a name or text. One argument: the term, optionally followed by " in <path>".

  python3 .git/tools/find.py "is_terminal"
  python3 .git/tools/find.py "def get_dependant in fastapi/dependencies"

Source files come before tests, definitions (def/class) first. With no exact match it retries ignoring case, then
lists the closest names in the code, so the reply always says what to try next instead of an empty error. A term the
shell emptied ("$ref" inside double quotes) gets a reply saying to use single quotes. Exit code is always 0: a search
with no match is an answer, not a failure.
"""

from __future__ import annotations

import difflib
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import tools_common as tc  # noqa: E402

TEXT = (".py", ".pyi", ".md", ".rst", ".txt", ".toml", ".cfg", ".ini", ".yaml", ".yml", ".json", ".html", ".js", ".css")
MAX_HITS = 40
IDENT = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]{2,}\b")


def parse(arg: str) -> tuple[str, str]:
    arg = tc.clean(arg)
    m = re.match(r"(.+?)\s+in\s+(\S+)$", arg)
    if m and (tc.REPO / tc.clean_path(m.group(2))).exists():
        return tc.clean(m.group(1)), tc.clean_path(m.group(2))
    return arg, ""


def search(term: str, where: str, ignore_case: bool) -> list[tuple[str, int, str]]:
    flags = re.IGNORECASE if ignore_case else 0
    pattern = re.compile(re.escape(term), flags)
    hits = []
    for rel in tc.repo_files():
        if where and not (rel == where or rel.startswith(where.rstrip("/") + "/")):
            continue
        if not rel.endswith(TEXT):
            continue
        try:
            lines = (tc.REPO / rel).read_text(errors="replace").splitlines()
        except OSError:
            continue
        for i, line in enumerate(lines, 1):
            if pattern.search(line):
                hits.append((rel, i, line.strip()))
    definition = re.compile(r"^\s*(async\s+def|def|class)\s+" + re.escape(term.split(".")[-1]) + r"\b", flags)
    hits.sort(key=lambda h: (not definition.search(h[2]) or bool(tc.TEST_PATH.search(h[0])),
                             not h[0].endswith((".py", ".pyi")), bool(tc.TEST_PATH.search(h[0])), h[0], h[1]))
    return hits


def close_names(term: str, where: str) -> list[str]:
    names = set()
    for rel in tc.repo_files():
        if rel.endswith(".py") and (not where or rel.startswith(where.rstrip("/"))):
            try:
                names.update(IDENT.findall((tc.REPO / rel).read_text(errors="replace")))
            except OSError:
                pass
    key = term.split(".")[-1]
    near = difflib.get_close_matches(key, sorted(names), n=6, cutoff=0.6)
    parts = [n for n in sorted(names) if key.lower() in n.lower() and n not in near][:4]
    return near + parts


SHELL_ATE = ("The search term reached find.py empty. If it holds a $ (like $ref) or backticks: inside double quotes "
             "the shell replaces $name and `...` before find.py runs, so \"$ref\" arrives as nothing. Put the term in "
             "single quotes: python3 .git/tools/find.py '$ref'.")


def repeat_note(earlier: dict | None) -> str:
    if not earlier:
        return ""
    return (f"REPEAT: the same search as call {earlier['n']}, and no file has changed since, so the result is the "
            "same. Search a different name, read the file, or make your edit.")


def main() -> None:
    raw = " ".join(sys.argv[1:])
    term, where = parse(raw)
    lost = re.match(r"^in\s+(\S+)$", term)          # "$ref" in path/ arrives as "in path/"
    lost = lost if lost and (tc.REPO / tc.clean_path(lost.group(1))).exists() else None
    if not term or lost:
        tc.emit(SHELL_ATE + (f" With a path: python3 .git/tools/find.py '$ref in {lost.group(1)}'" if lost else ""))
        return
    earlier = tc.record("find", f"{term}|{where}")
    scope = f" in {where}" if where else ""
    hits, note = search(term, where, False), ""
    if not hits:
        hits = search(term, where, True)
        note = f"No exact match for '{term}'{scope}; these match ignoring case." if hits else ""
    if not hits and where:
        elsewhere = search(term, "", False) or search(term, "", True)
        if elsewhere:
            places = ", ".join(f"{rel}:{n}" for rel, n, _ in elsewhere[:3])
            body = (f"No match for '{term}' in {where}, but {len(elsewhere)} matches elsewhere, first: {places}. "
                    f"Search again without ' in {where}', or read one of those.")
            tc.emit(body, repeat_note(earlier))
            return
    if not hits:
        names = close_names(term, where)
        body = f"No match for '{term}'{scope}."
        body += (" Closest names in the code: " + ", ".join(names) + ". Search one of those.") if names else \
            " Try a shorter part of the name, or search without the path."
    else:
        files = len({h[0] for h in hits})
        shown = hits[:MAX_HITS]
        lines = [f"{rel}:{n}: {text[:160]}" for rel, n, text in shown]
        head = f"{len(hits)} matches in {files} files for '{term}'{scope}"
        head += f" (first {MAX_HITS} shown; add ' in <path>' to narrow)" if len(hits) > MAX_HITS else ""
        body = "\n".join(p for p in (note, head + ":", *lines) if p)
    tc.emit(body, repeat_note(earlier))


if __name__ == "__main__":
    main()
