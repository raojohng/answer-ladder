# Answer Ladder: given the answer, does a small coding agent act on it?

Code, data and paper for **"Can Once, Cannot Reliably: Given the answer, does a small coding agent act on it?"**, a paper-track
submission to the Kaggle competition *The Gemma 4 Developer Agent*.

Answer Ladder gives a coding agent the same bug-fixing task at five rungs of help (nothing; the reference files and lines; the
reference patch; the patch as ready-made edit commands; the patch plus a one-call apply tool) and measures how often, and how
reliably, the agent turns the help into a passing fix. Rungs 3 to 5 contain the answer, so the gap between them and 100%
measures execution apart from search.

| | Link |
|---|---|
| Paper (PDF) | `paper.pdf` in this repository; source `paper.md` |
| Benchmark dataset (task files, apply tool, scorer, 7,623 sessions) | https://www.kaggle.com/datasets/jaejohn/answer-ladder |
| Task snapshots and inputs for hosted runs | https://www.kaggle.com/datasets/jaejohn/answer-ladder-inputs |
| Reproduce every table (CPU, no model calls) | https://www.kaggle.com/code/jaejohn/answer-ladder-reproduce-and-score |
| Run all five rungs on a Gemma model (Kaggle Benchmarks, official harness) | https://www.kaggle.com/code/jaejohn/answer-ladder-gemma-4-31b-on-all-five-rungs |

## Results on the competition's official loop (77 tasks; three tries per rung for the local runs, one for Gemma 4 31B on Kaggle Benchmarks)

| Added to the task | Gemma 4 E4B | Qwen3.5-4B | Gemma 4 E2B | Gemma 4 31B (hosted, 1 try) |
|---|---|---|---|---|
| Nothing ("find this in the repository yourself") | 10.0% | 27.3% | 5.6% | 44.2% |
| Reference files and lines | 18.2% | 30.3% | 14.7% | 49.4% |
| Reference patch | 70.1% | 94.8% | 40.7% | 96.1% |
| Patch as ready-made edit commands | 66.2% | 87.4% | 53.2% | 94.8% |
| Patch and a one-call apply tool | 70.6% | 96.1% | 64.5% | 96.1% |

Given the patch, the apply tool adds 18 solves per pass for E2B and no detectable gain for E4B or Qwen3.5-4B on this loop;
on our own scaffold E4B gains 15 to 18 from the tool. Which form of help pays depends on the model and on the scaffold.

## Layout

```
paper.md, paper.pdf, figures/        the paper
REPRODUCE.md                         every number in the paper -> its data file -> the script that made it
data/, annotation/, tables/          per-session rows, labels and summaries behind every table and figure
analysis/                            analysis scripts; analysis/kaggle_harness_integration/ holds the Kaggle Benchmarks tasks
release/answer_ladder/               the benchmark (as on Kaggle, without the session archives): task files for every rung,
                                     agent bundles, apply tool, stage labels, scripts (score.py scores your own agent)
release/notebook/                    the reproduce notebook
e4b_track/rtx/                       the run scripts used on our GPU machine (two RTX 6000 Ada, vLLM 0.19.1)
```

## Quick start

Reproduce the ladder tables from the released sessions (standard library only, a few seconds):

```
kaggle datasets download jaejohn/answer-ladder -p answer_ladder --unzip
python3 answer_ladder/scripts/score.py --release answer_ladder/sessions/
```

Score your own agent: run it with the competition harness (`swegemma` 0.2.11) on each rung's task file in
`release/answer_ladder/tasks/`, three tries per task, then

```
python3 release/answer_ladder/scripts/score.py --rung control=runs/ctrl --rung lines=runs/loc --rung patch=runs/diff \
    --rung commands=runs/edits --rung apply=runs/apply
```

On Kaggle, the benchmark notebook above runs all five rungs with the official harness in subprocess mode, without a GPU or Docker;
set `MODEL` in its last cell.

## Licence and attribution

Our code, task text, tools and sessions: Apache 2.0. Task statements, snapshots and reference patches come from the
competition's public tasks (fastapi and rich, both MIT-licensed), released by the competition under Apache 2.0.
