"""The `delay` tickets under `tickets/deferred/` that give a case: the
priced loss of a case, the threshold of an editor, the groups of the
deferred `delay` tickets, and the moves of their tickets into and out of
`tickets/deferred/`, whose rules `file_ticket.py case --help-all` states."""

import re
import statistics
import time
from dataclasses import dataclass
from pathlib import Path

from run_reads import run_entries
from spends import change_spend, closed_changes
from ticket_files import ticket_files, ticket_name
from ticket_form import bounds, check_fix, front, ticket_kind, title
from ticket_log import line_time, log_lines, log_moves, read_ticket
from ticket_numbers import TicketNumber
from token_prices import span_cost
from transcript_entries import epoch
from transcripts import find
from transcript_snapshots import Refused

from controlled_markdown import mctx
from operations.roles import Role
from ticketing.loss import CASE, Found, loss, rate
from ticketing.loss import cases as loss_cases
from ticketing.times import TIME_FORM, stamp_time
from ticketing.vocabulary import DEFECT_SECTIONS, Kind, Resolution, Status

_, EVIDENCE = DEFECT_SECTIONS

CHANGES = 10
"""The count of the most recent fixed changes an editor's threshold is the
median loss of."""


CAP = 100
"""The most `delay` tickets `tickets/deferred/` holds."""


@dataclass(frozen=True)
class Case:
    """A span of extra calls in a run, with its loss."""
    run: str
    start: str
    end: str
    dollars: float | None
    seconds: float

    @property
    def note(self) -> str:
        assert self.dollars is not None
        return CASE.format(run=self.run, start=self.start, end=self.end,
                           dollars=self.dollars, seconds=self.seconds)


def case_loss(run: str, start: str, end: str, undecided: list[str]) -> Case:
    """The case of the run `run` from `start` to `end`, times in
    `TIME_FORM`, with its dollars None where a request of the run has no
    price, with an `undecided` line for it. Refuses a span that starts
    before the run's first entry or ends after the time of the call."""
    try:
        begin, finish = stamp_time(start), stamp_time(end)
    except ValueError:
        raise Refused(mctx("a case's span is two times of the form `{form}`").format(form=TIME_FORM))
    if finish < begin:
        raise Refused(mctx("the span of the case ends before it starts"))
    entries = list(run_entries(find(run)))
    first = entries[0]["timestamp"]
    if begin < epoch(first) or finish > time.time():
        raise Refused(mctx("the case's span starts before the run's first entry at {first} "
                           "or ends after the time of the call").format(first=first))
    dollars = span_cost(entries, begin, finish, undecided)
    return Case(run, start, end, dollars, finish - begin)


def fix_field(text: str) -> Role | None:
    """The role the `fix` field of the front matter of the ticket text
    `text` gives, or None where it has none. Refuses a `fix` that is no
    editor."""
    fix = front(text).get("fix")
    if fix is None:
        return None
    check_fix(fix)
    return Role(fix)


def threshold(tickets: Path, editor: Role, undecided: list[str]) -> float | None:
    """The median loss of the most recent `CHANGES` changes closed `fixed`
    with a known cost whose `editors` give `editor`, or None, with an
    `undecided` line, where fewer exist."""
    losses: list[float] = []
    for c in sorted(closed_changes(tickets), key=lambda c: c.at, reverse=True):
        if editor not in (c.editors or ()):
            continue
        s = change_spend(c.path, undecided)
        if s is not None:
            losses.append(loss(s.dollars, s.seconds))
        if len(losses) == CHANGES:
            return statistics.median(losses)
    undecided.append(mctx("threshold of `{editor}` unknown: {count} fixed changes with a known "
                          "cost, of the {changes} it is taken over").format(
                              editor=editor, count=len(losses), changes=CHANGES))
    return None


def cases(text: str) -> list[Found]:
    """The cases of a ticket's log, whose text is `text`."""
    return loss_cases((line_time(m), m["note"] or "") for m in log_lines(text))


TARGET_PATH = re.compile(r"[\w.-]+(?:/[\w.-]+)+\.\w+")
"""A repository path in a title's target: slash-joined parts that end in
a file suffix."""


@dataclass(frozen=True)
class Group:
    """The key the deferred `delay` tickets that one change of one file by one
    editor would fix share: their `fix`, with the first repository path of
    their title's target, or the whole target where it gives none."""
    fix: Role
    target: str


def group_of(path: Path, text: str) -> Group:
    """The group of the deferred `delay` ticket at `path` with text `text`."""
    fix = fix_field(text)
    if fix is None:
        raise Refused(mctx("{path} gives no `fix`").format(path=path))
    head = title(path, text)
    if ": " not in head:
        raise Refused(mctx("the title of {path} is not of the form `<target>: <what is wrong "
                           "in it>`").format(path=path))
    target = head.split(": ", 1)[0]
    found = TARGET_PATH.search(target)
    return Group(fix, target if found is None else found.group())


