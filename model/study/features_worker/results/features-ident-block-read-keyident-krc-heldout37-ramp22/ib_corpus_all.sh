#!/bin/bash
# ib_corpus_all.sh N: N shard loops at once. Loop k runs ib_corpus.py --shard k/N again until R/corpus/rows-kofN.jsonl holds {"rec":"shard_done"}.
# Run through: bash ib_env.sh N ib_corpus_all.sh N
: "${IB_PY:?run through ib_env.sh}"
R="$IB_R"
N="${1:?usage: ib_corpus_all.sh N}"
loop() {
    k="$1"; f="$R/corpus/rows-${k}of${N}.jsonl"
    while true; do
        before=$(cat "$f" 2>/dev/null | wc -l)
        "$IB_PY" -u "$R/ib_corpus.py" --shard "$k/$N" 2>&1 | sed -u "s/^/[shard $k] /"
        if grep -q '"rec":"shard_done"' "$f" 2>/dev/null; then break; fi
        after=$(cat "$f" 2>/dev/null | wc -l)
        if [ "$after" -le "$before" ]; then echo "[shard $k] no progress, stopping" >&2; return 1; fi
    done
}
mkdir -p "$R/corpus"
pids=()
for ((k = 0; k < N; k++)); do
    loop "$k" &
    pids+=($!)
done
rc=0
for p in "${pids[@]}"; do wait "$p" || rc=1; done
echo "corpus shards finished, status $rc"
exit $rc
