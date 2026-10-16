"""The monitor's steps, which the operator's command gives among its own
(`plan`): the alerts that go to a watched agent itself (`alerts.to_agent`),
once per occurrence of what fired, as `ALERTS`, which
`scripts/operate.py --help alerts` prints, gives them.

The watched agents are the agents whose work is open that an operator of
the session or the coordinator launched, other than an operator. `scripts/monitor_reads.py` reads each reading of a watched
agent from the running agents' listing and its transcript. The command
keeps no state of its own: an alert counts as sent where an operator sent
it after the occurrence it is on. A stall alert goes only to an agent that
`TranscriptsRead.stalled` leaves out."""

from collections.abc import Callable
from dataclasses import dataclass

from controlled_markdown import mctx
from operations.alerts import READING, REPEATS, AlertKind, to_agent
from operations.constants import STUCK_SECONDS
from operations.steps import Send, Step


@dataclass(frozen=True)
class Watched:
    """A watched agent at the time of the read.
    `over_budget` is whether its self time is past its budget. `stalled`
    is the time its turn ended where it stalled, as
    `stalled_at` in `scripts/monitor_reads.py` gives it, or None. `repeated` gives the time of the last call of each run
    of `REPEATS` or more identical Bash calls with identical results.
    `stuck` is the start of the stretch where it is stuck, as `stuck_at` in
    `scripts/monitor_reads.py` gives it, or None; it reaches the coordinator
    through `TranscriptsRead.stuck`, and no alert goes to the agent, since
    an agent that a system fault holds cannot act on that fault."""
    agent_id: str
    over_budget: bool
    stalled: float | None
    repeated: tuple[float, ...]
    stuck: float | None


@dataclass(frozen=True)
class MonitorState:
    """`stalled` gives the agents of `TranscriptsRead.stalled`."""
    watched: tuple[Watched, ...]
    stalled: frozenset[str]
    undecided: tuple[str, ...]
    """The lines on what the read of the state left unknown."""


def undecided(state: MonitorState) -> list[str]:
    """The lines on what the read of the state left unknown."""
    return list(state.undecided)


ALERTS = mctx("""
    - `next` sends an agent that an operator of the session or the coordinator launched, whose work is open and that is no operator, an alert that gives it its step, then holds the line `alert: <kind> <agent id>` on a line of its own, once for each time one of these fires:
        - `budget`: {budget}.
        - `repeated`: {repeated}, other than a command led by `: 'unattended-wait:`.
        - `stall`: {stall}.
    - The operator takes the final reply of a stalled agent as its report, sends the final reply of a stalled agent the coordinator launched to the coordinator once, and files a `bug` ticket on it.
    - The operator files a `bug` ticket on each resume of an operator of the session after the next operator of the session made its first entry, or writes a line in it.
        - A resume of an operator is a prompt that reached it after its turn ended and that no agent it launched or resumed sent.
    - The operator sends the coordinator once, and records in a `bug` ticket, each agent that an operator of the session or the coordinator launched that is stuck: no entry of its transcript, or of an agent under it, is less than {stuck_minutes} minutes old, or each of its Bash calls in those minutes repeats the call before it with the same result, a command led by `: 'unattended-wait:` included. The message gives the agent's own work that still runs. No alert goes to the agent.
    - An operator stops waiting on an agent or a holder that is stuck, and where nothing else holds it, gives its final reply with each such wait.
    """).format(stuck_minutes=STUCK_SECONDS // 60, **{k.value: READING[k] for k in AlertKind})
"""The alerts of `step`, which `scripts/operate.py --help alerts` gives."""


def alert(kind: AlertKind, w: Watched, since: float | None = None) -> Send:
    """The alert of `kind` on `w`, to `w` itself, sent after `since`."""
    return Send(w.agent_id, to_agent(kind, w.agent_id), since)


def budget_alert(w: Watched) -> Send:
    """The budget alert on `w`, to `w` itself."""
    return alert(AlertKind.BUDGET, w)


def alerts(state: MonitorState, w: Watched) -> list[Send]:
    """The alerts on `w`, one per reading that fired."""
    out: list[Send] = []
    if w.over_budget:
        out.append(budget_alert(w))
    out.extend(alert(AlertKind.REPEATED, w, t) for t in w.repeated)
    if w.stalled is not None and w.agent_id not in state.stalled:
        out.append(alert(AlertKind.STALL, w, w.stalled))
    return out


def step(state: MonitorState, handled: Callable[[Step], bool]) -> Step | None:
    """The monitor's next step, or None where none is ready, where
    `handled` holds for a step an operator already made."""
    for w in state.watched:
        for s in alerts(state, w):
            if not handled(s):
                return s
    return None
