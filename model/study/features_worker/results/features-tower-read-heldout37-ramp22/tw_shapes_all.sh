#!/bin/bash
# tw_shapes_all.sh P: tw_shapes.py for the 59 held tasks, P at a time.
# Run through: bash tw_env.sh P tw_shapes_all.sh P
: "${TW_PY:?run through tw_env.sh}"
R="$TW_R"
P="${1:?usage: tw_shapes_all.sh P}"
H=/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/sampler-worker/held
export R
cat "$H/tasks.txt" "$H/ramp-fold.txt" | xargs -P "$P" -I{} bash -c 'set -o pipefail; "$TW_PY" -u "$R/tw_shapes.py" --task {} 2>&1 | sed -u "s/^/[{}] /"'
