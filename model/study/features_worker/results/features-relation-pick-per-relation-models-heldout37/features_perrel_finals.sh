#!/bin/bash
# The final fits, one call per ARM. Usage: features_perrel_finals.sh NAME [gold|drawn]. Each fit writes its keys' rows as they finish, and a rerun skips finished keys.
D=/Users/davidlu/code/arc-workspace/work/lm/data-study/features-worker/results/features-relation-pick-per-relation-models-heldout37
NOORDER='readers,recency,recency_frac,kept_reads,prevform*,scopereads*'
FAM="--cap 30000 --cap-min 4000 --cap-per 8 --selfkeys 40"
REL="--cap 15000 --cap-min 4000 --cap-per 30"
L=${2:-gold}
P=final; [ "$L" = drawn ] && P=control
case "$1" in
  hyb-noorder) A="--level hyb $FAM --drop $NOORDER";;
  hyb-all) A="--level hyb $FAM";;
  rel) A="--level rel $REL --drop $NOORDER";;
  comp) A="--level comp $REL --drop $NOORDER";;
  fam) A="--level fam $FAM --drop $NOORDER";;
esac
exec bash $D/features_perrel_env.sh 4 features_perrel_fit.py "$P-$1" --procs 4 --eta .15 --ntok 150 --depth 4 --rounds 200 --label "$L" $A
