#!/bin/bash
# usage: rerun_no_tables.sh SET N
# Runs the programs of fits-SET.jsonl that give no tables again, with FITS_CAP=300 seconds, in N shards (rerun_no_tables.py) through run_heavy; then writes the results into the fits shard files (apply_reruns.py) and merges (fits-SET.jsonl). SITE (default site-exp29) is the engine on PYTHONPATH. Results and logs go to $UNION_SCRATCH/tor (UNION_SCRATCH default: the scratchpad of session 64993706). The outputs are in work/lm/data-study/gold/gold-union.
cd /Users/davidlu/code/arc-workspace
S=${UNION_SCRATCH:-/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/64993706-bdea-4acd-bcaf-7d7b1e3ea40a/scratchpad}
U=model/study/gold/reads/union
export FITS_CAP=300 ARCLOG_IDENT_SOURCE=value PYTHONPATH=${SITE:-/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/b9773fdd-d09f-4bd5-b2d0-ebeaa83d8c6d/scratchpad/site-exp29}
mkdir -p $S/tor
for ((k=0; k<$2; k++)); do
  scripts/run_heavy.py --need soon .venv/bin/python $U/runs/rerun_no_tables.py $1 $k $2 > $S/tor/$1-$k.jsonl 2>&1 &
done
wait
cat $S/tor/$1-*.jsonl > $S/tor/$1-all.jsonl
.venv/bin/python $U/runs/apply_reruns.py $1 $S/tor/$1-all.jsonl
.venv/bin/python $U/gold_union_fits.py $1 merge
