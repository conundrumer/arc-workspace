#!/bin/bash
# Prefix rows of a list of points, 3 at a time; a finished point is skipped. run.sh LIST OUT BUDGET
list=${1:?}; out=${2:?}; budget=${3:?}; S=$(dirname "$0"); K=$S/../arm/podkit8x/kit8; R=/Users/davidlu/code/arc-workspace
cd "$K" || exit 1
export PY=$R/work/lm/data-study/ast/run/runtime-kaggle-py313/venv/bin/python PYTHONPATH=$R/work/lm/data-study/sampler/fit-torch FEATS=$S/../arm/podkit7/policy SEARCH_GOLDS=$PWD/points-eval.json SEARCH_MODELS=models-held PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 RAYON_NUM_THREADS=1
xargs -P 3 -L 1 sh -c 'exec "$PY" -u "$0"/features_prefix_rows.py "$1" "$2" "$3" --budget '"$budget"' --out '"$out"' 2>&1 | tail -n 1' "$S"  < "$list"
