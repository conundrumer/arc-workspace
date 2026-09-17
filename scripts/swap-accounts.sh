#!/usr/bin/env bash
# Swap the two Claude accounts between the console's Claude home and your own.
#
# Each home is logged into one account, kept in a keychain entry keyed by the
# home's path. The swap logs each home into the account the other one had.
# Every login runs in the browser, so the script waits before each one for
# you to make the right browser active. `just swap` runs this.
set -euo pipefail

CONSOLE="${CONSOLE_CLAUDE_HOME:-$HOME/.claude-console}"
MAIN="$HOME/.claude"
PORT="${CONSOLE_PORT:-8347}"

# `claude` under the given home. The main home is the CLI's default and must
# not be named through CLAUDE_CONFIG_DIR: the keychain entry of a home named
# that way carries a suffix, so it would be a different entry.
run() {
    local home="$1"; shift
    if [ "$home" = "$MAIN" ]; then
        env -u CLAUDE_CONFIG_DIR claude "$@"
    else
        CLAUDE_CONFIG_DIR="$home" claude "$@"
    fi
}

email() {
    run "$1" auth status --json 2>/dev/null \
        | python3 -c 'import json,sys
try: print(json.load(sys.stdin).get("email") or "")
except Exception: print("")' || true
}

show() {
    printf '  console  %-32s %s\n' "$CONSOLE" "${1:-not logged in}"
    printf '  yours    %-32s %s\n' "$MAIN" "${2:-not logged in}"
}

if curl -fs -o /dev/null --max-time 2 "http://127.0.0.1:$PORT/api/state"; then
    echo "The console is running on port $PORT. Its workers hold the current" >&2
    echo "account's token, so stop it first (ctrl-c in its terminal), then rerun." >&2
    exit 1
fi
sessions=$(pgrep -x claude | wc -l | tr -d ' ')
if [ "$sessions" != 0 ]; then
    echo "note: $sessions claude session(s) are running. One that refreshes its" >&2
    echo "token after the swap writes the old account back. Quit them first." >&2
fi

console_was=$(email "$CONSOLE")
main_was=$(email "$MAIN")
echo "Now:"
show "$console_was" "$main_was"
echo

login() {
    local home="$1" who="$2" want="$3"
    echo "Log $who ($home) in as ${want:-the other account}."
    read -r -p "Make that account's browser active, then press enter (ctrl-c aborts). "
    run "$home" auth login
    echo
}

login "$CONSOLE" console "$main_was"
login "$MAIN" yours "$console_was"

echo "After:"
show "$(email "$CONSOLE")" "$(email "$MAIN")"
echo
echo "Start the console again with \`just console\`."
