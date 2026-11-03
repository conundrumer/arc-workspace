#!/bin/bash
# Walks each part of the plan's table in order, on one shard. A part that ends with an error stops the shard. A rerun skips finished walks.
# Usage: features_dagc_walk_all.sh I N
I=$1; N=$2
D=$(cd "$(dirname "$0")" && pwd); E=$D/features_dagc_env.sh
F=/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/sampler-worker/sampler-priors-folds-8a5ffec60/'fold{}'/live_priors.pkl
cd "$D" || exit 1
mkdir -p walk-logs
run() {  # part steers [extra args]
    p=$1; s=$2; shift 2
    c=--content; [ "$s" = live ] && c=
    echo "$(date +%H:%M:%S) start $p $s shard $I/$N" >> walk-logs/driver-$I.log
    bash "$E" 1 features_dagc_walk.py --part "$p" --steers "$s" $c --shard "$I/$N" "$@" >> "walk-logs/$p-$s-$I.log" 2>&1 || { echo "$(date +%H:%M:%S) FAILED $p $s" >> walk-logs/driver-$I.log; exit 1; }
    echo "$(date +%H:%M:%S) end $p $s" >> walk-logs/driver-$I.log
}
for p in held-parents held-cut dev-cut held-pool held-wide; do run $p off; run $p live; done
run test-parents off --priors-fold "$F"
run test-parents live --priors-fold "$F"
run test-cut live --priors-fold "$F"
run fit-cut off --priors-fold "$F"
run fit-pool off --priors-fold "$F"
