#!/bin/bash
# usage: features_unread_env.sh SCRIPT ARG... : runs a script of this folder with the census's setting of sampler-helper-forms/run.sh, on the worktree's sampler code, which is byte-equal to the main checkout's at the manifest's commit.
R=/Users/davidlu/code/arc-workspace
HERE=$(cd "$(dirname "$0")" && pwd)
W=$R/work/lm/data-study/sampler/sampler-worker
B=$W/sampler-helper-forms/gold-v3-helper-forms-a036da074
export SAMPLER_CODE=${SAMPLER_CODE:-$R/model/study/sampler}
export PYTHONPATH=$R/work/lm/data-study/ast/run/runtime-ba0754492/py313-path
export RAYON_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 STEER_COVER=init,branch
export SAMPLER_CORPUS=$R/work/lm/data-study/gold/gold-v3-helper-forms-a036da074/corpus-view/
export SEARCH_GOLDS=$B/points-base.json SEARCH_MODELS=$B/models-base FORMS=$B/forms-base.json
cd "$SAMPLER_CODE" || exit 1
exec "$R/work/lm/data-study/ast/run/runtime-kaggle-py313/venv/bin/python" -u "$HERE/$1" "${@:2}"
