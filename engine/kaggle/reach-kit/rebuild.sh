#!/bin/bash
# rebuild.sh SET [JOBS]: rebuilds the reach measurement kit's union gold for SET from the current gold/gold-union files: the records, the shipped maps, gold-union.json with every set that has records, and the kit's sha.
# Run from anywhere. A task with no merged record in union-SET.jsonl or union-SET-addendum.jsonl takes the text-level record of union-identity-SET.jsonl, and gets no map.
# With --resume after SET, it keeps the records and maps it has, and adds the tasks that are new or newly merged.
set -euo pipefail
S=$(cd "$(dirname "$0")" && pwd)  # the scripts
H=${UNION_REACH_OUT:-/Users/davidlu/code/arc-workspace/work/synth-kaggle/kit-union-read}  # the kit, its records and its maps
SET=$1; shift; RESUME=0; [ "${1:-}" = --resume ] && { RESUME=1; shift; }; JOBS=${1:-4}
R=/Users/davidlu/code/arc-workspace
PY=$R/work/lm/data-study/ast/run/runtime-kaggle-py313/venv/bin/python
cd "$H"
[ $RESUME = 1 ] || { rm -f "records-$SET.jsonl" "records-$SET.jsonl.zst"; : > "maps-$SET.jsonl.part"; }  # maps-SET.jsonl stays until build_map.py renames the new one over it
$PY "$S/build.py" --code  # the study runtime reads .zst files
SAMPLER_CODE=$H/kit-union-read-79af0a4f2/model/study/sampler PYTHONPATH=$R/model/study/gold/cover_forms:$R/work/synth-kaggle/macsite13 \
  $R/scripts/run_heavy.py --cpus "$JOBS" --need soon $PY "$S/build_merged.py" --jobs "$JOBS" "$SET"
$R/scripts/run_heavy.py --cpus "$JOBS" --need soon $PY "$S/build_map.py" "$SET" "$JOBS"
SETS=$(ls records-*.jsonl* | sed 's/\.zst$//' | sort -u | sed 's/records-\(.*\)\.jsonl/\1/' | grep -v '\.' | grep -vx training | tr '\n' ' ')  # training's records serve maps-training.jsonl, not the kit's gold
$PY "$S/build.py" $SETS
python3 "$S/kit_sha.py"
