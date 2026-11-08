#!/bin/bash
# Fits one store with `softmax` and with `softmax-gpu` from the same settings, and compares the trees. Run it on a machine with a CUDA card, with a binary built by
# `cargo build --release --features gpu`:
#
#   compare_cpu_gpu.sh BIN SETTINGS.json OUT [ROUNDS]
#
# SETTINGS.json is a `softmax` settings file (the store is its `train`, `groups` and `labels`; its `out` is ignored). The store must have been built by block_store.py, which
# marks the categorical columns; this scans and compiles it if it holds no compiled.json. ROUNDS (default 25) replaces `max_rounds`.
#
# It writes OUT/cpu and OUT/gpu (each a `softmax` out folder, with model.jsonl and a log) and OUT/compare.txt. A fit whose trees hold categorical splits on the token id is the
# one to look at: in compare.txt the line `categorical splits` must show a count above 0 for both fits. The trees of the two fits are not bit-equal (the card sums in a changing
# order), so a first tree that differs at a near tie is allowed. What a GPU fit must show is the score agreement of work/lm/data-study/samples-r3x/fit/gpu-takeover.md, on the
# models of the two folders, exported with block_model_lgb.py.
set -eu
bin=$1; settings=$2; out=$3; rounds=${4:-25}
here=$(cd "$(dirname "$0")" && pwd)
compare="$here/../../../model/study/samples/block_model_compare.py"
store=$(python3 -c 'import json, sys; print(json.load(open(sys.argv[1]))["train"])' "$settings")
mkdir -p "$out"
if [ ! -f "$store/compiled.json" ]; then
  "$bin" scan "$store" && "$bin" compile "$store"
fi
for kind in cpu gpu; do
  python3 - "$settings" "$out/$kind.json" "$out/$kind" "$rounds" <<'EOF'
import json, sys
settings = json.load(open(sys.argv[1]))
settings.update(out=sys.argv[3], max_rounds=int(sys.argv[4]))
json.dump(settings, open(sys.argv[2], 'w'))
EOF
done
start=$(date +%s)
"$bin" softmax "$out/cpu.json" > "$out/cpu.log" 2>&1
middle=$(date +%s)
"$bin" softmax-gpu "$out/gpu.json" > "$out/gpu.log" 2>&1
end=$(date +%s)
{
  echo "rounds $rounds; cpu fit $((middle - start)) s, gpu fit $((end - middle)) s"
  for kind in cpu gpu; do
    echo "categorical splits $kind: $(grep -o '"categorical"' "$out/$kind/model.jsonl" | wc -l)"
  done
  if [ -f "$compare" ]; then
    python3 "$compare" "$out/cpu/model.jsonl" "$out/gpu/model.jsonl" --tol 1e-7 || true
  else
    echo "this checkout has no block_model_compare.py: compare $out/cpu/model.jsonl and $out/gpu/model.jsonl with it elsewhere"
  fi
} | tee "$out/compare.txt"
