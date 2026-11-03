#!/bin/bash
# mac99.sh: the stage dagcut2 on the 99 less the stems with an incomplete pod row (95), in 3 shards, with the start figures from ROWS/pod-all and the text of lines.json. A restart skips the stems that are done.
# ETA about 20 to 35 minutes (3 processes; each stem has 900 s and 8 GiB, so at most 45 minutes). Rows: mac99/out/rows-<k>.jsonl.
# After the run: the report (also against the first pass rows, outcut99 and outcut99-fix), the refit of the estimate (refit.json, which the kit build writes in the manifest), and the check stem for the kit (check-task.txt: the stem with a commit and the least cpu).
# Run from any folder: bash mac99.sh
cd "$(dirname "$0")"
H=/Users/davidlu/code/arc-workspace/scripts/run_heavy.py
V1=/Users/davidlu/code/arc-workspace/work/lm/data-study/gold/gold-v3-dag-bits
python3 gold_dagcut2_kit.py mac99 || exit 1
mkdir -p mac99/out
for k in 0 1 2; do
  $H --cpus 1 --need soon bash gold_dagcut2_env.sh gold_dagcut2_run.py mac99/tasks.txt lines.json mac99/weights.json mac99/base-rows.json mac99/out/rows-$k.jsonl $k 3 >> mac99/out/rows-$k.log 2>&1 &
done
wait
python3 gold_dagcut2_report.py 'mac99/out/rows-*.jsonl' --v1 "$V1/outcut99/rows-*.jsonl" "$V1/outcut99-fix/rows-*.jsonl" | tee mac99/report.txt
python3 gold_dagcut2_kit.py refit 'mac99/out/rows-*.jsonl'
python3 gold_dagcut2_kit.py choose 'mac99/out/rows-*.jsonl'
