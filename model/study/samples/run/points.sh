#!/bin/bash
# points_write.py with the writer and engine of a writer kit release. The writer leaves the vector's cand block out unless WRITER_VECTOR_OFF is set.
#   KIT=<writer kit release folder> [POINTS_MAX=5] model/study/samples/run/points.sh <points_write.py arguments>
X=${KIT:?KIT names a writer kit release}/model/study/sampler
W=$(ls -d "$KIT"/site-exp* | tail -1)
REPO=$(cd "$(dirname "$0")/../../../.." && pwd)
PY=$REPO/work/lm/data-study/ast/run/runtime-kaggle-py313/venv/bin/python
cd "$REPO" || exit 1
# POINTS_MAX (default 5): the most points_write processes at once on this machine. A run claims one of POINTS_MAX slot folders with mkdir, which is atomic,
# so runs that start together cannot pass the cap. A slot whose run is gone is freed. The count of running processes also stays under the cap.
SLOTS=$REPO/work/lm/data-study/samples/.points-slots
mkdir -p "$SLOTS"
claim() {
  for i in $(seq 1 "${POINTS_MAX:-5}"); do
    d=$SLOTS/$i
    if mkdir "$d" 2>/dev/null; then echo $$ > "$d/pid"; S=$d; return 0; fi
    p=$(cat "$d/pid" 2>/dev/null)
    if [ -n "$p" ] && ! kill -0 "$p" 2>/dev/null; then rm -rf "${d:?}"; fi
  done
  return 1
}
until claim; do /bin/sleep 15; done
trap 'rm -rf "${S:?}"' EXIT
while [ "$(pgrep -f '^[^ ]*python[^ ]* -u model/study/samples/points_write.py' | wc -l)" -ge "${POINTS_MAX:-5}" ]; do /bin/sleep 15; done
WRITER_VECTOR_OFF=${WRITER_VECTOR_OFF-cand} PYTHONPATH=$X:$W ARCLOG_IDENT_SOURCE=value PYTHONDONTWRITEBYTECODE=1 RAYON_NUM_THREADS=1 OMP_NUM_THREADS=1 ARCLOG_THREADS=1 \
  scripts/run_heavy.py --cpus 1 --need soon $PY -u model/study/samples/points_write.py "$@"
