"""The reads the ticket dashboard (`ticket_dashboard`) renders from: the
recorded states of the operators of each session, live agents from their
transcripts, and of a ticket its phrase,
the change it waits on, whether it is the user's, the stage of the work
on it and the work on its change, from the change's log and the sessions'
step journals; the Codex weekly account limit from local rollouts; and the
time a usage window reaches 100% at its rate so far."""

import os
import re
import json
import math
import threading
import time
from collections import Counter
from collections.abc import Mapping, Sequence, Set
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from codex_rollout import rollout_files
from dashboard_stages import ROLE_STAGE, Stage
from idle_sessions import live, named_main
from open_agents import Listed, running_agents
from shown_state import Shown, ShownAgent, ShownParty, Start, shown_read
from step_journal import records
from ticket_form import section, section_head
from ticket_numbers import indexed, indexes, parsed_number
from tree_reads import scratch
from run_reads import read_meta, session_agents
from transcript_entries import epoch
from transcripts import chain, mains_named

from engine import checkout
from operations.filing import files_of
from operations.lineage import tickets as agent_tickets
from operations.journal import Outcome
from operations.pacing import WINDOW_SECONDS, Usage, WindowName
from operations.printed_forms import REPORT_SUFFIX
from operations.roles import BARE_BRIEFS, Role, described
from operations.state import Ticket, Tool
from operations.tracker import wait_line
from ticketing.vocabulary import COORDINATOR, Kind, Status

CLEARED_FILE = "dashboard-cleared"
"""The file, under `.cache/` of the main tree, that holds the time of the
newest event the user cleared from Updates."""

CLEAR_LOCK = threading.Lock()


def cleared() -> float:
    """The time the user cleared Updates up to; 0 where the file is missing
    or unreadable."""
    try:
        at = float((checkout.caches() / CLEARED_FILE).read_text())
    except (OSError, ValueError):
        return 0.0
    return at if math.isfinite(at) else 0.0


def clear(at: float) -> None:
    """Move the mark to `at`, unless it is already later. The write goes
    through a rename, so a reader sees the old value or the new one."""
    path = checkout.caches() / CLEARED_FILE
    with CLEAR_LOCK:
        if at <= cleared():
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(repr(at))
        os.replace(tmp, path)


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
    where it has none; with the live agent listing where supplied."""
    records: tuple[SessionRecord, ...]
    main_missing: str | None
    running: tuple[Listed, ...] | None = None

    def expedited(self) -> frozenset[str]:
        """The tickets any record gives as expedited."""
        return frozenset(n for r in self.records for n in r.shown.expedited)

    def agents(self) -> dict[str, list[ShownAgent]]:
        """The live agents by ticket, or the recorded agents where no live
        read was supplied."""
        out: dict[str, list[ShownAgent]] = {}
        agents = (tuple(a for r in self.records for a in r.shown.agents)
                  if self.running is None else
                  tuple(ShownAgent(d.role, x.launch.since, tuple(agent_tickets(d.role, d.subject)))
                        for x in self.running if (d := described(x.run.description)) is not None))
        for a in agents:
            for n in a.tickets:
                out.setdefault(n, []).append(a)
        return out

    def any_running(self) -> bool:
        """Whether an agent runs, including one with no ticket or known role."""
        return (any(r.shown.agents for r in self.records) if self.running is None
                else bool(self.running))

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


def operator_records(tickets: Path, now: float, undecided: list[str] | None = None,
                     live_agents: bool = True) -> OperatorRecords:
    """The records of the last reads of the operators of each session that
    `ticket_numbers.indexes` gives (`shown_state.write_shown`): the main
    session's, or why it has none; each other session's whose time is
    within `STALE_RECORD` of `now`, or whose session `idle_sessions.live`
    gives as live; and none of another session whose record is missing or
    does not parse; with the agents `open_agents.running_agents` gives
    under the indexed sessions and the main session, independently of
    those records and their ages. Where `live_agents` is false, running is
    None and the records supply the agents."""
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
    sessions = {s for names in ids.values() for s in names}
    if main is not None:
        sessions.add(main)
    notes = [] if undecided is None else undecided
    running = tuple(x for session in sorted(sessions) for path in mains_named(session)
                    for x in running_agents(path, notes)) if live_agents else None
    return OperatorRecords(tuple(records), missing, running)


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


ABOUT = {Kind.CHANGE: "Intent", Kind.REQUEST: "Goal", Kind.VALIDATION: None}
"""The section of each kind that says what its ticket is about, None where
the kind has none; every other kind has `Impact`."""


def about(t: Ticket, phrase: str) -> str | None:
    """The first sentence of the section of `t` that `ABOUT` gives, without
    backticks and its list mark; None where its kind or file has no such
    section, or where `phrase` already begins with that sentence."""
    name = ABOUT.get(t.kind, "Impact")
    try:
        text = t.path.read_text()
    except OSError:
        return None
    if name is None or section_head(text, name) is None:
        return None
    body = re.sub(r"^(?:- |\d+\. )", "", section(text, name).strip())
    first = re.split(r"\n|(?<=[.!?])\s+(?=[A-Z`])", body, maxsplit=1)[0]
    sentence = " ".join(first.replace("`", "").split())
    return None if not sentence or phrase.startswith(sentence) else sentence


def change_of(t: Ticket, all_: Mapping[str, Ticket]) -> Ticket | None:
    """The change the last wait line of `t`'s log gives, where the tracker
    holds it."""
    line = wait_line(t)
    return None if line is None or line.on_change is None else all_.get(line.on_change)


def users(t: Ticket, expedited: frozenset[str]) -> bool:
    """Whether `t` is the user's: the coordinator filed it, or it is
    expedited."""
    return t.filer == COORDINATOR or t.number in expedited


ROLES: Mapping[str, Role] = {**{r.value: r for r in Role}, "draft-analyst": Role.TICKET_ANALYST}
"""Each role by the name a log line's bracket gives it."""


