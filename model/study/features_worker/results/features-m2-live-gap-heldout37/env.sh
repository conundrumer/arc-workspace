#!/bin/bash
# env.sh SCRIPT ARGS...   runs SCRIPT (a .py in this folder) in the engine environment of the live M2 kit (sampler-pool-m2-48211b300), through run_heavy.py, one CPU.
R="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KIT=/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/sampler-worker/kits/sampler-pool-m2-48211b300
ENGINE=/Users/davidlu/code/arc-workspace/work/lm/data-study/ast/run/runtime-0a7d32160/py313-path
PY=/Users/davidlu/code/arc-workspace/work/lm/data-study/ast/run/runtime-kaggle-py313/venv/bin/python
export PYTHONPATH="$KIT/model/study/sampler:$ENGINE"
export P_DAG=1 ORDER_FREE=col,tie,key ARCLOG_IDENT_SOURCE=value ONE_REPAIR=30 CHOOSE_LIFT=0 RAYON_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 STEER_DERIVED=m2-export.pkl
unset STEER_COVER KEY_IDENT STEER_REL_GROUPS
SCRIPT="$1"; shift
exec /Users/davidlu/code/arc-workspace/scripts/run_heavy.py --cpus 1 --need soon "$PY" -u "$R/$SCRIPT" "$@"
