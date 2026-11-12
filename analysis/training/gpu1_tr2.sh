#!/bin/bash
# GPU 1: after gpu1_official.sh, the tr2 adapters (4 passes, and after 2) on the 86 official tasks, 3 tries each (runs/tr2_official)
# -> work/tr2/summary_official.txt, then E2B resumes. Log: rtx_test/gpu1_tr2.log, ends GPU1_TR2_DONE.
W=$HOME/workspace/Gemma4/work
cd $W/rtx_test || exit 1
say() { echo "$(date +%H:%M:%S) $*"; }
until grep -q GPU1_OFFICIAL_DONE gpu1_official.log && grep -q "bundles ready" tr2_run.log; do grep -q TR2_STOPPED tr2_run.log 2>/dev/null && { say "tr2 stopped"; exit 1; }; sleep 30; done
sleep 10
bash stop_e2b.sh > /dev/null 2>&1
for i in $(seq 1 40); do [ "$(/usr/lib/wsl/lib/nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits -i 1)" -lt 2000 ] && break; sleep 3; done
LORA_MODULES="tr2_lora=$W/bundles/e4b_tr2_v1/agent/adapters/tr2_lora,tr2_lora_p2=$W/bundles/e4b_tr2p2_v1/agent/adapters/tr2_lora_p2" GPUS="1" \
  bash arm_test.sh tr2_official 3 e4b_tr2_v1 e4b_tr2p2_v1 > tr2_official.log 2>&1
say "official runs: $(ls runs/tr2_official/*/task_results.jsonl | wc -l) sessions"
taskset -c 24-47 nice python3 -I trajectory_stages.py $W/tr2/stages_official_tr2.csv 24 runs/tr2_official=$W/../competition_data/tasks.jsonl > $W/tr2/stages_official.log 2>&1
python3 -I tr1_official_summary.py $W/tr2/stages_official_tr2.csv stages_official.csv > $W/tr2/summary_official.txt 2>&1
cat $W/tr2/summary_official.txt
(setsid nohup bash e2b_run.sh 1 > e2b_run.log 2>&1 < /dev/null &)
say "E2B resumes"; say GPU1_TR2_DONE
