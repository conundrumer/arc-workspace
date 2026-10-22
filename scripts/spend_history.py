"""Historical change spends and the budgets computed from them."""

import statistics
from dataclasses import dataclass
from pathlib import Path

import read_interrupts
from controlled_markdown import mctx
from operations.roles import Role
from operations.state import Budget, Spend
from spends import Recorded, change_spend, held_closed, recorded_spend
from state_reads import DERIVED, state_cache
from ticket_files import listed_tickets
from ticketing.vocabulary import Kind, Status
from transcript_snapshots import SUBJECT_FAULTS


@dataclass(frozen=True)
class Closed:
    """A ticket under `tickets/closed/` of kind `change`: its path, the
    roles its `editors` field gives (`ticket_reads.editors_field`), and the
    time of its last log line."""
    path: Path
    editors: tuple[Role, ...] | None
    at: float


@dataclass(frozen=True)
class SpendFault:
    """A closed change whose metadata or spend could not be read."""
    path: Path
    why: str


def closed_change(path: Path) -> Closed | None:
    """The closed change at `path`, or None for another ticket kind."""
    t = held_closed(path)
    return Closed(path, t.editors, t.last_time) if t.kind is Kind.CHANGE else None


@state_cache(DERIVED)
def closed_changes(tickets: Path) -> tuple[Closed, ...]:
    """Each ticket under `tickets/closed/` of kind `change`, as
    `ticket_reads.held_ticket` reads it."""
    out: list[Closed] = []
    for path in listed_tickets(tickets, Status.CLOSED):
        read_interrupts.checkpoint()
        if (c := closed_change(path)) is not None:
            out.append(c)
    return tuple(out)


@state_cache(DERIVED)
def closed_spends(tickets: Path) -> tuple[tuple[Closed, Recorded] | SpendFault, ...]:
    """Closed changes and their recorded spends, held by record revisions.
    A fault of a ticket or its spend is kept for the budget read to report."""
    out: list[tuple[Closed, Recorded] | SpendFault] = []
    for path in listed_tickets(tickets, Status.CLOSED):
        read_interrupts.checkpoint()
        try:
            c = closed_change(path)
            if c is not None:
                out.append((c, recorded_spend(path)))
        except SUBJECT_FAULTS as exc:
            out.append(SpendFault(path, str(exc)))
    return tuple(out)


OVERRUN = 8
"""The multiple of the median of the changes like a change that is its
budget."""


FEWEST_LIKE = 5
"""The fewest earlier changes with the change's `editors` set that its
budget is taken over; with fewer, it is taken over every earlier one."""


def like_changes(tickets: Path, editors: frozenset[Role], before: float,
                 undecided: list[str], me: str = "") -> list[Spend]:
    """The spend of each `change` closed `fixed` before `before` with a
    known spend whose `editors` set is `editors`, or of each such change
    whatever its `editors` where fewer than `FEWEST_LIKE` have it. A spend
    is in subscription dollars, Claude and Codex."""
    every: list[tuple[tuple[Role, ...] | None, Spend]] = []
    for item in closed_spends(tickets):
        read_interrupts.checkpoint()
        fault = item if isinstance(item, SpendFault) else None
        if fault is None:
            assert isinstance(item, tuple)
            c, _ = item
            if c.at >= before:
                continue
            try:
                s = change_spend(c.path, undecided)
            except SUBJECT_FAULTS as exc:
                fault = SpendFault(c.path, str(exc))
        if fault is not None:
            line = mctx("{run}: the budget calculation omits {path}: "
                        "its spend could not be read ({error})").format(
                            run=me, path=fault.path, error=fault.why)
            if line not in undecided:
                undecided.append(line)
            continue
        if isinstance(s, Spend):
            every.append((c.editors, s))
    like = [s for e, s in every if e is not None and frozenset(e) == editors]
    return like if len(like) >= FEWEST_LIKE else [s for _, s in every]


def budget(tickets: Path, editors: frozenset[Role], before: float,
           undecided: list[str], me: str = "") -> Budget | None:
    """The budget of a change with the `editors` set `editors` taken at
    `before`, or None, with an `undecided` line, where no earlier change
    has a known spend."""
    like = like_changes(tickets, editors, before, undecided, me)
    if not like:
        undecided.append(mctx("budget unknown: no spend is known for a change "
                              "closed `fixed` before the take"))
        return None
    return Budget(OVERRUN * statistics.median(s.dollars for s in like),
                  OVERRUN * statistics.median(s.seconds for s in like))
