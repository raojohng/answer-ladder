# packaging_1305

## Task statement (first 1,500 characters)

> fix(utils): reject empty project name in parse_wheel_filename/parse_sdist_filename
> 
> ## Pull Request
> 
> fix(utils): reject empty project name in parse_wheel_filename/parse_sdist_filename
> 
> `parse_wheel_filename` and `parse_sdist_filename` silently accept a filename whose distribution name is **empty** and return `("", Version(...))` instead of raising the documented `InvalidWheelFilename` / `InvalidSdistFilename`:
> ``` 
>     >>> from packaging.utils import parse_wheel_filename, parse_sdist_filename
>     >>> parse_wheel_filename("-1.0-py3-none-any.whl")
>     ('', <Version('1.0')>, (), frozenset({<py3-none-any @ ...>}))
>     >>> parse_sdist_filename("-1.0.tar.gz")
>     ('', <Version('1.0')>)
> ```
> 
> An empty name is invalid per the binary/source distribution-format specs, and `canonicalize_name(..., validate=True)` already rejects it — so the parsers are inconsistent with their own `:raises:` contract, and callers using them to validate artifact filenames get a silently-empty name instead of a clear parse error.
> 
> **Fix**
> 
>   * wheel: `_wheel_name_regex` used `*` (zero-or-more), so it matched the empty string and the existing "Invalid project name" branch never fired; change it to `+`.
>   * sdist: add an explicit empty-name guard after the `rpartition`, before `canonicalize_name`.
> 
> Both raise the parser-specific exception (`InvalidWheelFilename` / `InvalidSdistFilename`, both `ValueError` subclasses) so back-compat holds; valid filenames are unaffected. Regression cases added to the existing e


---

## Try A

_No applied edit was detected._

**Final patch** (0 tool calls):
_empty_

**Final message:** I have noted that the tool call budget has been exhausted. The task, which involved modifying `src/packaging/utils.py` to correct regex in `parse_wheel_filename` and adding a validation guard in `parse_sdist_filename`, could not be completed or verified due to the budget limitations.


---

## Try B

**Applied edit 1 (tool call 3).** Thinking before it (last 1500 characters):

>  I will try to use `edit.py` to apply the fix for `parse_wheel_filename` by searching for the regex definition and replacing it. The description of `_wheel_name_regex` is: `# PEP 427: Valid characters for an escaped project name in a wheel filename.` Current definition seems to be: `_wheel_name_regex = re.compile(r"^[\\w._]*$", re.UNICODE)` The fix requires changing `*` to `+`. **Step 1: Fix for `_wheel_name_regex`** Search: `_wheel_name_regex = re.compile(r"^[\\w._]*$", re.UNICODE)` Replace: `_wheel_name_regex = re.compile(r"^[\\w._]+$", re.UNICODE)` I will execute this using `python3 .git/tools/edit.py`. **Step 2: Find `parse_sdist_filename` and apply the guard.** I still need to locate `parse_sdist_filename` and see its body to apply the guard after `rpartition` and before `canonicalize_name`. Since I cannot read the full file, I will rely on the instruction that these fixes are required and assume the `edit.py` tool, when applied generally, can handle context. I will proceed with the first edit and then another one for the second function, if possible. I need to find the definition of `parse_sdist_filename` and the relevant lines within it. I will assume the fix for `_wheel_name_regex` is correct and perform the first edit. Then I will try to find the function definition of `parse_sdist_filename` using `find.py` if possible, or proceed with a high-confidence edit based on common implementation patterns if finding the exact line fails. Let's start with the wheel regex fix.

- `src/packaging/utils.py` near line 66, in `<module level>`
```diff
-_wheel_name_regex = re.compile(r"^[\w._]*$", re.UNICODE)
+_wheel_name_regex = re.compile(r"^[\w._]+$", re.UNICODE)
```
Tool report after this edit: no existing test broke.
**Applied edit 2 (tool call 6).** Thinking before it (last 600 characters):

