#!/bin/bash
# One shard of a walk of census points on the helper-forms base view, the census's setting. Usage: features_ps_walks_census.sh NAME SHARD_I SHARD_N [BUDGET_S]
export SAMPLER_CORPUS=/Users/davidlu/code/arc-workspace/work/lm/data-study/gold/gold-v3-helper-forms-a036da074/corpus-view/
exec bash /private/tmp/claude-501/-Users-davidlu-code-arc-workspace/9899b29d-4bf5-4cd3-9cdc-a669f9aea9b2/scratchpad/records/features-relation-pick-per-relation-pool-scope-heldout37/features_ps_walks.sh "$1" "$2" "$3" "${4:-170}"
