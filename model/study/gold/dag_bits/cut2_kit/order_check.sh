#!/bin/bash
# order_check.sh: runs gold_dagcut2_one.py with DAG_START_READ=1 on T and on T:a (the forms and atoms in another valid order) of 409aa875, 8f215267, 58f5dbd5, 4c3d4a41, 71e489b6 and 142ca369, one process at a time, then compares the rows.
# ETA about 8 minutes (12 runs of 5 to 90 s; 142ca369 reads a 53-bit form, so it is the longest). Rows and texts: orderchk/. Passes where the steps, the committed `after` figures and `program` are equal, or each difference is on a form with an OR and a `=` and is named.
# Run from any folder: bash order_check.sh
cd "$(dirname "$0")"
H=/Users/davidlu/code/arc-workspace/scripts/run_heavy.py
STEMS="409aa875 8f215267 58f5dbd5 4c3d4a41 71e489b6 142ca369"
mkdir -p orderchk
$H --cpus 1 --need soon bash gold_dagcut2_env.sh gold_dagcut2_ordertexts.py $STEMS || exit 1
for s in $STEMS; do
  for v in T A; do
    echo "$s $v $(date +%T)"
    DAG_START_READ=1 $H --cpus 1 --need soon bash gold_dagcut2_env.sh gold_dagcut2_one.py $s orderchk/lines-$s-$v.json 840 > orderchk/row-$s-$v.jsonl 2> orderchk/row-$s-$v.err
  done
done
python3 gold_dagcut2_cmp.py orderchk $STEMS
