#!/bin/bash
# shapes_rows_check.sh quick|full BUILD_NAME KNOWN.jsonl: runs shapes_rows_check.py on the engine build BUILD_NAME (engine_build.sh NAME wheel encoder).
#   quick  00dbd492's table that holds the known shapes: seconds.
#   full   quick, then 00dbd492's three smallest tables, then 42918530 with its first table whose walk stops, and last a second run of 00dbd492 under ARCLOG_MAP_SEED=1 whose rows() bytes must equal the first run's.
# KNOWN.jsonl is what known_values.py wrote for 00dbd492's `&changed`. PY is the runtime python (default: the one in work/lm/data-study/ast/run/runtime-kaggle-py313).
# Run it through scripts/run_heavy.py --cpus 1. It prints counts and seconds only.
set -u
MODE=$1; NAME=$2; KNOWN=${3:-}
HERE=$(cd "$(dirname "$0")" && pwd)
MAIN=$(dirname "$(git -C "$HERE" rev-parse --path-format=absolute --git-common-dir)")
R=$MAIN/work/engine-builds
PY=${PY:-$MAIN/work/lm/data-study/ast/run/runtime-kaggle-py313/venv/bin/python}
MERGED=$MAIN/work/feature-spec/results/all-merged
# The feature corpus file of a task's gold program, in the train part or the dev part.
mutants() { for part in train dev; do [ -f "$MERGED/$part/mutants/$1.json.zst" ] && { echo "$MERGED/$part/mutants/$1.json.zst"; return; }; done; echo "no feature corpus file for $1" >&2; exit 1; }
ENC=$R/bin/feature-encoder-$NAME
OUT=${OUT:-$(mktemp -d)}
export PYTHONPATH=$R/builds/$NAME ARC_ROOT=$MAIN
check() { "$PY" "$HERE/shapes_rows_check.py" "$@" --encoder "$ENC"; }
[ -n "$KNOWN" ] || { echo "usage: shapes_rows_check.sh quick|full BUILD_NAME KNOWN.jsonl"; exit 1; }
known=(--known "$KNOWN")
check 00dbd492 "$(mutants 00dbd492)" ${known[@]+"${known[@]}"} --tables 0 --work "$OUT/quick" --digest-out "$OUT/digests.json" || exit 1
[ "$MODE" = full ] || exit 0
check 00dbd492 "$(mutants 00dbd492)" --tables 3 --work "$OUT/small" || exit 1
check 42918530 "$(mutants 42918530)" --tables 1 --stopped --work "$OUT/stopped" || exit 1
ARCLOG_MAP_SEED=1 check 00dbd492 "$(mutants 00dbd492)" ${known[@]+"${known[@]}"} --tables 0 --work "$OUT/seeded" --digest-in "$OUT/digests.json" || exit 1
