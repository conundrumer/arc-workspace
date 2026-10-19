"""The messages to the coordinator on the concept faults the reports of the
solver passes that ended give, as `scripts/operate.py --help alerts` gives
them."""

from controlled_markdown import mctx
from operations.constants import COORDINATOR
from operations.handled import held_aside, sent, sent_with
from operations.roles import PASSES
from operations.state import Agent, State
from operations.steps import Send, Step

HELP = mctx("""
    - Once a solver pass that an operator of the session launched ends, and its report holds items under `## Concept faults`, `next` sends the coordinator one message on that pass with each of those items that no earlier such message gave.
    """)
"""The part of `--help alerts` on these messages."""

HEAD = mctx("The {role} pass {agent} on task {task} ended, and its report gives "
            "these claims of the concept, each with the form the program bans "
            "that it needs:")
"""The opening of the message on a pass, which tells whether it was sent."""


def ended(state: State) -> list[Agent]:
    """The solver passes with an agent id that ended, in the order of
    their launch."""
    return [a for a in state.transcripts.agents
            if a.role in PASSES and not a.pending and a.agent_id is not None]


def fault_key(item: str) -> str:
    """The part of a concept fault's item that names the fault: its task id
    and claim slug, before the colon, or the whole item where it has
    none."""
    return item.split(":", 1)[0].lstrip("-*+ ").strip()


def step(state: State) -> Step | None:
    """The first message on a pass's concept faults an operator has not
    sent."""
    for a in ended(state):
        report = state.transcripts.pass_reports.get(a.agent_id or "")
        if report is None or not report.faults:
            continue
        head = HEAD.format(role=a.role, agent=a.agent_id, task=a.subject)
        new = [i for i in report.faults if not sent_with(state, COORDINATOR, fault_key(i))]
        if not new:
            continue
        message = "\n".join([head, *new])
        step = Send(COORDINATOR, message, " ".join([head, *map(fault_key, new)]))
        if not sent(state, COORDINATOR, message, head) and not held_aside(state, step):
            return step
    return None
