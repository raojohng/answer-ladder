# Reproducing the paper's numbers

Every number in `paper_v17.md` comes from a file in `data/`, `data/training/` or `data/graph_hint/`, produced by a script in `analysis/`, `analysis/training/`, `analysis/graph_hint/` or `annotation/`. The released benchmark (`release/answer_ladder/`, Section 8) holds the task files, bundles, apply tool, graph hints, stage labels and the 7,623 ladder and graph-arm sessions (events, results, final patches).

Runs used the competition harness (`swegemma` 0.2.11, Docker sandbox), the 4-bit model `gemma-4-e4b-it-qat-w4a16-ct` on vLLM 0.19.1 (temperature 1.0, top-p 0.95, top-k 40, thinking budget 3,072), one server per GPU (2× RTX 6000 Ada), 8 minutes and 50 tool calls per session.

| Paper item | Output file | Script (inputs) |
|---|---|---|
| Section 3, Figure 1 | `tables/table1_tries_curve.csv`, `figures/fig1_tries_curve.png` | `analysis/make_tables.py`, `analysis/make_figures.py` (`data/sessions.csv`) |
| Table 1, first run | `data/training/ladder_summary.txt`, `ladder_stages.csv` | tasks `analysis/training/loc1_tasks.py`, `diff1_tasks.py`, `diff2_prep.py` + `diff2_bundles.sh` + `apply_fix.py`; runs `gpu1_diff1.sh`, `gpu_diff2.sh`; stages `analysis/trajectory_stages.py` |
| Table 1, replication | `data/training/ladder2_summary.txt`, `ladder2_stages.csv` | `ladder2_test.sh` (seeds 7100+GPU) |
| Table 1, official loop | `data/training/ladder3_stages.csv`, `ladder3_steps.txt`, `ladder3_failures.txt` | `e4b_track/rtx/ladder3_prep.py` (edit_file calls, apply wheel), `ladder3_test.sh` (seeds 7300+GPU) |
| Table 1, Qwen3.5-4B and E2B (official loop) | `data/training/ladder5_stages.csv`, `ladder5_steps.txt`, `ladder8_stages.csv`, `ladder8_steps.txt` | `e4b_track/rtx/ladder56_prep.py`, `ladder5_test.sh` (`QWEN_TOOL_PARSER=qwen3_coder`), `ladder8_prep.py`, `ladder8_test.sh`; `trajectory_stages.py` |
| Section 8, hosted calibration (77/77) and Gemma 4 31B probe (9/10, rung 3) | `analysis/kaggle_harness_integration/hosted_calibration_v1/run_log.txt`, `valid_ids.txt`, `hosted_gemma31b_rung3_10/report.json`, `model_calls.jsonl` | `analysis/kaggle_harness_integration/build_ladder.py` (from `ladder_template.py`); Kaggle tasks `answer-ladder-0-calibration`, `answer-ladder-3-reference-patch-10`; inputs `jaejohn/answer-ladder-inputs` |
| Table 1 Gemma 4 31B column, Section 8 hosted steps (all rungs, one try) | `data/training/hosted_gemma31b.txt`; run outputs `analysis/kaggle_harness_integration/hosted_gemma31b_all_rungs/` | Kaggle task `answer-ladder-all-rungs` (notebook `jaejohn/answer-ladder-gemma-4-31b-on-all-five-rungs`); `analysis/training/hosted_gemma31b.py <report.json> data/training/ladder3_stages.csv ladder5_stages.csv ladder8_stages.csv` |
| Section 4, tool use per model (mentioned, ran, applied, solved) | `data/training/tool_use_models.txt` | unpack ladder3/5/8 from `release/answer_ladder/sessions/`, then `analysis/training/tool_use_models.py <runs>` |
| Section 4, model differences per step | `data/training/ladder_models.txt` | `analysis/training/ladder_models.py data/training/ladder3_stages.csv data/training/ladder5_stages.csv data/training/ladder8_stages.csv` |
| Section 8, released sessions and scorer | `release/answer_ladder/` (7,623 sessions) | `e4b_track/rtx/assemble_release.sh`; `python3 -I scripts/score.py --release sessions/` (reproduces Tables 1-2) |
| Paired step intervals | `data/training/ladder_steps.txt`, `ladder3_steps.txt` | `analysis/training/ladder_steps.py <stages> <name> run:bundle:rung ...` |
| Figure 2 | `figures/fig_ladder.png`, `figures/source_data/fig_ladder.csv` | `analysis/make_ladder_figure.py` |
| Same-line-change patches, tool use | `data/training/diff2_apply_v2_failures.txt`, `ladder2_failures_77.txt`, `ladder3_failures.txt`, `apply_tool_use.txt` | `analysis/training/diff1_failures.py`, `apply_tool_use.py` (raw sessions) |
| Section 5 graph hint, offline | `data/graph_hint/offline.txt`, `hints.json`, `nodes_test.jsonl` | `analysis/graph_hint/graph_hint.py <competition data> data/graph_hint_dev_ids.txt data/ladder_ids77.txt data/graph_hint` |
| Table 2 (graph arms) | `data/graph_hint/graph_arms_summary.txt`, `graph_split.txt`, `ladder4_stages.csv` | `e4b_track/rtx/ladder4_prep.py`, `ladder4_test.sh` (seeds 7500+GPU); `analysis/graph_hint/graph_arms_summary.py`, `graph_split.py` |
| Table 2 run 2 (text-only hint, told-to-use tools), pooled hint | `data/graph_hint/ladder6_summary.txt`, `graph_pooled.txt`, `ladder6_stages.csv`; text hint `data/graph_hint_text/` | RTX `ladder6` run; `trajectory_stages.py`; `analysis/graph_hint/ladder6_summary.py <ladder6_stages> <ladder4_stages> data/graph_hint/nodes_test.jsonl data/graph_hint_text/nodes_test.jsonl`, `graph_pooled.py <ladder4_stages> <ladder6_stages> data/graph_hint/nodes_test.jsonl` |
| Table 3 and Section 6 | `data/stage_tables.txt`, `data/retry_pairs.txt`, `data/feedback_audit.txt` | `analysis/stage_tables.py`, `retry_pairs.py`, `feedback_audit.py` |
| Annotation (20 tasks) | `annotation/results.txt`, `REPORT.md` | `annotation/make_records.py`, `mech_locations.py`, `analyse.py`; rules `GUIDE.md` (with corrections); review `review_fable/REVIEW.md` |
| Figure 3 (adapters) | `figures/fig3_solves_per_pass.png` | `analysis/make_figures.py` |
| Section 7 reinforcement, token scores, parity | `data/training/probe_report.txt`, `parity.txt` | `analysis/training/probe_adapters.py`, `parity_*.py` |
| Section 7 imitation | `data/training/transfer_summary.txt`, `tr1_official_summary.txt`, `tr2_held_summary.txt`, `tr2_official_summary.txt` | `analysis/training/tr1_*.py`, `tr2_data.py`, `tr2_run.sh` |
| Section 7 answer-given imitation | `data/training/col1_summary_official.txt`, `col1_diagnosis.txt`, `col1_stages_official.csv` | `e4b_track/rtx/col1_prep.py`, `col1_data.py`, `col1_train.py`, `col1_chain.sh` |
| Section 8 release | `release/answer_ladder/` | `e4b_track/rtx/release_pack.py`, then home paths and archive owners scrubbed |

The first apply-tool run (`e4b_diff_apply_v1`), which crashed when called through the skill channel, is kept in `data/training/diff2_failures_v1arms.txt`; the paper reports the fixed rerun (`e4b_diff_apply_v2`).
