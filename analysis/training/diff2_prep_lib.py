"""files_of() from diff2_prep.py, importable."""
import re


def files_of(patch):
    """[(path, new_file, [(old_lines, new_lines), ...])] from a unified diff."""
    res, cur, hunk = [], None, None
    for line in patch.splitlines():
        if line.startswith("--- "):
            cur = None
        elif line.startswith("+++ "):
            path = line[4:].split("\t")[0]
            path = path[2:] if path.startswith("b/") else path
            cur = [path, False, []]
            res.append(cur)
        elif line.startswith("@@") and cur is not None:
            if re.match(r"@@ -0,0 ", line):
                cur[1] = True
            hunk = ([], [])
            cur[2].append(hunk)
        elif cur is not None and hunk is not None and line[:1] in (" ", "-", "+"):
            if line[0] in " -":
                hunk[0].append(line[1:])
            if line[0] in " +":
                hunk[1].append(line[1:])
        elif line.startswith("\\"):
            pass
    return res

