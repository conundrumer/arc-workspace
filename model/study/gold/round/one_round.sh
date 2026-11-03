#!/bin/bash
# Reconvert stems from master, gold them on the current runtime, and overlay what published into gen-v3.
# A stem with no gold stays out of gen-v3; an existing entry moves to replaced-round<n>/.
# usage: one_round.sh <round number> <stem>...
set -uo pipefail
n=$1; shift; stems=("$@")
repo=/Users/davidlu/code/arc-workspace
pad=/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/64993706-bdea-4acd-bcaf-7d7b1e3ea40a/scratchpad
data=$repo/work/lm/data-study
g3=$data/gold/gen-v3-11f6a212c
out=$repo/work/arclog-v2-r$n/out
gen=$data/gold/gen-r$n
runtime=runtime-${RUNTIME:-45de58e5c-b}
mkdir -p "$out"
cd "$repo"
if [ -z "${RESUME:-}" ]; then
PYTHONPATH=$pad/${ARCLOG_DIR:-arclog-45de} timeout 600 scripts/run_heavy.py --cpus 2 --need soon "$repo/.venv/bin/python" -m arclog_convert.convert --out "$out" "${stems[@]}" > "$pad/convert-r$n.log" 2>&1
echo "$(date +%T) convert exit $?"; grep -E "converted|skipped" "$pad/convert-r$n.log"
[ -n "${EDIT:-}" ] && "$repo/.venv/bin/python" "$EDIT" "$out/gen"
cd "$pad"
sed -e "s#\$repo/work/arclog-v2-det3/out#$out#g; s#gen-v10-det3#gen-r$n#g; s#order8#order-r$n#g; s#r8shard#rshard$n#g; s#materialize8#materialize-r$n#g; s#runtime-1636b082b#$runtime#g" gold_shards8.sh > "gold_shards-r$n.sh"
sed -e "s#\$repo/work/arclog-v2-det3/out#$out#g" -e "s#arclog-v2-det3/out#arclog-v2-r$n/out#g" materialize8.cmd > "materialize-r$n.cmd"
printf '%s\n' "${stems[@]}" > "ready-r$n.txt"
shards=$(( ${#stems[@]} < 3 ? ${#stems[@]} : 3 ))
timeout 2400 bash "gold_shards-r$n.sh" "ready-r$n.txt" "$shards" 1 240 > "gold-shards-r$n.log" 2>&1
echo "$(date +%T) gold exit $?"; grep -E "failed|kept original" "gold-shards-r$n.log" | tail -4 | cut -c1-200
fi
cd "$pad"
cut -c1-220 "$gen/original.tsv"
ok=(); for t in "${stems[@]}"; do [ -e "$gen/ast-corpus/$t" ] && ! grep -q "^$t	" "$gen/original.tsv" && ok+=("$t"); done
echo "to overlay: ${ok[*]:-none}"
[ -n "${PREP:-}" ] && { echo prepared; exit 0; }
[ ${#ok[@]} -gt 0 ] || exit 0
w=norm-r$n; rm -rf "$w"; mkdir -p "$w/gen/ast-corpus"
for t in "${ok[@]}"; do cp -R "$gen/ast-corpus/$t" "$w/gen/ast-corpus/$t"; done
NOCASES=1 timeout 300 "$repo/.venv/bin/python" norm.py extract "$w/gen" "$w/w" 1 | tail -1
timeout 1500 bash norm_run.sh "$w/w" 1
"$repo/.venv/bin/python" norm.py apply "$w/w" | tail -1
back=$g3/replaced-round$n; mkdir -p "$back/ast-corpus" "$back/ast-corpus.souffle-order" "$back/cases-links"
for t in "${ok[@]}"; do
  [ -e "$g3/ast-corpus/$t" ] && mv "$g3/ast-corpus/$t" "$back/ast-corpus/$t"
  [ -e "$g3/ast-corpus.souffle-order/$t" ] && mv "$g3/ast-corpus.souffle-order/$t" "$back/ast-corpus.souffle-order/$t"
  [ -L "$g3/corpus/gen/cases/$t" ] && echo "$t $(readlink "$g3/corpus/gen/cases/$t")" >> "$back/cases-links/old-links.txt"
  [ -d "$g3/corpus/gen/cases/$t" ] && [ ! -L "$g3/corpus/gen/cases/$t" ] && mv "$g3/corpus/gen/cases/$t" "$back/cases-links/$t"
  cp -R "$gen/ast-corpus/$t" "$g3/ast-corpus.souffle-order/$t"; cp -R "$w/gen/ast-corpus/$t" "$g3/ast-corpus/$t"
  for k in 0 1 2; do
    for f in "$gen/corpus-$k/gen/$t.arclog" "$gen/corpus-$k/gen/$t.arcdata"; do [ -e "$f" ] && ln -sf "$f" "$g3/corpus/gen/"; done
    d=$gen/corpus-$k/gen/cases/$t; [ -e "$d" ] && ln -sfn "$d" "$g3/corpus/gen/cases/"
  done
  echo "$t cases $(( $(ls "$g3/corpus/gen/cases/$t" 2>/dev/null | wc -l) / 2 ))"
  grep -v "^$t\$" "$g3/missing-from-ast-corpus.txt" > "$g3/m.tmp"; mv "$g3/m.tmp" "$g3/missing-from-ast-corpus.txt"
done
printf '%s\n' "${ok[@]}" > "$g3/overlaid-round$n-tasks.txt"; cp "$g3/overlaid-round$n-tasks.txt" "$g3/changed-gold-round$n.txt"
w=$(ls $data/ast/run/$runtime/wheels/*.whl | head -1)
printf '{"round": %s, "runtime": "%s", "wheel_engine": {"file": "%s", "sha256": "%s"}}\n' "$n" "$runtime" "$(basename "$w")" "$(shasum -a 256 "$w" | cut -d' ' -f1)" >> "$g3/wheel-engine.jsonl"
echo "$(date +%T) overlaid ${#ok[@]}; ast-corpus $(ls "$g3/ast-corpus" | wc -l), missing $(wc -l < "$g3/missing-from-ast-corpus.txt")"
timeout 1800 bash "$data/gold/gold-v3-helper-forms-a036da074/gold_stage_round.sh" "$n" "${ok[@]}" > "$pad/stage-cut-r$n.log" 2>&1; echo "$(date +%T) stage cut exit $?"; tail -1 "$pad/stage-cut-r$n.log"
timeout 1800 bash "$data/gold/gold-v3-cover-forms-a036da074/gold_cover_round.sh" "$n" "${ok[@]}" > "$pad/cover-round-r$n.log" 2>&1; echo "$(date +%T) cover stage exit $?"; tail -1 "$pad/cover-round-r$n.log"
timeout 3600 bash "$data/gold/gold-v3-combined-cut/gold_combined_round.sh" "$n" "${ok[@]}" > "$pad/combined-round-r$n.log" 2>&1; echo "$(date +%T) cut stages exit $?"; tail -1 "$pad/combined-round-r$n.log"