>  we split on the last dash. name_part, sep, version_part = file_stem.rpartition("-") if not sep: raise InvalidSdistFilename(f"Invalid sdist filename: {filename!r}") name = canonicalize_name(name_part) ``` The replacement should look like this: ```python # so we split on the last dash. name_part, sep, version_part = file_stem.rpartition("-") if not sep: raise InvalidSdistFilename(f"Invalid sdist filename: {filename!r}") if not name_part: raise InvalidSdistFilename(f"Invalid sdist filename (empty project name): {filename!r}") name = canonicalize_name(name_part) ``` I will use the `edit.py` tool.

- `src/packaging/utils.py` near line 303, in `parse_sdist_filename`
```diff
+    if not name_part:
+        raise InvalidSdistFilename(f"Invalid sdist filename (empty project name): {filename!r}")
+
```

**Final patch** (7 tool calls):
- `src/packaging/utils.py` lines 65-71, in `<module level>`
- `src/packaging/utils.py` lines 302-307, in `parse_sdist_filename`
```diff
-_wheel_name_regex = re.compile(r"^[\w._]*$", re.UNICODE)
+_wheel_name_regex = re.compile(r"^[\w._]+$", re.UNICODE)
+    if not name_part:
+        raise InvalidSdistFilename(f"Invalid sdist filename (empty project name): {filename!r}")
+
```

**Final message:** The issue has been fixed by changing the regex in `_wheel_name_regex` from zero-or-more (`*`) to one-or-more (`+`) and adding an explicit guard against empty project names in `parse_sdist_filename`.


---

## Try C

**Applied edit 1 (tool call 2).** Thinking before it (last 1500 characters):

> I have successfully read the beginning of `src/packaging/utils.py`. The fix for `parse_wheel_filename` requires changing the regex used for `_wheel_name_regex`. Current line (around line 26): `# PEP 427: Valid characters for an escaped project name in a wheel filename.` `_wheel_name_regex = re.compile(r"^[\\w._]*$", re.UNICODE)` The goal is to change `*` (zero or more) to `+` (one or more) inside the regex pattern. Original regex string inside `re.compile`: `r"^[\\w._]*$"` New regex string: `r"^[\\w._]+$"` I will proceed to apply Fix 1 for the wheel name regex. **Step 1: Apply Fix 1 (Wheel Regex)** File: `src/packaging/utils.py` Search: `_wheel_name_regex = re.compile(r"^[\\w._]*$", re.UNICODE)` Replace: `_wheel_name_regex = re.compile(r"^[\\w._]+$", re.UNICODE)` I will use `python3 .git/tools/edit.py` to apply this change. **Step 2: Apply Fix 2 (SDist Guard)** I need to find the definition of `parse_sdist_filename`. Since I only read lines 1-100, I will first search for the function definition to get context for the guard insertion. I will use `python3 .git/tools/read.py` again, perhaps spanning more lines, or just search for the function. Since I am using the generic `edit` command, I might be able to locate it by content. Let's start with Fix 1.

- `src/packaging/utils.py` near line 66, in `<module level>`
```diff
-_wheel_name_regex = re.compile(r"^[\w._]*$", re.UNICODE)
+_wheel_name_regex = re.compile(r"^[\w._]+$", re.UNICODE)
```
Tool report after this edit: no existing test broke.
**Applied edit 2 (tool call 5).** Thinking before it (last 600 characters):

> ython if not name_part: raise InvalidSdistFilename(f"Invalid sdist filename (empty project name): {filename!r}") name = canonicalize_name(name_part) ``` I need to capture the lines surrounding the change for the `edit.py` tool. Context: ```python # We are requiring a PEP 440 version, which cannot contain dashes, # so we split on the last dash. name_part, sep, version_part = file_stem.rpartition("-") if not sep: raise InvalidSdistFilename(f"Invalid sdist filename: {filename!r}") name = canonicalize_name(name_part) ``` I will use the `edit` tool to insert the check after the `if not sep:` block.

- `src/packaging/utils.py` near line 303, in `parse_sdist_filename`
```diff
+    if not name_part:
+        raise InvalidSdistFilename(f"Invalid sdist filename (empty project name): {filename!r}")
+
```

