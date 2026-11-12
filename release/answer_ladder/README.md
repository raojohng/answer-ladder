# Answer Ladder: does a coding agent act on what it is given?

Kaggle dataset: https://www.kaggle.com/datasets/jaejohn/answer-ladder

A benchmark of **execution reliability** for coding agents in the Gemma 4 Developer Agent competition's format, released with the paper *Can Once, Cannot Reliably: Given the answer, does a small coding agent act on it?*

Each of 77 official competition tasks (fastapi, rich) is given to the agent at five rungs of help, one paragraph added to the task statement:

| Rung | Added to the task |
|---|---|
| 1 | "Where to change: find this in the repository yourself." (control) |
| 2 | The reference files and line ranges |
| 3 | The reference patch (never the tests) |
| 4 | The patch written as the exact edit commands the scaffold accepts |
| 5 | The patch plus a one-call tool that applies it |

Rungs 3 to 5 contain the answer, so the gap between them and 100% measures **execution**, apart from search: whether the agent takes the action that would succeed. Score an agent by its solved share at each rung and by **tasks solved in all three tries**.

## Results, three tries per task and rung

| Rung | E4B, our scaffold, first run | E4B, our scaffold, replication | E4B, official loop | Qwen3.5-4B, official loop | Gemma 4 E2B, official loop |
|---|---|---|---|---|---|
| 1 Control | 11.3% | 14.3% | 10.0% | 27.3% | 5.6% |
| 2 Reference lines | 21.6% | 24.7% | 18.2% | 30.3% | 14.7% |
| 3 Reference patch | 63.2% | 61.5% | 70.1% | 94.8% | 40.7% |
| 4 Edit commands | 78.4% | 80.1% | 66.2% | 87.4% | 53.2% |
| 5 Apply tool | 83.1% | 85.3% | 70.6% | 96.1% | 64.5% |
| Tasks solved in all 3 tries at rung 5 | 52 / 77 | 53 / 77 | 37 / 77 | 71 / 77 | 30 / 77 |

Gemma 4 E4B and E2B are 4-bit; Qwen3.5-4B runs with vLLM's `qwen3_coder` tool parser (`qwen3_xml` gave malformed tool calls).

Graph arms (E4B, our scaffold, two interleaved runs, share of tries solved):

| Arm | Run 1 | Run 2 |
|---|---|---|
| Control | 12.6% | 15.2% |
| Code-graph tools offered (used in 18 of 231 tries) | 15.2% | |
| Code-graph tools, told to use them (used in 156 of 231) | | 9.5% |
| Code-graph hint written into the task | 17.7% | 15.2% |
| Text-only hint (same builder, graph weights zero) | | 13.4% |
| Reference lines | 20.8% | |

On the same official loop the three models need different help: given the patch, E4B gains nothing from commands or the
tool, E2B gains from both (+9.7 and +8.7 solves per pass, 95% intervals above zero), and Qwen3.5-4B loses with commands
(-5.7) and recovers with the tool. `python3 scripts/score.py --release sessions/` prints every step with its interval.

The hint's gain over control did not replicate (run 1 +4.0 solves per pass, run 2 0.0); the text-only hint does as well as the graph hint.

## Contents

```
tasks/our_scaffold/     tasks_<bundle>.jsonl for rungs 1-5 on our scaffold (helper scripts find/read/edit/check)
tasks/official_loop/    rungs 1-5 on the competition's official loop (run_command, read_file, edit_file, write_file, submit_patch)
tasks/official_loop_qwen/, tasks/official_loop_e2b/   the same official-loop rungs, run with Qwen3.5-4B and Gemma 4 E2B
tasks/graph_arms/       control, graph tools (pull), graph hint (push), reference lines
tasks/graph_arms_2/     control, text-only hint, graph hint, graph tools with an instruction to use them
tasks/ids_77.txt        the 77 task ids
bundles/                the agent bundles used (agent.yaml, prompts, configs, skills)
apply_tool/             apply_fix.py + fixes_data.py; swe_fixtool-1.0-py3-none-any.whl (see below); the skill-script version
hosted/                 Gemma 4 31B on Kaggle Benchmarks (all rungs, one try): gemma31b_report.json (every task and rung),
                        gemma31b_summary.json, gemma31b_model_calls_<rung>.jsonl.gz; scripts/hosted_gemma31b.py compares it with the local runs
graph_hint/             hints.json (the hints shown), text_only_hints.json, nodes_test.jsonl (ranked symbols per task), offline.txt, dev_ids.txt, test_ids.txt
stages/                 one row per session with outcome and stage labels (first edit, first applied edit, place of final patch, ...)
sessions/               7,623 sessions: <run>.tar.gz with task_results.jsonl, adk_events.jsonl, tool_calls.jsonl (name and
                        arguments of every call) and the final patch per session;
                        index.jsonl lists run, session, task and outcome
scripts/                score.py (scores your agent; reproduces the tables), task builders (loc1_tasks.py, diff1_tasks.py, diff2_prep.py,
                        ladder3_prep.py, ladder4_prep.py, ladder56_prep.py, ladder8_prep.py), graph_hint.py, trajectory_stages.py with
                        placement_census.py (stage labels), and the summaries used in the paper (ladder_steps.py, apply_tool_use.py,
                        diff1_failures.py, graph_arms_summary.py, graph_split.py, ladder6_summary.py, graph_pooled.py, gate.py, ladder_models.py,
                        tool_use_models.py)
```

Session runs: `loc1`, `diff1`, `d2_e4b_diff_blocks_v1`, `d2_e4b_diff_apply_v2` (first run, rungs 1-2, 3, 4, 5), `ladder2` (replication), `ladder3` (official loop), `ladder5` (official loop, Qwen3.5-4B), `ladder8` (official loop, Gemma 4 E2B), `ladder4` and `ladder6` (graph arms, runs 1 and 2).

