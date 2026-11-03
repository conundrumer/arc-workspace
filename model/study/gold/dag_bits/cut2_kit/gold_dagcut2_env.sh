#!/bin/bash
# gold_dagcut2_env.sh ARG...: the pod env (pinned sampler 0099a0c17) with the v2 cut code on the path; runs in this folder.
K=$(cd "$(dirname "$0")" && pwd)
P=$K
D=/Users/davidlu/code/arc-workspace/work/lm/data-study
export ARC_ROOT=/Users/davidlu/code/arc-workspace SAMPLER_CODE=$P/kit-model/study/sampler SEARCH_GOLDS=$D/gold/gold-or-rewrite-heldout7/final SEARCH_MODELS=$D/sampler/sampler-worker/sampler-helper-forms/gold-v3-helper-forms-a036da074/models-base
export ORCUT_SO_SHA256=4538e2630f39d751117a59354494a1d4035d873177c6e9abffe3927a71661371 PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 ARCLOG_THREADS=1 RAYON_NUM_THREADS=1 ORCUT_KEPT_NODES=48
export PYTHONPATH=$D/ast/run/runtime-ba0754492/py313-path:$D/sampler/fit-torch:$K:$P:$SAMPLER_CODE:$D/sampler/sampler-worker/front:$D/sampler/search-worker/poolsearch
cd $K
exec "$D/ast/run/runtime-kaggle-py313/venv/bin/python" "$@"
