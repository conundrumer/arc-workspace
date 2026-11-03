#!/bin/bash
# Runs a script of this record in the rank read's python, one thread per process, through run_heavy.py, on the pinned sampler code and engine. Usage: features_dagc_env.sh CPUS SCRIPT ARGS...
# CPUS `check` prints the sampler code hash and the engine hash, and exits 1 if either differs from the pin.
R=/Users/davidlu/code/arc-workspace
D=/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/9899b29d-4bf5-4cd3-9cdc-a669f9aea9b2/scratchpad/records/features-dag-conversion-heldout37
SAMPLER=/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/9899b29d-4bf5-4cd3-9cdc-a669f9aea9b2/scratchpad/records/sampler-wt-d1c0f40e6/model/study/sampler
WANT_CODE=13bbd6afa43e
WANT_SO=4538e2630f39d751117a59354494a1d4035d873177c6e9abffe3927a71661371
ENGINE=$R/work/lm/data-study/ast/run/runtime-ba0754492/py313-path
PY=$R/work/lm/data-study/ast/run/runtime-kaggle-py313/venv/bin/python
GOT_CODE=$(cat "$SAMPLER"/live.py "$SAMPLER"/or_q.py "$SAMPLER"/search.py "$SAMPLER"/search_gold.py "$SAMPLER"/live_try.py "$SAMPLER"/sample2_col.py "$SAMPLER"/sample.py | shasum -a 256 | cut -c1-12)
GOT_SO=$(shasum -a 256 "$ENGINE/arclog/arclog.abi3.so" | cut -d' ' -f1)
echo "sampler_code $GOT_CODE (pin $WANT_CODE) engine_so $GOT_SO (pin ba0754492 $WANT_SO)" >&2
if [ "$GOT_CODE" != "$WANT_CODE" ] || [ "$GOT_SO" != "$WANT_SO" ]; then echo "hash differs from the pin" >&2; exit 1; fi
export PYTHONPATH=$ENGINE
export RAYON_NUM_THREADS=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 STEER_COVER=init,branch SAMPLER_CODE=$SAMPLER PYTHONDONTWRITEBYTECODE=1
CPUS=$1; shift
if [ "$CPUS" = check ]; then exit 0; fi
S=$1; shift
exec "$R/scripts/run_heavy.py" --cpus "$CPUS" --need soon "$PY" -u "$D/$S" "$@"
