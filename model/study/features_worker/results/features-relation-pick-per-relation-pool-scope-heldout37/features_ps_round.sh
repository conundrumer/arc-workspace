#!/bin/bash
# Runs shards of a walk at once, each up to BUDGET_S seconds. Usage: features_ps_round.sh SCRIPT NAME SHARDS BUDGET_S. SCRIPT is features_ps_walks.sh or features_ps_walks_fit.sh.
D=/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/9899b29d-4bf5-4cd3-9cdc-a669f9aea9b2/scratchpad/records/features-relation-pick-per-relation-pool-scope-heldout37
seq 0 $(($3 - 1)) | xargs -P "$3" -I{} bash "$D/$1" "$2" {} "$3" "$4"
