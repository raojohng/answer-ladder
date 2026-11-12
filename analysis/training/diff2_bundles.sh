#!/bin/bash
# Build the D1 (apply tool) and D2 (edit blocks) bundles from e4b_edit_fair_v1. Needs work/diff2 from diff2_prep.py.
set -e
W=$HOME/workspace/Gemma4/work; B=$W/bundles
rm -rf $B/e4b_diff_apply_v1 $B/e4b_diff_blocks_v1
cp -r $B/e4b_edit_fair_v1 $B/e4b_diff_apply_v1; cp -r $B/e4b_edit_fair_v1 $B/e4b_diff_blocks_v1
S=$B/e4b_diff_apply_v1/agent/skills/tools/scripts
cp $W/rtx_test/apply_fix.py $W/diff2/fixes_data.py $S/
sed -i 's/^SCRIPTS = ("tools_common.py", "find.py", "read.py", "edit.py", "check.py")$/SCRIPTS = ("tools_common.py", "find.py", "read.py", "edit.py", "check.py", "apply_fix.py", "fixes_data.py")/' $S/install.py
grep -q '"apply_fix.py", "fixes_data.py")' $S/install.py
echo BUNDLES_OK
