#!/bin/bash
# GPU 0 after tr2_run.sh: the halfway tr2 checkpoint (tr2_lora_p2) on the same 60 held-out tasks, 8 tries.
W=$HOME/workspace/Gemma4/work; E=$W/extra_tasks; C=$W/tr2
cd $W/rtx_test || exit 1
say() { echo "$(date +%H:%M:%S) $*"; }
until grep -q TR2_DONE tr2_run.log; do grep -q TR2_STOPPED tr2_run.log && { say "tr2 stopped"; exit 1; }; sleep 30; done
for i in $(seq 1 40); do [ "$(/usr/lib/wsl/lib/nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits -i 0)" -lt 2000 ] && break; sleep 3; done
GPUS="0" SEED_BASE=9995 LORA_MODULES=tr2_lora_p2=$W/bundles/e4b_tr2p2_v1/agent/adapters/tr2_lora_p2 bash ctl_sweep.sh tr2p2_held e4b_tr2p2_v1 8 $C/ids_held.txt > rl_sweep_tr2p2_held.log 2>&1 || { say "p2 runs failed"; exit 1; }
say "p2 held-out runs: $(ls runs/tr2p2_held/*/task_results.jsonl | wc -l) sessions"
T=$E/r1/tasks.jsonl,$E/r2/tasks.jsonl,$E/public/freshswe-py/data/tasks.jsonl
taskset -c 24-47 nice python3 -I trajectory_stages.py $C/stages_p2.csv 24 runs/tr2p2_held=$T runs/v8_sweep=$T runs/fresh_v8_p1=$T runs/rl1_plain=$T > $C/stages_p2.log 2>&1
python3 -I tr1_summary.py $C/stages_p2.csv $C tr2p2_held > $C/summary_p2.txt 2>&1
cat $C/summary_p2.txt
say GPU0_TR2P2_DONE
