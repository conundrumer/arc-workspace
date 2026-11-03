#!/bin/bash
# run99.sh: the read-narrowing stage on the 99 less the 5 trial stems (trial99/tasks.txt, 94 stems), DAG_MARGIN=3, in 3 shards, each
# through run_heavy.py; then the report. Each stem has 900 s and 8 GiB over its process group. A restart skips stems whose row is done.
N=$(cd "$(dirname "$0")" && pwd)
H=/Users/davidlu/code/arc-workspace/scripts/run_heavy.py
mkdir -p "$N/trial99/out"
for k in 0 1 2; do
  RUN_DIR=trial99 DAG_MARGIN=3 $H --cpus 1 --need soon bash "$N/env.sh" "$N/narrow_run.py" tasks.txt lines.json weights.json base-rows.json out/rows-$k.jsonl $k 3 >> "$N/trial99/out/rows-$k.log" 2>&1 &
done
wait
python3 "$N/report.py" trial99 > "$N/trial99/report.txt"
tail -1 "$N/trial99/report.txt"
