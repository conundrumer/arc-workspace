"""The routing of a `delay` ticket that gives a case: the priced loss of a
case, the threshold of an editor, and the moves of
a ticket into and out of `tickets/watching/`. `file_ticket.py
case --help-all` states the rules. It also gives the spend of a change by
role, and the budget of a change taken over the changes like it."""

import re
import statistics
import time
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from agent_launches import runs_under
from agent_turns import first_time, last_time
from controlled_markdown import mctx
from operations.roles import Role
from operations.state import Budget, Spend
from run_reads import agent_type, run_entries
from ticket_files import ticket_files, ticket_name
from ticket_form import FRONT, front_fields, ticket_kind
from ticket_log import log_lines, log_moves, read_ticket, resolution_of
from ticket_numbers import TicketNumber
from ticket_reads import editors_field
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


def fix_field(text: str) -> Role | None:
    """The role the `fix` field of the front matter of the ticket text
    `text` gives, or None where it has none. Refuses a `fix` that is no
    role."""
    fix = front(text).get("fix")
    if fix is None:
        return None
    try:
        return Role(fix)
    except ValueError:
        raise Refused(mctx("`{fix}` is no role").format(fix=fix)) from None


def union_seconds(spans: list[tuple[float, float]]) -> float:
    total, end = 0.0, float("-inf")
    for a, b in sorted(spans):
        if b > end:
            total += b - max(a, end)
            end = b
    return total


def spend(runs: list[str], undecided: list[str]) -> Spend | None:
    """The spend of the runs `runs` and of the runs under them, or None
    where a run has no transcript, no price, no time or no agent type.
    Each transcript counts once, under the agent type of the nearest run
    of `runs` at or above it, so a run of `runs` launched under another
    keeps its own type."""
    trees: list[tuple[str, list[Path]]] = []
    for run in runs:
        try:
            top = find(run)
        except Refused:
            return None
        role = agent_type(top)
        if role is None:
            return None
        trees.append((role, [top, *runs_under(top)]))
    owner: dict[Path, tuple[int, str]] = {}
    for role, tree in trees:
        for p in tree:
            if p not in owner or len(tree) < owner[p][0]:
                owner[p] = (len(tree), role)
    total = 0.0
    spans: list[tuple[float, float]] = []
    by_role: dict[str, float] = {}
    for p, (_, role) in owner.items():
        cost = run_cost(run_entries(p), undecided)
        start, end = first_time(p), last_time(p)
        if cost is None or start is None or end is None:
            return None
        total += cost
        by_role[role] = by_role.get(role, 0.0) + cost
        spans.append((start, end))
    return Spend(total, union_seconds(spans), by_role)


def change_spend(path: Path, undecided: list[str]) -> Spend | None:
    """The spend of the `change` at `path`, closed `fixed`: that of the
    runs its closing line gives, or None where that line gives no run or
    `spend` gives none."""
    closing = [m for m in log_lines(read_ticket(path)) if m["status"] == Status.CLOSED
               and resolution_of(m["note"]) is Resolution.FIXED]
    runs = (closing[-1]["note"] or "").split()[3:] if closing else []
    return spend(runs, undecided) if runs else None


def closed_at(path: Path) -> float:
    return stamp_time(log_lines(read_ticket(path))[-1].group().split(" ", 1)[0])


def closed_changes(tickets: Path) -> Iterator[tuple[Path, str]]:
    """The path and text of each ticket under `tickets/closed/` of kind
    `change`."""
    for path in ticket_files(tickets, Status.CLOSED):
        text = read_ticket(path)
        if ticket_kind(text) is Kind.CHANGE:
            yield path, text


def threshold(tickets: Path, editor: Role, undecided: list[str]) -> float | None:
    """The median cost of the most recent `CHANGES` changes closed `fixed`
    with a known cost whose `editors` give `editor`, or None, with an
    `undecided` line, where fewer exist."""
    costs: list[float] = []
    for path, text in sorted(closed_changes(tickets), key=lambda c: closed_at(c[0]),
                             reverse=True):
        if editor not in (editors_field(front(text)) or ()):
            continue
        s = change_spend(path, undecided)
        if s is not None:
            costs.append(s.dollars)
        if len(costs) == CHANGES:
            return statistics.median(costs)
    undecided.append(mctx("threshold of `{editor}` unknown: {count} fixed changes with a known "
                          "cost, of the {changes} it is taken over").format(
                              editor=editor, count=len(costs), changes=CHANGES))
    return None


OVERRUN = 8
"""The multiple of the median of the changes like a change that is its
budget."""

FEWEST_LIKE = 5
"""The fewest earlier changes with the change's `editors` set that its
budget is taken over; with fewer, it is taken over every earlier one."""


def like_changes(tickets: Path, editors: frozenset[Role], before: float,
                 undecided: list[str]) -> list[Spend]:
    """The spend of each `change` closed `fixed` before `before` with a
    known spend whose `editors` set is `editors`, or of each such change
    whatever its `editors` where fewer than `FEWEST_LIKE` have it."""
    every: list[tuple[tuple[Role, ...] | None, Spend]] = []
    for path, text in closed_changes(tickets):
        if closed_at(path) >= before:
            continue
        s = change_spend(path, undecided)
        if s is not None:
            every.append((editors_field(front(text)), s))
    like = [s for e, s in every if e is not None and frozenset(e) == editors]
    return like if len(like) >= FEWEST_LIKE else [s for _, s in every]


def budget(tickets: Path, editors: frozenset[Role], before: float,
           undecided: list[str]) -> Budget | None:
    """The budget of a change with the `editors` set `editors` taken at
    `before`, or None, with an `undecided` line, where no earlier change
    has a known spend. A role with no run on a change spent nothing on
    it."""
    like = like_changes(tickets, editors, before, undecided)
    if not like:
        undecided.append(mctx("budget unknown: no change closed `fixed` before the take has a "
                              "known spend"))
        return None
    roles = sorted({r for s in like for r in s.by_role})
    return Budget(OVERRUN * statistics.median(s.dollars for s in like),
                  OVERRUN * statistics.median(s.seconds for s in like),
                  {r: statistics.median(s.by_role.get(r, 0.0) for s in like) for r in roles})


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
    fix = fix_field(read_ticket(path))
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
