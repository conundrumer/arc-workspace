#!/bin/bash
# usage: graph_run.sh SET N ROWS_VERSION
# Runs gold_union_graph.py on SET in N shards through run_heavy (ROWS_VERSION: the row store hash_version), concatenates the shard files of each kind into graph-{tables,prods,tasks}-SET.jsonl with a .code.json file made from the shards' (gold_union_code.py concat), then compares with the old graph (graph_compare.py). Logs go to $UNION_SCRATCH (default: the scratchpad of session 64993706). SITE (default site-exp30) is the engine. The outputs are in GOLD_UNION_DIR (default work/lm/data-study/gold/gold-union).
cd /Users/davidlu/code/arc-workspace
S=${UNION_SCRATCH:-/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/64993706-bdea-4acd-bcaf-7d7b1e3ea40a/scratchpad}
U=model/study/gold/reads/union
G=${GOLD_UNION_DIR:-work/lm/data-study/gold/gold-union}
for ((k=0; k<$2; k++)); do
  ROWS_VERSION=$3 scripts/run_heavy.py --need soon model/study/gold/cover_forms/gold_union_env.sh $PWD/$U/gold_union_graph.py $1 $k $2 > $S/graph-$1-$k.log 2>&1 &
done
wait
for f in tables prods tasks; do
  shards=$(for ((k=0; k<$2; k++)); do echo $G/graph-$f-$1-$k.jsonl; done)
  cat $shards > $G/graph-$f-$1.jsonl && python3 $U/gold_union_code.py concat $G/graph-$f-$1.jsonl $shards && rm $shards $(for s in $shards; do echo $s.code.json; done)
done
wc -l $G/graph-*-$1.jsonl
UNION_SCRATCH=$S timeout 300 python3 $U/runs/graph_compare.py $1 2>&1 | grep -v "^split\|^join"
