#!/bin/bash
# Labels, then the feature table, for one arm's records, streaming task by task. A rerun skips finished tasks.
# more.sh ARM_DIR TAG
d=${1:?}; tag=${2:?}
cd /Users/davidlu/code/arc-workspace || exit 1
PY=work/lm/data-study/ast/run/runtime-kaggle-py313/venv/bin/python
export PYTHONPATH=work/lm/data-study/sampler/fit-torch OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1
export LABELS=/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/9899b29d-4bf5-4cd3-9cdc-a669f9aea9b2/scratchpad/live/labels-$tag
scripts/run_heavy.py --cpus 1 --need soon $PY -u /private/tmp/claude-501/-Users-davidlu-code-arc-workspace/9899b29d-4bf5-4cd3-9cdc-a669f9aea9b2/scratchpad/live/live_labels_h.py 0 1 "$d"/*.nodes.jsonl.zst
scripts/run_heavy.py --cpus 1 --need soon $PY -u /private/tmp/claude-501/-Users-davidlu-code-arc-workspace/9899b29d-4bf5-4cd3-9cdc-a669f9aea9b2/scratchpad/live/live_table.py /private/tmp/claude-501/-Users-davidlu-code-arc-workspace/ede6795c-2b6f-4633-a6da-08e90de33bc4/scratchpad/policy1 $tag "$d" 0 1
