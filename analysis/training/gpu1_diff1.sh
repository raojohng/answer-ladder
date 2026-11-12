#!/bin/bash
# GPU 1 after gpu1_tr2.sh: diff test (third rung) on plain E4B, v8 scaffold, 3 tries per task -> work/diff1/summary.txt; then E2B again.
# Log: rtx_test/gpu1_diff1.log, ends GPU1_DIFF1_DONE or DIFF1_STOPPED.
W=$HOME/workspace/Gemma4/work; D=$W/diff1
cd $W/rtx_test || exit 1
say() { echo "$(date +%H:%M:%S) $*"; }
stop() { say "DIFF1_STOPPED: $1"; exit 1; }
mkdir -p $D; python3 -I diff1_tasks.py $W/../competition_data/tasks.jsonl valid_rtx.json $D > $D/tasks.log 2>&1 || stop "tasks"; say "$(cat $D/tasks.log)"
[ -d ../bundles/e4b_diff_v1 ] || cp -r ../bundles/e4b_edit_fair_v1 ../bundles/e4b_diff_v1
sed -e 's/arm_test_one/diff_test_one/g' \
    -e 's|PORT=$((8000+g)) TMPDIR=$t WHEELS_DIR=$wheels|PORT=$((8000+g)) TMPDIR=$t TASKS_FILE=$HOME/workspace/Gemma4/work/diff1/tasks_$b.jsonl WHEELS_DIR=$wheels|' \
    -e 's|tasks = json.load(open("valid_rtx.json"))\["official"\]|tasks = sorted(open("../diff1/ids_diff.txt").read().split())|' arm_test.sh > diff_test.sh
grep -q "TASKS_FILE=.*diff1/tasks_" diff_test.sh && grep -q "ids_diff.txt" diff_test.sh || stop "diff_test.sh: a line was not replaced"
until grep -q GPU1_TR2_DONE gpu1_tr2.log; do sleep 30; done
say "tr2 official done; stopping E2B on GPU 1"; sleep 20
bash stop_e2b.sh > /dev/null 2>&1
for i in $(seq 1 60); do [ "$(/usr/lib/wsl/lib/nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits -i 1)" -lt 2000 ] && break; sleep 3; done
GPUS="1" bash diff_test.sh diff1 3 e4b_diff_v1 > diff1.log 2>&1
say "diff test: $(ls runs/diff1/*/task_results.jsonl | wc -l) sessions"
taskset -c 24-47 nice python3 -I trajectory_stages.py $D/stages.csv 24 runs/diff1=$W/../competition_data/tasks.jsonl runs/loc1=$W/../competition_data/tasks.jsonl > $D/stages.log 2>&1 || stop "stages"
(setsid nohup bash e2b_run.sh 1 > e2b_run.log 2>&1 < /dev/null &)
say "E2B resumes"; say GPU1_DIFF1_DONE
