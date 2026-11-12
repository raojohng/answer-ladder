Fix this issue in the repository at `/workspace`: {problem_description}

## Maintainer hints (task context)

{hints?}

## How to work

Four helper scripts are installed. Do everything with run_command and these scripts:
- Search: python3 .git/tools/find.py "<exact symbol or phrase from the issue>"   (add " in <path>" to narrow)
- Read: python3 .git/tools/read.py "<path> <start>-<end>"
- Edit, in exactly this form:
python3 .git/tools/edit.py <<'EDIT'
FILE: <path>
<<<<<<< SEARCH
<the current lines, copied exactly>
=======
<the new lines>
>>>>>>> REPLACE
EDIT
- Tests: edit.py runs the related existing tests after each edit and says what broke; python3 .git/tools/check.py runs them again.

Steps:
1. Find the code the issue is about and read it.
2. Make the smallest source edit that fixes the issue. Never edit tests.
3. Run one short check: an existing test node, or an inline python3 -c assertion that exits nonzero on failure. Check the new behavior and one old behavior that must keep working.
4. When the check passes, call submit_patch. Then reply with one sentence.

Rules:
- Every step is a tool call. Never write a command in your reply text: put it in run_command.
- Do not run grep, rg, sed -i, or full test suites. Do not install anything.
- A failed check means: fix the source and run the same check again.
- Submit as soon as the check passes; more time adds nothing.
