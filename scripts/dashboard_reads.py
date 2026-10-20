"""The reads the ticket dashboard (`ticket_dashboard`) renders from: the
recorded states of the operators of each session, and of a ticket its phrase,
the change it waits on, whether it is the user's, the stage of the work
on it and the work on its change, from the change's log and the sessions'
step journals; and the time a usage window reaches 100% at its rate so far."""

import os
from collections import Counter
from collections.abc import Mapping, Sequence, Set
from dataclasses import dataclass
from enum import IntEnum
from pathlib import Path

from idle_sessions import live, named_main
from shown_state import Shown, ShownAgent, ShownParty, Start, shown_read
from step_journal import records
from ticket_numbers import indexed, indexes, parsed_number
from tree_reads import scratch

from operations.filing import files_of
from operations.journal import Outcome
from operations.pacing import WINDOW_SECONDS, Usage, WindowName
from operations.printed_forms import REPORT_SUFFIX
from operations.roles import BARE_BRIEFS, Role, described
from operations.state import Ticket, Tool
from operations.tracker import wait_line
from ticketing.vocabulary import COORDINATOR, Kind, Status

OPEN = frozenset(Status) - {Status.CLOSED, Status.DRAFT}
DAY = 86400.0

STALE_RECORD = 600.0
"""The age, in seconds, past which an operator's record reads as no
operator's read: a few minutes above the longest time between two full
reads of `operate.py next` (`operate_loop.FALLBACK_SECONDS`)."""


@dataclass(frozen=True)
class SessionRecord:
    """The record of a read of a session's operator, with the session's
    index, None where `ticket_numbers.indexes` gives the session none."""
    index: int | None
    shown: Shown


@dataclass(frozen=True)
class OperatorRecords:
    """The records the page is rendered from: the main session's first,
    then each other session's by index; and why the main session has none,
    where it has none."""
    records: tuple[SessionRecord, ...]
    main_missing: str | None

    def expedited(self) -> frozenset[str]:
        """The tickets any record gives as expedited."""
        return frozenset(n for r in self.records for n in r.shown.expedited)

    def agents(self) -> dict[str, list[ShownAgent]]:
        """The agents of every record, by the numbers of their tickets."""
        out: dict[str, list[ShownAgent]] = {}
        for r in self.records:
            for a in r.shown.agents:
                for n in a.tickets:
                    out.setdefault(n, []).append(a)
        return out

    def unwaited(self) -> dict[str, float]:
        """The tickets any record gives as waiting on nothing, each with
        the earliest time a record gives it."""
        out: dict[str, float] = {}
        for r in self.records:
            for n, at in r.shown.unwaited.items():
                out[n] = min(at, out.get(n, at))
        return out

    def starts(self) -> list[Start]:
        """The starts of the records in their order, each ticket once:
        unheld where any record gives it unheld, and otherwise with the
        hold of the record of its own session, or else of the first record
        that gives it, the main session's where that one does."""
        given: dict[str, list[tuple[int | None, ShownParty | None]]] = {}
        for r in self.records:
            for s in r.shown.starts:
                given.setdefault(s.number, []).append((r.index, s.held))
        out: list[Start] = []
        for n, holds in given.items():
            if any(h is None for _, h in holds):
                out.append(Start(n, None))
                continue
            number = parsed_number(n)
            own = None if number is None else number.session
            out.append(Start(n, next((h for i, h in holds if i is not None and i == own), holds[0][1])))
        return out


def operator_records(tickets: Path, now: float) -> OperatorRecords:
    """The records of the last reads of the operators of each session that
    `ticket_numbers.indexes` gives (`shown_state.write_shown`): the main
    session's, or why it has none; each other session's whose time is
    within `STALE_RECORD` of `now`, or whose session `idle_sessions.live`
    gives as live; and none of another session whose record is missing or
    does not parse."""
    ids = indexes(tickets)
    main = named_main(tickets)
    records: list[SessionRecord] = []
    missing: str | None = None
    if main is None:
        missing = "no main session is set (`file_ticket.py main`)"
    else:
        shown = shown_read(scratch(main))
        if isinstance(shown, str):
            missing = shown
        else:
            records.append(SessionRecord(indexed(ids, main), shown))
    for i in sorted(ids):
        for session in ids[i]:
            if session == main:
                continue
            shown = shown_read(scratch(session))
            if not isinstance(shown, str) and (now - shown.at <= STALE_RECORD or live(session, now)):
                records.append(SessionRecord(i, shown))
    return OperatorRecords(tuple(records), missing)


