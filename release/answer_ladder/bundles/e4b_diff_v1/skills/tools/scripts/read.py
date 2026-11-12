"""Read part of a file. One argument: the path and, optionally, a line range.

  python3 .git/tools/read.py "rich/table.py 755-910"
  python3 .git/tools/read.py "fastapi/dependencies/utils.py:226-300"

Any spelling of the range works ("226-300", "226 300", "start=226 end=300", "start_line\"=226", "#L226-L300"); one
number reads 100 lines from there; none reads the top 150. A range under 80 lines is widened to 80 (from 20 lines
before it), since every small slice costs a model call. At most 150 lines per call. The lines come back as they
are in the file (no line numbers, so they can be copied into an edit); the header says which lines of how many.
A path that does not exist gets the closest paths; a directory gets its listing.
"""

from __future__ import annotations

import difflib
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import tools_common as tc  # noqa: E402

MAX_LINES = 150
DEFAULT_SPAN = 100
MIN_SPAN, LEAD = 80, 20


def parse(arg: str) -> tuple[str, int | None, int | None]:
    arg = tc.clean(arg)
    arg = re.sub(r"^\s*(file_?path|path|file)\s*[\"']?\s*[:=]\s*", "", arg, flags=re.IGNORECASE)   # filepath=x.py ...
    m = re.match(r"\s*([^\s:#]+?)(?:[:#]|\s|$)(.*)$", arg)
    path, rest = (tc.clean_path(m.group(1)), m.group(2)) if m else (tc.clean_path(arg), "")
    numbers = [int(n) for n in re.findall(r"\d+", rest)]
    start = numbers[0] if numbers else None
    end = numbers[1] if len(numbers) > 1 else None
    return path, start, end


def main() -> None:
    raw = " ".join(sys.argv[1:])
    path, start, end = parse(raw)
    if not path:
        tc.emit('read.py needs a path: python3 .git/tools/read.py "path/to/file.py 120-180"')
        return
    target = tc.REPO / path
    earlier = tc.record("read", f"{path}|{start}|{end}")
    if target.is_dir():
        entries = sorted(p.name + ("/" if p.is_dir() else "") for p in target.iterdir() if p.name not in tc.SKIP_DIRS)
        tc.emit(f"{path}/ is a directory with {len(entries)} entries:\n" + "\n".join(entries[:120]))
        return
    if not target.is_file():
        files = tc.repo_files()
        near = difflib.get_close_matches(path, files, n=5, cutoff=0.5)
        base = Path(path).name
        same_name = [f for f in files if Path(f).name == base and f not in near][:5]
        options = near + same_name
        tc.emit(f"No file '{path}'." + (" Closest paths: " + ", ".join(options) + "." if options else
                                         " Use find.py to locate it."))
        return
    lines = target.read_text(errors="replace").splitlines()
    total = len(lines)
    if start is None:
        first, last = 1, min(total, MAX_LINES)
    else:
        first = max(1, min(start, total))
        last = end if end is not None and end >= first else first + DEFAULT_SPAN - 1
        last = min(last, total, first + MAX_LINES - 1)
        if last - first + 1 < MIN_SPAN:
            first = max(1, min(first - LEAD, total - MIN_SPAN + 1))
            last = min(total, max(last, first + MIN_SPAN - 1))
    head = f"{path} lines {first}-{last} of {total}"
    if end is not None and end > last and last < total:
        head += f" (at most {MAX_LINES} lines per read; continue from {last + 1})"
    body = head + ":\n" + "\n".join(lines[first - 1:last])
    repeat = ""
    if earlier:
        repeat = (f"REPEAT: you read these same lines at call {earlier['n']}, and the file has not changed since. "
                  "They are shown again below. Read a different range, or make your edit.")
    tc.emit(body, repeat)


if __name__ == "__main__":
    main()
