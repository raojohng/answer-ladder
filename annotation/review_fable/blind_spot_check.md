# Blind spot check (reviewer: Fable)

Written 2026-11-11, about 22:30 IST, after reading only GUIDE.md and the five records below. Not yet opened: SPOT_CHECK.md, labels_A/, labels_B.json, notes_B.md, REPORT.md, results.*, the key, analyse.py.

Category numbers follow GUIDE.md: 1 no patch; 2 different location; 3 same location, different diagnosis; 4 same location and diagnosis, different implementation; 5 unclear.

| # | Pair (failed vs solved) | My category | Confidence |
|---|---|---|---|
| 1 | w3lib_356 C vs B | 2, different location | clear |
| 2 | platformdirs_573 A vs C | 5, unclear (fallback 3; not 4) | unsure |
| 3 | w3lib_291 C vs A | 4, different implementation | clear |
| 4 | w3lib_307 D vs C | 4, different implementation | fairly clear |
| 5 | humanize_354 C vs A | 1, no patch | clear |

## Reasons

**1. w3lib_356 C vs B: different location.** C's whole patch is in `canonicalize_url` (adds `if path == "": path = "/"`), B's whole patch is in `_safe_url_split` (drops `and query` from the special-scheme condition). No function in common, so the order of the rules stops at category 2.

**2. platformdirs_573 A vs C: unclear, on the literal rule.** Both patches replace the same two `is_homebrew` blocks, so the location is shared. A states a cause in its final message ("incorrect detection ... due to strict string matching", fixed by "generalizing the detection to check for `/opt/`"), which is the opposite direction from the task's cause (the substring is too loose). C's shown thinking is only about the edit tool and its final message is empty; its only statement of intent is a code comment inside the patch ("Detect Homebrew Python path structure: /opt/python* followed by framework structure"). The guide says the diagnosis comes from thinking or text and is never inferred from the patch alone, so C is `unknown` and the pair is category 5. If the code comment is accepted as C explicitly adopting the task's stated fix, the pair becomes category 3 (A: check too strict, widen it; C: match the framework tail), because the two name different causes. I do not see a reading of the guide that gives category 4: A's own words name a cause the task does not.

**3. w3lib_291 C vs A: different implementation.** Both change the module-level `_HEADER_ENCODING_RE` (shared location) and both explicitly adopt the task's stated root cause and its regex (C's final message: "boundary checks and support for quoted strings"), so the diagnosis is the same task-stated one. A additionally changes `http_content_type_encoding` to read `group(1) or group(2)`; C leaves `match.group(1)`, which is `None` for an unquoted charset under the new regex, so the two behave differently on the task's cases. (C's literal tab characters in the raw string are equivalent to `\t` and do not count.)

**4. w3lib_307 D vs C: different implementation.** Both patch `resolve_encoding` and both adopt the task-stated cause (it returns any label Python's codecs knows, so utf-7 is honoured; reject it there). D rejects on the normalised alias before lookup with a fixed list (`utf-7`, `u7`, `unicode-1-1-utf-7`, no `utf7`), after considering and setting aside the task's "keyed on the canonical codec name"; C rejects on `codecs.lookup(...).name == 'utf-7'`. Same faulty behaviour and cause, different mechanism that can differ on the aliases the task lists, so category 4. The gray area: D knowingly departs from the task's stated fix, but the guide defines a diagnosis as faulty behaviour plus cause, not the fix mechanism.

**5. humanize_354 C vs A: no patch.** C's final patch is empty (no applied edit, one tool call), so category 1 applies before any other rule. C's final message nevertheless claims the fix was implemented.
