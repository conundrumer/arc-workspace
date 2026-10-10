"""The routing of a `delay` ticket that gives a case: the priced loss of a
case, the cost of a `change`, the threshold of an editor, and the moves of
a ticket into and out of `tickets/watching/`. `file_ticket.py
case --help-all` states the rules."""

import re
import statistics
import time
from dataclasses import dataclass
from pathlib import Path

from agent_launches import runs_under
from controlled_markdown import mctx
from run_reads import run_entries
from ticket_files import ticket_files, ticket_name
from ticket_form import FRONT, front_fields, list_items
from ticket_log import log_lines, log_moves, read_ticket, resolution_of
from ticket_numbers import TicketNumber
from ticketing.times import TIME_FORM, stamp_time
from ticketing.vocabulary import Kind, Resolution, Status
from token_prices import run_cost, span_cost
from transcripts import Refused, find

CHANGES = 10
"""The count of the most recent fixed changes an editor's threshold is the
median cost of."""

CAP = 30
"""The most tickets `tickets/watching/` holds."""

CASE = "case {run} {start} {end}: {dollars:.4f} dollars, {seconds:.0f} s"
"""The note of the log line that records a case."""

CASE_NOTE = re.compile(r"case (?P<run>\S+) (?P<start>\S+) (?P<end>\S+): "
                       r"(?P<dollars>[0-9.]+) dollars, (?P<seconds>[0-9]+) s")


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
    price, with an `undecided` line for it."""
    try:
        begin, finish = stamp_time(start), stamp_time(end)
    except ValueError:
        raise Refused(mctx("a case's span is two times of the form `{form}`").format(form=TIME_FORM))
    if finish < begin:
        raise Refused(mctx("the span of the case ends before it starts"))
    dollars = span_cost(run_entries(find(run)), begin, finish, undecided)
    return Case(run, start, end, dollars, finish - begin)


def front(text: str) -> dict[str, str]:
    head = re.match(FRONT, text)
    return {} if head is None else dict(front_fields(head))


def change_cost(path: Path, undecided: list[str]) -> float | None:
    """The cost of the `change` at `path`, closed `fixed`: the token cost
    of the runs its closing line gives and of the runs under them, or None
    where that line gives no run or a run has no transcript or no price."""
    closing = [m for m in log_lines(read_ticket(path)) if m["status"] == Status.CLOSED
               and resolution_of(m["note"]) is Resolution.FIXED]
    runs = (closing[-1]["note"] or "").split()[3:] if closing else []
    if not runs:
        return None
    total = 0.0
    for run in runs:
        try:
            top = find(run)
        except Refused:
            return None
        for p in [top, *runs_under(top)]:
            cost = run_cost(run_entries(p), undecided)
            if cost is None:
                return None
            total += cost
    return total


def closed_at(path: Path) -> float:
    return stamp_time(log_lines(read_ticket(path))[-1].group().split(" ", 1)[0])


def threshold(tickets: Path, editor: str, undecided: list[str]) -> float | None:
    """The median cost of the most recent `CHANGES` changes closed `fixed`
    with a known cost whose `editors` give `editor`, or None, with an
    `undecided` line, where fewer exist."""
    costs: list[float] = []
    for path in sorted(ticket_files(tickets, Status.CLOSED), key=closed_at, reverse=True):
        fields = front(read_ticket(path))
        if fields.get("kind") != Kind.CHANGE or editor not in list_items(fields.get("editors", "")):
            continue
        cost = change_cost(path, undecided)
        if cost is not None:
            costs.append(cost)
        if len(costs) == CHANGES:
            return statistics.median(costs)
    undecided.append(mctx("threshold of `{editor}` unknown: {count} fixed changes with a known "
                          "cost, of the {changes} it is taken over").format(
                              editor=editor, count=len(costs), changes=CHANGES))
    return None


def cases(text: str) -> list[tuple[float, float]]:
    """The time of each case line of a ticket's log, with its dollars."""
    out: list[tuple[float, float]] = []
    for m in log_lines(text):
        case = CASE_NOTE.fullmatch(m["note"] or "")
        if case:
            out.append((stamp_time(m.group().split(" ", 1)[0]), float(case["dollars"])))
    return out


def summed(path: Path) -> tuple[float, float]:
    """The summed dollars and seconds of the cases of the ticket at `path`."""
    text = read_ticket(path)
    seconds = sum(float(m["seconds"]) for line in log_lines(text)
                  if (m := CASE_NOTE.fullmatch(line["note"] or "")))
    return sum(d for _, d in cases(text)), seconds


def route(tickets: Path, number: TicketNumber, path: Path, agent: str,
          undecided: list[str]) -> Path:
    """Moves the watching ticket at `path` to `open` where its summed
    dollars reach the threshold of its `fix`, or where that threshold is
    unknown, and returns its path."""
    fix = front(read_ticket(path)).get("fix")
    if fix is None:
        raise Refused(mctx("{path} gives no `fix`").format(path=path))
    limit = threshold(tickets, fix, undecided)
    dollars, _ = summed(path)
    if limit is None:
        note = mctx("summed loss {dollars:.4f} dollars, the threshold of `{fix}` unknown").format(
            dollars=dollars, fix=fix)
        return log_moves(tickets, number, Status.OPEN, agent, Status.WATCHING, None, note).moved[0]
    if dollars < limit:
        return path
    note = mctx("summed loss {dollars:.4f} dollars reaches the threshold {limit:.4f} dollars "
                "of `{fix}`").format(dollars=dollars, limit=limit, fix=fix)
    return log_moves(tickets, number, Status.OPEN, agent, Status.WATCHING, None, note).moved[0]


def evict(tickets: Path, agent: str) -> None:
    """Closes `wontfix` the watching ticket with the lowest loss rate,
    where `tickets/watching/` holds `CAP` tickets."""
    watching = ticket_files(tickets, Status.WATCHING)
    if len(watching) < CAP:
        return
    now = time.time()

    def rate(path: Path) -> float:
        times = cases(read_ticket(path))
        if not times:
            raise Refused(mctx("{path} stands under `watching` with no case").format(path=path))
        return sum(d for _, d in times) / ((now - times[0][0]) / 86400)

    lowest = min(watching, key=rate)
    dollars, seconds = summed(lowest)
    number = ticket_name(lowest).number
    note = mctx("{wontfix}: the lowest loss rate under `watching` at its cap of {cap}, summed "
                "loss {dollars:.4f} dollars, {seconds:.0f} s").format(
                    wontfix=Resolution.WONTFIX, cap=CAP, dollars=dollars, seconds=seconds)
    log_moves(tickets, number, Status.CLOSED, agent, Status.WATCHING, None, note)


def add_evidence(text: str, evidence: str) -> str:
    """`text` with `evidence` at the end of its `## Evidence` section."""
    at = re.search(r"^## Evidence\n(?:(?!## ).*\n)*", text, re.MULTILINE)
    if at is None:
        raise Refused(mctx("the ticket has no `## Evidence` section"))
    body = at.group().rstrip("\n")
    return f"{text[:at.start()]}{body}\n{evidence.strip(chr(10))}\n\n{text[at.end():].lstrip(chr(10))}"
