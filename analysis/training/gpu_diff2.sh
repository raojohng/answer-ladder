#!/bin/bash
# Diff test, follow-up arm on one GPU (decision rule agreed with John 23:35 IST: run D1 and D2 if diff1 solves under 90% of tries).
# Usage: gpu_diff2.sh <gpu> <bundle> <ids file> <wait-for-marker-file> <marker>
# Log: rtx_test/gpu<g>_<bundle>.log, ends DIFF2_ARM_DONE.
G=$1; BUNDLE=$2; IDS=$3; WAITF=$4; MARK=$5
W=$HOME/workspace/Gemma4/work; D=$W/diff2
cd $W/rtx_test || exit 1
say() { echo "$(date +%H:%M:%S) $*"; }
until grep -q "$MARK" "$WAITF" 2>/dev/null; do sleep 20; done
say "$MARK seen; freeing GPU $G"
sleep 15
if [ "$G" = 1 ]; then bash stop_e2b.sh > /dev/null 2>&1; fi
for i in $(seq 1 60); do [ "$(/usr/lib/wsl/lib/nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits -i $G)" -lt 2000 ] && break; sleep 3; done
S=diff2_test_$BUNDLE.sh
sed -e "s/arm_test_one/d2one_$BUNDLE/g" \
    -e 's|PORT=$((8000+g)) TMPDIR=$t WHEELS_DIR=$wheels|PORT=$((8000+g)) TMPDIR=$t TASKS_FILE=$HOME/workspace/Gemma4/work/diff2/tasks_$b.jsonl WHEELS_DIR=$wheels|' \
    -e "s|tasks = json.load(open(\"valid_rtx.json\"))\[\"official\"\]|tasks = sorted(open(\"$IDS\").read().split())|" arm_test.sh > $S
grep -q "TASKS_FILE=.*diff2/tasks_" $S && grep -q "$IDS" $S || { say "DIFF2_STOPPED: $S lines not replaced"; exit 1; }
GPUS="$G" bash $S d2_$BUNDLE 3 $BUNDLE > diff2_$BUNDLE.log 2>&1
say "$BUNDLE: $(ls runs/d2_$BUNDLE/*/task_results.jsonl | wc -l) sessions"
say DIFF2_ARM_DONE
