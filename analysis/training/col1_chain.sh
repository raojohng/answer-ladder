#!/bin/bash
# col1 (John, 2026-11-12 03:00 IST): after the ladder replication, (1) collect one try per training/FreshSWE-Py task with the fix given
# as edit commands, both GPUs; (2) build rows with the commands removed; (3) train two adapters at once: full imitation (GPU 0,
# thinking weight 1) and action-only (GPU 1, thinking weight 0), tool calls weight 4, same rows; (4) test both on the 86 official
# tasks, 3 tries each, both GPUs -> work/col1/summary_official.txt. Log: rtx_test/col1_chain.log, ends COL1_DONE or COL1_STOPPED.
W=$HOME/workspace/Gemma4/work; C=$W/col1
cd $W/rtx_test || exit 1
say() { echo "$(date +%H:%M:%S) $*"; }
stop() { say "COL1_STOPPED: $1"; exit 1; }
until grep -q TEST_DONE ladder2.log; do sleep 30; done
say "ladder2 done; collection starts"
for i in $(seq 1 60); do [ "$(/usr/lib/wsl/lib/nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | sort -n | tail -1)" -lt 2000 ] && break; sleep 5; done
sed -e 's/ctl_sweep_one/col1_one/g' \
    -e 's|TASKS_FILE=$D/data/tasks.jsonl|TASKS_FILE=$HOME/workspace/Gemma4/work/col1/tasks_fresh.jsonl|' \
    -e 's|TASKS_FILE=$E/$s/tasks.jsonl|TASKS_FILE=$HOME/workspace/Gemma4/work/col1/tasks_$s.jsonl|' ctl_sweep.sh > col1_sweep.sh
[ "$(grep -c 'col1/tasks_' col1_sweep.sh)" = 2 ] || stop "col1_sweep.sh lines not replaced"
GPUS="0 1" SEED_BASE=9300 bash col1_sweep.sh col1 e4b_diff_blocks_v1 1 $C/ids.txt > col1_sweep.log 2>&1
grep -q SWEEP_DONE col1_sweep.log || stop "collection, see col1_sweep.log"
say "collection: $(ls runs/col1/*/task_results.jsonl | wc -l) sessions, $(grep -l '"resolved": "True"\|"resolved": true' runs/col1/*/task_results.jsonl | wc -l) solved"
for i in $(seq 1 60); do [ "$(/usr/lib/wsl/lib/nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | sort -n | tail -1)" -lt 2000 ] && break; sleep 5; done
pid=$(SERVER_SEED=9400 ../../.venv_harness/bin/python start_server.py 0 8000 vllm_col1_data.log 2>&1 | awk '/^pid/{print $2}')
for i in $(seq 1 90); do curl -s -m 5 http://127.0.0.1:8000/v1/models | grep -q gemma-4 && break; sleep 10; done
taskset -c 0-23 nice ../../.venv/bin/python -u col1_data.py 8000 > $C/data.log 2>&1; kill -9 -- -$pid 2>/dev/null
grep -q COL1_DATA_DONE $C/data.log || stop "data, see $C/data.log"
say "$(tail -n 3 $C/data.log | head -n 2 | tr '\n' ' ')"
for i in $(seq 1 60); do [ "$(/usr/lib/wsl/lib/nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits -i 0)" -lt 2000 ] && break; sleep 5; done
mkdir -p $C/trained
for spec in "0 1.0 col1t_lora" "1 0.0 col1a_lora"; do
  set -- $spec
  (TR_W_THINK=$2 TR_PASSES=3 TR_EXPORTS= TR_HOURS=0.75 CUDA_VISIBLE_DEVICES=$1 R2_MODEL=$W/../models/gemma-4-e4b-it-qat-w4a16-ct \
    ../../.venv/bin/python -u col1_train.py $W/v8con/train_v8con.py $C $C/trained/$3 > $C/train_$3.log 2>&1) &
done
wait
grep -q TR1_TRAINED $C/train_col1t_lora.log && grep -q TR1_TRAINED $C/train_col1a_lora.log || stop "training, see $C/train_*.log"
say "trained: full $(grep '^pass' $C/train_col1t_lora.log | tail -1 | cut -c1-90) | action-only $(grep '^pass' $C/train_col1a_lora.log | tail -1 | cut -c1-90)"
for a in col1t_lora col1a_lora; do
  B=$W/bundles/e4b_${a%_lora}_v1
  rm -rf $B && cp -r $W/bundles/e4b_rl1r1_v1 $B && rm -rf $B/agent/adapters && mkdir -p $B/agent/adapters && cp -r $C/trained/$a $B/agent/adapters/ || stop "bundle"
  sed -i "s/^adapter: rl1r1_lora$/adapter: $a/" $B/agent/sub_agents/swe_agent.yaml
  grep -q "^adapter: $a$" $B/agent/sub_agents/swe_agent.yaml || stop "bundle $B"
done
for i in $(seq 1 60); do [ "$(/usr/lib/wsl/lib/nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | sort -n | tail -1)" -lt 2000 ] && break; sleep 5; done
LORA_MODULES="col1t_lora=$W/bundles/e4b_col1t_v1/agent/adapters/col1t_lora,col1a_lora=$W/bundles/e4b_col1a_v1/agent/adapters/col1a_lora" GPUS="0 1" \
  bash arm_test.sh col1_official 3 e4b_col1t_v1 e4b_col1a_v1 > col1_official.log 2>&1
say "official runs: $(ls runs/col1_official/*/task_results.jsonl | wc -l) sessions"
taskset -c 24-47 nice python3 -I trajectory_stages.py $C/stages_official.csv 24 runs/col1_official=$W/../competition_data/tasks.jsonl > $C/stages_official.log 2>&1
python3 -I tr1_official_summary.py $C/stages_official.csv stages_official.csv > $C/summary_official.txt 2>&1
cat $C/summary_official.txt
say COL1_DONE
