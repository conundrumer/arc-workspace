#!/bin/bash
# usage: fits_run.sh SET N
# Runs N shards of gold_union_fits.py through run_heavy, then merges them (fits-SET.jsonl). SITE (default site-exp29) is the engine on PYTHONPATH. Logs go to $UNION_SCRATCH (default: the scratchpad of session 64993706). The outputs are in work/lm/data-study/gold/gold-union.
cd /Users/davidlu/code/arc-workspace
SITE=${SITE:-/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/b9773fdd-d09f-4bd5-b2d0-ebeaa83d8c6d/scratchpad/site-exp29}
S=${UNION_SCRATCH:-/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/64993706-bdea-4acd-bcaf-7d7b1e3ea40a/scratchpad}
export ARCLOG_IDENT_SOURCE=value PYTHONPATH=$SITE
for ((k=0; k<$2; k++)); do
  scripts/run_heavy.py --need soon .venv/bin/python model/study/gold/reads/union/gold_union_fits.py $1 $k $2 > $S/fits-$1-$k.log 2>&1 &
done
wait
.venv/bin/python model/study/gold/reads/union/gold_union_fits.py $1 merge > $S/fits-$1-merge.log 2>&1
echo merged $1
