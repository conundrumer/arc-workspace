#!/bin/sh
# The command of `reader_update_hook.py`. Where the caller's record holds
# its tree's `HEAD` twice, the update gives nothing, so this exits before
# any Python starts: a hook on each call of a tool runs too often for a
# Python start on each. The record's path and its tree are those of
# `reader_commits.record_path` and `reader_commits.reader_tree`, which
# `tests/test_reader_commits.py` checks this reading against. Where this
# reading fails, the hook's Python runs.
input=$(cat)
fields=$(printf '%s' "$input" | jq -r '@sh "transcript=\(.transcript_path // "") agent=\(.agent_id // "") cwd=\(.cwd // "")"' 2>/dev/null) \
    && eval "$fields" && [ -n "$transcript" ] && {
    case $transcript in
        */subagents/*) session=${transcript%%/subagents/*} ;;
        *) session=${transcript%.jsonl} ;;
    esac
    if [ -z "$agent" ]; then
        record=$session/reader-commits/main tree=$CLAUDE_PROJECT_DIR
    else
        record=$(dirname "$session")/reader-commits/$agent tree=$cwd
    fi
    head=$(git -C "$tree" rev-parse HEAD 2>/dev/null) \
        && [ -f "$record" ] && [ "$(cat "$record")" = "$head
$head" ]
} && exit 0
printf '%s' "$input" | exec uv run --project "$CLAUDE_PROJECT_DIR" python "$CLAUDE_PROJECT_DIR/scripts/reader_update_hook.py" "$@"
