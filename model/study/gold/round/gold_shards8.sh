#!/bin/bash
# The new gold generation over a task list in parallel shards, smallest solvers first. Each shard publishes, materializes
# and writes the gold-only AST corpus chunk by chunk, so the outputs grow as it goes; each step resumes.
# A native evaluation past the deadline keeps the task's original gold; the round lists those tasks at the end.
# usage: gold_shards.sh <task list> <shards> <chunk> <deadline seconds>
set -uo pipefail
repo=/Users/davidlu/code/arc-workspace
data=$repo/work/lm/data-study
pad=/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/64993706-bdea-4acd-bcaf-7d7b1e3ea40a/scratchpad
rev=739797316
runtime=$data/ast/run/runtime-1636b082b
out=$repo/work/arclog-v2-det3/out
gen=$data/gold/gen-v10-det3
python=$runtime/venv/bin/python
tree=$repo/.claude/worktrees/gold-empty-$rev
list=$1; shards=$2; chunk=$3; deadline=$4
order=$(mktemp "$pad/order8.XXXXXX")
while read -r t; do echo "$(stat -f %z "$repo/programs/solvers/$t.dl" 2>/dev/null || echo 0) $t"; done < "$list" | sort -n | awk '{print $2}' > "$order"
shard() {
  k=$1; pub=$gen/publication-$k; mkdir -p "$pub"
  awk -v k="$k" -v n="$shards" 'NR % n == k' "$order" > "$pad/r8shard-$k.txt"
  split -l "$chunk" "$pad/r8shard-$k.txt" "$pad/r8shard-$k.part."
  for part in "$pad"/r8shard-$k.part.*; do
    args=(); while read -r t; do args+=(--task "$t"); done < "$part"
    cd "$repo"
    "$repo/scripts/run_heavy.py" --cpus 1 --need soon "$python" -B "$tree/model/study/empty_gold_publication.py" publish \
      --corpus "$out/gen" --tasks "$repo/data/tasks" --runtime "$runtime" --output "$pub/gold.jsonl.zst" "${args[@]}" \
      --deadline-seconds "$deadline" > "$pub/publish.log" 2>&1 || { echo "shard $k publish failed on $part"; tail -3 "$pub/publish.log"; }
    bash "$pad/materialize8.cmd" "$rev" "$pub/gold.jsonl.zst" "$gen/corpus-$k" "$part" "$runtime" > "$pub/materialize.log" 2>&1 || { echo "shard $k materialize failed on $part"; tail -3 "$pub/materialize.log"; }
    "$repo/.venv/bin/python" "$pad/check_excluded.py" "$gen/corpus-$k/gen" "$out/gen" || { echo "shard $k: excluded case files, stopping this shard"; return 1; }
    "$repo/.venv/bin/python" "$pad/gold_corpus.py" "$pub/gold.jsonl.zst" "$data/ast/run/corpus-v11" "$gen/ast-corpus" | tail -1
    mkdir -p "$gen/corpus/gen/cases"
    for f in "$gen/corpus-$k"/gen/*.arclog "$gen/corpus-$k"/gen/*.arcdata; do [ -e "$f" ] && ln -sf "$f" "$gen/corpus/gen/"; done
    for d in "$gen/corpus-$k"/gen/cases/*; do [ -e "$d" ] && ln -sfn "$d" "$gen/corpus/gen/cases/"; done
    echo "$(date +%T) shard $k: $(zstd -dc "$pub/gold.jsonl.zst" 2>/dev/null | wc -l) published"
  done
}
for k in $(seq 0 $((shards - 1))); do shard "$k" & done
wait
echo "$(date +%T) done; ast-corpus $(ls "$gen/ast-corpus" | wc -l) tasks"
for k in $(seq 0 $((shards - 1))); do zstd -dc "$gen/publication-$k/gold.jsonl.zst" 2>/dev/null; done | jq -r 'select(.result.selection=="original") | "\(.task)\t\(.result.reason[0:100])"' > "$gen/original.tsv"
echo "kept original gold: $(wc -l < "$gen/original.tsv") tasks, $(grep -ci deadline "$gen/original.tsv") by the deadline (list: $gen/original.tsv)"