@dataclass(frozen=True)
class Watched:
    """The tickets of a group under `tickets/deferred/`, with the time,
    the dollars and the seconds of each of their cases."""
    group: Group
    numbers: list[TicketNumber]
    found: list[Found]

    @property
    def loss(self) -> float:
        return sum(loss(d, s) for _, d, s in self.found)

    @property
    def named(self) -> str:
        return mctx("the group {target} of `{fix}`, tickets {numbers}").format(
            target=self.group.target, fix=self.group.fix,
            numbers=", ".join(str(n) for n in self.numbers))


def deferred(tickets: Path, kind: Kind) -> list[tuple[Path, str]]:
    """The path and text of each ticket of kind `kind` under
    `tickets/deferred/`, in the tracker's order."""
    texts = ((path, read_ticket(path)) for path in ticket_files(tickets, Status.DEFERRED))
    return [(path, text) for path, text in texts if ticket_kind(text) is kind]


def watched(tickets: Path) -> list[Watched]:
    """The groups of the `delay` tickets under `tickets/deferred/`, ordered
    by their `fix` and their target."""
    by: dict[Group, Watched] = {}
    for path, text in deferred(tickets, Kind.DELAY):
        group = group_of(path, text)
        w = by.setdefault(group, Watched(group, [], []))
        w.numbers.append(ticket_name(path).number)
        w.found.extend(cases(text))
    return [by[g] for g in sorted(by, key=lambda g: (g.fix.value, g.target))]


class Thresholds:
    """The threshold of each editor, taken once per call of the
    command."""

    def __init__(self, tickets: Path, undecided: list[str]) -> None:
        self.tickets = tickets
        self.undecided = undecided
        self.taken: dict[Role, float | None] = {}

    def __call__(self, editor: Role) -> float | None:
        if editor not in self.taken:
            self.taken[editor] = threshold(self.tickets, editor, self.undecided)
        return self.taken[editor]


def route(tickets: Path, agent: str, limits: Thresholds,
          own: TicketNumber | None) -> dict[TicketNumber, Path]:
    """Moves to `reopened` the tickets of the deferred groups as `file_ticket.py
    case --help-all` states, with `own` the ticket the call appends to, and
    returns the path each moved ticket went to."""
    moved: dict[TicketNumber, Path] = {}
    for w in watched(tickets):
        total, limit = w.loss, limits(w.group.fix)
        if limit is None:
            if own not in w.numbers:
                continue
            note = mctx("{group}: summed loss {total:.4f} dollars, the threshold of `{fix}` "
                        "unknown").format(group=w.named, total=total, fix=w.group.fix)
        elif total < limit:
            continue
        else:
            note = mctx("{group}: summed loss {total:.4f} dollars reaches the threshold "
                        "{limit:.4f} dollars of `{fix}`").format(
                            group=w.named, total=total, limit=limit, fix=w.group.fix)
        for number in w.numbers:
            moved[number] = log_moves(tickets, number, Status.REOPENED, agent, Status.DEFERRED,
                                      None, note).moved[0]
    return moved


def evict(tickets: Path, agent: str) -> None:
    """Closes `wontfix` each ticket of the deferred group with the lowest
    loss rate, where `tickets/deferred/` holds `CAP` `delay` tickets."""
    if len(deferred(tickets, Kind.DELAY)) < CAP:
        return
    now = time.time()

    def rate_of(w: Watched) -> float:
        if not w.found:
            raise Refused(mctx("{group} stands under `{deferred}` with no case").format(
                group=w.named, deferred=Status.DEFERRED))
        return rate(w.found, now)

    lowest = min(watched(tickets), key=rate_of)
    note = mctx("{wontfix}: {group} has the lowest loss rate under `{deferred}` at its cap of "
                "{cap}, its cases summing {total:.4f} dollars of loss").format(
                    wontfix=Resolution.WONTFIX, deferred=Status.DEFERRED, cap=CAP, group=lowest.named, total=lowest.loss)
    for number in lowest.numbers:
        log_moves(tickets, number, Status.CLOSED, agent, Status.DEFERRED, None, note)


def add_evidence(text: str, evidence: str) -> str:
    """`text` with `evidence` at the end of its `Evidence` section."""
    _, end = bounds(text, EVIDENCE)
    return f"{text[:end].rstrip(chr(10))}\n{evidence.strip(chr(10))}\n\n{text[end:].lstrip(chr(10))}"
