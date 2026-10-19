"""The values that both the operator's command and the scripts an agent
runs hold: the address of the coordinator, the interval of the keep-alive
timer, the bound on a stretch with no progress, the bound on a foreground
Bash call's timeout, the bound on a Bash step the command runs itself,
the bounds on a call of the command's `next`, the
harness's limit of concurrent subagents, the waits of the step journal
(`journal.due`), and the cap on the rounds of each kind of review of a
built change. This module
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


def stuck_reached(since: float, now: float) -> bool:
    """Whether a stretch with no progress that started at `since` has
    reached `STUCK_SECONDS` at `now`."""
    return now - since >= STUCK_SECONDS

FOREGROUND_MS = 240000
"""The bound `scripts/pending_wait_hook.py` holds a subagent's foreground
Bash call's timeout to."""

RUN_SECONDS = 1200
"""The longest run of a Bash step the command runs itself
(`scripts/step_journal.py`): about three times the longest measured run
of `scripts/merge_change.py`, 391 s."""

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


AGAIN_SECONDS = 60
"""How long after a held change's step closed done `next` waits before it
gives that step once more, where the change's procedure still gives it
(`changes.step`): a read in that time may not yet show the step's
effect."""

BACKOFF_SECONDS = 60
"""The wait after the first launch in a row that the harness refused at
`SUBAGENT_LIMIT` (`journal.backoff`)."""

BACKOFF_CAP = 960
"""The longest wait after a launch the harness refused at
`SUBAGENT_LIMIT`."""

WAIT_SECONDS_IDLE = 300
"""How long an operator's calls of `next` in a row find no step ready
before it waits with its turn ended or gives its final reply for a wait
(`plan.next_step`), and the bound on the time from an operator's launch to
its end that counts the end as quick (`relay.next_step`)."""

WAIT_CAP = 1800
"""The longest run of the command's `wait`."""

REVIEW_ROUNDS = 3
"""The cap on the rounds of each kind of review of a built change since its
last move out of `tickets/draft/`."""


WAKE = "The coordinator recorded lines for the operators' command."
"""The whole text of each message of the coordinator's to an operator
launcher after `operate.py send` recorded its lines, and of the brief
the relay gives the next operator and a fresh operator launcher: a text
the command reads as no line (`directives.message_lines`), which ends
the block of `next` as any message does."""
