#!/bin/bash
# The shadow tables of a list of forms, 3 at a time; a finished form is skipped. run.sh LIST OUT BUDGET
list=${1:?}; out=${2:?}; budget=${3:?}; P=$(cd "$(dirname "$0")" && pwd); R=/Users/davidlu/code/arc-workspace
cd "$P/../arm/podkit7" || exit 1
export PY=$R/work/lm/data-study/ast/run/runtime-kaggle-py313/venv/bin/python PYTHONPATH=$R/work/lm/data-study/sampler/fit-torch SAMPLER_CODE=$R/model/study/sampler FEATS=$P/extra SEARCH_GOLDS=$PWD/points-eval.json SEARCH_MODELS=models-held PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 RAYON_NUM_THREADS=1
xargs -P 3 -L 1 sh -c 'timeout 120 "$PY" -u "$0"/features_port_shadow.py "$1" "$2" --budget '"$budget"' --out '"$out"' 2>&1 | tail -n 1 | cut -c1-260' "$P" < "$list"
