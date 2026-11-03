#!/bin/bash
set -euo pipefail
repo=/Users/davidlu/code/arc-workspace
data="$repo/work/lm/data-study"
revision=$(git -C "$repo" rev-parse "${1:?merged publisher commit}^{commit}")
publication=${2:?publication JSONL path (plain/gzip/framed zstd)}
output=${3:?new versioned corpus output directory}
ids=${4:-}
runtime=${5:-"$data/ast/run/runtime-b157cc37"}
tree="$repo/.claude/worktrees/gold-materialize-$revision"
if [ ! -d "$tree" ]; then git -C "$repo" worktree add --detach "$tree" "$revision"; fi
test "$(git -C "$tree" rev-parse HEAD)" = "$revision"
test -z "$(git -C "$tree" status --porcelain --untracked-files=no)"
python=$(/usr/bin/python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["python"])' "$runtime/ready.json")
args=(materialize --publication "$publication" --corpus "$repo/work/arclog-v2-det3/out/gen" --runtime "$runtime" --output "$output")
if [ -n "$ids" ]; then args+=(--task-ids "$ids"); fi
# No gold/table/FITS/OUT/mask evaluation is repeated. Case files are made only
# for missing tasks; completed tasks are hash-validated and reused. Prepared
# interrupted stages resume without regenerating their native case metadata.
export RAYON_NUM_THREADS=1
cd "$repo"
exec /usr/bin/python3 "$repo/scripts/run_heavy.py" --cpus 1 --need soon \
 "$python" -B "$tree/model/study/empty_gold_publication.py" "${args[@]}"
