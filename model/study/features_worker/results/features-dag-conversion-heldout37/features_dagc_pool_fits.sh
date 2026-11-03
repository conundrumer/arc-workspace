#!/bin/bash
# The fits of item 18. Usage: features_dagc_pool_fits.sh ARM [PROCS]
#   pool           fit-pool train and test tasks (RULE picks), tuned on the test tasks of fit-pool
#   union          the same rows and fit-cut RULE
#   pool-control, union-control   the same rows with a label drawn from the offset
# The `parents` arm is the model of item 10 (features_dagc_perfits.sh hyb hyb gold, control: hyb control... see commands-items-11-19.txt): no fit here.
# Options are those of features_dagc_perfits.sh (level hyb). Fit rows: PS_FIT. Tune rows: PS_TUNE. No held task may stand in either, and perfit stops if one does.
D=$(cd "$(dirname "$0")" && pwd)
ARM=$1; P=${2:-4}
case "$ARM" in
  pool|pool-control) FIT=fit-pool-train-off,fit-pool-test-off;;
  union|union-control) FIT=fit-pool-train-off,fit-pool-test-off,fit-cut-off;;
  *) echo "ARM is pool, pool-control, union or union-control"; exit 1;;
esac
case "$ARM" in *control) LABEL=drawn;; *) LABEL=gold;; esac
export PS_FIT=$FIT PS_TUNE=fit-pool-test-off
exec bash "$D/features_dagc_perfits.sh" "$ARM" hyb "$LABEL" "$P"
