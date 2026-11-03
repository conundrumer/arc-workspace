#!/bin/bash
# Retries after retry1, one at a time: deadline stops, then the big afe3afe9 and 50846271 tables.
S=/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/9899b29d-4bf5-4cd3-9cdc-a669f9aea9b2/scratchpad
cd /Users/davidlu/code/arc-workspace || exit 1
FX=work/lm/data-study/feat-exp
while pgrep -f "points.cache-retry1" >/dev/null; do sleep 20; done
run() {  # name workers tasks... -- flags...
  name=$1; w=$2; shift 2; tasks=(); while [ "$1" != "--" ]; do tasks+=("$1"); shift; done; shift
  printf '%s\n' "${tasks[@]}" > $S/fast/$name.tasks
  echo "=== $name $(date +%T) $*" >> $S/fast/$name.log
  /usr/bin/time -l scripts/run_heavy.py --cpus $w --need soon work/lm/data-study/ast/run/runtime-5b046ceee/venv/bin/python -B $FX/study/build_points.py work/lm/data-study/gold/gen-v3-11f6a212c/corpus $FX/fstore-gen3/points --tasks $S/fast/$name.tasks --cache $FX/fstore-gen3/points.cache-$name --workers $w --recycle 1 --stall 300 --task-gib 3 --step-cap 20000 --session-mib 1024 "$@" >> $S/fast/$name.log 2>&1
  echo "=== $name end $(date +%T)" >> $S/fast/$name.log
}
run retry2 2 58490d8a 1b60fb0c -- --deadline 120 --table-max-cells 1048576
run retry3 2 afe3afe9 -- --table-max-cells 2097152
run retry4 1 50846271 -- --deadline 120 --table-max-cells 6000000
