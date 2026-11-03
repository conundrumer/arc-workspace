#!/bin/bash
# run_direct.sh KIT OUTDIR TASK SECONDS SEED
# One direct worker (kaggle_worker.py, no supervisor) on one task, with the joint arm's settings. It needs $PY (the python) and
# EXTRA_PATH (the arclog path) in the environment. A setting such as PROPOSER_MASK=1 or ALL_COUNTS=1 passes through the environment.
# OUTDIR gets the worker's files and log (worker.log); the search state goes to OUTDIR/store, so a run starts from no state.
set -u
KIT=$1; O=$2; T=$3; S=$4; SEED=$5
mkdir -p "$O" "$O/store"
touch "$O/beat"
S0=$KIT/model/study/sampler
cd "$KIT" || exit 1
env ARCLOG_IDENT_SOURCE=value P_DAG=1 ORDER_FREE=tie,key ARC_SESSION_SHARE=.9 SEARCH_LIMIT_SHARE=.65 ONE_REPAIR=30 CHOOSE_LIFT=0 SEARCH_LOG_VISITS=1 \
  SEARCH_GOLD2=$KIT/points-cheapest.json SEARCH_SCOPE_RULE=$KIT/scope/joint.py \
  ARC_GOLD=$KIT/points-eval.json PYTHONPATH=$S0:${EXTRA_PATH:-} ARC_MODELS=$KIT/models-tk ARC_POLICY=$KIT/policy POLICY_MODEL=$KIT/policy/policy_model.pkl \
  ARC_STORE=$O/store POOL_CLAUSES=search RAYON_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 \
  $PY -u "$S0/kaggle_worker.py" --task "$KIT/data/tasks/$T.json" --out "$O/$T.out.jsonl" --beat "$O/beat" --seconds "$S" --seed "$SEED" --rss-limit-mib 2888 --models "$KIT/models-tk" > "$O/worker.log" 2>&1
echo "exit $?"
