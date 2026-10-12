"""The resume of each agent of the session's operators that the usage limit
stopped (`state.Agent.limited`): once a reading of the limit made after
that stop gives it as lifted (`State.limit_lifted`), a message that asks
the agent to carry on its work. A step that sends it only after the stop's
time counts as made, so each stop gets one resume, and a later stop of the
resumed agent gets its own."""

from controlled_markdown import mctx
from operations.state import State
from operations.steps import Send, Step

RESUME = mctx("""
    - The usage limit stopped you, and it no longer stops calls.
    - Carry on your work from where it stopped.
    """)


def step(state: State) -> Step | None:
    lifted = state.limit_lifted
    if lifted is None:
        return None
    for a in state.agents:
        if a.agent_id is not None and a.limited is not None and lifted > a.limited:
            return Send(a.agent_id, RESUME, since=a.limited)
    return None
