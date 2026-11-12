# Kaggle Benchmarks hosted compatibility test

Tested 12 November 2026, approximately 14:30–14:37 IST, using private
Kaggle Benchmark tasks and the platform's default Gemini 3.8 Flash model.

**Result: a real repository patch-and-test workflow works in the hosted
runtime using subprocesses and a virtual environment. The default runtime
does not provide Docker, so the existing Docker runner cannot run unchanged.**

This is a feasibility test, not an Answer Ladder score. Neither task is public.

## Hosted evidence

| Probe | Version / run | Result |
|---|---|---|
| [Toy runtime probe](https://www.kaggle.com/benchmarks/tasks/jaejohn/answer-ladder-runtime-probe-20261112/1) | v1 / 6651262 | Passed: baseline test fails; supplied fix passes; fresh-checkout replay passes; model calls fixed apply and test tools |
| [Rich repository probe](https://www.kaggle.com/benchmarks/tasks/jaejohn/answer-ladder-repository-probe-20261112/1) | v1 / 6651308 | Failed before model call: missing final newline in source patch strings caused `git apply` to reject the test patch |
| [Corrected Rich probe](https://www.kaggle.com/benchmarks/tasks/jaejohn/answer-ladder-repository-probe-20261112/2) | v2 / 6651321 | Passed: repository fetch, dependency installation, negative/positive calibration, model tool calls, fresh-checkout verification |

Raw reports, source notebooks, task metadata and model conversation records
are under `hosted_v1/`, `hosted_repository_v1/`, and `hosted_repository_v2/`.
The JSON filenames are `answer_ladder_runtime_probe.json` and
`answer_ladder_repository_probe.json`. `local_stub_report.json` uses a local
test double and is **not** hosted model evidence.

## Real task

- Competition task: `rich_3278`, selected from the released 77-task manifest.
- Repository: `Textualize/rich`.
- Commit: `4c5d305bb902ce97011666ada19e48d0b27b49e1`, fetched by exact SHA and checked.
- Test command: isolated venv Python, `-B -m pytest -q -o addopts= tests/test_ansi.py`.
- Empty patch plus reference test patch: **16 failed, 7 passed**.
- Reference patch plus reference test patch: **23 passed**.
- Model called `apply_supplied_fix` and `submit_and_verify`; submitted patch: **23 passed**.
- Independent final fresh-checkout verification: **23 passed**.
- Hosted task execution: approximately **16 seconds**, excluding scheduling/startup.

The reference test patch is applied only in fresh verification copies, not
the agent checkout. The model receives the supplied fix and two fixed tools.
It does not receive a general shell, arbitrary code execution tool, or test source.
The v2 builder normalizes final newlines on both input patches; original task
data is unchanged. Installed dependency versions are recorded in the report.

## Runtime capabilities observed

| Capability | Observation |
|---|---|
| Python | 3.12.10 |
| CPU | 4 reported CPUs |
| Git | Available, 2.47.3 |
| Temporary files and subprocesses | Working |
| GitHub fetch | Working for the pinned Rich commit |
| Virtual environment | Created successfully with `uv venv` |
| Dependency installation | `uv pip install` successfully installed pytest and Rich dependencies |
| Native model tool calls | Working on Gemini 3.8 Flash |
| Docker / dockerd / podman | No executables in PATH |
| Docker socket / Docker host config | Not present |
| pytest and competition harness preinstalled | No |
| Hosted artifacts | JSON report and SDK conversation/result records downloaded successfully |

`hosted_models.txt` records the model catalog observed that day. It contains
Gemma 4 31B and Gemma 4 26B A4B, but not the paper's E4B/E2B variants or Qwen.
Catalog availability can change. No equivalence with the paper's quantized,
locally served model configurations is claimed.

## What remains untested

1. The full `swegemma` evaluator and its metric script in this hosted runtime.
2. All five rungs, repeated attempts, all 77 tasks, and FastAPI dependencies.
3. General agent editing/navigation tools, isolation of model-generated code,
   and protection of evaluator state and runtime credentials. A directory/venv
   is not a security boundary; these probes expose only fixed trusted operations.
4. Score parity with the Docker-based evaluation and frozen dependency set.
5. Full-run concurrency, inference quota and cost, and leaderboard aggregation.
6. Whether Docker could be provisioned through a supported configuration;
   the probe checks the default runtime and does not install/start a daemon.

The existing `swegemma` 0.2.11 wheel includes
`swegemma.sandbox.subprocess.SubprocessManager`. Its existence was verified
locally, but that manager was not installed or exercised on Kaggle in this test.

## Reproduce

From the project root (pushes create/update private remote tasks and start
their initial default-model runs):

```sh
kaggle benchmarks tasks push answer-ladder-runtime-probe-20261112 -f paper_track/analysis/kaggle_benchmarks_probe/runtime_probe.py
python3 paper_track/analysis/kaggle_benchmarks_probe/build_repository_probe.py
kaggle benchmarks tasks push answer-ladder-repository-probe-20261112 -f paper_track/analysis/kaggle_benchmarks_probe/repository_probe.py
kaggle benchmarks tasks status answer-ladder-repository-probe-20261112
kaggle benchmarks tasks download answer-ladder-repository-probe-20261112 -o /tmp/answer-ladder-probe-results -s
```

The builder needs the existing competition `data/tasks.jsonl`. The generated
script embeds only the selected task's identity, commit, reference patch and
test patch. Do not publish the private smoke probes as benchmark results.
