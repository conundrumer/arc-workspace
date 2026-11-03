#!/bin/bash
# One shard of a walk of the non-held fit points on corpus-v3mix, under each task's fold priors. Usage: features_ps_walks_fit.sh PART SHARD_I SHARD_N [BUDGET_S]
R=/Users/davidlu/code/arc-workspace
D=/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/9899b29d-4bf5-4cd3-9cdc-a669f9aea9b2/scratchpad/records/features-relation-pick-per-relation-pool-scope-heldout37
W=$R/work/lm/data-study/sampler/sampler-worker
export SEARCH_MODELS=$R/work/lm/data-study/features-worker/results/features-relation-pick-rank-context-rows-heldout37/steer-models
export SAMPLER_CORPUS=$R/work/lm/data-study/sampler/corpus-v3mix/
exec bash $D/features_ps_env.sh 1 features_ps_walk.py --points $D/points-fit-$1.jsonl --out $D/walks/walk-fit-$1-$2of$3.jsonl.zst --shard $2/$3 --budget ${4:-170} --priors-fold "$W/sampler-priors-folds-8a5ffec60/fold{}/live_priors.pkl"
