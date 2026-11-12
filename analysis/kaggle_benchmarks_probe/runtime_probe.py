# %%
"""Private hosted-runtime smoke test; this is not an Answer Ladder result.

No competition data or credentials are embedded. Model tools perform only
fixed operations in a disposable toy repository, never model-supplied code.
"""
import importlib.util
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
import time

import kaggle_benchmarks as kbench


def command(args, cwd=None, stdin=None, timeout=20):
    started = time.monotonic()
    try:
        result = subprocess.run(
            args, cwd=cwd, input=stdin, text=True, capture_output=True,
            timeout=timeout,
        )
        return {
            "returncode": result.returncode,
            "stdout": result.stdout[-5000:], "stderr": result.stderr[-3000:],
            "seconds": round(time.monotonic() - started, 3),
        }
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"returncode": None, "error": str(exc)[:1000]}


PATCH = """diff --git a/calculator.py b/calculator.py
--- a/calculator.py
+++ b/calculator.py
@@ -1,2 +1,2 @@
 def add(a, b):
-    return a - b
+    return a + b
"""
TEST = """import unittest
from calculator import add

class AdditionTest(unittest.TestCase):
    def test_addition(self):
        self.assertEqual(add(2, 3), 5)
        self.assertEqual(add(-2, 3), 1)

if __name__ == '__main__':
    unittest.main()
"""


def make_repo(path):
    path.mkdir()
    (path / "calculator.py").write_text("def add(a, b):\n    return a - b\n")
    (path / "test_calculator.py").write_text(TEST)
    for args in (["git", "init", "-q"], ["git", "add", "."],
                 ["git", "-c", "user.name=Runtime Probe", "-c",
                  "user.email=probe@example.invalid", "commit", "-qm", "baseline"]):
        result = command(args, cwd=path)
        if result["returncode"] != 0:
            raise RuntimeError(json.dumps(result))


def run_tests(path):
    # No bytecode cache, so a rapid same-size source edit cannot reuse stale code.
    return command([sys.executable, "-B", "-m", "unittest", "-v", "test_calculator"], cwd=path)


def capabilities():
    report = {
        "python": sys.version, "platform": platform.platform(),
        "uid": os.getuid() if hasattr(os, "getuid") else None,
        "cpu_count": os.cpu_count(),
        "executables": {name: shutil.which(name) for name in
                        ("git", "docker", "dockerd", "podman", "uv", "pytest")},
        "modules": {name: importlib.util.find_spec(name) is not None for name in
                    ("swegemma", "adk_eval_core", "adk_submission", "pytest")},
        "docker_socket_present": Path("/var/run/docker.sock").exists(),
        "docker_host_configured": bool(os.environ.get("DOCKER_HOST")),
        "git": command(["git", "--version"]),
        "pytest": command([sys.executable, "-m", "pytest", "--version"]),
        "venv": command([sys.executable, "-m", "venv", "--help"]),
    }
    # Read-only daemon check. No daemon startup, image pulls or privileges added.
    report["docker_version"] = command(["docker", "version", "--format", "{{json .}}"])
    report["docker_info"] = command(["docker", "info", "--format", "{{json .ServerVersion}}"])
    report["docker_daemon_accessible"] = report["docker_info"]["returncode"] == 0
    return report


# %%
@kbench.task(name="answer-ladder-runtime-probe-20261112")
def runtime_probe(llm) -> bool:
    """Check hosted execution and fixed patch tools on a toy repository."""
    report = {"probe_version": 1, "scope": "synthetic runtime smoke test", "capabilities": capabilities()}
    report_path = Path.cwd() / "answer_ladder_runtime_probe.json"
    events = []
    report["tool_events"] = events
    try:
        with tempfile.TemporaryDirectory(prefix="answer-ladder-probe-") as tmp:
            root = Path(tmp)
            calibration = root / "calibration"
            make_repo(calibration)
            before = run_tests(calibration)
            applied = command(["git", "apply", "-"], cwd=calibration, stdin=PATCH)
            after = run_tests(calibration)
            diff = command(["git", "diff", "--binary"], cwd=calibration)
            fresh = root / "verification"
            make_repo(fresh)
            replay = command(["git", "apply", "-"], cwd=fresh, stdin=diff.get("stdout", ""))
            verified = run_tests(fresh)
            report["calibration"] = dict(before=before, apply=applied, after=after,
                                         diff=diff, fresh_apply=replay, fresh_test=verified)
            report["subprocess_workflow_passed"] = (
                before["returncode"] == 1 and applied["returncode"] == 0
                and after["returncode"] == 0 and diff["returncode"] == 0
                and bool(diff["stdout"].strip()) and replay["returncode"] == 0
                and verified["returncode"] == 0
            )
            agent_repo = root / "agent"
            make_repo(agent_repo)

            def apply_supplied_fix() -> str:
                """Apply the provided correct patch to the toy repository."""
                if len(events) >= 8:
                    raise RuntimeError("Probe tool budget exhausted")
                result = command(["git", "apply", "-"], cwd=agent_repo, stdin=PATCH)
                events.append({"tool": "apply_supplied_fix", "result": result})
                return json.dumps(result)

            def check_repository_tests() -> str:
                """Run the toy repository's addition tests and return their verdict."""
                if len(events) >= 8:
                    raise RuntimeError("Probe tool budget exhausted")
                result = run_tests(agent_repo)
                events.append({"tool": "check_repository_tests", "result": result})
                return json.dumps(result)

            try:
                response = llm.prompt(
                    "This is a runtime compatibility smoke test. The repository's add(a,b) "
                    "function incorrectly subtracts. Call apply_supplied_fix once, then "
                    "check_repository_tests once. Finally report the test outcome briefly. "
                    "Do not call either tool again. Here is the supplied fix:\n" + PATCH,
                    tools=[apply_supplied_fix, check_repository_tests],
                )
                report["model_response"] = str(response)[:3000]
            except Exception as exc:
                report["model_error"] = f"{type(exc).__name__}: {exc}"[:2000]
            report["agent_final_test"] = run_tests(agent_repo)
            report["model_tool_workflow_passed"] = (
                report["agent_final_test"]["returncode"] == 0
                and any(e["tool"] == "apply_supplied_fix" and e["result"]["returncode"] == 0 for e in events)
                and any(e["tool"] == "check_repository_tests" and e["result"]["returncode"] == 0 for e in events)
            )
    except Exception as exc:
        report["probe_error"] = f"{type(exc).__name__}: {exc}"[:2000]
    finally:
        report_path.write_text(json.dumps(report, indent=2) + "\n")
        print("ANSWER_LADDER_RUNTIME_REPORT\n" + json.dumps(report, indent=2))
    return bool(report.get("subprocess_workflow_passed") and report.get("model_tool_workflow_passed"))


# %%
if __name__ == "__main__":
    runtime_probe.run(kbench.llm)
