#!/bin/bash
# points_write.py with the writer and engine of a writer kit release. The writer leaves the vector's cand block out unless WRITER_VECTOR_OFF is set.
#   KIT=<writer kit release folder> [POINTS_MAX=5] model/study/samples/run/points.sh <points_write.py arguments>
X=${KIT:?KIT names a writer kit release}/model/study/sampler
W=$(ls -d "$KIT"/site-exp* | tail -1)
REPO=$(cd "$(dirname "$0")/../../../.." && pwd)
PY=$REPO/work/lm/data-study/ast/run/runtime-kaggle-py313/venv/bin/python
cd "$REPO" || exit 1
# POINTS_MAX (default 5): the most points_write processes at once on this machine; a new one waits for one to end
while [ "$(pgrep -f 'samples/points_write.py' | wc -l)" -ge "${POINTS_MAX:-5}" ]; do /bin/sleep 15; done
WRITER_VECTOR_OFF=${WRITER_VECTOR_OFF-cand} PYTHONPATH=$X:$W ARCLOG_IDENT_SOURCE=value PYTHONDONTWRITEBYTECODE=1 RAYON_NUM_THREADS=1 OMP_NUM_THREADS=1 ARCLOG_THREADS=1 \
  exec scripts/run_heavy.py --cpus 1 --need soon $PY -u model/study/samples/points_write.py "$@"
