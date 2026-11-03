#!/bin/bash
# usage: norm_run.sh <work dir> <shards>: run slot_order_check on each shard, one process per shard, under run_heavy
B=/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/b9773fdd-d09f-4bd5-b2d0-ebeaa83d8c6d/scratchpad/slot/bin2/slot_order_check
work=$1; shards=$2
for k in $(seq 0 $((shards - 1))); do
  /Users/davidlu/code/arc-workspace/scripts/run_heavy.py --cpus 1 --need soon "$B" "$work/in-$k" "$work/out-$k" > "$work/log-$k.txt" 2>&1 &
done
wait
tail -qn 1 "$work"/log-*.txt