## Scoring

`scripts/score.py` needs only the Python standard library. Score your own agent from one harness results folder per rung (searched recursively for `task_results.jsonl`):

```
python3 scripts/score.py --rung control=runs/ctrl --rung lines=runs/loc --rung patch=runs/diff --rung commands=runs/edits --rung apply=runs/apply
```

It prints, per rung, the share of tries solved, solves per pass, tasks solved at least once and in every try, and each rung minus the one before with a paired 95% task-bootstrap interval. `python3 scripts/score.py --release sessions/` reproduces every ladder and graph table above from the released sessions in a few seconds.

## Hosted on Kaggle Benchmarks

The official-loop rungs are packaged as a Kaggle Benchmarks task, `answer-ladder-all-rungs` (notebook:
https://www.kaggle.com/code/jaejohn/answer-ladder-gemma-4-31b-on-all-five-rungs), which runs all five rungs on the 77 tasks side by side with the
competition's own harness (`swegemma` 0.2.11, official loop and grader) in subprocess mode, without a GPU or Docker. It reads
everything as plain files: the rung task files, task ids, agent prompt and apply tool from this dataset, and the snapshots,
sandbox setup and task wheels from `jaejohn/answer-ladder-inputs` (sha256-checked), plus the competition's public wheelhouse.
Set `MODEL` in its last cell. Statements are byte-identical to the official-loop runs here. Task sources and builder:
https://github.com/raojohng/answer-ladder (`analysis/kaggle_harness_integration/`).

Evidence so far: on Kaggle all 77 tasks calibrate (the empty patch fails, the reference patch passes; task
`answer-ladder-0-calibration`), a one-try probe of rung 3 (patch given) on the first five tasks per repository solved 9 of
10 with Gemma 4 31B, and the full task (all five rungs, 77 tasks, one try, 385 sessions) gave Gemma 4 31B 44.2%, 49.4%, 96.1%,
94.8% and 96.1% of tasks solved. Hosted runs use the provider's sampling (the proxy takes no temperature), unlike the locally served 4-bit
runs above.

## Re-running the analysis scripts

On Kaggle (https://www.kaggle.com/datasets/jaejohn/answer-ladder) the session archives arrive unpacked, as
`sessions/<run>/<run>/<session>/`; every command below reads that layout as well as the `.tar.gz` archives, so on Kaggle use
`sessions` (or `sessions/<run>/<run>` for `graph_arms_summary.py`) in place of `runs`. With the archives, unpack the runs you
need first, for example:

```
mkdir runs && tar -xzf sessions/ladder4.tar.gz -C runs
python3 -I scripts/graph_arms_summary.py stages/graph_arms_stages.csv runs/ladder4      # Table 2, run 1, incl. graph-tool use
python3 -I scripts/apply_tool_use.py runs                                               # needs ladder2 and d2_e4b_diff_apply_v2
python3 -I scripts/ladder_models.py stages/official_loop_stages.csv stages/official_loop_qwen_stages.csv stages/official_loop_e2b_stages.csv
```

These read each session's `task_results.jsonl`, `adk_events.jsonl`, `tool_calls.jsonl` and patch, and reproduce the paper's
files exactly. Two scripts are the exception: `trajectory_stages.py` and `placement_census.py` read the full model transcripts
(every tool result and thinking token), which are not released for size; their outputs are the files in `stages/`.

## Running it

Use the competition harness (`swegemma` 0.2.11) with the competition's snapshots and wheels. For each rung, point `TASKS_FILE` at the rung's task file and run your agent (or the bundle given) on the ids in `tasks/ids_77.txt`, three tries each.

- **Rung 5 without changing your agent's tools.** The harness unpacks every small wheel in the task's wheels folder into the sandbox's site-packages. Add `apply_tool/swe_fixtool-1.0-py3-none-any.whl` to a copy of the wheels folder used **only** for the rung-5 arm; the agent can then run `python3 -m apply_fix <task id>`, which `git apply`s the saved reference patch and prints `FIX APPLIED`.
- **Graph tools.** The harness offers `search_similar_code`, `get_code_neighbors` and `get_code_subgraph` only when `graphs/<repo>_<commit>.json` and `embeddings/<repo>_<commit>.npz` sit beside the tasks file (or in `data/`); otherwise it silently omits the tools' description.
- **Graph hint.** `scripts/graph_hint.py <competition data> graph_hint/dev_ids.txt graph_hint/test_ids.txt <out>` rebuilds the hints with no reference answer (the reference is used only to score them offline); its two weights are chosen on the dev tasks.

A five-rung run (1,155 sessions) took under an hour on two RTX 6000 Ada GPUs with vLLM.

## Stage columns (stages/*.csv)

`solved`; `place` of the final patch (gold lines, right file other lines, another file, no patch); `i_first_edit`, `i_first_applied` (1-based tool call); `first_applied_gold_lines`; `edits`, `edits_applied`; `calls`, `minutes`; `crash`. "Gold lines" means a hunk within three lines of a reference hunk in the same file. The edit columns (`i_first_edit`, `i_first_applied`, `first_applied_gold_lines`, `edits`, `edits_applied`) apply to our scaffold only: the extractor recognises its `edit.py` calls, so they are empty for the official-loop runs (`official_loop*_stages.csv`); `solved` and `place` apply to every run.

## License and attribution

Our task text, tools, hints, scripts and sessions: Apache 2.0. Task statements and reference patches come from the competition's public tasks, drawn from fastapi and rich (both MIT-licensed).
