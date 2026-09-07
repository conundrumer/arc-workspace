_default:
    @just --list

# Start claude with the solver handbook in its system prompt. Arguments pass through.
session *args:
    uv run python scripts/claude.py {{args}}

# Start the console for batch solver work. Arguments pass through.
console *args:
    uv run python tools/console/server.py {{args}}

# Swap the two accounts between your Claude home and the console's. Stop the console first.
swap:
    scripts/swap-accounts.sh
