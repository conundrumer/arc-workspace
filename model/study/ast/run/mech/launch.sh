#!/bin/bash
set -euo pipefail
mech_dir=$(cd -- "$(dirname -- "$0")" && pwd)
run_dir=$(dirname -- "$mech_dir")
data_root=$(python3 "$mech_dir/../../../study_paths.py")
export PYTHONDONTWRITEBYTECODE=1
mode=${1:-full}
workers=${2:-4}
output=${3:-"$data_root/ast/run/mech/labels.sqlite3"}
case "$mode" in
  pilot)
    for source in kept recovered; do
      python3 "$mech_dir/run.py" "$data_root/ast/run/corpus-v11" "$output" \
        --workers "$workers" --tasks 00576224 007bbfb7 009d5c81 \
        --sources "$source" --limit-per-task 3
    done
    ;;
  full)
    exec python3 "$mech_dir/run.py" "$data_root/ast/run/corpus-v11" "$output" --workers "$workers"
    ;;
  *) echo 'usage: bash launch.sh pilot|full [workers=4] [output=labels.sqlite3]' >&2; exit 2 ;;
esac
