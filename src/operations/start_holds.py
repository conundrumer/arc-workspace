"""The Claude usage pace holds, as `scripts/operate.py --help pace` gives them."""

from collections.abc import Callable

import re

from controlled_markdown import form
from operations import codex_mode, pacing
from operations.roles import CODEX_LAUNCHER, CODEX_LINE, CODEX_ROLES, launched_type
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
    """The harness capacity shared by all agents."""
    return SUBAGENT_LIMIT


CODEX_MARKER = re.compile("^" + form(CODEX_LINE, {
    "role": "(?P<role>[^`]+)", "model": "[^`]+", "effort": "[^`]+"}) + "$", re.MULTILINE)


def codex_wrapper(brief: str) -> bool:
    """Whether a recorded launch brief identifies a Codex wrapper."""
    return any(m["role"] in {r.value for r in CODEX_ROLES} for m in CODEX_MARKER.finditer(brief))


def claude_running(state: State) -> int:
    """The pending Claude workers, excluding recorded Codex wrappers."""
    return sum(a.pending and not codex_wrapper(a.brief) for a in state.transcripts.agents)


def admission_held(state: State) -> bool:
    """Whether the Claude pace prevents early ticket admission."""
    return not codex_mode.enabled() and past_pace(state)


def hold(state: State) -> Pace | Capped | None:
    """The current Claude pace hold, or None."""
    if past_pace(state):
        return state.computed.pace
    cap = pace_cap(state)
    return None if cap is None or claude_running(state) < cap else Capped(cap)


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


def claude_start(state: State, step: Step) -> bool:
    """Whether a step starts work subject to the Claude pace."""
    if isinstance(step, Launch):
        return launched_type(step.role, step.subject, step.model) != CODEX_LAUNCHER
    if isinstance(step, Send) and starts_run(state, step):
        target = next(a for a in reversed(state.transcripts.agents) if a.agent_id == step.to)
        return not codex_wrapper(target.brief)
    return False


def pace_holds(state: State, step: Callable[[], Step | None]) -> bool:
    """Whether the Claude pace holds the lazily computed step."""
    return hold(state) is not None and (s := step()) is not None and claude_start(state, s)
