_default:
    @just --list

# Start claude with the solver handbook in its system prompt. Arguments pass through.
session *args:
    uv run python scripts/claude.py {{args}}


# Serve the ticket dashboard at port 8787 on this machine's Tailscale IPv4 address.
dashboard:
    uv run python scripts/ticket_dashboard.py "$(/Applications/Tailscale.app/Contents/MacOS/Tailscale ip -4)" 8787
