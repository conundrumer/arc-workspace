#!/bin/bash
# rt600.sh SCRIPT ARGS: a script on the Mac runtime ba0754492 with the N600 kit's code and models-final (the engine step of items 5 and 6 on N600).
ROOT=/Users/davidlu/code/arc-workspace/work/lm/data-study
KIT=$ROOT/sampler/sampler-worker/kits/sampler-pool-dag-nodes-train50-final-8be414670
cd "$KIT"
exec env PYTHONPATH=$ROOT/ast/run/runtime-ba0754492/py313-path:$KIT/model/study/sampler:$KIT/policy ARC_MODELS=$KIT/models-final POLICY_MODEL=$KIT/policy/policy_model.pkl POOL_CLAUSES=search RAYON_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 ARC_SESSION_SHARE=.9 ONE_REPAIR=30 CHOOSE_LIFT=0 \
  $ROOT/ast/run/runtime-kaggle-py313/venv/bin/python -u "$@"
