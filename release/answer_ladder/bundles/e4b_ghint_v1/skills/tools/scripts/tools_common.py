"""Shared by find.py and read.py once install.py has copied them to <repo>/.git/tools/.

The model calls them through run_command with one string argument, so the backtick quirk has no later argument to
swallow. This module cleans up what Gemma sends (stray quotes, backticks, 「」 brackets, a /workspace/ prefix), keeps a
small call log in .git/tools/state.json for the repeat guard, and prints the clock line that ends every reply.
Standard library only.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]                  # <repo>/.git/tools/this.py

USAGE = {"find.py": 'python3 .git/tools/find.py "name"   (add " in path/" to narrow)',
         "read.py": 'python3 .git/tools/read.py "path/to/file.py 120-180"',
         "edit.py": "python3 .git/tools/edit.py <<'EDIT'  (FILE: path, then <<<<<<< SEARCH / ======= / >>>>>>> REPLACE blocks, then EDIT)",
         "check.py": "python3 .git/tools/check.py"}


def _redirect_skill_call() -> None:
    """A script started by run_skill_script runs from the skill folder, not .git/tools, and gets its arguments as
    --flags it cannot use. Small models then retry it forever (E4B: 8 identical calls). Make sure the tools are
    installed, say how to call this one, and stop."""
    import sys
    script = Path(sys.argv[0]).name
    done = subprocess.run([sys.executable, str(HERE / "install.py")], capture_output=True, text=True, timeout=60)
    state = "The tools are installed" if "TOOLS_OK" in done.stdout else "Installing the tools failed"
    print(f"{state}. {script} works only through run_command, not run_skill_script. Call run_command with:\n"
          f"{USAGE.get(script, 'python3 .git/tools/' + script)}")
    raise SystemExit(0)


if HERE.parent.name != ".git":
    _redirect_skill_call()
STATE = HERE / "state.json"
LIMITS = HERE / "limits.json"
MAX_CHARS = 4000                        # the harness cuts command output at 5,000 characters
SKIP_DIRS = {".git", ".attempts", "__pycache__", "node_modules", ".tox", ".venv", "build", "dist", ".mypy_cache",
             ".pytest_cache"}
TEST_PATH = re.compile(r"(^|/)(tests?/|testing/|test_[^/]*\.py$|[^/]*_test\.py$|conftest\.py$)")
WRAPPERS = "`'\"「」『』【】“”‘’ "


def clean(text: str) -> str:
    """One argument as Gemma sent it, without wrapping quotes, backticks or brackets."""
    text = text.strip().strip(WRAPPERS).strip()
    return re.sub(r"^/?workspace/", "", text)


def clean_path(text: str) -> str:
    """A path relative to the repository; the repository itself becomes "". Handles /workspace and the real folder
    the no-Docker sandbox rewrites /workspace to."""
    text = clean(text)
    root = str(REPO).rstrip("/")
    if text.rstrip("/") in (root, "/workspace", "workspace") or text.startswith(root + "/"):
        text = text[len(root):]
    text = re.sub(r"^\.?/+", "", text)
    return text.strip(WRAPPERS)


def run(cmd: list[str], timeout: float = 20) -> str:
    try:
        return subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, timeout=timeout).stdout
    except (OSError, subprocess.TimeoutExpired):
        return ""


def repo_files() -> list[str]:
    """Every file in the repository, relative paths, skipping VCS, caches and build output."""
    out = []
    for root, dirs, files in os.walk(REPO):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and not d.endswith(".egg-info"))
        rel = os.path.relpath(root, REPO)
        for name in sorted(files):
            out.append(name if rel == "." else f"{rel}/{name}")
    return out


def tree_fingerprint() -> str:
    """Changes when any tracked or new file changes, so a repeat after an edit is not called a repeat."""
    diff = run(["git", "status", "--porcelain"]) + run(["git", "diff"])
    return hashlib.sha1(diff.encode()).hexdigest()[:12]


def load_state() -> dict:
    try:
        return json.loads(STATE.read_text())
    except (OSError, ValueError):
        return {"calls": []}


def record(tool: str, key: str) -> dict | None:
    """Log this call; return the earlier identical call (same tool, arguments and files) if there was one."""
    state = load_state()
    fingerprint = tree_fingerprint()
    earlier = next((c for c in reversed(state["calls"])
                    if c["tool"] == tool and c["key"] == key and c["tree"] == fingerprint), None)
    state["calls"].append({"tool": tool, "key": key, "tree": fingerprint, "at": time.time(),
                           "n": len(state["calls"]) + 1})
    try:
        STATE.write_text(json.dumps(state))
    except OSError:
        pass
    return earlier


def clock_line() -> str:
    """Minutes since the session's baseline commit, against the bundle's time cap."""
    started = run(["git", "log", "-1", "--format=%ct", "_swegemma_baseline"]).strip()
    try:
        cap = json.loads(LIMITS.read_text()).get("minutes")
    except (OSError, ValueError):
        cap = None
    if not started.isdigit():
        return ""
    used = (time.time() - int(started)) / 60
    if not 0 <= used < 180:              # not a session's own baseline commit
        return ""
    return f"[time: minute {used:.1f}" + (f" of {cap}]" if cap else "]")


def emit(body: str, repeat_note: str = "") -> None:
    """Print a reply: an optional repeat note first, the body cut to the output budget, the clock line last."""
    if len(body) > MAX_CHARS:
        body = body[:MAX_CHARS].rsplit("\n", 1)[0] + "\n... (output cut; narrow the search or the line range)"
    parts = [p for p in (repeat_note, body, clock_line()) if p]
    print("\n".join(parts))
