#!/bin/bash
# gold_q_d3.sh NAME ENV...: gold_q_ab.sh's holdout GOLD_Q run on RULE depth 3+ only, up to 3 points a task (up to 150 points), 55 draws a point.
# SCRIPT picks the sampler script (default sample2_col.py). Compare two runs with gq_pair.py and gq_parts.py.
C=$(cd "$(dirname "$0")" && pwd)
D=$(python3 "$C/../study_paths.py")/sampler
cd "$D/runs"
n=$1; shift
SCRIPT=${SCRIPT:-sample2_col.py}
H=$(git -C "$C" rev-parse --show-toplevel)/scripts/run_heavy.py
PY=$(dirname "$D")/ast/run/runtime-a8035993/venv/bin/python
rm -rf runD_$n && mkdir -p runD_$n && cp $C/$SCRIPT runD_$n/sample2.snapshot.py
env "$@" GOLD_Q=1 SKIP_TASKS=$D/models/tilt_v1.json.fit_tasks.txt SEED_TAG=v9 COL_FREQ=1 STRUCT_P=1 STRUCT_B=1 STRUCT_C=1 \
  $H --cpus 3 --need soon $PY -u $C/$SCRIPT --split holdout --groups 'RULE depth 3+' --points 150 --per-task 3 --draws 55 --seconds 1000 --jobs 3 --out runD_$n > runD_$n/log.txt 2>&1
