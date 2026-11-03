#!/bin/bash
# Walk of the RULE forms of a non-held part, on corpus-v3mix, under each task's fold priors. Usage: features_walk_part.sh PART SCOPE SHARD_I SHARD_N [BUDGET_S]
R=/Users/davidlu/code/arc-workspace
D=/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/9899b29d-4bf5-4cd3-9cdc-a669f9aea9b2/scratchpad/records/features-relation-pick-rank-context-rows-heldout37
. "$D/features_walk_env.sh"
export SAMPLER_CORPUS=$R/work/lm/data-study/sampler/corpus-v3mix/
cd "$CODE" || exit 1
exec "$R/scripts/run_heavy.py" --cpus 1 --need soon "$PY" -u "$D/features_rel_walk.py" --forms "$D/forms-$1.json" --priors-fold "$W/sampler-priors-folds-8a5ffec60/fold{}/live_priors.pkl" \
  --out "$D/walks/features-walk-$1-$2-$3of$4.jsonl.zst" --scope "$2" --shard "$3/$4" --budget "${5:-1e9}"
