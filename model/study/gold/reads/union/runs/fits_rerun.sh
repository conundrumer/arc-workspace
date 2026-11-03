#!/bin/bash
# usage: fits_rerun.sh SET N K...
# Runs shards K... of N of gold_union_fits.py again, with FITS_CAP=60 seconds a program (a restart skips the tasks that a shard file has), then merges (fits-SET.jsonl). SITE (default site-exp29) is the engine on PYTHONPATH. Logs are appended to $UNION_SCRATCH (default: the scratchpad of session 64993706). The outputs are in work/lm/data-study/gold/gold-union.
cd /Users/davidlu/code/arc-workspace
SITE=${SITE:-/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/b9773fdd-d09f-4bd5-b2d0-ebeaa83d8c6d/scratchpad/site-exp29}
S=${UNION_SCRATCH:-/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/64993706-bdea-4acd-bcaf-7d7b1e3ea40a/scratchpad}
export FITS_CAP=60 ARCLOG_IDENT_SOURCE=value PYTHONPATH=$SITE
for k in ${@:3}; do
  scripts/run_heavy.py --need soon .venv/bin/python model/study/gold/reads/union/gold_union_fits.py $1 $k $2 >> $S/fits-$1-$k.log 2>&1 &
done
wait
.venv/bin/python model/study/gold/reads/union/gold_union_fits.py $1 merge > $S/fits-$1-merge.log 2>&1
echo merged $1
