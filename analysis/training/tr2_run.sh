#!/bin/bash
# tr2 on GPU 0 (John, 2026-11-11 20:40 IST): stop dp1 (its first pass is kept if exported), train tr1's recipe on every task
# with a solved plain try (tr2_data.py, built beforehand against GPU 1's plain server), 4 passes (adapter after pass 2 kept),
# then 8 free tries on tr1's 60 held-out tasks (runs/tr2_held) -> work/tr2/summary.txt.
# Log: rtx_test/tr2_run.log, ends TR2_DONE or TR2_STOPPED.
W=$HOME/workspace/Gemma4/work
E=$W/extra_tasks
C=$W/tr2
A=$C/trained/tr2_lora
cd $W/rtx_test || exit 1
stop() { echo "$(date +%H:%M:%S) TR2_STOPPED: $1"; exit 1; }
grep -q TR2_DATA_DONE $C/data.log || stop "no data"
bash stop_gpu0.sh dp1_run.sh > $C/stop_dp1.log 2>&1
echo "$(date +%H:%M:%S) dp1 stopped; its exports: $(ls $W/dp1/trained 2>/dev/null | tr '\n' ' ')"
for i in $(seq 1 40); do [ "$(/usr/lib/wsl/lib/nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits -i 0)" -lt 2000 ] && break; sleep 3; done
mkdir -p $C/trained
TR_PASSES=4 TR_EXPORTS=2 TR_HOURS=2.5 CUDA_VISIBLE_DEVICES=0 R2_MODEL=$W/../models/gemma-4-e4b-it-qat-w4a16-ct \
  ../../.venv/bin/python -u dp1_train.py $W/v8con/train_v8con.py $C $A > $C/train.log 2>&1 || stop "training, see $C/train.log"
grep -q TR1_TRAINED $C/train.log || stop "training did not finish"
echo "$(date +%H:%M:%S) trained: $(grep '^pass' $C/train.log | tail -1)"
for v in "" _p2; do
  B=$W/bundles/e4b_tr2${v#_}_v1; [ -z "$v" ] && B=$W/bundles/e4b_tr2_v1
  rm -rf $B && cp -r $W/bundles/e4b_rl1r1_v1 $B && rm -rf $B/agent/adapters && mkdir -p $B/agent/adapters && cp -r $A$v $B/agent/adapters/ || stop "bundle"
  sed -i "s/^adapter: rl1r1_lora$/adapter: tr2_lora$v/" $B/agent/sub_agents/swe_agent.yaml
  [ "$(diff $W/bundles/e4b_edit_fair_v1/agent/sub_agents/swe_agent.yaml $B/agent/sub_agents/swe_agent.yaml | grep -c '^[<>]')" -eq 1 ] && grep -q "^adapter: tr2_lora$v$" $B/agent/sub_agents/swe_agent.yaml || stop "bundle $B"
done
echo "$(date +%H:%M:%S) bundles ready: e4b_tr2_v1 e4b_tr2p2_v1"
for i in $(seq 1 40); do [ "$(/usr/lib/wsl/lib/nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits -i 0)" -lt 2000 ] && break; sleep 3; done
sed 's/rl_sweep_one/ctl_sweep_one/g' rl_sweep.sh > ctl_sweep.sh
GPUS="0" SEED_BASE=9995 LORA_MODULES=tr2_lora=$W/bundles/e4b_tr2_v1/agent/adapters/tr2_lora bash ctl_sweep.sh tr2_held e4b_tr2_v1 8 $C/ids_held.txt > rl_sweep_tr2_held.log 2>&1 || stop "free runs"
echo "$(date +%H:%M:%S) held-out free runs: $(ls runs/tr2_held/*/task_results.jsonl | wc -l) sessions"
T=$E/r1/tasks.jsonl,$E/r2/tasks.jsonl,$E/public/freshswe-py/data/tasks.jsonl
taskset -c 24-47 nice python3 -I trajectory_stages.py $C/stages.csv 24 runs/tr2_held=$T runs/v8_sweep=$T runs/fresh_v8_p1=$T runs/rl1_plain=$T > $C/stages.log 2>&1 || stop "stages"
python3 -I tr1_summary.py $C/stages.csv $C tr2_held > $C/summary.txt 2>&1 || stop "summary"
cat $C/summary.txt
echo "$(date +%H:%M:%S) TR2_DONE"
