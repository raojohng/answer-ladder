# Answer Ladder on Kaggle Benchmarks (official harness, subprocess mode)

The Kaggle Benchmarks side of the paper (Section 8). The competition's `swegemma` 0.2.11 harness, official loop and official
grader run inside Kaggle Benchmarks tasks with `sandbox="subprocess"`; the model is served by Kaggle's model proxy through
`adapter.py` (ADK's LiteLlm with a client that calls the proxy's OpenAI-compatible endpoint).

| Kaggle task | What it does | Evidence here |
|---|---|---|
| `answer-ladder-0-calibration` | empty and reference patch for all 77 tasks, no model calls | `hosted_calibration_v1/run_log.txt`, `valid_ids.txt` (77 of 77) |
| `answer-ladder-3-reference-patch-10` | rung 3 on 10 tasks (first five per repository), one try | `hosted_gemma31b_rung3_10/` (Gemma 4 31B: 9 of 10) |
| `answer-ladder-all-rungs` | all five rungs on the 77 tasks, side by side; reads everything from public datasets | source `hosted_ladder/answer-ladder-all-rungs.py`, notebook `answer-ladder-all-rungs_gemma31b.ipynb`; Gemma 4 31B run (385 sessions, 0 platform errors): `hosted_gemma31b_all_rungs/` |

Subprocess mode installs no task dependencies, so each task unpacks the task wheels (the paper's set: public wheels minus
starlette 0.50+, plus five PyPI test wheels by sha256) ahead of the host packages in every sandbox venv; the apply tool reaches
only apply-rung sandboxes. History of the integration (probes, fixes) follows.

## Files

| File | Role |
|---|---|
| `prepare.py` | Stages the inputs (`payload/`: task, snapshot, sandbox setup, harness wheels, task wheels, official-loop bundle, sha256 manifest) and packs `private_dataset/harness_inputs.tar.gz` (120 MB) |
| `adapter.py` | ADK `LiteLlm` with a custom client that sends each completion to Kaggle's OpenAI-compatible proxy client, records request/response to `model_calls.jsonl` and (non-fatally) into the Kaggle chat log. Drops `temperature` when the proxy client says it does not support it (mirrors the SDK) |
| `controls.py` | Official `Evaluator` with a fixed patch (empty / reference / model patch) on either backend |
| `hosted_template.py` → `build_hosted.py` → `hosted_probe.py` | The Kaggle task source: verify manifest, install pinned deps, grader calibration, live official-loop run, replay of the model's patch in a fresh checkout |
| `test_adapter.py` | Tool-call / tool-result round trip through ADK's conversion (pytest) |
| `local_dryrun.py` | Runs `hosted_probe.py`'s integration code locally with a scripted fake model (OpenAI API): must print `DRYRUN_OK` |

## Status

- Local Docker and subprocess grading agree on `rich_3278` (empty fails exit 1, reference passes): `local_docker_v1/`, `local_subprocess_v1/`.
- Local dry run of the full hosted flow: `DRYRUN_OK` (after three fixes on 12 Nov: the model patch is read from
  `agent_run/patches/<task>.patch` since `task_results.jsonl` holds only its size; model calls are counted from
  `model_calls.jsonl` since the harness copies the registered model; `temperature` dropped for the proxy).
- Inputs dataset `jaejohn/answer-ladder-harness-probe-inputs` uploaded by John through the website (unpacked folder,
  not the archive; the task accepts both). From this machine `www.googleapis.com` (Kaggle's upload host) times out.
- Hosted v1 (`hosted_v1/`): failed at import, `rich` missing (harness wheels go in with `--no-deps`); the install had also
  lifted protobuf to 6.x, which kaggle-benchmarks 0.6.2 does not allow. Fixed: `rich` added, constraints
  `protobuf==5.29.6`, `hishel<2`; checked in a local copy of the hosted environment (kbench 0.6.2 + same installs).
- **Hosted v2 PASSED (12 Nov ~17:40 IST, run 6653573, `hosted_v2/`)**: grader calibration passed (empty fails, reference
  passes); Gemini 3.8 Flash in the official loop made 12 model calls / 11 tool calls (read_file x4, run_command x5,
  edit_file, submit_patch), patch 273 bytes, resolved in 48 s; fresh replay resolved; Kaggle result `booleanResult: true`;
  0 chat-log recording errors; temperature dropped on all 12 calls. **Docker parity**: the hosted model patch graded
  locally under Docker resolves too (`local_docker_replay_v2/`).

## Running it

`build_ladder.py --all` writes `hosted_ladder/answer-ladder-all-rungs.py` (from `ladder_all_template.py`
and `adapter.py`); `kaggle benchmarks tasks push answer-ladder-all-rungs -f <that file> -d jaejohn/answer-ladder
-d jaejohn/answer-ladder-inputs -d metric/gemma-4-developer-agent-wheelhouse` creates the task. Pushing starts a run on Kaggle's
default model, which the Gemma-only guard skips without model calls; the task's notebook then evaluates the model set in its
last cell. `local_ladder_test.py` runs any built task locally with a scripted fake model (set TMPDIR to a disk with a few GB free).
