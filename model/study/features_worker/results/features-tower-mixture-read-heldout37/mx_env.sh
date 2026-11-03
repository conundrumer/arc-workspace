#!/bin/bash
# mx_env.sh SCRIPT ARGS   runs SCRIPT (a .py in this folder) on the kit's Python through run_heavy.py, one CPU
R="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY=/Users/davidlu/code/arc-workspace/work/lm/data-study/ast/run/runtime-kaggle-py313/venv/bin/python
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 RAYON_NUM_THREADS=1
unset STEER_COVER KEY_IDENT
SCRIPT="$1"
if [ -z "$SCRIPT" ]; then echo "usage: mx_env.sh SCRIPT ARGS" >&2; exit 2; fi
shift
exec /Users/davidlu/code/arc-workspace/scripts/run_heavy.py --cpus 1 --need soon "$PY" -u "$R/$SCRIPT" "$@"
