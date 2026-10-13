"""The tickets under `tickets/deferred/` and the conditions they wait on.
The routing of a `delay` ticket that gives a case: the priced loss of a
case, the threshold of an editor, the groups of the deferred `delay`
tickets, and the moves of their tickets into and out of
`tickets/deferred/`, whose rules `file_ticket.py case --help-all` states.
The sweep of the deferred `request` tickets, whose rules `file_ticket.py
sweep --help-all` states. It also gives the spend of a change by role,
recorded under `tickets/spends/` once its runs have stopped, and the
budget of a change taken over the changes like it."""

import json
import os
import re
import signal
import statistics
import subprocess
import time
from collections.abc import Iterator
from dataclasses import asdict, dataclass
from pathlib import Path

from agent_launches import runs_under
from agent_turns import first_time, has_ended, last_time
from controlled_markdown import mctx
from engine import checkout
from engine.memo import write_whole
from operations.constants import FOREGROUND_MS
from operations.roles import Role
from operations.state import Budget, Spend
from run_reads import agent_type, run_entries
from ticket_files import ticket_files, ticket_name
from ticket_form import FRONT, check_fix, front_fields, section, ticket_kind, title
from ticket_log import VALIDATED, Moved, log_lines, log_moves, read_ticket, resolution_of
from ticket_numbers import TicketNumber
from ticket_reads import editors_field
from ticketing.text import VALIDATION
from ticketing.times import TIME_FORM, stamp_time, utc_stamp
from ticketing.vocabulary import Kind, Resolution, Status, Verdict
from token_prices import run_cost, span_cost
from transcripts import Refused, chain, entries_back, find

CHANGES = 10
"""The count of the most recent fixed changes an editor's threshold is the
median loss of."""

CAP = 100
"""The most `delay` tickets `tickets/deferred/` holds."""

SECOND_PRICE = 5 / 1800
"""The dollars a second of wall time is worth: the user's preference to
count about 30 minutes saved as worth about $5 of token cost
(`prompts/agents/notes/decisions.md`, The user's preferences)."""


