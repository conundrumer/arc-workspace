#!/bin/bash
# Walks again the off parts of one shard whose rows have no `scope`. Old files go to walks-no-scope/. Usage: features_dagc_rewalk.sh I PART ...
I=$1; shift
D=$(cd "$(dirname "$0")" && pwd); E=$D/features_dagc_env.sh
cd "$D" || exit 1
mkdir -p walks-no-scope
for p in "$@"; do
    f=walks/$p-off-${I}of3.jsonl.zst
    [ -f "$f" ] && mv "$f" walks-no-scope/
    echo "$(date +%H:%M:%S) start rewalk $p shard $I/3" >> walk-logs/rewalk-$I.log
    bash "$E" 1 features_dagc_walk.py --part "$p" --steers off --content --shard "$I/3" >> "walk-logs/rewalk-$p-$I.log" 2>&1 || { echo "$(date +%H:%M:%S) FAILED $p" >> walk-logs/rewalk-$I.log; exit 1; }
    echo "$(date +%H:%M:%S) end rewalk $p" >> walk-logs/rewalk-$I.log
done