@dataclass(frozen=True)
class Work:
    """A piece of the work on a change: its time, its stage, and whether
    it finished."""
    at: float
    stage: Stage
    finished: bool
    role: Role | None = None


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
                            i == 0 or ln.status is not before, None if i == 0 else role))
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


SUBAGENT_WORK: dict[Path, list[tuple[str, Work]]] = {}
"""The work `subagent_work` read from each agent's files, by the agent's
transcript path, for the life of the process: an agent's description and
first entry are written once, at its start."""


def subagent_work(main: Path) -> list[tuple[str, Work]]:
    """The agents under the session whose main transcript is `main`, as
    their `.meta.json` descriptions give them (`roles.described`), by the
    number of each ticket the launch serves, at the time of the first entry of
    its transcript. The journal holds no launch that an agent made, such
    as an editor's item checker. An agent whose description or first entry
    is not yet written is read again at the next call."""
    out: list[tuple[str, Work]] = []
    for path in session_agents(main.with_suffix("")).values():
        if path not in SUBAGENT_WORK:
            meta = read_meta(path)
            try:
                with open(chain(path)[0]) as f:
                    first = json.loads(f.readline()).get("timestamp")
            except (OSError, ValueError):
                first = None
            if meta is None or not first:
                continue
            d = described(meta.get("description", ""))
            SUBAGENT_WORK[path] = [] if d is None or d.role in BARE_BRIEFS else [
                (n, Work(epoch(first), ROLE_STAGE[d.role], True, d.role)) for n in agent_tickets(d.role, d.subject)]
        out.extend(SUBAGENT_WORK[path])
    return out


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
        for path in mains_named(session):
            for work in subagent_work(path):
                out.setdefault(work[0], []).append(work[1])
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
                Work(e.given, ROLE_STAGE[d.role], launched[e.digest] <= reports(names, e.digest), d.role))
    return out


@dataclass(frozen=True)
class Span:
    """A run of stages, `first` to `last`, that the work went through
    `passes` times."""
    first: Stage
    last: Stage
    passes: int


