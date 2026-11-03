#!/bin/bash
# build_training.sh [JOBS]: maps-training.jsonl from the training union, with no change to the kit's gold. A rerun builds only the tasks that are new or whose union line changed,
# so it can run on the union's part files and again when union-training.jsonl lands.
set -euo pipefail
S=$(cd "$(dirname "$0")" && pwd)  # the scripts
H=${UNION_REACH_OUT:-/Users/davidlu/code/arc-workspace/work/synth-kaggle/kit-union-read}  # the kit, its records and its maps
JOBS=${1:-4}
R=/Users/davidlu/code/arc-workspace
PY=$R/work/lm/data-study/ast/run/runtime-kaggle-py313/venv/bin/python
cd "$H"
python3 "$S/build.py" --code
SAMPLER_CODE=$H/kit-union-read-79af0a4f2/model/study/sampler PYTHONPATH=$R/model/study/gold/cover_forms:$R/work/synth-kaggle/macsite13 \
  $R/scripts/run_heavy.py --cpus "$JOBS" --need soon $PY "$S/build_merged.py" --jobs "$JOBS" --merged-only training
$R/scripts/run_heavy.py --cpus "$JOBS" --need soon python3 "$S/build_map.py" training "$JOBS"
