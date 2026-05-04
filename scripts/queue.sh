#!/usr/bin/env bash
# Next TS solver to port: shortest unported file without an #incorrect tag.
set -eu

wc -l ../arc-synth-bun/programs/solvers/*.ts \
  | sort -n \
  | while read -r lines path; do
      [ "$path" = "total" ] && continue
      id=$(basename "$path" .ts)
      [ -f "programs/solvers/$id.py" ] && continue
      head -10 "$path" | grep -q '#incorrect' && continue
      printf "%4s  %s\n" "$lines" "$id"
    done \
  | head -1
