#!/bin/bash
# tw_held_all.sh PASS P: tw_held.py --pass PASS for the 59 held tasks, P at a time. A task runs again while its exit code is 75 (RSS past 3 GiB).
# Run through: bash tw_env.sh P tw_held_all.sh PASS P
: "${TW_PY:?run through tw_env.sh}"
R="$TW_R"
PASS="${1:?usage: tw_held_all.sh PASS P}"
P="${2:?usage: tw_held_all.sh PASS P}"
H=/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/sampler-worker/held
export R PASS
cat "$H/tasks.txt" "$H/ramp-fold.txt" | xargs -P "$P" -I{} bash -c 'set -o pipefail; for try in 1 2 3 4 5 6 7 8; do "$TW_PY" -u "$R/tw_held.py" --task {} --pass "$PASS" 2>&1 | sed -u "s/^/[{}] /"; rc=$?; [ $rc -ne 75 ] && exit $rc; done'
