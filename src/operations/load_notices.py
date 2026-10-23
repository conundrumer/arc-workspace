"""The message to the coordinator on the runs a taken change states as
expected to load the machine, as `scripts/operate.py --help alerts` gives
it."""

from controlled_markdown import mctx
from operations.change_budget import taken
from operations.constants import COORDINATOR
from operations.handled import held_aside, sent_at
from operations.state import State, Ticket
from operations.steps import Send, Step
from ticketing.vocabulary import Kind, Status

HELP = mctx("""
    - Once an operator of the session takes a change whose ticket has a `## Load` section, `next` sends the coordinator one message that opens `Planned high load: change <number>` and gives each item of that section, once per take.
    """)
"""The part of `--help alerts` on these messages."""

HEAD = mctx("Planned high load: change {number}")
"""The opening of the message on a change, which tells whether it was sent."""


def held_with_load(t: Ticket, me: str) -> bool:
    """Whether `t` is a change that the operator `me` holds and that gives
    runs under `## Load`."""
    return (t.kind is Kind.CHANGE and t.status is Status.ASSIGNED and t.holder == me
            and bool(t.load))


def step(state: State) -> Step | None:
    """The first message on a held change's planned load that no operator
    sent since the change's take."""
    for t in sorted(state.tracker.tickets.values(), key=lambda t: t.order):
        take = taken(t)
        if take is None or not held_with_load(t, state.me):
            continue
        head = HEAD.format(number=t.number)
        step = Send(COORDINATOR, "\n".join([head, *t.load]), head, since=take.time)
        if not any(time > take.time for time in sent_at(state, COORDINATOR, step.message, head)) \
                and not held_aside(state, step):
            return step
    return None
