#!/bin/bash
# gold_q_ab.sh NAME ENV...: holdout run of sample2_col.py with GOLD_Q=1, up to 40 points per group (not the output group), 55 draws a point; gold's row gets logq_steer.
#   tilt off: gold_q_ab.sh off
#   tilt on:  gold_q_ab.sh tilt TILT=$D/models/tilt_v1.json TILT_STOP=lw
# then: gold_q_report.py runG_off runG_tilt   (run through run_heavy.py --cpus 1)
# The tilt file's fit tasks are left out of both arms, so both draw the same points. Same SEED_TAG in both arms.
C=$(cd "$(dirname "$0")" && pwd)
D=$(python3 "$C/../study_paths.py")/sampler
cd "$D/runs"
n=$1; shift
SCRIPT=${SCRIPT:-sample2_col.py}  # the sampler script to run
H=$(git -C "$C" rev-parse --show-toplevel)/scripts/run_heavy.py
PY=$(dirname "$D")/ast/run/runtime-a8035993/venv/bin/python
rm -rf runG_$n && mkdir -p runG_$n && cp $C/$SCRIPT runG_$n/sample2.snapshot.py
env "$@" GOLD_Q=1 SKIP_TASKS=$D/models/tilt_v1.json.fit_tasks.txt SEED_TAG=v9 COL_FREQ=1 STRUCT_P=1 STRUCT_B=1 STRUCT_C=1 \
  $H --cpus 2 --need soon $PY -u $C/$SCRIPT --split holdout --groups 'DET,RULE depth 1,RULE depth 2,RULE depth 3+,INIT port' --points 40 --per-task 1 --draws 55 --seconds 1000 --jobs 2 --out runG_$n > runG_$n/log.txt 2>&1
