"""Copy find.py, read.py, edit.py and check.py into <repo>/.git/tools/ so the model can call them through run_command. No arguments.

Inside .git they can never enter the patch. Prints how to call them, then checks both work.
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

MINUTES = 5.5        # the bundle's max_time_minutes, shown in every reply's clock line
SCRIPTS = ("tools_common.py", "find.py", "read.py", "edit.py", "check.py")


def find_repo() -> Path:
    """/workspace in Docker; under the no-Docker sandbox the PYTHONPATH entry that holds the checkout."""
    candidates = ["/workspace"] + [p for p in os.environ.get("PYTHONPATH", "").split(os.pathsep) if p]
    candidates += [os.path.dirname(p) for p in candidates]
    for c in candidates:
        if os.path.isdir(os.path.join(c, ".git")):
            return Path(c)
    return Path(os.getcwd())


repo = find_repo()
target = repo / ".git" / "tools"
target.mkdir(parents=True, exist_ok=True)
here = Path(__file__).resolve().parent
for name in SCRIPTS:
    shutil.copy(here / name, target / name)
(target / "limits.json").write_text(json.dumps({"minutes": MINUTES}))
check = subprocess.run([sys.executable, str(target / "read.py"), "README.md 1-1"], cwd=repo, capture_output=True,
                       text=True, timeout=30)
ok = check.returncode == 0 and ("lines" in check.stdout or "No file" in check.stdout)
print("TOOLS_OK" if ok else "TOOLS_FAILED: " + (check.stderr or check.stdout)[-300:])
print('Search: python3 .git/tools/find.py "name"   (add " in path/" to narrow)')
print('Read:   python3 .git/tools/read.py "path/to/file.py 120-180"')
print("Edit:   python3 .git/tools/edit.py <<'EDIT'  (FILE: path, then <<<<<<< SEARCH / ======= / >>>>>>> REPLACE blocks, then EDIT)")
print("Tests:  edit.py runs the related existing tests after each edit; python3 .git/tools/check.py runs them again")