**Final patch** (7 tool calls):
- `src/packaging/utils.py` lines 65-71, in `<module level>`
- `src/packaging/utils.py` lines 302-307, in `parse_sdist_filename`
```diff
-_wheel_name_regex = re.compile(r"^[\w._]*$", re.UNICODE)
+_wheel_name_regex = re.compile(r"^[\w._]+$", re.UNICODE)
+    if not name_part:
+        raise InvalidSdistFilename(f"Invalid sdist filename (empty project name): {filename!r}")
+
```

**Final message:** The empty project name handling in `parse_wheel_filename` and `parse_sdist_filename` in `src/packaging/utils.py` has been fixed by changing the regex quantifier in `_wheel_name_regex` from `*` to `+` and adding an explicit empty-name guard to `parse_sdist_filename`.


---

## Try D

**Applied edit 1 (tool call 10).** Thinking before it (last 1500 characters):

> for `parse_sdist_filename` is clear. ```python # We are requiring a PEP 440 version, which cannot contain dashes, # so we split on the last dash. name_part, sep, version_part = file_stem.rpartition("-") if not sep: raise InvalidSdistFilename(f"Invalid sdist filename: {filename!r}") name = canonicalize_name(name_part) try: version = Version(version_part) except InvalidVersion as e: raise InvalidSdistFilename(f"Invalid sdist filename (invalid version): {filename!r}") from e return (name, version) ``` The requirement is: "add an explicit empty-name guard after the `rpartition`, before `canonicalize_name`." If `name_part` is empty, `canonicalize_name(name_part)` will likely return an empty or invalid name, which should be caught before proceeding, or we can check `name_part` directly. If the input is something like `-1.0.tar.gz`, `file_stem` is `-1.0`. `name_part` = `""` (empty string) `sep` = `-` `version_part` = `1.0` If `name_part` is empty, it should fail. I will add a check for `name_part`. **Fix 2: Sdist Empty Name Guard** After: `name_part, sep, version_part = file_stem.rpartition("-")` Before: `name = canonicalize_name(name_part)` Add: `if not name_part: raise InvalidSdistFilename(f"Invalid sdist filename (empty project name): {filename!r}")` I have the plan. I will execute the edits using `edit.py` for both fixes. --- **Step 1: Wheel Fix (Regex Change)** File: `src/packaging/utils.py` Line 68: `_wheel_name_regex = re.compile(r"^[\\w._]*$", re.UNICODE)` Change `*` to `+`.

- `src/packaging/utils.py` near line 66, in `<module level>`
```diff
-_wheel_name_regex = re.compile(r"^[\w._]*$", re.UNICODE)
+_wheel_name_regex = re.compile(r"^[\w._]+$", re.UNICODE)
```
Tool report after this edit: no existing test broke.
**Applied edit 2 (tool call 11).** Thinking before it (last 600 characters):

> dSdistFilename(f"Invalid sdist filename: {filename!r}") name = canonicalize_name(name_part) ``` New segment: ```python # We are requiring a PEP 440 version, which cannot contain dashes, # so we split on the last dash. name_part, sep, version_part = file_stem.rpartition("-") if not sep: raise InvalidSdistFilename(f"Invalid sdist filename: {filename!r}") if not name_part: raise InvalidSdistFilename(f"Invalid sdist filename (empty project name): {filename!r}") name = canonicalize_name(name_part) ``` I need to be careful with the search context for `edit.py`. I'll search for the `rpartition` call.

- `src/packaging/utils.py` near line 303, in `parse_sdist_filename`
```diff
+    if not name_part:
+        raise InvalidSdistFilename(f"Invalid sdist filename (empty project name): {filename!r}")
+
```

**Final patch** (12 tool calls):
- `src/packaging/utils.py` lines 65-71, in `<module level>`
- `src/packaging/utils.py` lines 302-307, in `parse_sdist_filename`
```diff
-_wheel_name_regex = re.compile(r"^[\w._]*$", re.UNICODE)
+_wheel_name_regex = re.compile(r"^[\w._]+$", re.UNICODE)
+    if not name_part:
+        raise InvalidSdistFilename(f"Invalid sdist filename (empty project name): {filename!r}")
+
```

**Final message:** The fix for `parse_wheel_filename` (changing `*` to `+` in `_wheel_name_regex`) and the guard added to `parse_sdist_filename` (explicit check for empty project name) have been implemented and submitted.