def spans(work: Sequence[Work]) -> list[Span]:
    """The runs of stages that `work` repeats, apart, in their order. Work
    at a lower stage than the work before it follows a result that asked for
    more, and adds a pass to the stages from the lower to the earlier one;
    runs that overlap are one run. Work of Triage counts only for a ticket
    analyst, whose revising of a draft follows a finding of Design; the
    operator's takes and releases are no pass, and work of Triage or Design
    after work of Build is none either."""
    steps: list[Work] = []
    for w in sorted(work, key=lambda w: w.at):
        past = any(x.stage >= Stage.BUILD for x in steps)
        if (w.stage > Stage.TRIAGE or w.role is Role.TICKET_ANALYST) and (w.stage >= Stage.BUILD or not past):
            steps.append(w)
    back = [(b.stage, a.stage) for a, b in zip(steps, steps[1:]) if b.stage < a.stage]
    out: list[Span] = []
    for first, last in sorted(back):
        if out and first <= out[-1].last:
            out[-1] = Span(out[-1].first, max(out[-1].last, last), out[-1].passes + 1)
        else:
            out.append(Span(first, last, 2))
    return out


def latest(work: Sequence[Work]) -> Work | None:
    """The newest of `work`."""
    return max(work, key=lambda w: w.at, default=None)


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


@dataclass(frozen=True)
class CodexWindow:
    """A weekly account observation, with its observation and reset times."""
    used_pct: float
    observed: float
    resets_at: float


def codex_window(row: Any) -> CodexWindow | None:
    """Read a weekly Codex account limit from a token_count event.

    Other limit identities, malformed observations and token totals give
    no account observation. The duration identifies the weekly window.
    """
    if not isinstance(row, dict) or row.get("type") != "event_msg":
        return None
    payload = row.get("payload")
    if not isinstance(payload, dict) or payload.get("type") != "token_count":
        return None
    limits = payload.get("rate_limits")
    if not isinstance(limits, dict) or limits.get("limit_id") not in (None, "codex"):
        return None
    try:
        at = datetime.fromisoformat(row["timestamp"])
        if at.tzinfo is None:
            return None
        observed = at.timestamp()
    except (KeyError, TypeError, ValueError, OverflowError):
        return None
    for key in ("primary", "secondary"):
        window = limits.get(key)
        if not isinstance(window, dict) or window.get("window_minutes") != 10080:
            continue
        used, reset = window.get("used_percent"), window.get("resets_at")
        if (not isinstance(used, (int, float)) or isinstance(used, bool)
                or not isinstance(reset, (int, float)) or isinstance(reset, bool)
                or not math.isfinite(used) or not math.isfinite(reset)
                or not 0 <= used <= 100 or not observed < reset <= observed + 604800):
            continue
        return CodexWindow(float(used), observed, float(reset))
    return None


@dataclass
class CodexSource:
    """The complete-line offset and latest weekly observation of one file."""
    identity: tuple[int, int]
    offset: int = 0
    latest: CodexWindow | None = None


class CodexLimits:
    """Incremental local account reads, serialized across HTTP threads.

    Discover rollouts at most once in 30 seconds. Read appended complete
    lines, and restart a file after replacement or truncation. An expired
    latest observation gives unavailable until another observation arrives.
    """
    def __init__(self, home: Path) -> None:
        self.home = home
        self.sources: dict[Path, CodexSource] = {}
        self.discover_at = 0.0
        self.lock = threading.Lock()

    def read(self, now: float) -> CodexWindow | None:
        with self.lock:
            tick = time.monotonic()
            if tick >= self.discover_at:
                paths = rollout_files(self.home)
                self.sources = {p: self.sources.get(p, CodexSource((0, 0))) for p in paths}
                self.discover_at = tick + 30
            for path, source in self.sources.items():
                try:
                    with path.open("rb") as stream:
                        stat = os.fstat(stream.fileno())
                        identity = (stat.st_dev, stat.st_ino)
                        if source.identity != identity or stat.st_size < source.offset:
                            source = CodexSource(identity)
                            self.sources[path] = source
                        stream.seek(source.offset)
                        while line := stream.readline():
                            if not line.endswith(b"\n"):
                                break
                            source.offset = stream.tell()
                            try:
                                found = codex_window(json.loads(line))
                            except (ValueError, UnicodeError):
                                continue
                            if found is not None and (source.latest is None
                                                      or found.observed >= source.latest.observed):
                                source.latest = found
                except OSError:
                    self.sources[path] = CodexSource((0, 0))
            latest = max((s.latest for s in self.sources.values()
                          if s.latest is not None and s.latest.observed <= now),
                         key=lambda w: (w.observed, w.resets_at, w.used_pct), default=None)
            return latest if latest is not None and now < latest.resets_at else None
