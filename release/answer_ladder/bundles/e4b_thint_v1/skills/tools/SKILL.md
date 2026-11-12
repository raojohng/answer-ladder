---
name: tools
description: Search and read helpers for the repository. install.py copies find.py, read.py, edit.py and check.py into .git/tools so they run through run_command.
---

# tools

- Install (once, by the setup stage): skill_name="tools", args={}, file_path="install.py".
- Search: run_command with python3 .git/tools/find.py "name" (add " in path/" to narrow).
- Read: run_command with python3 .git/tools/read.py "path/to/file.py 120-180".
- Edit: run_command with python3 .git/tools/edit.py and a quoted heredoc of FILE: / SEARCH / REPLACE blocks.
- Tests: edit.py runs the related existing tests after each edit; python3 .git/tools/check.py runs them again.
