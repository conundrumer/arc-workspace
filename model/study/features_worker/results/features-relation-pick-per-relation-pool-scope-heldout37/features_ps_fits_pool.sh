#!/bin/bash
# A refit with no fact of lexical order on non-held pool scope rows. Usage: features_ps_fits_pool.sh ARM pool|union|shuffled [gold|drawn] [PROCS]
# pool: rows of non-held forms with gold's parents plus a visit's forms. union: those and the parents and before rows of features_ps_fits.sh. shuffled: pool rows with the atoms in a random valid order.
# The tune rows are the non-held test rows of the same kind, read out of fold.
D=/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/9899b29d-4bf5-4cd3-9cdc-a669f9aea9b2/scratchpad/records/features-relation-pick-per-relation-pool-scope-heldout37
case "$2" in
  pool) export PS_FIT=fit-train-a,fit-train-b,fit-test PS_TUNE=fit-test;;
  union) export PS_FIT=train-before-0,train-before-1,train-before-2,test-before,fit-train-a,fit-train-b,fit-test PS_TUNE=fit-test;;
  shuffled) export PS_FIT=fit-train-shuffled,fit-test-shuffled PS_TUNE=fit-test-shuffled;;
esac
exec bash $D/features_ps_fits.sh "$1" "${3:-gold}" "${4:-4}"
