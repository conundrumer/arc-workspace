"""The monitor's steps, which the operator's command gives among its own
(`plan`): the alerts that go to a watched agent itself (`alerts.to_agent`),
once per occurrence of what fired, as `ALERTS`, in the `--help` of
`scripts/operate.py`, gives them.

The watched agents are the agents an operator of the session launched whose
work is open. `scripts/operator_state.py` reads each reading of a watched
agent from the running agents' listing and its transcript. The command
keeps no state of its own: an alert counts as sent where an operator sent
it after the occurrence it is on. A stall alert goes only to an agent that
`State.stalled` leaves out."""

from collections.abc import Callable
from dataclasses import dataclass

from controlled_markdown import mctx
from operations.alerts import HUNG_FACTOR, READING, REPEATS, AlertKind, to_agent
from operations.steps import Send, Step


@dataclass(frozen=True)
class Watched:
    """A watched agent at the time of the read. `hung` is the time its oldest
    call in flight counted as hung (`hung_from`), or None where none has.
    `over_budget` is whether its active time is past its budget. `stalled`
    is the time its turn ended where it stalled, as `ALERTS` gives a
    stall, or None. `repeated` gives the time of the last call of each run
    of `REPEATS` or more identical Bash calls with identical results."""
    agent_id: str
    hung: float | None
    over_budget: bool
    stalled: float | None
    repeated: tuple[float, ...]


@dataclass(frozen=True)
class MonitorState:
    """`stalled` gives the agents of `State.stalled`."""
    watched: tuple[Watched, ...]
    stalled: frozenset[str]
    undecided: tuple[str, ...]
    """The lines on what the read of the state left unknown."""


def undecided(state: MonitorState) -> list[str]:
    """The lines on what the read of the state left unknown."""
    return list(state.undecided)


def hung_from(start: float, usual: float) -> float:
    """The time at which a call that began at `start`, with `usual` as its
    label's usual time, counts as hung."""
    return start + HUNG_FACTOR * usual


ALERTS = mctx("""
    - `next` sends an agent an operator of the session launched, whose work is open, an alert that gives it its step, then holds the line `alert: <kind> <agent id>` on a line of its own, once for each time one of these fires:
        - `budget`: {budget}.
        - `hung`: {hung}.
        - `repeated`: {repeated}, other than a command led by `: 'unattended-wait:`.
        - `stall`: {stall} since its parent's latest message to it, with no agent it launched and no command it backgrounded still running or ended after that turn ended, though the parent's transcripts hold an `assistant` entry timestamped after that turn ended, before which the harness delivers each report that waits for the parent. An agent whose transcript holds, after the latest message to it, a `SubagentHandback` result that says the harness delivered its report to its caller is not stalled.
    - The operator takes the final reply of a stalled agent as its report, and files a `bug` ticket on it.
    """).format(**{k.value: READING[k] for k in AlertKind})
"""The alerts of `step`, which the `--help` of `scripts/operate.py` gives."""


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
    if w.hung is not None:
        out.append(alert(AlertKind.HUNG, w, w.hung))
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
