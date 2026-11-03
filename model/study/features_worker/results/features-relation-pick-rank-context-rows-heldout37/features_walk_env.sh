R=/Users/davidlu/code/arc-workspace
W=$R/work/lm/data-study/sampler/sampler-worker
D=/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/9899b29d-4bf5-4cd3-9cdc-a669f9aea9b2/scratchpad/records/features-relation-pick-rank-context-rows-heldout37
CODE=$R/.claude/worktrees/agent-a860e02625417f74b/model/study/sampler
export PYTHONPATH=$R/work/lm/data-study/ast/run/runtime-ba0754492/py313-path
export RAYON_NUM_THREADS=1 OMP_NUM_THREADS=1 STEER_COVER=init,branch SAMPLER_CODE=$CODE PYTHONDONTWRITEBYTECODE=1
export SEARCH_MODELS=$D/steer-models
PY=$R/work/lm/data-study/ast/run/runtime-kaggle-py313/venv/bin/python
