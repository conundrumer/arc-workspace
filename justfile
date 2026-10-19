_default:
    @just --list

# Start claude with the solver handbook in its system prompt. Arguments pass through.
session *args:
    uv run python scripts/claude.py {{args}}

# Start the console for batch solver work. Arguments pass through.
console *args:
    uv run python tools/console/server.py {{args}}

# Swap the two accounts between the console's Claude home and yours. Stop the console first.
swap:
    scripts/swap-accounts.sh

# Serve the ticket dashboard at port 8787 on this machine's Tailscale IPv4 address.
dashboard:
    uv run python scripts/ticket_dashboard.py "$(/Applications/Tailscale.app/Contents/MacOS/Tailscale ip -4)" 8787
