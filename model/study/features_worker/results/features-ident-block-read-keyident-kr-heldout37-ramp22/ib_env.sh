#!/bin/bash
# ib_env.sh check
# ib_env.sh CPUS SCRIPT ARGS   checks the pins, exports the settings and runs SCRIPT (a .py script or a .sh script) through run_heavy.py
R="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export IB_R="$R"
export IB_PY=/Users/davidlu/code/arc-workspace/work/lm/data-study/ast/run/runtime-kaggle-py313/venv/bin/python
export P_DAG=1 ORDER_FREE=col,tie,key KEY_IDENT=rel ARCLOG_IDENT_SOURCE=value RAYON_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1
unset STEER_COVER
if [ "$1" = check ]; then
    exec "$IB_PY" -u "$R/ib_lib.py" check
fi
CPUS="$1"; SCRIPT="$2"
if [ -z "$CPUS" ] || [ -z "$SCRIPT" ]; then echo "usage: ib_env.sh check | ib_env.sh CPUS SCRIPT ARGS" >&2; exit 2; fi
shift 2
"$IB_PY" -u "$R/ib_lib.py" check >/dev/null || exit 1
case "$SCRIPT" in
    *.py) CMD=("$IB_PY" -u "$R/$SCRIPT" "$@");;
    *.sh) CMD=(bash "$R/$SCRIPT" "$@");;
    *) echo "ib_env.sh: $SCRIPT is neither .py nor .sh" >&2; exit 2;;
esac
exec /Users/davidlu/code/arc-workspace/scripts/run_heavy.py --cpus "$CPUS" --need soon "${CMD[@]}"
