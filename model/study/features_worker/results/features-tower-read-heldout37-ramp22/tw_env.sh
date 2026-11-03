#!/bin/bash
# tw_env.sh check
# tw_env.sh CPUS SCRIPT ARGS   checks the pins, exports the settings and runs SCRIPT (a .py or a .sh script in this folder) through run_heavy.py
R="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export TW_R="$R"
export TW_PY=/Users/davidlu/code/arc-workspace/work/lm/data-study/ast/run/runtime-kaggle-py313/venv/bin/python
export P_DAG=1 ORDER_FREE=col,tie,key ARCLOG_IDENT_SOURCE=value RAYON_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1
unset STEER_COVER KEY_IDENT
if [ "$1" = check ]; then
    exec "$TW_PY" -u "$R/tw_lib.py" check
fi
CPUS="$1"; SCRIPT="$2"
if [ -z "$CPUS" ] || [ -z "$SCRIPT" ]; then echo "usage: tw_env.sh check | tw_env.sh CPUS SCRIPT ARGS" >&2; exit 2; fi
shift 2
"$TW_PY" -u "$R/tw_lib.py" check >/dev/null || exit 1
case "$SCRIPT" in
    *.py) CMD=("$TW_PY" -u "$R/$SCRIPT" "$@");;
    *.sh) CMD=(bash "$R/$SCRIPT" "$@");;
    *) echo "tw_env.sh: $SCRIPT is neither .py nor .sh" >&2; exit 2;;
esac
exec /Users/davidlu/code/arc-workspace/scripts/run_heavy.py --cpus "$CPUS" --need soon "${CMD[@]}"
