#!/bin/bash
# The held reads of item 18: each arm once on held-pool and held-wide, and union (and its control) once on held-parents. Each call of features_dagc_pread.py --held is one held read and appends to held-reads.jsonl.
# Run it once, after the fits and after features_dagc_pool_data.sh held. Usage: features_dagc_pool_reads.sh
D=$(cd "$(dirname "$0")" && pwd); E=$D/features_dagc_env.sh
cd "$D" || exit 1
for ARM in hyb control pool pool-control union union-control; do
  for P in held-pool held-wide; do
    bash $E 1 features_dagc_pread.py $ARM $P-off --live-bits scratch/bits-$P-live.npz --forms form-bits-dag.tsv --part $P --held
  done
done
for ARM in union union-control; do
  bash $E 1 features_dagc_pread.py $ARM held-parents-off --live-bits scratch/bits-held-parents-live.npz --forms form-bits-dag.tsv --part held-parents --held
done
bash $E 1 features_dagc_pool_summary.py
