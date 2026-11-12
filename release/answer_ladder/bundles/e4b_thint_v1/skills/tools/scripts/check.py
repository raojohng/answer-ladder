"""Run the repository's own tests that relate to the current patch and report the ones the patch broke. No argument.

  python3 .git/tools/check.py

edit.py calls this after every edit of a source file, so the reply to an edit already says whether existing tests
still pass. Related test files: named after an edited module (rich/live.py -> tests/test_live*.py), importing it by
its dotted path, or mentioning a rare name from the changed lines (one found in at most 8 test files). A test that
fails now is checked against the files as they were at the session's start; only tests that passed then are reported
as broken. When the tests run out of time after an edit, they are timed on the original files: fast there means the
edit hangs (reported as TESTS HANG, tests stay on); slow there too means a slow suite (tests switch off for the
session). A self-written assertion only checks the model's own reading of the issue; these tests check what the
repository already promised.
"""

from __future__ import annotations

import json
import keyword
import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import tools_common as tc  # noqa: E402

BASE_TAG = "_swegemma_baseline"
MAX_FILES = 12
MAX_MENTION_FILES = 8
RUN_SECONDS = 20                       # after the edit; run_command stops everything at 60
BASE_SECONDS = 15                      # the original files: failing tests, or the whole run after a timeout
TEST_FILE = re.compile(r"^tests?/(.*/)?(test_[^/]*|[^/]*_test)\.py$")
FAILED = re.compile(r"^(?:FAILED|ERROR) (.+?)(?: - .*)?$", re.M)


def base_ref() -> str:
    return BASE_TAG if tc.run(["git", "rev-parse", "--verify", "-q", BASE_TAG]).strip() else "HEAD"


def patch_now(base: str) -> tuple[list[str], list[str], list[str]]:
    """Changed files, the changed source .py files, and the changed lines (both sides)."""
    changed = tc.run(["git", "diff", "--name-only", base]).split()
    sources = [f for f in changed if f.endswith(".py") and not tc.TEST_PATH.search(f)]
    diff = tc.run(["git", "diff", "-U0", base, "--", *sources]) if sources else ""
    lines = [l[1:] for l in diff.splitlines() if l[:1] in "+-" and not l.startswith(("+++", "---"))]
    return changed, sources, lines


def related(sources: list[str], lines: list[str]) -> list[str]:
    tests = [f for f in tc.repo_files() if TEST_FILE.match(f)]
    text = {}
    for f in tests:
        try:
            text[f] = (tc.REPO / f).read_text(errors="replace")
        except OSError:
            text[f] = ""
    picked = {}
    for src in sources:
        mod = src[:-3].replace("/", ".").removeprefix("src.")
        stem = Path(src).stem
        pattern = re.compile(rf"\b(from|import) {re.escape(mod)}\b")
        for f in tests:
            if Path(f).stem.startswith(f"test_{stem}") or pattern.search(text[f]):
                picked.setdefault(f, 0)
    words = {w for l in lines for w in re.findall(r"[A-Za-z_]\w{5,}", l)} - set(keyword.kwlist)
    for w in sorted(words):
        hits = [f for f in tests if w in text[f]]
        if len(hits) <= MAX_MENTION_FILES:
            for f in hits:
                picked.setdefault(f, 1)
    return sorted(picked, key=lambda f: (picked[f], f))[:MAX_FILES]


def pytest(targets: list[str], seconds: float) -> tuple[set[str], str, str] | None:
    """Failing test ids, pytest's last line, its output; None when it ran out of time."""
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    try:
        r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-rfE", "--tb=short",
                            "--no-header", *targets], cwd=tc.REPO, env=env, capture_output=True, text=True,
                           timeout=seconds)
    except subprocess.TimeoutExpired:
        return None
    out = r.stdout + r.stderr
    if "No module named pytest" in out:
        return set(), "pytest is not installed here", out
    last = next((l.strip("= ") for l in reversed(r.stdout.splitlines()) if l.strip()), "")
    return set(FAILED.findall(r.stdout)), last, r.stdout


def failed_at_start(ids: list[str], changed: list[str], base: str) -> set[str] | None:
    """Which of these tests fail with every changed file put back as it was at the start; None if out of time."""
    result = at_start(ids, changed, base, BASE_SECONDS)
    return None if result is None else result[0]


