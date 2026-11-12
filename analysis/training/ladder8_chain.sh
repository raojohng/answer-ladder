#!/bin/bash
# GPU 1 after the graph ablation (ladder6): the official-loop ladder with Gemma 4 E2B (ladder8). Log ladder8.log, ends TEST_DONE.
cd ~/workspace/Gemma4/work/rtx_test
until grep -q TEST_DONE ladder6.log; do sleep 30; done
sleep 30
GPUS=1 MODEL_NAME=gemma-4-e2b-it-qat-w4a16-ct ./ladder8_test.sh ladder8 3 e2b_off_ctrl_v1 e2b_off_loc_v1 e2b_off_diff_v1 e2b_off_edits_v1 e2b_off_apply_v1 > ladder8.log 2>&1
