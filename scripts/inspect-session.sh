#!/bin/bash
# inspect-session.sh — render session(s) for a meta session to inspect.
#
# Usage:
#   scripts/inspect-session.sh <session-id>   # inspect one session
#   scripts/inspect-session.sh                # inspect window since previous meta session
#
# Multi-session window: previous meta session (inclusive, identified by
# META SOLVER END in its last user message) + all solver sessions started
# after it (identified by SOLVER START in their first user message — which
# also matches META SOLVER START).

set -eu

PROJECT_DIR="$HOME/.claude/projects/-Users-davidlu-code-arc-workspace"
SOLVER_KEYWORD="SOLVER START"
META_END_KEYWORD="META SOLVER END"

render_session() {
  local file="$1"
  local sid first_ts last_ts
  sid=$(basename "$file" .jsonl)
  first_ts=$(jq -rc 'select(.timestamp) | .timestamp' "$file" | head -1)
  last_ts=$(jq -rc 'select(.timestamp) | .timestamp' "$file" | tail -1)

  echo "=== SESSION $sid ==="
  echo "Start: $first_ts"
  echo "End:   $last_ts"
  echo ""

  jq -rc '
    if .type == "user" and (.message.content | type == "string") then
      "USER: " + .message.content
    elif .type == "assistant" then
      .message.content[]? |
      if .type == "text" then "ASST: " + .text
      elif .type == "tool_use" then "TOOL " + .name
      else empty end
    else empty end
  ' "$file"

  echo ""
}

first_user_msg() {
  jq -rc 'select(.type == "user" and (.message.content | type == "string")) | .message.content' "$1" | head -1
}

last_user_msg() {
  jq -rc 'select(.type == "user" and (.message.content | type == "string")) | .message.content' "$1" | tail -1
}

if [ $# -eq 1 ]; then
  render_session "$PROJECT_DIR/$1.jsonl"
  exit 0
fi

# Multi-session mode: build chronologically sorted file list, find previous
# meta session boundary, render the window.
all_files=()
while IFS= read -r line; do
  all_files+=("${line#*|}")
done < <(
  for f in "$PROJECT_DIR"/*.jsonl; do
    [ -f "$f" ] || continue
    ts=$(jq -rc 'select(.timestamp) | .timestamp' "$f" | head -1)
    [ -n "$ts" ] && echo "$ts|$f"
  done | sort
)

prev_meta_idx=-1
for ((i=${#all_files[@]}-1; i>=0; i--)); do
  if last_user_msg "${all_files[i]}" 2>/dev/null | grep -q "$META_END_KEYWORD"; then
    prev_meta_idx=$i
    break
  fi
done

if [ "$prev_meta_idx" -ge 0 ]; then
  start_idx=$prev_meta_idx
else
  echo "(No previous META SOLVER END found; including all solver sessions.)" >&2
  start_idx=0
fi

for ((i=start_idx; i<${#all_files[@]}; i++)); do
  if first_user_msg "${all_files[i]}" 2>/dev/null | grep -q "$SOLVER_KEYWORD"; then
    render_session "${all_files[i]}"
  fi
done
