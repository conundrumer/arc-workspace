#!/bin/bash
# newthread.sh <name> <request id> <brief file> [writable root ...]: creates the thread worktree and starts its first turn.
set -euo pipefail
code_dir=$(cd -- "$(dirname -- "$0")/.." && pwd)
repo=$(git -C "$code_dir" rev-parse --show-toplevel)
D="$(python3 "$code_dir/study_paths.py")/codex-adm"
n=$1; id=$2; brief=$3; shift 3
cwd=$(uv run --project "$repo" python "$repo/scripts/change_worktree.py" --name "$n")
roots=$(jq -nc --arg c "$cwd" --arg s "${D%/codex-adm}" '$ARGS.positional + [$c, $s]' --args "$@")
jq -nc --arg c "$cwd" --argjson id "$id" '{jsonrpc:"2.0",id:$id,method:"thread/start",params:{cwd:$c,approvalPolicy:"never",sandbox:"workspace-write"}}' > $D/in
t=
for i in $(seq 1 60); do
  t=$(tail -c 5000000 $D/out.ndjson | tail -n +2 | jq -r --argjson id "$id" 'select(.id==$id).result.thread.id // empty' 2>/dev/null | tail -1)
  [ -n "$t" ] && break; sleep 0.5
done
[ -n "$t" ] || { echo "no thread id for $n"; exit 1; }
echo "$t" > "$D/$n.thread"
jq -r '.[]' <<<"$roots" > "$D/$n.roots"
jq -nc --arg t "$t" --rawfile m "$brief" --argjson r "$roots" --argjson id "$((id+1))" '{jsonrpc:"2.0",id:$id,method:"turn/start",params:{threadId:$t,input:[{type:"text",text:$m}],sandboxPolicy:{type:"workspaceWrite",writableRoots:$r,networkAccess:false}}}' > $D/in
echo "$n $t"
