#!/bin/bash
# The held reads other than the primary's: each final model and each control, once. Scale per model from the tune reads.
D=/Users/davidlu/code/arc-workspace/work/lm/data-study/features-worker/results/features-relation-pick-per-relation-models-heldout37
for x in final-hyb-all:1 final-rel:.8 final-comp:.8 final-fam:1 control-hyb-noorder:1 control-hyb-all:1 control-rel:.8 control-comp:.8 control-fam:1; do
  a=${x%%:*}; s=${x##*:}
  bash $D/features_perrel_env.sh 1 features_perrel_read.py "$a" --eta .15 --alpha "$s" > "$D/scratch/read-$a.log" 2>&1
done
