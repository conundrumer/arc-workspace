#!/bin/bash
# Walk of the census's RULE forms of the 37 held tasks, in the census's setting. Usage: features_walk_held.sh SHARD_I SHARD_N [BUDGET_S]
R=/Users/davidlu/code/arc-workspace
D=/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/9899b29d-4bf5-4cd3-9cdc-a669f9aea9b2/scratchpad/records/features-relation-pick-rank-context-rows-heldout37
. "$D/features_walk_env.sh"
B=$W/sampler-helper-forms/gold-v3-helper-forms-a036da074
export SAMPLER_CORPUS=$R/work/lm/data-study/gold/gold-v3-helper-forms-a036da074/corpus-view/ SEARCH_GOLDS=$B/points-base.json
cd "$CODE" || exit 1
exec "$R/scripts/run_heavy.py" --cpus 1 --need soon "$PY" -u "$D/features_rel_walk.py" --forms "$W/sampler-relation-pick-read-heldout431-census/forms_all.json" --golds "$B/points-base.json" \
  --out "$D/walks/features-walk-held-$1of$2.jsonl.zst" --shard "$1/$2" --budget "${3:-1e9}"