def served_request(t: Ticket, all_: Mapping[str, Ticket], seen: frozenset[str] = frozenset()) -> Ticket | None:
    """The first `request` the Motivation of `t` gives, followed through
    the `change` tickets it gives."""
    for m in t.motivation:
        r = all_.get(m)
        if r is None or m in seen:
            continue
        if r.kind is Kind.REQUEST:
            return r
        if r.kind is Kind.CHANGE and (found := served_request(r, all_, seen | {t.number, m})) is not None:
            return found
    return None


def phrase(t: Ticket, all_: Mapping[str, Ticket]) -> str:
    """The phrase of `t`: its Goal; else the Goal of `served_request`; else
    its title's text after its first `: `, up to its first `, ` or `;`,
    with its first letter capitalized."""
    r = served_request(t, all_)
    goal = t.goal if t.goal is not None else None if r is None else r.goal
    if goal is not None:
        return " ".join(goal.split())
    _, colon, after = t.title.partition(": ")
    cut = (after if colon else t.title).split(", ")[0].split(";")[0]
    return cut[:1].upper() + cut[1:]


def change_of(t: Ticket, all_: Mapping[str, Ticket]) -> Ticket | None:
    """The change the last wait line of `t`'s log gives, where the tracker
    holds it."""
    line = wait_line(t)
    return None if line is None or line.on_change is None else all_.get(line.on_change)


def users(t: Ticket, expedited: frozenset[str]) -> bool:
    """Whether `t` is the user's: the coordinator filed it, or it is
    expedited."""
    return t.filer == COORDINATOR or t.number in expedited


class Stage(IntEnum):
    """The stages of a ticket's work, in their order."""
    TRIAGE = 0
    DESIGN = 1
    BUILD = 2
    REVIEW = 3
    MERGE = 4


ROLE_STAGE: Mapping[Role, Stage] = {
    Role.TICKET_ANALYST: Stage.TRIAGE, Role.TRANSCRIPT_REVIEW: Stage.TRIAGE,
    Role.COST_AUDIT: Stage.TRIAGE, Role.LISTING_WAIT: Stage.TRIAGE, Role.OPERATOR: Stage.TRIAGE,
    Role.TICKET_REVIEWER: Stage.DESIGN, Role.DESIGN_REVIEWER: Stage.DESIGN,
    Role.CODE_EDITOR: Stage.BUILD, Role.DOC_EDITOR: Stage.BUILD, Role.HANDBOOK_EXPANDED: Stage.BUILD,
    Role.SOLVER_FIX: Stage.BUILD, Role.ANALYZE: Stage.BUILD, Role.CREATE: Stage.BUILD,
    Role.REFINE: Stage.BUILD,
    Role.ITEM_CHECKER: Stage.REVIEW, Role.CODE_REVIEWER: Stage.REVIEW, Role.DOC_REVIEWER: Stage.REVIEW,
    Role.LIB_REVIEWER: Stage.REVIEW, Role.GATE: Stage.REVIEW, Role.BATCH_PROFILE: Stage.REVIEW,
    Role.LOAD_CHECK: Stage.REVIEW,
    Role.AFTER_MERGE: Stage.MERGE,
}
"""The stage of the work an agent of each role does."""

assert set(ROLE_STAGE) == set(Role), "each role has a stage"


def stage(roles: list[Role], change: Ticket | None) -> Stage:
    """The stage of a ticket at whose work, or that of its change
    `change`, agents of `roles` are: the highest of theirs, and at least
    Design for a change in `tickets/draft/` and Build for a change past
    it."""
    floor = (Stage.TRIAGE if change is None or change.kind is not Kind.CHANGE
             else Stage.DESIGN if change.status is Status.DRAFT else Stage.BUILD)
    return max([floor, *(ROLE_STAGE[r] for r in roles)])


