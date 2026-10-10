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
from operations.alerts import AlertKind, opening, to_agent
from operations.steps import Send, Step


REPEATS = 3
"""How many times in a row an agent runs the same Bash command with the same
result before it gets a `repeated` alert."""


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


HUNG_FACTOR = 10
"""How many times a call's usual time a call in flight runs before it
counts as hung, once. A call whose usual time no run gives takes
`steps.BLOCK_SECONDS` as its usual time."""


def hung_from(start: float, usual: float) -> float:
    """The time at which a call that began at `start`, with `usual` as its
    label's usual time, counts as hung."""
    return start + HUNG_FACTOR * usual


BUDGET_ALERT = mctx("Its active time is past its budget.")
REPEATED_ALERT = mctx("It ran the same Bash command with the same result at least "
                      "{repeats} times in a row.").format(repeats=REPEATS)
STALL_ALERT = mctx("Its turn ended while its work is open, and no report of it reached its "
                   "parent.")


ALERTS = mctx("- `next` sends an agent an operator of the session launched, whose work is "
              "open, an alert that gives it its step, then holds the line `alert: <kind> "
              "<agent id>` on a line of its own, once for "
              "each time one of these fires: its active time is past its budget (`budget`), "
              "a call of it in flight has run {factor} times its usual time (`hung`), it ran "
              "the same Bash command with the same result at least {repeats} times in a row, "
              "other than a command led by `: 'unattended-wait:` (`repeated`), or its turn "
              "ended while its work is open, with no agent it launched and no command it "
              "backgrounded still running, and no report of it reached its parent since its "
              "parent's latest message to it, though the parent's transcripts hold an "
              "`assistant` entry timestamped after that turn ended, before which the "
              "harness delivers each report that waits for the parent (`stall`). The "
              "operator takes the final reply of a stalled agent as its report, and files "
              "a `bug` ticket on it.").format(
                  factor=HUNG_FACTOR, repeats=REPEATS)
"""The alerts of `step`, which the `--help` of `scripts/operate.py` gives."""


HUNG_ALERT = mctx("A call of it in flight has run {factor} times its usual time.").format(
    factor=HUNG_FACTOR)


def alert(kind: AlertKind, w: Watched, text: str, since: float | None = None) -> Send:
    """The alert of `kind` on `w`, to `w` itself, sent after `since`."""
    return Send(w.agent_id, to_agent(kind, opening(kind, w.agent_id) + "\n\n" + text), since)


def budget_alert(w: Watched) -> Send:
    """The budget alert on `w`, to `w` itself."""
    return alert(AlertKind.BUDGET, w, BUDGET_ALERT)


def alerts(state: MonitorState, w: Watched) -> list[Send]:
    """The alerts on `w`, one per reading that fired."""
    out: list[Send] = []
    if w.over_budget:
        out.append(budget_alert(w))
    if w.hung is not None:
        out.append(alert(AlertKind.HUNG, w, HUNG_ALERT, w.hung))
    out.extend(alert(AlertKind.REPEATED, w, REPEATED_ALERT, t) for t in w.repeated)
    if w.stalled is not None and w.agent_id not in state.stalled:
        out.append(alert(AlertKind.STALL, w, STALL_ALERT, w.stalled))
    return out


def step(state: MonitorState, handled: Callable[[Step], bool]) -> Step | None:
    """The monitor's next step, or None where none is ready, where
    `handled` holds for a step an operator already made."""
    for w in state.watched:
        for s in alerts(state, w):
            if not handled(s):
                return s
    return None
