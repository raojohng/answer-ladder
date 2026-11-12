# Annotation guide: what differs between a failed and a solved try of the same task

Fixed on 2026-11-11 at 21:05 IST, before any try in the sample was read. Changes after that are listed at the end with their reason.

## Question

Among tasks that the untrained agent (E4B, v8 scaffold) solves in some tries and fails in others, when a failed try is compared with a solved try of the same task, do they differ in **where** they change the code, in **why** they change it, or only in **how**?

## Sample

- Population: untrained v8 four-try sweeps (`v8_sweep`, `fresh_v8_p1`); single-file reference patch; no harness crash; at least one solved and one failed try (251 tasks).
- Sample: 20 tasks drawn with `random.seed(20261111)` from that list, all of their tries (`annotation/sample.json`, written by `make_records.py`).
- Second annotator: 8 of the 20 tasks, drawn from the sample with `random.seed(1)`, labelled independently from the same records and this guide, without seeing the first labels.

## Records

One record per try (`annotation/records/<task>.md`), built mechanically:
- the task statement (first 1,500 characters);
- the agent's thinking right before its first applied edit (last 1,500 characters), and its text before any later applied edit (last 600 characters);
- every applied edit: file, enclosing function or class (from the original file's syntax tree), and the changed lines;
- the final patch's changed lines, with their enclosing functions.

Records do **not** show the verdict, the reference patch or any reference overlap. Verdicts are joined only after all labels are written.

## Labels per try

| Field | Values | Rule |
|---|---|---|
| `location` | `file::function` of the final patch's main change (the hunk with most changed lines); several when the patch changes several functions substantively | Mechanical, from the record; the annotator only picks the main one when there are several |
| `diagnosis` | a one-line paraphrase of what the agent says is wrong and why, and a per-task id: `D1`, `D2`, ... | Use the agent's own stated reason (thinking or text). Two tries share an id when they name the same faulty behaviour and the same cause, even in different words. `unknown` when the agent states no cause, or only restates the task. Never infer a diagnosis from the patch alone. |
| `implementation` | a one-line description of the change, and a per-task id within the diagnosis: `D1.I1`, `D1.I2`, ... | Two tries share an implementation when their changes would behave the same on the cases the task describes (formatting, names and comments do not count). |
| `revised` | `none`, `implementation`, `diagnosis`, `location` | Whether the try changed course after its first applied edit, and what changed. |
| `confidence` | `clear`, `unsure` | `unsure` when the label needed a guess. |

## Pair categories (derived, not labelled)

For every pair (failed try, solved try) of the same task, in this order:

1. **No patch**: the failed try submitted nothing.
2. **Different location**: no function in common between the two final patches.
3. **Same location, different diagnosis**: a shared function, different diagnosis ids (neither `unknown`).
4. **Same location and diagnosis, different implementation**: shared function, same diagnosis id, different implementation id.
5. **Unclear**: a diagnosis is `unknown`, or the labels are the same yet the outcomes differ (for example a flaky test).

## Outcomes, fixed in advance

- **Primary:** share of failed–solved pairs in each category, each task weighted equally, with a 95% task bootstrap interval (20 tasks, so wide).
- **Agreement:** on the 8 double-labelled tasks, raw agreement and Cohen's kappa on the pair category, and the share of tries where the two diagnosis groupings agree.
- **Secondary:** share of tries with `unknown` diagnosis; share of tries with any revision, by kind; for failed tries, the last test evidence they saw (from `analysis/feedback_audit.py`).

## Changes after the start

Clarifications found while labelling (21:25 IST). They were not sent to the second annotator, who was already labelling from the text above, so any disagreement they cause is part of the measured agreement.

1. **Task-stated causes.** When the task statement itself names the cause (or the fix) and the try adopts it explicitly, the diagnosis is that stated cause (an id such as `D1`), not `unknown`. `unknown` is kept for tries that state no cause, or only repeat the symptom.
2. **Mechanical location.** The record's "in `function`" for a final-patch hunk is computed from the hunk's first line, which includes up to three lines of context, so it can name the preceding function. Pair categories therefore use a location recomputed from the first changed line of each hunk (`analyse.py`), not the record's label.

## Corrections after the independent review (22:45 IST)

An independent model reviewer (Fable, `review_fable/REVIEW.md`) audited the study. Corrections:

3. **Times.** The times stated above (21:05 and 21:25 IST) are wrong. File times show the sample, records, guide, labels and analysis were all written between 20:47 and 20:55 IST; the guide's last change is at 20:50, so file times cannot show that the guide was fixed before the labels were written. The folder was not under version control at the time.
4. **Who annotated.** Annotator A is the language-model assistant that ran the analysis (Claude), which designed the study and knew its hypothesis; annotator B is a separate language-model agent with its own context. Neither is a person. An author (John) checked 5 random pairs and agreed with all 5 (`SPOT_CHECK_RESULT.md`).
5. **Label edits.** `labels_A/platformdirs_573.json` (try C's implementation note) was rewritten at 20:55, after `analyse.py` existed; the category did not change. `labels_A/w3lib_291.json` try A: `revised` changed from `implementation` to `none` at 22:45 (its second edit was planned before the first), so solved tries that revised are 2 of 36.
6. **Reporting.** Following the review, the diagnosis-versus-implementation split is reported as not separable: clarification 1 (task-stated causes count as diagnoses) was added during labelling and not given to B, and most same-function pairs share the diagnosis the task itself states. The headline merges categories 3 and 4 into "same function, different change"; `analyse.py` also prints agreement on the pairs that need judgement and a line-level location sensitivity.
