#!/bin/bash
# send.sh <name> <request id> <text>: steers the thread's running turn, or starts a turn if it is idle.
code_dir=$(cd -- "$(dirname -- "$0")/.." && pwd)
D="$(python3 "$code_dir/study_paths.py")/codex-adm"; t=$(cat $D/$1.thread 2>/dev/null)
[ -n "$t" ] || { echo "send.sh: no thread named $1; nothing sent. Threads: $(cd $D && ls *.thread | sed 's/\.thread$//' | tr '\n' ' ')" >&2; exit 1; }
last=$(tail -c 60000000 $D/out.ndjson | grep -F "$t" | grep -E '"method":"turn/(started|completed)"' | tail -1)
if [ "$(jq -r .method <<<"$last")" = "turn/started" ]; then
  jq -nc --arg t "$t" --arg e "$(jq -r .params.turn.id <<<"$last")" --arg m "$3" --argjson id $2 '{jsonrpc:"2.0",id:$id,method:"turn/steer",params:{threadId:$t,expectedTurnId:$e,input:[{type:"text",text:$m}]}}' > $D/in
else
  # <name>.roots lists the thread's writable roots, one per line; a turn started without them loses write access to its worktree.
  roots=null; [ -f $D/$1.roots ] && roots=$(jq -Rnc '[inputs|select(length>0)]' < $D/$1.roots)
  jq -nc --arg t "$t" --arg m "$3" --argjson id $2 --argjson r "${roots:-null}" '{jsonrpc:"2.0",id:$id,method:"turn/start",params:({threadId:$t,input:[{type:"text",text:$m}]} + (if $r then {sandboxPolicy:{type:"workspaceWrite",writableRoots:$r,networkAccess:false}} else {} end))}' > $D/in
fi
