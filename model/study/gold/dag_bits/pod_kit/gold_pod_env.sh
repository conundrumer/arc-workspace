#!/bin/bash
# usage: gold_pod_env.sh ARG... : runs the Mac runtime python (runtime-ba0754492) in this folder, with the models-base priors and the pinned sampler of this folder (kit-model/study/sampler, master e1434cf72). SAMPLER_CODE and SEARCH_MODELS in the environment replace the defaults.
HERE=$(cd "$(dirname "$0")" && pwd)
D=/Users/davidlu/code/arc-workspace/work/lm/data-study
export ARC_ROOT=/Users/davidlu/code/arc-workspace SAMPLER_CODE=${SAMPLER_CODE:-$HERE/kit-model/study/sampler} SEARCH_GOLDS=$D/gold/gold-or-rewrite-heldout7/final SEARCH_MODELS=${SEARCH_MODELS:-$D/sampler/sampler-worker/sampler-helper-forms/gold-v3-helper-forms-a036da074/models-base}
export ORCUT_SO_SHA256=4538e2630f39d751117a59354494a1d4035d873177c6e9abffe3927a71661371 PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 ARCLOG_THREADS=1 RAYON_NUM_THREADS=1
export PYTHONPATH=$D/ast/run/runtime-ba0754492/py313-path:$D/sampler/fit-torch:$HERE:$SAMPLER_CODE
cd "$HERE" || exit 1
exec "$D/ast/run/runtime-kaggle-py313/venv/bin/python" "$@"
