#!/bin/bash
# Test bundles side by side on the official tasks that pass the gold check. Each GPU serves the plain model (plus LORA_MODULES if set).
# Every bundle gets <tries> tries per task; jobs alternate GPUs so each arm runs on both. Restart skips finished sessions.
# Usage: arm_test.sh <run> <tries> <bundle> [bundle ...]. Env: LIMIT=n runs only the first n tasks (smoke);
# GPUS="1" uses only those GPUs (default "0 1"); LORA_MODULES=name=folder serves an adapter a bundle names (default none);
# SESSION_TIMEOUT=s kills a session's runner after s seconds (default 900; keep it above the bundle's max_time_minutes plus grading).
# Log: <run>.log, ends TEST_DONE. Sessions: runs/<run>/<bundle>_<task>_t<k>.
export RUN=$1 TRIES=$2; shift 2
export GPUS=${GPUS:-0 1} SESSION_TIMEOUT=${SESSION_TIMEOUT:-900}
W=$HOME/workspace/Gemma4/work
cd $W/rtx_test || exit 1
PY=../../.venv_harness/bin/python
mkdir -p runs/$RUN/logs
for b in "$@"; do [ -f ../bundles/$b/agent/agent.yaml ] || { echo "missing bundle $b"; exit 1; }; done
BUNDLES="$*" python3 > runs/$RUN/jobs.txt <<'PY'
import json, os, random
bundles = os.environ["BUNDLES"].split(); tries = int(os.environ["TRIES"])
tasks = sorted(open("../ladder5/ids.txt").read().split()); random.seed(20261112); random.shuffle(tasks)
if os.environ.get("LIMIT"): tasks = tasks[:int(os.environ["LIMIT"])]
for i, t in enumerate(tasks):
    for k in range(1, tries + 1):
        for j, b in enumerate(bundles):
            gpus = os.environ["GPUS"].split(); print(b, t, k, gpus[(i + k + j) % len(gpus)])
PY
export GPU_MEMORY=0.90
export LORA_MODULES=${LORA_MODULES:-}
pids=()
# Start the servers 60 s apart: started together, torch's rendezvous port can clash (EADDRINUSE) and one server never comes up.
first=1
for g in $GPUS; do
  [ $first = 1 ] || sleep 60; first=0
  pid=$(SERVER_SEED=$((7700+g)) $PY start_server.py $g $((8000+g)) vllm_${RUN}_gpu$g.log 2>&1 | awk '/^pid/{print $2}'); pids+=($pid)
done
for g in $GPUS; do
  up=0
  for i in $(seq 1 90); do
    curl -s -m 5 http://127.0.0.1:$((8000+g))/v1/models | grep -q "${MODEL_NAME:-gemma-4}" && { echo "$(date +%H:%M:%S) GPU $g up"; up=1; break; }
    sleep 10
  done
  # A dead server would turn every session on that GPU into a connection error: stop instead.
  [ $up = 1 ] || { echo "GPU $g server not up, see vllm_${RUN}_gpu$g.log; stopping"; for p in "${pids[@]}"; do kill -- -$p 2>/dev/null; done; echo TEST_DONE; exit 1; }
done
cat > ladder5_one.sh <<'S'
#!/bin/bash
b=$1; id=$2; k=$3; g=$4
W=$HOME/workspace/Gemma4/work
out=runs/$RUN/${b}_${id}_t$k
[ -f "$out/task_results.jsonl" ] && exit 0
rm -rf "$out"
t=$W/extra_tasks/tmp_$RUN/${b}_${id}_$k; mkdir -p "$t"
case $id in rich*) wheels=$W/wheels_rich;; *) wheels=$W/wheels_fastapi;; esac
case $b in *_off_apply_*) wheels=${wheels}_fix;; esac   # the apply arm alone carries the apply_fix wheel
PORT=$((8000+g)) TMPDIR=$t TASKS_FILE=$HOME/workspace/Gemma4/work/ladder5/tasks_$b.jsonl WHEELS_DIR=$wheels timeout $SESSION_TIMEOUT ../../.venv_harness/bin/python run_tasks.py ../bundles/$b/agent "$out" "$id" > "runs/$RUN/logs/${b}_${id}_t$k.log" 2>&1
rm -rf "$t"
echo "$(date +%H:%M:%S) $b $id t$k $(tail -1 runs/$RUN/logs/${b}_${id}_t$k.log | cut -c1-70)"
S
chmod +x ladder5_one.sh
for g in $GPUS; do
  awk -v g=$g '$4==g' runs/$RUN/jobs.txt | xargs -P 20 -L 1 ./ladder5_one.sh &
done
wait
for p in "${pids[@]}"; do kill -- -$p 2>/dev/null; done
echo TEST_DONE
