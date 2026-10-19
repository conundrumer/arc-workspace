"""The paths of links from a ticket (`paths`), and the mark of each ticket
on them, which gives why it does not move (`mark`), as
`scripts/operate.py --help alerts` gives them."""

from collections.abc import Mapping
from dataclasses import dataclass

from controlled_markdown import mctx
from operations import taking, unwaited
from operations.pacing import Pace
from operations.parties import Hold
from operations.state import State, Ticket
from operations.tracker import blocked_on_user, closed, exits
from ticketing.times import utc_stamp
from ticketing.vocabulary import UNTAKEN, Status


ON_USER = mctx("it waits on the user")
NO_STEP = mctx("it has had no step since {time}")


@dataclass(frozen=True)
class OnUser:
    since: float


@dataclass(frozen=True)
class NoStep:
    since: float


@dataclass(frozen=True)
class Unwaited:
    since: float


@dataclass(frozen=True)
class OnCycle:
    tickets: tuple[str, ...]
    """The tickets of the cycle in the order of its links, from the marked
    ticket on."""


@dataclass(frozen=True)
class InDraft:
    pass


@dataclass(frozen=True)
class NotRead:
    pass


@dataclass(frozen=True)
class Held:
    by: Hold
    pace: Pace | None = None
    """The pace, where `by` is `Hold.PACE`."""


type Mark = OnUser | NoStep | Unwaited | OnCycle | InDraft | NotRead | Held


def cycle(state: State, number: str) -> tuple[str, ...] | None:
    """The tickets of a cycle of links through `number`, in the order of
    its links from `number` on, or None where no chain of links leads from
    it back to it."""
    tickets = state.tracker.tickets
    back: dict[str, str] = {}
    todo = [number]
    while todo:
        t = tickets.get(todo.pop())
        if t is None:
            continue
        for d in taking.links(t):
            if d == number:
                out = [t.number]
                while out[-1] != number:
                    out.append(back[out[-1]])
                return tuple(reversed(out))
            if d not in back and not closed(state, d):
                back[d] = t.number
                todo.append(d)
    return None


def held(state: State, t: Ticket) -> Held | None:
    """The hold that keeps `t` back, where `t` is untaken, each ticket of
    its `depends-on` is closed, and the party an exit of it waits on
    (`unwaited.named`) is the usage pace or a line of the user."""
    if t.status not in UNTAKEN or not all(closed(state, d) for d in t.depends_on):
        return None
    for e in sorted(exits(state, t).by):
        if isinstance(p := unwaited.named(state, t, e), Hold):
            return Held(p, state.computed.pace if p is Hold.PACE else None)
    return None


def mark(state: State, number: str, stalls: Mapping[str, float]) -> Mark | None:
    """The mark of ticket `number`, with `stalls` as `ticket_stall.stalled`
    gives them."""
    t = state.tracker.tickets.get(number)
    if t is None:
        return NotRead()
    if blocked_on_user(t) is not None:
        return OnUser(taking.status_since(t))
    if number in stalls:
        return NoStep(stalls[number])
    if (since := unwaited.unwaited(state).get(number)) is not None:
        return Unwaited(since)
    if (c := cycle(state, number)) is not None:
        return OnCycle(c)
    if t.status is Status.DRAFT:
        return InDraft()
    return held(state, t)


@dataclass(frozen=True)
class Node:
    """A ticket of the paths, with its mark and the tickets its links
    reach, or, where `again`, a ticket expanded at an earlier place."""
    number: str
    mark: Mark | None
    below: tuple["Node", ...]
    again: bool = False


def paths(state: State, number: str, stalls: Mapping[str, float]) -> Node:
    """The paths of links from ticket `number`, with `stalls` as
    `ticket_stall.stalled` gives them."""
    seen: set[str] = set()

    def walk(n: str) -> Node:
        if n in seen:
            return Node(n, None, (), again=True)
        seen.add(n)
        t = state.tracker.tickets.get(n)
        below = () if t is None else tuple(walk(d) for d in taking.links(t) if not closed(state, d))
        return Node(n, mark(state, n, stalls), below)

    return walk(number)


def nodes(root: Node) -> list[Node]:
    """The nodes of the tree under `root`, `root` included, that are not
    `again`, in the order of the walk."""
    if root.again:
        return []
    return [root, *(n for b in root.below for n in nodes(b))]


def mark_text(m: Mark) -> str:
    """Why a ticket with mark `m` does not move."""
    match m:
        case OnUser(since):
            return mctx("{reason}, since {time}").format(reason=ON_USER, time=utc_stamp(since))
        case NoStep(since):
            return NO_STEP.format(time=utc_stamp(since))
        case Unwaited(since):
            return mctx("it waits on nothing that moves it, since {time}").format(
                time=utc_stamp(since))
        case OnCycle(tickets):
            return mctx("it stands on the cycle of links {cycle}").format(
                cycle=" → ".join([*tickets, tickets[0]]))
        case InDraft():
            return mctx("it stands under `tickets/draft/`")
        case NotRead():
            return mctx("the read of the tracker left it out")
        case Held(by):
            return mctx("{line} holds it").format(line=by.value)


def rendered(state: State, root: Node) -> str:
    """`root`'s tree as a nested list, a line per node: the ticket, its
    status and its mark, or, for a node `again`, the ticket alone."""
    lines: list[str] = []

    def put(node: Node, depth: int) -> None:
        indent = "    " * depth
        t = state.tracker.tickets.get(node.number)
        if node.again:
            lines.append(indent + mctx("- {number}, given above").format(number=node.number))
            return
        status = "" if t is None else f" (`tickets/{t.status.value}/`)"
        why = "" if node.mark is None else ": " + mark_text(node.mark)
        lines.append(f"{indent}- {node.number}{status}{why}")
        for b in node.below:
            put(b, depth + 1)

    put(root, 0)
    return "\n".join(lines)
