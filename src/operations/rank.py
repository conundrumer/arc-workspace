"""The rank of an open change, in which the operators take open changes
(`taking.takeable`), the highest first, computed from the tracker at each
read and never written to a file. The tickets a change serves have a
standing of their own, from which the change takes its rank.

A ticket's class comes first, the lowest first:

- `SEND`: a `request` whose last route note (`vocabulary.ROUTED`) gives
  `op send`.
- `CASE`: a fault ticket (`FAULTS`) with a case: a case line of its own
  log, or of a ticket closed as its duplicate (`ticket_log.DUPLICATE_OF`).
- `RECURS`: a fault ticket with a recurrence and no case: a ticket closed
  as its duplicate, or a line of its log whose note opens with
  `Note.RECURS`.
- `OTHER`: each other ticket.
- `REFACTOR`: a `refactor` ticket with neither.

Within a class, the higher score first: for `RECURS`, the recurrences per
day since the first; for any other class, the loss rate of the ticket's
cases (`loss.rate`), divided, for a `change`, by the loss of its budget
(`Computed.budgets`), and a `change` whose budget `Computed.budgets` does
not give scores 0.

A `validation` ticket takes the class and the score of the request it
checks, which its subject gives. A `change` takes the class and the loss
rate of the best of the tickets from which a chain of links
(`taking.reached`) reaches it, and `OTHER` where none does.

A ticket's class moves one step toward the first for each `AGE_DAYS` days
since its last move into `tickets/open/`, never past the first. Within one
class and score, a ticket of the session's own index comes before one of
an adopted session, and then the tracker's order."""

from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from enum import IntEnum

from operations import taking
from operations.state import State, Ticket
from ticketing import loss
from ticketing.loss import Found
from ticketing.vocabulary import ROUTED, SETTLED, Kind, Note, Resolution, Route, Status

AGE_DAYS = 7

FAULTS = frozenset({Kind.INTERFERENCE, Kind.DELAY, Kind.BUG, Kind.PERFORMANCE, Kind.REFACTOR})
"""The kinds of a fault ticket."""


class Class(IntEnum):
    SEND = 0
    CASE = 1
    RECURS = 2
    OTHER = 3
    REFACTOR = 4


type Key = tuple[int, float, bool, tuple[int, int]]


@dataclass(frozen=True)
class Standing:
    """A ticket's class, before aging, and its loss rate or, in `RECURS`,
    its recurrences per day."""
    cls: Class
    rate: float


def route(t: Ticket) -> Route | None:
    """The route the last route note of `t`'s log gives."""
    for ln in reversed(t.log):
        if (m := ROUTED.match(ln.note)) is not None:
            return Route(m["route"])
    return None


def recurs(note: str) -> bool:
    return note.startswith(f"{Note.RECURS} ")


def duplicates(state: State) -> dict[str, list[Ticket]]:
    """The tickets closed as a duplicate of each ticket, by its number."""
    out: dict[str, list[Ticket]] = defaultdict(list)
    for t in sorted(state.tracker.tickets.values(), key=lambda t: t.order):
        if t.status is not Status.CLOSED:
            continue
        last = t.log[-1]
        if last.resolution is Resolution.DUPLICATE and last.duplicate_of is not None:
            out[last.duplicate_of].append(t)
    return out


def found(t: Ticket) -> list[Found]:
    return loss.cases((ln.time, ln.note) for ln in t.log)


def opened(t: Ticket) -> float:
    """The time of `t`'s last move into `tickets/open/`."""
    at = t.filed
    before: Status | None = None
    for ln in t.log:
        if ln.status is Status.OPEN and before is not Status.OPEN:
            at = ln.time
        before = ln.status
    return at


def ranking(state: State) -> Callable[[Ticket], Key]:
    """The sort key of the rank of each ticket of the tracker, the highest
    rank first."""
    dups = duplicates(state)
    served: dict[str, list[Ticket]] = defaultdict(list)
    for t in sorted(state.tracker.tickets.values(), key=lambda t: t.order):
        if t.kind is Kind.CHANGE or t.status in SETTLED:
            continue
        for n in taking.reached(state, {t.number}) - {t.number}:
            served[n].append(t)

    def own(t: Ticket) -> Standing:
        if t.kind is Kind.REQUEST:
            return Standing(Class.SEND if route(t) is Route.SEND else Class.OTHER, 0.0)
        if t.kind not in FAULTS:
            return Standing(Class.OTHER, 0.0)
        cases = [*found(t), *(c for d in dups.get(t.number, []) for c in found(d))]
        if cases:
            return Standing(Class.CASE, loss.rate(cases, state.now))
        times = [*(d.filed for d in dups.get(t.number, [])),
                 *(ln.time for ln in t.log if recurs(ln.note))]
        if times:
            return Standing(Class.RECURS, loss.per_day(len(times), min(times), state.now))
        return Standing(Class.REFACTOR if t.kind is Kind.REFACTOR else Class.OTHER, 0.0)

    def standing(t: Ticket) -> Standing:
        if t.kind is Kind.VALIDATION and (r := state.tracker.tickets.get(t.subject)) is not None:
            return own(r)
        if t.kind is not Kind.CHANGE:
            return own(t)
        return min((own(s) for s in served.get(t.number, [])),
                   key=lambda s: (s.cls, -s.rate), default=Standing(Class.OTHER, 0.0))

    def score(t: Ticket, s: Standing) -> float:
        if s.cls is Class.RECURS or t.kind is not Kind.CHANGE:
            return s.rate
        b = state.computed.budgets.get(t.number)
        return s.rate / loss.loss(b.dollars, b.seconds) if b is not None else 0.0

    def key(t: Ticket) -> Key:
        s = standing(t)
        aged = max(0, s.cls - int((state.now - opened(t)) // (AGE_DAYS * loss.DAY)))
        return (aged, -score(t, s), t.session != state.tracker.index, t.order)

    return key
