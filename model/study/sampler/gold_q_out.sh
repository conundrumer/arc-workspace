#!/bin/bash
# gold_q_out.sh NAME ENV...: the output group of the holdout set (the points of runO_out_old), GOLD_Q on, 55 draws a point, into runO_NAME.
# SCRIPT picks the sampler script (default sample2_col.py). The output group has no tilt.
#   ./gold_q_out.sh full STEER_REL=$D/models/relR3_rk2.pkl STEER_CHOICE=$D/models/choice3_ch.pkl
C=$(cd "$(dirname "$0")" && pwd)
D=$(python3 "$C/../study_paths.py")/sampler
cd "$D/runs"
n=$1; shift
SCRIPT=${SCRIPT:-sample2_col.py}
H=$(git -C "$C" rev-parse --show-toplevel)/scripts/run_heavy.py
PY=$(dirname "$D")/ast/run/runtime-kaggle-py313/venv/bin/python
rm -rf runO_$n && mkdir -p runO_$n && cp $C/$SCRIPT runO_$n/sample2.snapshot.py
env "$@" GOLD_Q=1 SEED_TAG=v5 COL_FREQ=1 STRUCT_P=1 STRUCT_B=1 STRUCT_C=1 \
  $H --cpus 3 --need soon $PY -u $C/$SCRIPT --split holdout --groups output --points 40 --per-task 1 --draws 55 --seconds 1000 --jobs 3 --out runO_$n > runO_$n/log.txt 2>&1
