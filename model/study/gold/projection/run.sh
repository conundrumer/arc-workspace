#!/bin/bash
# run.sh: the read-narrowing trial on the stems of trial/tasks.txt, in 5 shards, one stem each, each through run_heavy.py; then the report.
# Each stem has 900 s and 8 GiB over its process group (gold_pod_run.py caps). A restart skips stems whose row is done.
N=$(cd "$(dirname "$0")" && pwd)
H=/Users/davidlu/code/arc-workspace/scripts/run_heavy.py
mkdir -p "$N/trial/out"
for k in 0 1 2 3 4; do
  $H --cpus 1 --need soon bash "$N/env.sh" "$N/narrow_run.py" tasks.txt lines.json weights.json base-rows.json out/rows-$k.jsonl $k 5 >> "$N/trial/out/rows-$k.log" 2>&1 &
done
wait
python3 "$N/report.py" | tee "$N/trial/report.txt"
