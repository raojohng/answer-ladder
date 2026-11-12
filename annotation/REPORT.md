# What differs between a failed and a solved try of the same task (idea 2, existing traces)

Untrained E4B, v8 scaffold, four-try sweeps. All numbers from `analysis/retry_pairs.py`, `analysis/feedback_audit.py`, and this folder (`analyse.py` -> `results.txt`). Rules in `GUIDE.md`, with two clarifications made during labelling and four corrections after an independent review (`review_fable/REVIEW.md`). Revised 22:50 IST after that review; the earlier version headlined a kappa and a diagnosis/implementation split that the review showed were not supported.

## 1. Location only, all 251 mixed tasks (mechanical)
Failed-solved pairs, task-weighted: both final patches on the reference lines, so the tries differ in the fix, 44% (39-50); failed try has no patch 26% (21-30); different lines 21% (17-26); solved try not on the reference lines 9% (6-13). Solved tries whose first applied edit was elsewhere and that recovered: 10 of 490. This is the better estimate of how often the failed try submits nothing.

## 2. Annotated sample, 20 tasks (seed 20261111), 78 tries, 62 failed-solved pairs
Location is the function of each hunk's first changed line (mechanical). Diagnosis and implementation were labelled without the verdict by annotator A, the language-model assistant that designed the study (Claude); annotator B, a separate language-model agent, labelled 8 tasks. An author spot-checked 5 random pairs and agreed with all 5.

| Failed try vs solved try | Share (95% task bootstrap) |
|---|---|
| Failed try submitted no patch | 38% (20-57) |
| Different location (no function in common) | 17% (5-30) |
| Same function, different change | 45% (27-64) |
| Same labels, different outcome | 0 of 62 pairs |

- **Line-level sensitivity:** counting a failed patch off the reference lines as a different location even inside a shared function: different location 27% (12-45), same function different change 35% (18-54).
- **Diagnosis versus implementation is not separated.** Under the rules as applied, same location different diagnosis is 14% (3-28) and different implementation 31% (14-50), but the two differ by 17 points (-8 to 41), 8 of the 9 different-diagnosis pairs rest on labels marked unsure, and 38 of 67 patched tries take their diagnosis from the task statement itself (clarification 1, not given to B). Under the original rule those would be `unknown`, and nearly all "different implementation" pairs would be unclear.
- **Agreement:** 91% on all 23 double-labelled pairs, but 14 of those are fixed by the shared mechanical location; on the 9 pairs decided by labels, 7 of 9. Kappa (0.87 on all pairs) is not reported as evidence of label reliability.
- In 5 same-function pairs the solved patch also changes a function the failed patch never touches.
- 9 of the 11 failed tries with no patch end with a message claiming or describing a fix that was never applied (checked against all 11 final messages).
- Revisions after the first applied edit: 2 of 36 solved tries, 2 of 42 failed tries; none changed location or diagnosis.
- No pair with identical labels differs in outcome (0 of 62 pairs; 0 of 20 tasks bounds the rate at about 14%).

## 3. Could the failed try have known? (all untrained v8 tries, `feedback_audit.py`)
Failed tries with a patch (2,762): exactly one applied edit 70%; last test evidence before submitting "no existing test broke" 53%, tests broken 23%, no tests ran 24%; ran its own Python or pytest check after editing 9%. Solved tries: 81%, 69/8/22, 11%.

## Reading
Among tasks the agent solves sometimes, the largest group of failed tries changes the same place as a solved try but differently (44% of pairs on 251 tasks; 45% in the annotated sample), and the next largest submits nothing, usually while claiming a fix (26%; 38% in the sample). Where the failed and solved changes share a diagnosis, it is usually the one the task states, so the difference is mostly in how the change is carried out; the sample cannot reliably separate diagnosis from implementation. Tries almost never revise, and most failed tries were told no existing test broke. This complements the location test: placement is a causal gate (+8 solves per pass when given), but among tries that reach the right place the change itself decides, and the agent gets little evidence to correct it.

## Limits
20-task sample (wide intervals); both annotators are language models, and A knew the hypothesis; location is function-level from the first changed line, and two patches share a location when any function overlaps; "no patch" mixes budget exhaustion and false claims; diagnoses come from the last 1,500 characters of thinking before each edit; file times cannot show that the guide preceded the labels (GUIDE.md correction 3).
