#!/bin/bash
# Build the Answer Ladder release (paper Section 8) after all runs are done. Run from the repository root on John's machine.
#  1. On the RTX: stage labels for the runs that lack them, then release_pack.py (sessions with tool_calls.jsonl, scrubbed).
#  2. Copy the package here (paper_track/release/answer_ladder), keeping README.md and dataset-metadata.json.
#  3. Add the stage files, graph hints and scripts, then scan for personal paths and names.
set -e
R=user@gpu-host; WK='~/workspace/Gemma4/work'
OUT=paper_track/release/answer_ladder
ssh $R "cd $WK/rtx_test && for run in ladder5 ladder6 ladder8; do
  [ -d runs/\$run ] || continue
  [ -f ../\$run/stages.csv ] && [ ../\$run/stages.csv -nt ../\$run/tasks_\$(ls ../\$run | grep -m1 -o 'e[0-9a-z_]*_v1').jsonl ] || true
  taskset -c 24-47 nice python3 -I trajectory_stages.py ../\$run/stages.csv 24 runs/\$run=\$(ls ../\$run/tasks_*.jsonl | paste -sd,) | tail -1
done && taskset -c 24-47 nice python3 -I release_pack.py | tail -12"
mkdir -p paper_track/release/keep && cp $OUT/README.md $OUT/dataset-metadata.json paper_track/release/keep/
rm -rf $OUT && mkdir -p paper_track/release
ssh $R "cd $WK/release && tar cf - answer_ladder" | tar xf - -C paper_track/release
cp paper_track/release/keep/* $OUT/
mkdir -p $OUT/stages $OUT/graph_hint $OUT/scripts
cp paper_track/data/training/ladder_stages.csv $OUT/stages/first_run_stages.csv
cp paper_track/data/training/ladder2_stages.csv $OUT/stages/replication_stages.csv
cp paper_track/data/training/ladder3_stages.csv $OUT/stages/official_loop_stages.csv
cp paper_track/data/graph_hint/ladder4_stages.csv $OUT/stages/graph_arms_stages.csv
for run in ladder5 ladder6 ladder8; do scp -q $R:$WK/$run/stages.csv $OUT/stages/${run}_stages.csv 2>/dev/null || true; done
mv -f $OUT/stages/ladder5_stages.csv $OUT/stages/official_loop_qwen_stages.csv 2>/dev/null || true
mv -f $OUT/stages/ladder8_stages.csv $OUT/stages/official_loop_e2b_stages.csv 2>/dev/null || true
mv -f $OUT/stages/ladder6_stages.csv $OUT/stages/graph_arms_2_stages.csv 2>/dev/null || true
cp paper_track/data/graph_hint/{hints.json,nodes_test.jsonl,offline.txt} $OUT/graph_hint/
cp paper_track/data/graph_hint_text/hints.json $OUT/graph_hint/text_only_hints.json
cp paper_track/data/ladder_ids77.txt $OUT/graph_hint/test_ids.txt
cp paper_track/data/graph_hint_dev_ids.txt $OUT/graph_hint/dev_ids.txt
cp e4b_track/rtx/score.py paper_track/analysis/graph_hint/{graph_hint.py,graph_arms_summary.py,graph_split.py,gate.py,ladder6_summary.py,graph_pooled.py} \
   paper_track/analysis/training/{ladder_steps.py,ladder_models.py,tool_use_models.py,apply_tool_use.py,diff1_failures.py,diff1_tasks.py,diff2_prep.py,loc1_tasks.py} \
   paper_track/analysis/trajectory_stages.py e4b_track/train/placement_census.py \
   e4b_track/rtx/{ladder3_prep.py,ladder4_prep.py,ladder56_prep.py,ladder8_prep.py,release_pack.py} $OUT/scripts/
find $OUT -name __pycache__ -prune -exec rm -rf {} +
echo "personal strings: $(grep -rIl -i 'user\|user\|user\|/home/' $OUT | grep -v '^$' | wc -l) text files"
for f in $OUT/sessions/*.tar.gz; do n=$(zcat $f | grep -a -c -i 'user\|user\|user' || true); [ "$n" = 0 ] || echo "  $f: $n"; done
du -sh $OUT; echo ASSEMBLE_DONE
