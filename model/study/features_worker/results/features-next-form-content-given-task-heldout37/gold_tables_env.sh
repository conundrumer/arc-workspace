#!/bin/bash
# usage: gold_tables_env.sh SCRIPT ARG... : runs the runtime python of engine runtime-ba0754492, with the sampler code of the main checkout.
D=/Users/davidlu/code/arc-workspace/work/lm/data-study
export ARC_ROOT=/Users/davidlu/code/arc-workspace SAMPLER_CODE=/Users/davidlu/code/arc-workspace/model/study/sampler SEARCH_MODELS=$D/sampler/sampler-worker/sampler-priors-refit-heldout-8a5ffec60 PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 ARCLOG_THREADS=1 RAYON_NUM_THREADS=1
export PYTHONPATH=$D/ast/run/runtime-ba0754492/py313-path:/Users/davidlu/code/arc-workspace/model/study/sampler:$D/sampler/sampler-worker/front:$D/sampler/search-worker/poolsearch
exec $D/ast/run/runtime-kaggle-py313/venv/bin/python -u "$@"
