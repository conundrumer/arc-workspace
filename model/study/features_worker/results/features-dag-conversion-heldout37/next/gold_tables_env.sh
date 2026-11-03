#!/bin/bash
# Usage: gold_tables_env.sh CPUS SCRIPT ARG... : runs a script of next/ in the venv python of the kaggle runtime, through run_heavy.py, on the engine and the sampler code of the pin of the conversion record. CPUS `check` prints the hashes and exits 1 if either differs from the pin.
R=/Users/davidlu/code/arc-workspace
DS=$R/work/lm/data-study
N=/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/9899b29d-4bf5-4cd3-9cdc-a669f9aea9b2/scratchpad/records/features-dag-conversion-heldout37/next
SAMPLER=/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/9899b29d-4bf5-4cd3-9cdc-a669f9aea9b2/scratchpad/records/sampler-wt-d1c0f40e6/model/study/sampler
WANT_CODE=13bbd6afa43e
WANT_SO=4538e2630f39d751117a59354494a1d4035d873177c6e9abffe3927a71661371
ENGINE=$DS/ast/run/runtime-ba0754492/py313-path
PY=$DS/ast/run/runtime-kaggle-py313/venv/bin/python
GOT_CODE=$(cat "$SAMPLER"/live.py "$SAMPLER"/or_q.py "$SAMPLER"/search.py "$SAMPLER"/search_gold.py "$SAMPLER"/live_try.py "$SAMPLER"/sample2_col.py "$SAMPLER"/sample.py | shasum -a 256 | cut -c1-12)
GOT_SO=$(shasum -a 256 "$ENGINE/arclog/arclog.abi3.so" | cut -d' ' -f1)
echo "sampler_code $GOT_CODE (pin $WANT_CODE) engine_so $GOT_SO (pin $WANT_SO)" >&2
if [ "$GOT_CODE" != "$WANT_CODE" ] || [ "$GOT_SO" != "$WANT_SO" ]; then echo "hash differs from the pin" >&2; exit 1; fi
export ARC_ROOT=$R SAMPLER_CODE=$SAMPLER SEARCH_MODELS=$DS/features-worker/results/features-relation-pick-rank-context-rows-heldout37/steer-models PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 ARCLOG_THREADS=1 RAYON_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1
export PYTHONPATH=$ENGINE:$SAMPLER:$N/..
CPUS=$1; shift
if [ "$CPUS" = check ]; then exit 0; fi
S=$1; shift
exec "$R/scripts/run_heavy.py" --cpus "$CPUS" --need soon "$PY" -u "$N/$S" "$@"
