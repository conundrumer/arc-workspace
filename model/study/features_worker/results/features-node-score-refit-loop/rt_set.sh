#!/bin/bash
# rt_set.sh SET SCRIPT ARGS: a script on the Mac runtime ba0754492 with the kit and models of SET (n600, hour or base). The engine step of items 5 and 6.
SET=$1; shift
ROOT=/Users/davidlu/code/arc-workspace/work/lm/data-study
case $SET in
  n600) KITN=sampler-pool-dag-nodes-train50-final-8be414670; MODELS=models-final;;
  hour) KITN=sampler-pool-fold-hour-8be414670; MODELS=models-coverf;;
  base) KITN=sampler-pool-extended-text-pass1-8be414670; MODELS=models-base;;
  *) echo "unknown SET $SET" >&2; exit 2;;
esac
KIT=$ROOT/sampler/sampler-worker/kits/$KITN
HERE=$(cd "$(dirname "$0")" && pwd)
cd "$KIT"
exec env PYTHONPATH=$ROOT/ast/run/runtime-ba0754492/py313-path:$KIT/model/study/sampler:$KIT/policy ARC_MODELS=$KIT/$MODELS POLICY_MODEL=$KIT/policy/policy_model.pkl POOL_CLAUSES=search RAYON_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 ARC_SESSION_SHARE=.9 ONE_REPAIR=30 CHOOSE_LIFT=0 \
  $ROOT/ast/run/runtime-kaggle-py313/venv/bin/python -u "$HERE/$1" "${@:2}"
