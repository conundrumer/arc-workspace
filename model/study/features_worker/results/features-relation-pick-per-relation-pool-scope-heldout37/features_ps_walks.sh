#!/bin/bash
# One shard of a walk of held points, on the view-pass1 text. Usage: features_ps_walks.sh NAME SHARD_I SHARD_N [BUDGET_S] [LIMIT]
# NAME is the points file's stem, as held-pool for points-held-pool.jsonl. A restart skips finished points.
R=/Users/davidlu/code/arc-workspace
D=/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/9899b29d-4bf5-4cd3-9cdc-a669f9aea9b2/scratchpad/records/features-relation-pick-per-relation-pool-scope-heldout37
export SEARCH_MODELS=$R/work/lm/data-study/features-worker/results/features-relation-pick-rank-context-rows-heldout37/steer-models
export SAMPLER_CORPUS=${SAMPLER_CORPUS:-$R/work/lm/data-study/gold/gold-v3-extended-cut/view-pass1/corpus-view/}
mkdir -p $D/walks
exec bash $D/features_ps_env.sh 1 features_ps_walk.py --points $D/points-$1.jsonl --out $D/walks/walk-$1-$2of$3.jsonl.zst --shard $2/$3 --budget ${4:-170} --limit ${5:-0}
