#!/bin/bash
# Arrays and live bits for the pool refit (item 18). A rerun resumes from scratch/chunks-NAME. Usage: features_dagc_pool_data.sh [fit|held|all] [SECONDS]
# fit-pool is two data sets, train and test tasks (the tune rows are the test tasks). fit-cut is the RULE forms of the fit tasks, seed 0. Each line is one process; the lines are independent.
D=$(cd "$(dirname "$0")" && pwd); E=$D/features_dagc_env.sh
cd "$D" || exit 1
W=${1:-all}; S=${2:-25}
if [ "$W" = fit ] || [ "$W" = all ]; then
  bash $E 1 features_dagc_pool_data.py fit-pool-train-off points-fit-pool.jsonl 'walks/fit-pool-off-*.jsonl.zst' --tasks train --seconds "$S"
  bash $E 1 features_dagc_pool_data.py fit-pool-test-off points-fit-pool.jsonl 'walks/fit-pool-off-*.jsonl.zst' --tasks test --seconds "$S"
  bash $E 1 features_dagc_data.py fit-cut-off points-fit-cut.jsonl 'walks/fit-cut-off-*.jsonl.zst' --seconds "$S"
fi
if [ "$W" = held ] || [ "$W" = all ]; then
  for P in held-pool held-wide held-parents; do
    bash $E 1 features_dagc_data.py $P-off points-$P.jsonl "walks/$P-off-*.jsonl.zst" --seconds "$S"
    bash $E 1 features_dagc_data.py --bits $P-live points-$P.jsonl "walks/$P-live-*.jsonl.zst"
  done
fi
