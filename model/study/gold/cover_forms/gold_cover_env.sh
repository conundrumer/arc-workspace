#!/bin/bash
# usage: gold_cover_env.sh ARG... : runs the runtime python (runtime-ba0754492) in the revision folder, with the environment of a helper round.
D=/Users/davidlu/code/arc-workspace/work/lm/data-study; R=$D/gold/gold-v3-cover-forms-a036da074
cd $R || exit 1
export ARC_ROOT=/Users/davidlu/code/arc-workspace SAMPLER_CODE=${SAMPLER_CODE:-/Users/davidlu/code/arc-workspace/model/study/sampler} SEARCH_GOLDS=$D/gold/gold-or-rewrite-heldout7/final SEARCH_MODELS=$D/sampler/sampler-worker/sampler-priors-refit-heldout-8a5ffec60 PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 ARCLOG_THREADS=1 RAYON_NUM_THREADS=1
export PYTHONPATH=$D/ast/run/runtime-ba0754492/py313-path:$D/sampler/fit-torch:$R:$D/sampler/sampler-worker/front:$D/sampler/search-worker/poolsearch
exec $D/ast/run/runtime-kaggle-py313/venv/bin/python "$@"
