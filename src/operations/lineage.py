"""The causes of a launch, and the hold on a launch whose chain of causes
runs `DEPTH` launches of its kind deep.

A launch is caused by each ticket its subject gives, and a launch that no
batch holds (`batches.follows`) by each member of the batch it follows. A
ticket of domain `agent` is caused by the launch of the agent its subject
gives. A chain ends at a cause that is no launch of the session's
operators, or whose agent id is unknown.

Two launches are of the same kind where they have the same role and, for
ticket analysts, the same purpose."""

from controlled_markdown import mctx
from operations import batches
from operations.directives import Decision, decided
from operations.roles import Purpose, Role, analyst_of, description, subjects
from operations.state import Agent, State
from operations.steps import Launch, Step, Undecided
from ticketing.vocabulary import Domain

DEPTH = 3
"""The number of launches of one kind, the held one counted, each caused
by the one before it, that holds a launch."""

CHOICES = {Decision.PASSES: mctx("print the launch")}

type Kind = tuple[Role, Purpose | None]


def kind(role: Role, subject: str) -> Kind:
    if role is not Role.TICKET_ANALYST:
        return role, None
    parsed = analyst_of(subject)
    return role, None if parsed is None else parsed[0]


def tickets(role: Role, subject: str) -> list[str]:
    """The words of `subject` that may be ticket numbers."""
    parsed = analyst_of(subject) if role is Role.TICKET_ANALYST else None
    return subjects(subject if parsed is None else parsed[1])


def causes(state: State, role: Role, subject: str, at: float) -> list[Agent]:
    """The launches of the session's operators, with a known agent id, that
    cause the launch of `role` on `subject` made at `at`."""
    if batches.follows(role, subject):
        found = batches.followed(state, at)
    else:
        found = [a for n in tickets(role, subject)
                 if (t := state.tickets.get(n)) is not None and t.domain is Domain.AGENT
                 for a in state.agents if a.agent_id == t.subject]
    return [a for a in found if a.agent_id is not None]


def chain(state: State, role: Role, subject: str, at: float, seen: frozenset[str],
          need: int) -> list[Agent]:
    """The longest chain, up to `need` launches, of causes of the kind of
    `role` on `subject`, each caused by the one after it, the first such
    chain in the order of `causes` where several are as long."""
    own = kind(role, subject)
    best: list[Agent] = []
    for a in causes(state, role, subject, at):
        if len(best) == need:
            break
        if a.agent_id in seen or kind(a.role, a.subject) != own:
            continue
        rest = chain(state, a.role, a.subject, a.launched, seen | {str(a.agent_id)}, need - 1)
        if len(rest) + 1 > len(best):
            best = [a, *rest]
    return best


def held(state: State, launch: Launch) -> Step:
    """`launch`, or, where its chain of causes runs `DEPTH` launches of
    its kind deep and no ruling lets it go on, the step held on it."""
    found = chain(state, launch.role, launch.subject, state.now, frozenset(), DEPTH - 1)
    if len(found) < DEPTH - 1:
        return launch
    links = "; ".join(mctx("agent {agent} on {subject}").format(agent=a.agent_id,
                                                                 subject=a.subject)
                      for a in found)
    what = mctx("the launch `{launch}` is caused by launches of its kind {depth} deep, the "
                "nearest first: {links}").format(
        launch=description(launch.role, launch.subject), depth=DEPTH, links=links)
    choice = decided(state, what, CHOICES)
    return choice if isinstance(choice, Undecided) else launch