def loss(dollars: float, seconds: float) -> float:
    """The loss of a spend of `dollars` of tokens and `seconds` of wall
    time, in dollars."""
    return dollars + seconds * SECOND_PRICE


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
    editor."""
    fix = front(text).get("fix")
    if fix is None:
        return None
    check_fix(fix)
    return Role(fix)


def union_seconds(spans: list[tuple[float, float]]) -> float:
    """The seconds the spans cover, counting an overlap once."""
    total, end = 0.0, float("-inf")
    for a, b in sorted(spans):
        if b > end:
            total += b - max(a, end)
            end = b
    return total


SPENDS = "spends"
"""The directory under `tickets/` that holds, for each change closed
`fixed` whose runs have all stopped, its spend as `change_spend` read it,
one JSON file per ticket number. It is no status directory, so no reader
of tickets takes a record for a ticket."""


def owners(runs: list[str]) -> dict[Path, str] | None:
    """The transcript of each of the runs `runs` and of the runs under them,
    with the agent type it counts under, or None where a run has no
    transcript or no agent type. Each transcript counts once, under the
    agent type of the nearest run of `runs` at or above it, so a run of
    `runs` launched under another keeps its own type."""
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
    return {p: role for p, (_, role) in owner.items()}


def priced(owner: dict[Path, str], undecided: list[str]) -> Spend | None:
    """The spend of the transcripts `owner` gives, each under its agent
    type, or None where one has no price or no time."""
    total = 0.0
    spans: list[tuple[float, float]] = []
    by_role: dict[str, float] = {}
    for p, role in owner.items():
        cost = run_cost(run_entries(p), undecided)
        start, end = first_time(p), last_time(p)
        if cost is None or start is None or end is None:
            return None
        total += cost
        by_role[role] = by_role.get(role, 0.0) + cost
        spans.append((start, end))
    return Spend(total, union_seconds(spans), by_role)


def spend(runs: list[str], undecided: list[str]) -> Spend | None:
    """The spend of the runs `runs` and of the runs under them, as `owners`
    and `priced` give it."""
    owner = owners(runs)
    return None if owner is None else priced(owner, undecided)


def stopped(path: Path) -> bool:
    """Whether the run at `path` does nothing until a message resumes it:
    it has ended its turn, or its last entry is an API error entry."""
    if has_ended(path):
        return True
    for p in reversed(chain(path)):
        for e in entries_back(p):
            return e.get("isApiErrorMessage") is True
    return False


def change_spend(path: Path, undecided: list[str]) -> Spend | None:
    """The spend of the `change` at `path`, closed `fixed`: that of the
    runs its closing line gives, or None where that line gives no run or
    `spend` gives none. A spend is recorded under `SPENDS` only once each
    run it read has stopped, since the spend of a run that goes on still grows."""
    record = path.parent.parent / SPENDS / f"{ticket_name(path).number}.json"
    if record.exists():
        return Spend(**json.loads(record.read_text()))
    closing = [m for m in log_lines(read_ticket(path)) if m["status"] == Status.CLOSED
               and resolution_of(m["note"]) is Resolution.FIXED]
    runs = (closing[-1]["note"] or "").split()[3:] if closing else []
    owner = owners(runs) if runs else None
    if owner is None:
        return None
    lines = len(undecided)
    s = priced(owner, undecided)
    if s is not None and len(undecided) == lines and all(stopped(p) for p in owner):
        record.parent.mkdir(exist_ok=True)
        write_whole(record, (json.dumps(asdict(s), sort_keys=True) + "\n").encode())
    return s


def line_time(line: re.Match[str]) -> float:
    """The time of a match of `ticket_log.LOG_LINE`."""
    return stamp_time(line.group().split(" ", 1)[0])


def closed_at(path: Path) -> float:
    return line_time(log_lines(read_ticket(path))[-1])


def closed_changes(tickets: Path) -> Iterator[tuple[Path, str]]:
    """The path and text of each ticket under `tickets/closed/` of kind
    `change`."""
    for path in ticket_files(tickets, Status.CLOSED):
        text = read_ticket(path)
        if ticket_kind(text) is Kind.CHANGE:
            yield path, text


def threshold(tickets: Path, editor: Role, undecided: list[str]) -> float | None:
    """The median loss of the most recent `CHANGES` changes closed `fixed`
    with a known cost whose `editors` give `editor`, or None, with an
    `undecided` line, where fewer exist."""
    losses: list[float] = []
    for path, text in sorted(closed_changes(tickets), key=lambda c: closed_at(c[0]),
                             reverse=True):
        if editor not in (editors_field(front(text)) or ()):
            continue
        s = change_spend(path, undecided)
        if s is not None:
            losses.append(loss(s.dollars, s.seconds))
        if len(losses) == CHANGES:
            return statistics.median(losses)
    undecided.append(mctx("threshold of `{editor}` unknown: {count} fixed changes with a known "
                          "cost, of the {changes} it is taken over").format(
                              editor=editor, count=len(losses), changes=CHANGES))
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


def cases(text: str) -> list[tuple[float, float, float]]:
    """The time of each case line of a ticket's log, with its dollars and
    its seconds."""
    out: list[tuple[float, float, float]] = []
    for m in log_lines(text):
        case = CASE_NOTE.fullmatch(m["note"] or "")
        if case:
            out.append((line_time(m), float(case["dollars"]),
                        float(case["seconds"])))
    return out


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
    found: list[tuple[float, float, float]]

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
    """Moves to `open` the tickets of the deferred groups as `file_ticket.py
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
            moved[number] = log_moves(tickets, number, Status.OPEN, agent, Status.DEFERRED,
                                      None, note).moved[0]
    return moved


def evict(tickets: Path, agent: str) -> None:
    """Closes `wontfix` each ticket of the deferred group with the lowest
    loss rate, where `tickets/deferred/` holds `CAP` `delay` tickets."""
    if len(deferred(tickets, Kind.DELAY)) < CAP:
        return
    now = time.time()

    def rate(w: Watched) -> float:
        if not w.found:
            raise Refused(mctx("{group} stands under `{deferred}` with no case").format(
                group=w.named, deferred=Status.DEFERRED))
        return w.loss / ((now - min(t for t, _, _ in w.found)) / 86400)

    lowest = min(watched(tickets), key=rate)
    note = mctx("{wontfix}: {group} has the lowest loss rate under `{deferred}` at its cap of "
                "{cap}, its cases summing {total:.4f} dollars of loss").format(
                    wontfix=Resolution.WONTFIX, deferred=Status.DEFERRED, cap=CAP, group=lowest.named, total=lowest.loss)
    for number in lowest.numbers:
        log_moves(tickets, number, Status.CLOSED, agent, Status.DEFERRED, None, note)


UNEXERCISED_DAYS = 7
"""The days since its last move into `deferred` from which a `request`
that no run exercised moves into `open`."""

COMMAND_SECONDS = 60
"""The seconds the sweep lets the command of a check run."""

SWEEP = "sweep"
"""The `<agent>` of the lines the sweep writes."""

EXERCISED_FIELD = "Exercised:"

COMMAND_FIELD = "Command:"

EXERCISED_LINE = re.compile(rf"^- {EXERCISED_FIELD} (?P<pattern>.+)$", re.MULTILINE)

COMMAND_LINE = re.compile(rf"^- {COMMAND_FIELD} `(?P<command>.+)`$", re.MULTILINE)

EXERCISED = mctx("{exercised}: {runs}")

UNEXERCISED = mctx("{unexercised}: no run matched since {time}")

EXITED = mctx("{failed}: {command} exited {code}")

TIMED_OUT = mctx("{failed}: {command} timed out")

UNREAD = mctx("{failed}: {reason}")

SWEEP_MARGIN = 30
"""The seconds of a sweep's Bash call kept for its work other than the
commands of checks."""


@dataclass(frozen=True)
class Check:
    """The check a `request`'s `Validation` section gives: the patterns of
    its `Exercised:` lines, and the command of its `Command:` line, None
    where it gives none."""
    patterns: tuple[re.Pattern[str], ...]
    command: str | None


def check_of(path: Path, text: str) -> Check:
    """The check of the request at `path` with text `text`. Refuses a
    section with more than one `Command:` line, or with a pattern that
    does not compile."""
    body = section(text, VALIDATION)
    commands = [m["command"] for m in COMMAND_LINE.finditer(body)]
    if len(commands) > 1:
        raise Refused(mctx("{path} gives more than one `{field}` line").format(
            path=path, field=COMMAND_FIELD))
    try:
        patterns = tuple(re.compile(m["pattern"]) for m in EXERCISED_LINE.finditer(body))
    except re.error as e:
        raise Refused(mctx("{path} gives an `{field}` pattern that does not compile: "
                           "{error}").format(path=path, field=EXERCISED_FIELD, error=e))
    return Check(patterns, commands[0] if commands else None)


@dataclass(frozen=True)
class GivenRun:
    """A run given to the sweep: the time of its first timestamped entry,
    and the lines of its transcripts."""
    start: float
    lines: list[str]


def given_run(run: str) -> GivenRun:
    """The run `run`, read once for the sweep. Refuses a run whose
    transcripts hold no timestamped entry."""
    path = find(run)
    start = first_time(path)
    if start is None:
        raise Refused(mctx("{run} has no timestamped entry").format(run=run))
    return GivenRun(start, [line for p in chain(path) for line in p.read_text().splitlines()])


def exercisers(check: Check, runs: dict[str, list[str]]) -> list[str] | None:
    """The runs of `runs`, by agent id with the lines of their transcripts,
    that exercise `check`, each of them where it gives no pattern, or None
    where `runs` is empty or no run matches a pattern it gives."""
    if not runs:
        return None
    if not check.patterns:
        return list(runs)
    by = [run for run, lines in runs.items()
          if any(p.search(line) for p in check.patterns for line in lines)]
    return by or None


def deferred_since(path: Path, text: str) -> float:
    """The time of the last line of the log of the ticket at `path` with
    text `text` that moves it into `deferred`."""
    lines = log_lines(text)
    moves = [m for i, m in enumerate(lines) if m["status"] == Status.DEFERRED
             and (i == 0 or lines[i - 1]["status"] != Status.DEFERRED)]
    if not moves:
        raise Refused(mctx("{path} has no log line that moves it into `{deferred}`").format(
            path=path, deferred=Status.DEFERRED))
    return line_time(moves[-1])


def run_command(command: str) -> tuple[Status, str]:
    """Runs the command of a check from the main tree, and gives the status
    its request moves into, with the note of that line. The command runs in
    a session of its own, so that its whole process group ends at the
    timeout."""
    with subprocess.Popen(command, shell=True, cwd=checkout.main_worktree(checkout.ROOT),
                          env=checkout.tree_env(), stdin=subprocess.DEVNULL,
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                          start_new_session=True) as process:
        try:
            code = process.wait(COMMAND_SECONDS)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
            return Status.OPEN, TIMED_OUT.format(failed=Verdict.FAILED, command=command)
    if code == 0:
        return Status.CLOSED, f"{VALIDATED} {command}"
    return Status.OPEN, EXITED.format(failed=Verdict.FAILED, command=command, code=code)


class OutOfTime(Exception):
    """The sweep has no time left to run the command of a check within its
    Bash call."""


def judged(path: Path, text: str, runs: dict[str, GivenRun], now: float,
           deadline: float) -> tuple[Status, str] | None:
    """The status the deferred request at `path` with text `text` moves
    into at a sweep at `now` of the runs `runs`, with the note of that
    line, or None where it stays. Raises `OutOfTime` where its command
    would run past `deadline`, a `time.monotonic` time."""
    check = check_of(path, text)
    since = deferred_since(path, text)
    by = exercisers(check, {run: given.lines for run, given in runs.items()
                            if given.start >= since})
    if by is not None and check.command is not None:
        if time.monotonic() + COMMAND_SECONDS > deadline:
            raise OutOfTime
        return run_command(check.command)
    if by is not None:
        return Status.OPEN, EXERCISED.format(exercised=Verdict.EXERCISED,
                                             runs=" ".join(by))
    if now - since < UNEXERCISED_DAYS * 86400:
        return None
    return Status.OPEN, UNEXERCISED.format(unexercised=Verdict.UNEXERCISED, time=utc_stamp(since))


def sweep(tickets: Path, runs: list[str], undecided: list[str]) -> list[Path]:
    """Moves each `request` under `tickets/deferred/` as `file_ticket.py
    sweep --help-all` states, then routes the deferred groups as `route`
    does, and returns the path each moved ticket went to."""
    deadline = time.monotonic() + FOREGROUND_MS / 1000 - SWEEP_MARGIN
    given = {run: given_run(run) for run in runs}
    now = time.time()
    moved: list[Path] = []
    for path, text in deferred(tickets, Kind.REQUEST):
        try:
            move = judged(path, text, given, now, deadline)
        except OutOfTime:
            undecided.append(mctx("{path}: the command of its `{field}` line did not run, with no time "
                                  "left in the sweep's Bash call, and the next sweep runs it").format(path=path, field=COMMAND_FIELD))
            continue
        except Moved:
            continue
        except Refused as e:
            move = Status.OPEN, UNREAD.format(failed=Verdict.FAILED, reason=e)
        if move is None:
            continue
        try:
            moved += log_moves(tickets, ticket_name(path).number, move[0], SWEEP,
                               Status.DEFERRED, None, move[1]).moved
        except Moved:
            continue
    return moved + list(route(tickets, SWEEP, Thresholds(tickets, undecided), None).values())


def add_evidence(text: str, evidence: str) -> str:
    """`text` with `evidence` at the end of its `## Evidence` section."""
    at = re.search(r"^## Evidence\n(?:(?!## ).*\n)*", text, re.MULTILINE)
    if at is None:
        raise Refused(mctx("the ticket has no `## Evidence` section"))
    body = at.group().rstrip("\n")
    return f"{text[:at.start()]}{body}\n{evidence.strip(chr(10))}\n\n{text[at.end():].lstrip(chr(10))}"
