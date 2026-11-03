#!/bin/bash
# Runs a script of this record in the rank read's python, one thread per process, through run_heavy.py. Usage: features_perrel_env.sh CPUS SCRIPT ARGS...
R=/Users/davidlu/code/arc-workspace
D=/Users/davidlu/code/arc-workspace/work/lm/data-study/features-worker/results/features-relation-pick-per-relation-models-heldout37
W=$R/work/lm/data-study/features-worker/results/features-relation-pick-rank-context-rows-heldout37/walks
PY=$R/work/lm/data-study/ast/run/runtime-kaggle-py313/venv/bin/python
export PYTHONPATH=$R/work/lm/data-study/ast/run/runtime-ba0754492/py313-path
export RAYON_NUM_THREADS=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 STEER_COVER=init,branch SAMPLER_CODE=$R/model/study/sampler PYTHONDONTWRITEBYTECODE=1
CPUS=$1; shift
S=$1; shift
exec "$R/scripts/run_heavy.py" --cpus "$CPUS" --need soon "$PY" -u "$D/$S" "$@"
