"""Run a bundle on tasks against a vLLM server already running. Run with .venv_harness.
Same compaction and cache settings as e4b_track/notebook/cells/06_run.py, Docker sandbox as the scorer.
Saves llm_calls.jsonl and adk_events.jsonl beside the harness's own results.
Usage: run_tasks.py <bundle_agent_dir> <results_dir> <task_id> [<task_id> ...]
New tasks: set TASKS_FILE, SNAPSHOTS_DIR, WHEELS_DIR, SANDBOX_IMAGE, KAGGLE_SANDBOX_DIR and a fresh TMPDIR per environment."""
import asyncio, json, sys, time, warnings
from pathlib import Path
import litellm
import yaml
from google.adk.agents.context_cache_config import ContextCacheConfig
from google.adk.apps.app import EventsCompactionConfig
from swegemma.evaluate import EvalConfig, Evaluator
import os
from common import DATA, ROOT, registry

warnings.filterwarnings("ignore", message=r".*EXPERIMENTAL.*")
litellm.drop_params = True
here = Path(__file__).parent
for name in ("recorder.py", "event_recorder.py"):
    exec((here / name).read_text(), globals())

bundle, results, ids = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve(), sys.argv[3:]
assert not results.exists(), f"{results} exists: never overwrite a run"
# WHEELS_DIR="" means no wheels folder: the image carries its own environment (public task sets with their own image)
wheels = None if os.environ.get("WHEELS_DIR") == "" else Path(os.environ.get("WHEELS_DIR", ROOT / "work/wheels"))
limits = yaml.safe_load((bundle / "eval_config.yaml").read_text())["evaluation"]
cfg = EvalConfig(
    tasks_path=Path(os.environ.get("TASKS_FILE", DATA / "tasks.jsonl")), results_dir=results, submission_dir=bundle,
    snapshots_dir=Path(os.environ.get("SNAPSHOTS_DIR", DATA / "snapshots")),
    image=os.environ.get("SANDBOX_IMAGE", "swebench-sandbox:latest"),
    models=registry(),
    sandbox="docker", wheels_dir=wheels, task_ids=ids, concurrency=len(ids), display_mode="quiet",
    max_time_minutes=limits["max_time_minutes"], max_tool_calls=limits["max_tool_calls"],
    timeout_seconds=limits["timeout_seconds"], max_turns=limits["max_turns"], verification_timeout_seconds=300,
    events_compaction_config=EventsCompactionConfig(compaction_interval=15, overlap_size=2, token_threshold=14336,
                                                    event_retention_size=5),
    context_cache_config=ContextCacheConfig(min_tokens=2048, ttl_seconds=1800, cache_intervals=10))
t0 = time.time()
result = asyncio.run(Evaluator(cfg).run())
print(f"done in {(time.time() - t0) / 60:.1f} min: {result.resolved}/{result.total} resolved")
for line in open(results / "task_results.jsonl"):
    r = json.loads(line)
    print(r["instance_id"], "resolved", r["resolved"], "patch bytes", r.get("agent_patch_size"), "exit", r.get("test_exit_code"),
          "error", str(r.get("error"))[:200])
