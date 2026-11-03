#!/bin/bash
# Stage 2 through the samples for one SET, each stage in N shards: skeleton, tables, supplement, sample_write. Each stage skips current tasks.
#   KIT=<writer kit release folder> model/study/samples/run/stages.sh SET [N]
# The engine is the kit's site-exp* folder. ARC_SAMPLE_GRAPHS, when set, names the graph folder that skeleton reads.
set -o pipefail
SET=${1:?set}; N=${2:-1}
W=$(ls -d "${KIT:?KIT names a writer kit release}"/site-exp* | tail -1)
REPO=$(cd "$(dirname "$0")/../../../.." && pwd)
PY=$REPO/work/lm/data-study/ast/run/runtime-kaggle-py313/venv/bin/python
H=$REPO/scripts/run_heavy.py
cd "$REPO" || exit 1
export ARCLOG_IDENT_SOURCE=value PYTHONPATH=$W
export H PY SET
shards() { seq 0 $((N - 1)) | sed "s|\$|/$N|"; }
echo "== $SET skeleton on $(basename "$W") $(date +%T)"
shards | xargs -P "$N" -n 1 sh -c '$H --cpus 1 --need soon uv run python model/study/samples/skeleton.py $SET --shard "$1" 2>&1 | tail -1 | cut -c1-300' _ || exit 1
echo "== $SET tables $(date +%T)"
shards | xargs -P "$N" -n 1 sh -c '$H --cpus 1 --need soon $PY model/study/samples/build_tables.py $SET --shard "$1" 2>&1 | grep -v " 0 differ from Python, 0 from the dev module" | tail -1 | cut -c1-300' _ || exit 1
echo "== $SET supplement $(date +%T)"
$H --cpus "$N" --need soon $PY model/study/samples/supplement.py $SET --stage both --jobs "$N" 2>&1 | tail -2 | cut -c1-400 || exit 1
echo "== $SET samples $(date +%T)"
shards | xargs -P "$N" -n 1 sh -c '$H --cpus 1 --need soon uv run python model/study/samples/sample_write.py $SET --shard "$1" 2>&1 | tail -1 | cut -c1-600' _ || exit 1
echo "== $SET done $(date +%T)"
