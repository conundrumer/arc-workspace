#!/bin/bash
# Each shard of one SET goes through all stages on its own: skeleton, tables, supplement, sample_write, then points_write when POINTS holds its
# arguments. A shard does not wait for the other shards, so its training rows exist as soon as its own stages end. Each stage skips current tasks.
#   KIT=<writer kit release folder> [POINTS='--plan ordered --vectors --samples-per-task 8'] [POINTS_BATCH=12] [SUPPLEMENT_JOBS=1] model/study/samples/run/chain.sh SET N
set -o pipefail
SET=${1:?set}; N=${2:?shards}
W=$(ls -d "${KIT:?KIT names a writer kit release}"/site-exp* | tail -1)
HERE=$(cd "$(dirname "$0")" && pwd)
REPO=$(cd "$HERE/../../../.." && pwd)
PY=$REPO/work/lm/data-study/ast/run/runtime-kaggle-py313/venv/bin/python
H=$REPO/scripts/run_heavy.py
cd "$REPO" || exit 1
export ARCLOG_IDENT_SOURCE=value PYTHONPATH=$W ARC_SAMPLER_KIT=$KIT/model/study/sampler
export H PY SET HERE POINTS REPO SUPPLEMENT_JOBS
one() {
    set -o pipefail
    s=$1
    say() { echo "$SET $s $1 $(date +%T): $(tail -1 | cut -c1-400)"; }
    $H --cpus 1 --need soon uv run python model/study/samples/skeleton.py $SET --shard $s 2>&1 | say skeleton || return 1
    $H --cpus 1 --need soon $PY model/study/samples/build_tables.py $SET --shard $s 2>&1 | grep -v " 0 differ from Python, 0 from the dev module" | say tables || return 1
    $H --cpus "${SUPPLEMENT_JOBS:-1}" --need soon $PY model/study/samples/supplement.py $SET --stage both --jobs "${SUPPLEMENT_JOBS:-1}" --shard $s 2>&1 | say supplement || return 1
    $H --cpus 1 --need soon uv run python model/study/samples/sample_write.py $SET --shard $s 2>&1 | say samples || return 1
    [ -z "$POINTS" ] && return 0
    # points_write's memory grows with the tasks a process has done, so each process takes POINTS_BATCH tasks of the shard
    python3 -c "
import os, sys, zlib
k, n = map(int, sys.argv[2].split('/'))
ts = sorted(f[:-6] for f in os.listdir(sys.argv[1]) if f.endswith('.jsonl') and zlib.crc32(f[:-6].encode()) % n == k)
b = int(sys.argv[3])
for i in range(0, len(ts), b): print(','.join(ts[i:i + b]))
" "$REPO/work/lm/data-study/samples/$SET/skeleton" "$s" "${POINTS_BATCH:-12}" | while read -r ts; do
        "$HERE/points.sh" $SET $POINTS --tasks "$ts" 2>&1 | say points
    done
}
export -f one
seq 0 $((N - 1)) | sed "s|\$|/$N|" | xargs -P "$N" -n 1 bash -c 'one "$1"' _
echo "== $SET done $(date +%T)"
