#!/bin/bash
# Runs the value join probes on one shard, held tasks then test tasks. A rerun skips finished picks.
# Usage: features_dagc_probe_all.sh I N
I=$1; N=$2
D=$(cd "$(dirname "$0")" && pwd); E=$D/features_dagc_env.sh
F=/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/sampler-worker/sampler-priors-folds-8a5ffec60/'fold{}'/live_priors.pkl
cd "$D" || exit 1
bash "$E" 1 features_dagc_probe.py --part held-parents --shard "$I/$N" >> "walk-logs/probe-held-$I.log" 2>&1 || exit 1
bash "$E" 1 features_dagc_probe.py --part test-parents --shard "$I/$N" --priors-fold "$F" >> "walk-logs/probe-test-$I.log" 2>&1
