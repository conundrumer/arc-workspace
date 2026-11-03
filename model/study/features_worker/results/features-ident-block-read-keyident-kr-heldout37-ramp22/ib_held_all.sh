#!/bin/bash
# ib_held_all.sh PASS P: ib_held.py --pass PASS for each task, P at a time. Passes 1 and 2: the 37 and the 22. Pass 3: the stems of ib_held.py --list-pass3.
# Run through: bash ib_env.sh P ib_held_all.sh PASS P
: "${IB_PY:?run through ib_env.sh}"
R="$IB_R"
PASS="${1:?usage: ib_held_all.sh PASS P}"
P="${2:?usage: ib_held_all.sh PASS P}"
H=/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/sampler-worker/held
if [ "$PASS" = 3 ]; then
    TASKS=$("$IB_PY" -u "$R/ib_held.py" --list-pass3) || exit 1
else
    TASKS=$(cat "$H/tasks.txt" "$H/ramp-fold.txt")
fi
export R PASS
printf '%s\n' $TASKS | xargs -P "$P" -I{} bash -c 'set -o pipefail; for try in 1 2 3 4 5 6; do "$IB_PY" -u "$R/ib_held.py" --task {} --pass "$PASS" 2>&1 | sed -u "s/^/[{}] /"; rc=$?; [ $rc -ne 75 ] && exit $rc; done'
