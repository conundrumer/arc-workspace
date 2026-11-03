#!/bin/bash
# The row stores of one split on a writer kit release: the union records (build_merged.py, from GOLD_UNION_DIR) and then the row store of each task (rows_replay.py).
# Both stages stream and skip finished tasks.
#   KIT=<writer kit release folder> GOLD_UNION_DIR=<union folder> [JOBS=4] model/study/samples/run/stores.sh SPLIT
set -eo pipefail
SPLIT=${1:?split}
W=$(ls -d "${KIT:?KIT names a writer kit release}"/site-exp* | tail -1)
REPO=$(cd "$(dirname "$0")/../../../.." && pwd)
PY=$REPO/work/lm/data-study/ast/run/runtime-kaggle-py313/venv/bin/python
H=$REPO/scripts/run_heavy.py
cd "$REPO"
export GOLD_UNION_DIR=${GOLD_UNION_DIR:?GOLD_UNION_DIR names the union folder}
echo "== $SPLIT records $(date +%T)"
SITE=$W SAMPLER_CODE=$KIT/model/study/sampler $H --cpus "${JOBS:-4}" --need soon "$REPO/model/study/gold/cover_forms/gold_union_env.sh" "$REPO/engine/kaggle/reach-kit/build_merged.py" --jobs "${JOBS:-4}" "$SPLIT" 2>&1 | grep --line-buffered -v Warning
echo "== $SPLIT rows $(date +%T)"
$H --cpus "${JOBS:-4}" --need soon $PY -u model/study/samples/rows_replay.py "$SPLIT" "${JOBS:-4}" --release "$KIT" 2>&1 | grep --line-buffered -v Warning
echo "== $SPLIT done $(date +%T)"
