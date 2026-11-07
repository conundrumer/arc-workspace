#!/bin/bash
# usage: gold_union_env.sh ARG... : runs the runtime python (runtime-kaggle-py313) in the revision folder, with the environment of a helper round, and the engine of SITE (default site-exp30) ahead of runtime-ba0754492.
SITE=${SITE:-/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/b9773fdd-d09f-4bd5-b2d0-ebeaa83d8c6d/scratchpad/site-exp30}
D=/Users/davidlu/code/arc-workspace/work/lm/data-study; R=$D/gold/gold-v3-cover-forms-a036da074
cd $R || exit 1
export ARC_ROOT=/Users/davidlu/code/arc-workspace SAMPLER_CODE=${SAMPLER_CODE:-/Users/davidlu/code/arc-workspace/model/study/sampler} SEARCH_GOLDS=$D/gold/gold-or-rewrite-heldout7/final SEARCH_MODELS=$D/sampler/sampler-worker/sampler-priors-refit-heldout-8a5ffec60 PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 ARCLOG_THREADS=1 RAYON_NUM_THREADS=1
export ARCLOG_IDENT_SOURCE=value PYTHONPATH=$SITE:$D/ast/run/runtime-ba0754492/py313-path:$D/sampler/fit-torch:$R:$D/sampler/sampler-worker/front:$D/sampler/search-worker/poolsearch
for m in arclog/__init__.py; do  # a site with no package file lets `import arclog` load another engine with no error
  [ -f "$SITE/$m" ] || { echo "gold_union_env.sh: SITE $SITE has no $m, so import would load another engine; repair the site or set SITE to a whole one" >&2; exit 2; }
done
exec $D/ast/run/runtime-kaggle-py313/venv/bin/python "$@"
