#!/bin/bash
# Runs the key and frame read on every group of features-rigid-groups.txt on the corpus pool records.
set -u
D=work/lm/data-study/features-worker/results/features-rigid-instance-d4-fact-corpus-pool-seed1-ship7
R=work/lm/data-study/features-worker/results/features-corpus-pool-seed1-120s-ship7/level1_search
PY=work/lm/data-study/ast/run/runtime-kaggle-py313/venv/bin/python
while read -r group stems; do
  files=""; for t in $stems; do files="$files $R/$t.nodes.jsonl.zst"; done
  $PY -B $D/features_rigid_fact_key_frame.py $D/fact-rows-key-frame.jsonl $group $files
done < $D/features-rigid-groups.txt
$PY -B $D/features_rigid_fact_key_frame.py $D/fact-rows-key-frame.jsonl held-positive work/lm/data-study/sampler/search-worker/runs/search-pool-gate-steers-out-heldout37-600s-c87cf482a/gate_search/269e22fb.nodes.jsonl.zst work/lm/data-study/sampler/search-worker/runs/search-pool-gate-steers-out-heldout37-600s-c87cf482a/gate_search/142ca369.nodes.jsonl.zst