def at_start(targets: list[str], changed: list[str], base: str, seconds: float) -> tuple[set[str], str, str] | None:
    """pytest on `targets` with every changed file put back as it was at the start; None if out of time.
    The files are restored before this returns, also when the command is stopped: the scorer's `timeout -k 5s`
    sends SIGTERM first, which by default ends Python without running `finally`, leaving the original files in the
    patch."""
    saved = {}
    previous = {s: signal.signal(s, stopped) for s in (signal.SIGTERM, signal.SIGHUP)}
    try:
        for f in changed:
            path = tc.REPO / f
            saved[f] = path.read_bytes() if path.exists() else None
            old = subprocess.run(["git", "show", f"{base}:{f}"], cwd=tc.REPO, capture_output=True)
            if old.returncode == 0:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(old.stdout)
            elif path.exists():
                path.unlink()
        return pytest(targets, seconds)
    finally:
        for s in previous:                     # a second signal must not cut the restore short
            signal.signal(s, signal.SIG_IGN)
        for f, data in saved.items():
            path = tc.REPO / f
            if data is None:
                if path.exists():
                    path.unlink()
            else:
                path.write_bytes(data)
        for s, handler in previous.items():
            signal.signal(s, handler)


def stopped(signum: int, frame) -> None:
    raise SystemExit(128 + signum)


def first_failure(output: str, test_id: str) -> str:
    """Where the test failed and pytest's E lines, each line cut short (assertion reprs can be huge)."""
    name = test_id.split("::")[-1]
    failures = output.split("= FAILURES =", 1)[-1]          # FAILURES before ERRORS (teardown noise)
    for section in (failures, output):
        blocks = re.split(r"^_{3,} .* _{3,}$", section, flags=re.M)
        heads = re.findall(r"^_{3,} (.*) _{3,}$", section, flags=re.M)
        for head, body in zip(heads, blocks[1:]):
            if name in head:
                body = re.split(r"^={5,}", body, flags=re.M)[0]
                lines = [l if len(l) <= 160 else l[:157] + "..." for l in body.strip("\n").splitlines() if l.strip()]
                return "\n".join(lines[:12])
    return ""


def save(state: dict) -> None:
    try:
        tc.STATE.write_text(json.dumps(state))
    except OSError:
        pass


def report() -> str:
    """The test lines for an edit reply, or "" when no source file is changed."""
    base = base_ref()
    changed, sources, lines = patch_now(base)
    if not sources:
        return ""
    targets = related(sources, lines)
    if not targets:
        return "Tests: no existing test file relates to the changed code."
    shown = ", ".join(targets[:4]) + (f" and {len(targets) - 4} more" if len(targets) > 4 else "")
    state = tc.load_state()
    if state.get("tests_too_slow"):
        return "Tests: not run (too slow here); run one targeted test node yourself."
    result = pytest(targets, RUN_SECONDS)
    if result is None:                       # a hang caused by the edit, or a slow suite: time the original code
        started = time.time()
        if at_start(targets, changed, base, BASE_SECONDS) is not None:
            return (f"TESTS HANG: the related tests ({shown}) ran past {RUN_SECONDS} s after your edit and were "
                    f"stopped, but take {time.time() - started:.1f} s on the original code. Your edit probably "
                    "makes the code loop forever or wait: change the source. Never edit the tests.")
        state["tests_too_slow"] = True
        save(state)
        return (f"Tests: the related tests ({shown}) took over {RUN_SECONDS} s and were stopped; they will not run again "
                "after edits. Run one targeted test node yourself.")
    failing, last, output = result
    if not failing:
        return f"Tests: {last} ({shown}): no existing test broke."
    ids = sorted(failing)
    known = state.setdefault("failed_at_start", {})
    unknown = [t for t in ids if t not in known]
    if unknown:
        before = failed_at_start(unknown, changed, base)
        for t in unknown:
            known[t] = None if before is None else t in before
        save(state)
    broken = [t for t in ids if known.get(t) is False]
    unsure = [t for t in ids if known.get(t) is None]
    old = len(ids) - len(broken) - len(unsure)
    note = f" ({old} other failing tests already failed before your edits: ignore them.)" if old else ""
    if not broken and not unsure:
        return f"Tests: {last} ({shown}): no existing test broke.{note}"
    if broken:
        head = (f"TESTS BROKEN: {len(broken)} existing tests passed before your edits and fail now:\n  "
                + "\n  ".join(broken[:8]) + ("\n  ..." if len(broken) > 8 else ""))
    else:
        head = (f"TESTS FAILING: {len(unsure)} related tests fail (no time to check whether they failed before):\n  "
                + "\n  ".join(unsure[:8]))
    detail = first_failure(output, (broken or unsure)[0])
    return (head + (f"\nFirst failure:\n{detail}" if detail else "") + note
            + "\nIf the issue asks to change exactly what these tests check, they are outdated: keep your edit. "
            "Otherwise your edit broke working behaviour: change the source so they pass again. Never edit the tests.")


def main() -> None:
    earlier = tc.record("check", "")
    body = report() or "Tests: you have not changed any source file yet."
    repeat = f"REPEAT: nothing changed since the check at call {earlier['n']}." if earlier else ""
    tc.emit(body, repeat)


if __name__ == "__main__":
    main()
