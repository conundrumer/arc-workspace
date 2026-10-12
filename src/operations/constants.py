"""The values that both the operator's command and the scripts an agent
runs hold: the address of the coordinator, the interval of the keep-alive
timer, and the bound on a foreground Bash call's timeout. This module
imports nothing, so a hook loads it at no cost."""

COORDINATOR = "main"
"""The address SendMessage reaches the coordinator at, and the sender of
the main session's messages."""

WAIT_SECONDS = 272
"""The interval of the keep-alive timer: the 5-minute cache lifetime of an
agent's previous request, less the longest measured time past the interval
from that request to the agent's next one, 27.6 s."""

FOREGROUND_MS = 240000
"""The bound `scripts/pending_wait_hook.py` holds a subagent's foreground
Bash call's timeout to, and the timeout of each one the command prints."""
