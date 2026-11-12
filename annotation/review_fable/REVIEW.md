# Review of the failed-vs-solved annotation study

Reviewer: Fable, 2026-11-11. Blind calls: `blind_spot_check.md`, written before I opened any label or result.

## Verdict

**Publish the mechanical numbers and one merged number; do not publish the kappa or the diagnosis-versus-implementation split as stated.**

- Trustworthy with caveats: no patch 38% (20-57), different location 17% (5-30), and "same function, different change" 45% (27-64), categories 3 and 4 merged.
- Not trustworthy as stated: kappa 0.87, the 14% versus 31% split, the Reading's first sentence.
- `analyse.py`, re-run on a scratch copy, reproduces `results.txt` and `results.json` byte for byte, and REPORT section 2 matches. Sections 1 and 3 use scripts outside `annotation/`; not checked.

## Spot-check comparison

| Pair | Mine (blind) | A | Result |
|---|---|---|---|
| w3lib_356 C vs B | different location | different location | agree |
| platformdirs_573 A vs C | unclear (fallback: different diagnosis) | different diagnosis | gray area; the guide's literal text supports me |
| w3lib_291 C vs A | different implementation | different implementation | agree |
| w3lib_307 D vs C | different implementation | different implementation | agree |
| humanize_354 C vs A | no patch | no patch | agree |

**Pair 2.** A different diagnosis, not a different implementation: try A's final message blames "strict string matching" and widens the check, the opposite of the task's cause (the substring is too loose). The weak point is try C: its shown thinking is about the edit tool, its final message is empty, and its diagnosis comes only from a code comment in the patch. GUIDE.md:30 forbids inferring a diagnosis from the patch alone, so C is strictly `unknown` and the task's three pairs are unclear. A marked it `unsure`: a gray area, not an error.

**Pair 4.** A is right. Try D weighs the task's "keyed on the canonical codec name" and sets it aside for an alias list: a mechanism choice under the same stated cause.

## Findings, most serious first

**1. Kappa 0.87 is inflated by pairs that cannot disagree.** 14 of the 23 double-labelled pairs are "no patch" or "different location", decided from shared mechanical inputs (`analyse.py:17-21`). On the 9 pairs where labels decide, agreement is 7 of 9 and kappa is 0.28. B marked 5 of 24 patched tries `unknown`; A none. Fix: REPORT.md:19 should report 7 of 9 and the 80% diagnosis-grouping figure; kappa is unstable at n=9.

**2. The 14% versus 31% split depends on a rule changed mid-labelling.** Clarification 1 (GUIDE.md:55, "or the fix") reverses the rule fixed at GUIDE.md:30 ("`unknown` when the agent ... only restates the task") and was not given to B.
- 14 of 20 tasks have a diagnosis A marks "as the task states"; 18 of the 19 "different implementation" pairs share a task-supplied diagnosis.
- Reading those as `unknown` moves "different implementation" from 30.8% to 1.7% and "unclear" to 30.8% (an upper bound; B's reading gives 10% unclear on 8 tasks).
- The two categories differ by 17 points (-8 to 41): not separable anyway.
- Fix: headline the merged 45% (27-64); give the split under both readings; say the shared diagnosis is usually the task's own.

**3. The Reading overstates (REPORT.md:28).** It ranks "never produced a patch" first. The sample cannot rank it against a different change at the same place (38% against 45%; difference 7 points, -28 to 42), and the 251-task population ranks them the other way (26% against 44%). On section 1's definition the sample gives 32/38/25/5 against the population's 44/26/21/9. "About one in six" and "one in seven" carry intervals of 5-30 and 3-28. Fix: quote the population figure for no patch; report the split among the 14 tasks whose failed try has a patch: 27% (10-48), 24% (7-45), 49% (26-73).

**4. "Different diagnosis" is fragile.**
- 8 of its 9 pairs rest on a label A marked `unsure`.
- 6 of 9 have the failed try off the reference lines (click_2158, tabulate_139): another spot in one function. With line-level location, different location becomes 27% and different diagnosis 6%.
- Two diagnoses rest only on a code comment (platformdirs_573 C, pydantic_settings_920 D); as `unknown` they give 12.5/25.8/6.7.
- w3lib_359 C gets `D2`; clarification 1 as applied elsewhere gives `D1`, and B gave `unknown`.

**5. "Shared function" hides missed locations.** In w3lib_291 and werkzeug_3218 the solved patch changes a second function the failed patches never touch. Those 5 pairs (10 of the 31 points) count as "different implementation" because one function overlaps (`analyse.py:20`). Fix: flag and report pairs where the failed patch covers only a subset of the solved functions.

**6. Provenance and blinding cannot be verified.**
- The folder is untracked in git. GUIDE.md:3 and :53 say 21:05 and 21:25 IST, but every file's modification time is between 20:47 and 20:55 IST.
- `labels_A/platformdirs_573.json` was rewritten at 20:55:05, after `analyse.py` (20:54:06). SPOT_CHECK.md:54 mentions it; GUIDE.md's change log does not.
- REPORT.md:9 says "hand-labelled" and :31 implies only B is a model. The 20 label files were written in batches within three minutes, so A looks like a model too. John's answers in SPOT_CHECK.md are still blank.
- Fix: commit the folder, correct the times, log the edit, say who A is, complete the spot check.

**7. Smaller code and label issues.**
- `analyse.py:18` with `mech_locations.py:66-67`: a patch touching only non-Python files or paths containing "test" would count as "no patch". All 11 here are empty.
- `analyse.py:102` counts claims by substring in A's free text; against all 11 final messages, 9 is right. Add a boolean field.
- `mech_locations.py:46-47` assigns a pure insertion to the following line (pydantic_settings_920 A's new method is labelled `get_field_value`); no category changes.
- w3lib_291 A is `revised: implementation` though its second edit was planned before the first; solved revisions are 2 of 36.
- REPORT.md:17 renames "Unclear" and prints 0% with no bound; 0 of 20 tasks allows about 14%.

**What held up.** Category order, the bootstrap (stable across seeds), all 26 same-label try pairs sharing a verdict.

**Label sample.** Six tasks drawn with `random.seed(4242)` from the 15 outside the spot check, plus isort_2267, tabulate_139 and every no-patch try. No outright category error; doubtful labels are in findings 4 and 7.

## Caveats the paper should carry

| Threat | Caveat |
|---|---|
| Annotator A | The first annotator designed the study and knew its hypothesis. |
| Annotator B | The second annotator is a model; its agreement does not show a person would agree. |
| Location | Location is the function of each hunk's first changed line, so different spots in one function count as the same place. |
| Multi-hunk | Two patches count as the same place when any function overlaps. |
| Weighting | Tasks are weighted equally; pair weighting agrees within a point. |
| No patch | This category mixes budget exhaustion, silence and false claims of a fix; it says nothing about where or why. |
| Records | Diagnoses come from the last 1,500 characters of thinking before the first edit; earlier reasoning is unseen. |
| Sample | 20 tasks with single-file reference patches, one model, one scaffold. |
