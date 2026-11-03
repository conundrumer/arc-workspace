#!/bin/bash
# One loop process per task, because a process's memory grows from task to task. Skips tasks it finished.
# The models folder is pinned to the bundle's, because the repo's priors file changes during runs.
# [REL_BETA=b] [POINTS=FILE] [MODELS=DIR] run_rel.sh OUT_NAME POLICY_DIR SECONDS TASK_FILE
A=$(dirname "$0"); out=${1:?}; pol=${2:?}; sec=${3:?}; file=${4:?}
POINTS=${POINTS:-work/lm/data-study/sampler/runs/pool1/points.json}
MODELS=${MODELS:-$A/../../arm/models-pin}
cd /Users/davidlu/code/arc-workspace || exit 1
for t in $(cat "$file"); do
  [ -e "$A/$out/$t.done.json" ] && continue
  PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 PYTHONPATH=work/lm/data-study/sampler/fit-torch scripts/run_heavy.py --cpus 1 --need soon work/lm/data-study/ast/run/runtime-kaggle-py313/venv/bin/python -u "$A/../../arm/superdag_rel.py" --seconds "$sec" --policy "$pol" --models "$MODELS" --points "$POINTS" --out "$A/$out" "$t"
done
echo arm done
