#!/bin/bash
# env.sh SCRIPT ARGS...   exports the engine environment and runs SCRIPT (a .py in this folder) through run_heavy.py, one CPU.
# source env.sh           exports the environment only.
R="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KIT=/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/sampler-worker/kits/sampler-pool-tiekey-value-0729e4943
ENGINE=/Users/davidlu/code/arc-workspace/work/lm/data-study/ast/run/runtime-0a7d32160/py313-path
export SL_R="$R" SL_KIT="$KIT" SL_ENGINE="$ENGINE"
export SL_PY=/Users/davidlu/code/arc-workspace/work/lm/data-study/ast/run/runtime-kaggle-py313/venv/bin/python
export PYTHONPATH="$KIT/model/study/sampler:$ENGINE"
export P_DAG=1 ORDER_FREE=tie,key ARCLOG_IDENT_SOURCE=value ONE_REPAIR=30 CHOOSE_LIFT=0 RAYON_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1
unset STEER_COVER KEY_IDENT
if [ "${BASH_SOURCE[0]}" != "$0" ]; then return 0; fi
SCRIPT="$1"
if [ -z "$SCRIPT" ]; then echo "usage: env.sh SCRIPT.py ARGS" >&2; exit 2; fi
shift
exec /Users/davidlu/code/arc-workspace/scripts/run_heavy.py --cpus 1 --need soon "$SL_PY" -u "$R/$SCRIPT" "$@"
