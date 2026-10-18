"""A gate agent, on the gate's outputs, launches at any step
where a change merged since `occasions.opened` of the gate agents, none runs, and
the last launch of one stands at least `batches.BATCH_SPAN` back."""

from operations import briefs
from operations.batches import BATCH_SPAN
from operations.filing import scratch_dir
from operations.occasions import merged_since, next_number
from operations.state import State
from operations.steps import Launch, Step
from operations.unbatched import GATE


def gate(state: State) -> Step | None:
    """The launch of a gate agent, where one is due."""
    past = GATE.agents(state)
    since = merged_since(state, past)
    if since is None or (past and state.now - since < BATCH_SPAN):
        return None
    n = next_number(past)
    return Launch(GATE.role, n, briefs.gate(scratch_dir(f"gate-{n}", state.scratch)),
                  occasion=str(since))