ROLES: Mapping[str, Role] = {r.value: r for r in Role}
"""Each role by the name a log line's bracket gives it."""


@dataclass(frozen=True)
class Work:
    """A piece of the work on a change: its time, its stage, and whether
    it finished."""
    at: float
    stage: Stage
    finished: bool


def log_work(change: Ticket) -> list[Work]:
    """The work the log of `change` records. A line is work of the stage
    `ROLE_STAGE` gives the role its bracket names, and the first line, the
    filing, is work of Triage, whoever filed it; a line whose bracket names
    no role is no work. A line finishes its work where it moves `change`
    to another status than the line before it left it in, as a review that
    approves a draft does, and the filing finishes its work."""
    out: list[Work] = []
    before: Status | None = None
    for i, ln in enumerate(change.log):
        role = ROLES.get(ln.agent)
        if i == 0 or role is not None:
            out.append(Work(ln.time, Stage.TRIAGE if role is None or i == 0 else ROLE_STAGE[role],
                            i == 0 or ln.status is not before))
        before = ln.status
    return out


def reports(names: Set[str], digest: str) -> int:
    """How many report files of the launches of the digest `digest` the
    names `names` of a session's `operator-files` hold, in the order of
    `filing.report_path`."""
    n = 0
    while f"{digest}{'' if n == 0 else f'-{n + 1}'}{REPORT_SUFFIX}" in names:
        n += 1
    return n


def journal_work(tickets: Path) -> dict[str, list[Work]]:
    """The launches of agents on changes that the step journal of each
    session `ticket_numbers.indexes` gives records (`step_journal.records`),
    by change number: each Agent call made or in flight whose description
    gives a role with a report file (`roles.described`,
    `roles.BARE_BRIEFS`), at the stage `ROLE_STAGE` gives that role,
    finished where its report file is written: the `k`-th such launch of a
    digest finishes with the `k`-th report file of that digest."""
    out: dict[str, list[Work]] = {}
    for session in (s for ids in indexes(tickets).values() for s in ids):
        found = records(scratch(session))
        files = files_of(scratch(session))
        names = set(os.listdir(files)) if found and files.is_dir() else set()
        launched: Counter[str] = Counter()
        for r in found:
            e = r.entry
            change = e.change
            d = None if e.tool is not Tool.AGENT or change is None else described(e.text)
            if change is None or d is None or d.role in BARE_BRIEFS or (
                    e.close is not None and e.close.outcome is Outcome.FAILED):
                continue
            launched[e.digest] += 1
            out.setdefault(change, []).append(
                Work(e.given, ROLE_STAGE[d.role], launched[e.digest] <= reports(names, e.digest)))
    return out


@dataclass(frozen=True)
class Logged:
    """Where the work on a change stands: the furthest stage of it, and
    whether the last work of that stage finished."""
    stage: Stage
    finished: bool


def logged(change: Ticket, work: Sequence[Work]) -> Logged | None:
    """Where the work on `change` stands, from the work its log records
    (`log_work`) and `work`, the other work on it, such as that of
    `journal_work`; None where there is none."""
    found: Logged | None = None
    for w in sorted([*log_work(change), *work], key=lambda w: w.at):
        if found is None or w.stage >= found.stage:
            found = Logged(w.stage, w.finished)
    return found


def hits_full(usage: Usage, name: WindowName) -> float | None:
    """The time the window `name` reaches 100% at its rate so far, where
    that is before its reset; None where the usage gives no such window or
    no use of it."""
    w = usage.windows.get(name)
    if w is None or w.used_pct <= 0:
        return None
    start = w.resets_at - WINDOW_SECONDS[name]
    if usage.now <= start:
        return None
    at = usage.now + (100 - w.used_pct) * (usage.now - start) / w.used_pct
    return at if at < w.resets_at else None
