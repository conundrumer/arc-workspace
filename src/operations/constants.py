"""The values that both the operator's command and the scripts an agent
runs hold: the address of the coordinator, the interval of the keep-alive
timer, the bound on a foreground Bash call's timeout, the bounds on
a call of the command's `next`, and the harness's limit of concurrent
subagents. This module
imports nothing, so a hook loads it at no cost."""

COORDINATOR = "main"
"""The address SendMessage reaches the coordinator at, and the sender of
the main session's messages."""

WAIT_SECONDS = 272
"""The interval of the keep-alive timer: the 5-minute cache lifetime of an
agent's previous request, less the longest measured time past the interval
from that request to the agent's next one, 27.6 s."""

STUCK_SECONDS = 1800
"""The bound on the time an agent may show no sign of progress before an
operator stops waiting on it and the coordinator hears of it
(`open_agents.quiet_since` in `scripts/open_agents.py`), or may repeat
its Bash calls with the same result (`stuck_at` in
`scripts/monitor_reads.py`)."""

FOREGROUND_MS = 240000
"""The bound `scripts/pending_wait_hook.py` holds a subagent's foreground
Bash call's timeout to, and the timeout of each one the command prints."""

BLOCK_SECONDS = (FOREGROUND_MS // 1000) - 30
"""The longest foreground block of the command's `next`, under the bound on
a foreground call, with room for the read of the state."""

LIMIT_SECONDS = (FOREGROUND_MS // 1000) - 20
"""The longest run of the command's `next` and `relay`, read of the state
included, under the bound on a foreground call, with room for the start
of the process: past it the caller has given up on the call."""

SUBAGENT_LIMIT = 20
"""The harness's limit of concurrent subagents, which the agents of a
session share: past it, an Agent call fails with `Concurrent subagent
limit reached`."""
