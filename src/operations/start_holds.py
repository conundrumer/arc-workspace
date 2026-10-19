"""The hold of agent starts under the usage pace (`pacing`): past the pace,
each step that starts an agent's run (`starts_run`) is held, and so is
each such step while the pace admits work and the running agents of the
session's operators (`running`) number its cap or more (`hold`)."""

from collections.abc import Callable

from operations import pacing
from operations.constants import SUBAGENT_LIMIT
from operations.pacing import Capped, Pace, Until
from operations.state import State, Waits
from operations.steps import Launch, Send, Step


def past_pace(state: State) -> bool:
    """Whether `State.now` is past the usage pace (`Computed.pace`)."""
    return not pacing.admits(state.computed.pace, state.now)


def running(state: State) -> int:
    """The number of pending agents of the session's operators, which share
    the harness's limit of concurrent subagents."""
    return sum(a.pending for a in state.transcripts.agents)


def pace_cap(state: State) -> int | None:
    """The cap of the usage pace (`pacing.Until`), or None where it gives
    none."""
    match state.computed.pace:
        case Until(_, cap):
            return cap
        case _:
            return None


def limit(state: State) -> int:
    """The most agents of the session's operators that may run once a call
    of `next` has made its launches: the pace's cap where it gives one, and
    `SUBAGENT_LIMIT` otherwise."""
    cap = pace_cap(state)
    return SUBAGENT_LIMIT if cap is None else cap


def hold(state: State) -> Pace | Capped | None:
    """What holds agent starts at `State.now`: the pace where it is past,
    the pace's cap where the running agents number it or more, or None."""
    if past_pace(state):
        return state.computed.pace
    cap = pace_cap(state)
    return None if cap is None or running(state) < cap else Capped(cap)


def starts_run(state: State, step: Step) -> bool:
    """Whether `step` starts an agent's run: a launch, or a message to an
    agent of the operators whose run has ended or that the usage limit
    stopped (`Waits.LIMITED`)."""
    match step:
        case Launch():
            return True
        case Send(to):
            found = [a for a in state.transcripts.agents if a.agent_id == to]
            return bool(found) and found[-1].waits in (None, Waits.LIMITED)
        case _:
            return False


def pace_holds(state: State, starts: Callable[[], bool]) -> bool:
    """Whether the usage pace holds a step: something holds agent starts
    (`hold`) and the step starts an agent's run, as `starts` gives it
    (`starts_run`). `starts` runs only where something holds agent starts,
    so a step is computed only where the pace can hold it."""
    return hold(state) is not None and starts()
