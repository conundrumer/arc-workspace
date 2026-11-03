#!/bin/bash
# rt_r1.sh SCRIPT ARGS: a script on the Mac engine build of round 1 (macsite, wheel commit e8c1b7882) with round 1's kit code and the bundle's settings.
REC=$(cd "$(dirname "$0")/.." && pwd)
KIT=$REC/kit/search-refit-r1-kit-0729e4943
HERE=$REC/scripts
cd "$KIT"
exec env PYTHONPATH=$REC/macsite:$KIT/model/study/sampler:$KIT/policy ARC_MODELS=$KIT/models-tk POLICY_MODEL=$KIT/policy/policy_model.pkl POOL_CLAUSES=search RAYON_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 \
  ARCLOG_IDENT_SOURCE=value P_DAG=1 ORDER_FREE=tie,key ARC_SESSION_SHARE=.9 ONE_REPAIR=30 CHOOSE_LIFT=0 \
  /Users/davidlu/code/arc-workspace/work/lm/data-study/ast/run/runtime-kaggle-py313/venv/bin/python -u "$HERE/$1" "${@:2}"
