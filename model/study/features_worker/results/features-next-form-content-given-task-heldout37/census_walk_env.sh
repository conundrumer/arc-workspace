#!/bin/bash
# usage: census_walk_env.sh SCRIPT ARG... : runs a script of this folder with the census-bands-cheapest settings: priors sampler-priors-refit-heldout-8a5ffec60, STEER_COVER unset, engine runtime-ba0754492.
HERE=$(cd "$(dirname "$0")" && pwd)
R=/Users/davidlu/code/arc-workspace
D=$R/work/lm/data-study
export ARC_ROOT=$R SAMPLER_CODE=$R/model/study/sampler SEARCH_MODELS=$D/sampler/sampler-worker/sampler-priors-refit-heldout-8a5ffec60 SEARCH_GOLDS=$D/gold/gold-or-rewrite-heldout7/final
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 ARCLOG_THREADS=1 RAYON_NUM_THREADS=1
export PYTHONPATH=$D/ast/run/runtime-ba0754492/py313-path:$D/sampler/fit-torch:$D/sampler/sampler-worker/front:$D/sampler/search-worker/poolsearch
cd "$SAMPLER_CODE" || exit 1
exec "$D/ast/run/runtime-kaggle-py313/venv/bin/python" -u "$HERE/$1" "${@:2}"
