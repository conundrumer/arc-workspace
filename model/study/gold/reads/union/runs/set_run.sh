#!/bin/bash
# usage: set_run.sh SET N
# Builds the union outputs of SET on the engine SITE in the folder GOLD_UNION_DIR, each stage in N shards through run_heavy and merged before the next stage starts: fits (FITS_CAP seconds a program, default 300), union rows, union keys, the graph (ROWS_VERSION: the row store hash_versions it accepts), and the walks. GOLD_UNION_DIR must hold cases-SET.jsonl. Each output's code stamp names the engine. Logs go to $UNION_SCRATCH/SET-*.log (UNION_SCRATCH default: the scratchpad of session 64993706), and a line with the clock time is printed as each stage starts and as the run ends.
set -e
cd /Users/davidlu/code/arc-workspace
: "${SITE:?}" "${GOLD_UNION_DIR:?}" "${ROWS_VERSION:?}"
export SITE GOLD_UNION_DIR ROWS_VERSION ARCLOG_IDENT_SOURCE=value FITS_CAP=${FITS_CAP:-300}
S=${UNION_SCRATCH:-/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/64993706-bdea-4acd-bcaf-7d7b1e3ea40a/scratchpad}
U=$PWD/model/study/gold/reads/union
E=model/study/gold/cover_forms/gold_union_env.sh
G=$GOLD_UNION_DIR
shards() {  # shards STAGE CMD...: runs CMD... K N for each shard K
  local stage=$1; shift
  for ((k=0; k<$N; k++)); do
    scripts/run_heavy.py --need soon "$@" $k $N > $S/$SET-$stage-$k.log 2>&1 &
  done
  wait
}
SET=$1 N=$2

echo "$(date +%H:%M) $SET fits"
shards fits env PYTHONPATH=$SITE .venv/bin/python $U/gold_union_fits.py $SET
PYTHONPATH=$SITE .venv/bin/python $U/gold_union_fits.py $SET merge > $S/$SET-fits-merge.log 2>&1

echo "$(date +%H:%M) $SET union"
for ((k=0; k<$N; k++)); do
  scripts/run_heavy.py --need soon $E $U/gold_union.py run $k $N $SET > $S/$SET-union-$k.log 2>&1 &
done
wait
$E $U/gold_union.py merge $SET > $S/$SET-union-merge.log 2>&1

echo "$(date +%H:%M) $SET keys"
shards keys $E $U/gold_union_keys.py $SET
$E $U/gold_union_keys.py $SET merge > $S/$SET-keys-merge.log 2>&1
mkdir -p $G/keys-shards-done
mv $G/union-keys-$SET-[0-9]*.jsonl $G/keys-shards-done/

echo "$(date +%H:%M) $SET graph"
shards graph $E $U/gold_union_graph.py $SET
for f in tables prods tasks; do
  parts=$(for ((k=0; k<$N; k++)); do echo $G/graph-$f-$SET-$k.jsonl; done)
  cat $parts > $G/graph-$f-$SET.jsonl
  python3 $U/gold_union_code.py concat $G/graph-$f-$SET.jsonl $parts
  rm $parts $(for p in $parts; do echo $p.code.json; done)
done
echo "$(date +%H:%M) $SET walks"
python3 $U/gold_union_walks.py $SET > $S/$SET-walks.log 2>&1
echo "$(date +%H:%M) $SET done"
