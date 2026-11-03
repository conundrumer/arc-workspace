#!/bin/bash
# env.sh ARG...: the Mac runtime python (runtime-ba0754492) with the reread kit's pinned sampler (b8e52e249) and priors, the stage code of
# cut2-kit, and this folder first on the path; runs in $RUN_DIR (default trial/) of this folder.
N=$(cd "$(dirname "$0")" && pwd)
K=/Users/davidlu/code/arc-workspace/work/lm/data-study/gold/gold-v3-dag-bits/cut2-kit
D=/Users/davidlu/code/arc-workspace/work/lm/data-study
export ARC_ROOT=/Users/davidlu/code/arc-workspace SAMPLER_CODE=$N/kit/gold-v3-reread-kit/model/study/sampler SEARCH_GOLDS=$D/gold/gold-or-rewrite-heldout7/final SEARCH_MODELS=$N/kit/gold-v3-reread-kit/models
export ORCUT_SO_SHA256=4538e2630f39d751117a59354494a1d4035d873177c6e9abffe3927a71661371 PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 ARCLOG_THREADS=1 RAYON_NUM_THREADS=1 ORCUT_KEPT_NODES=48
export DAG_MARGIN=${DAG_MARGIN:-0}
export PYTHONPATH=$D/ast/run/runtime-ba0754492/py313-path:$D/sampler/fit-torch:$N:$K:$SAMPLER_CODE:$D/sampler/sampler-worker/front:$D/sampler/search-worker/poolsearch
cd "$N/${RUN_DIR:-trial}" || exit 1
exec "$D/ast/run/runtime-kaggle-py313/venv/bin/python" "$@"
