#!/bin/bash
# usage: union_run.sh SET N
# Runs N shards of gold_union.py through run_heavy, merges them (union-SET.jsonl, union-SET.manifest.json), then writes the union keys (gold_union_keys.py SET). Logs go to $UNION_SCRATCH (default: the scratchpad of session 64993706); logs of an earlier run go to old-logs there. The outputs are in work/lm/data-study/gold/gold-union.
cd /Users/davidlu/code/arc-workspace
S=${UNION_SCRATCH:-/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/64993706-bdea-4acd-bcaf-7d7b1e3ea40a/scratchpad}
U=$PWD/model/study/gold/reads/union
E=model/study/gold/cover_forms/gold_union_env.sh
mkdir -p $S/old-logs
mv $S/union-$1-*.log $S/old-logs/ 2>/dev/null
for ((k=0; k<$2; k++)); do
  scripts/run_heavy.py --need soon $E $U/gold_union.py run $k $2 $1 > $S/union-$1-$k.log 2>&1 &
done
wait
$E $U/gold_union.py merge $1 > $S/union-$1-merge.log 2>&1
$E $U/gold_union_keys.py $1 > $S/keys-$1.log 2>&1
echo merged $1; tail -1 $S/keys-$1.log
