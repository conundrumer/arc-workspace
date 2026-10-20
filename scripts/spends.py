"""The spend of a change by role, recorded under `tickets/spends/` once it
is settled, and the budget of a change taken over the changes like
it."""

import json
import statistics
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path

from agent_launches import runs_under
from agent_turns import first_time, has_ended, last_time
from run_reads import agent_type, run_entries
from file_reads import file_text, stat_read
from state_reads import DERIVED, Kept, state_cache
from ticket_files import listed_tickets, ticket_name
from ticket_log import moved
from ticket_reads import held_ticket
from token_prices import run_cost
from transcripts import chain, held_find
from entry_reads import entries_back
from transcript_snapshots import Refused

from controlled_markdown import mctx
from engine.memo import write_whole
from operations.roles import Role
from operations.state import Budget, Spend, Ticket
from ticketing.vocabulary import Kind, Resolution, Status


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
`fixed` whose spend `change_spend` settled, one JSON file per ticket
number: the spend as `change_spend` read it, or JSON `null` where it has
no known spend. It is no status directory, so no reader of tickets takes
a record for a ticket."""


class Unknown(Enum):
    """The record of a change whose spend no later read can make known."""
    SPEND = "unknown"


type Recorded = Spend | Unknown | None
"""What the file under `SPENDS` of a change records: its spend, no known
spend, or, as None, no file."""


def owners(runs: list[str], pending: Mapping[str, str]) -> dict[Path, str] | None:
    """The transcript of each of the runs `runs` and of the runs under them,
    with the agent type it counts under, or None where a run has no
    transcript or no agent type. Each transcript counts once, under the
    agent type of the nearest run of `runs` at or above it, so a run of
    `runs` launched under another keeps its own type. A refused read of a
    transcript raises `Refused`.
    `pending` gives each run that is still running with the agent type its
    launch gives. Such a run, and each run under it, is read from the agent
    index this state holds (`held_find`) alone: one whose transcript that
    index does not give is left out, as having spent nothing so far, and
    such a run whose transcript gives no agent type yet counts under the
    type of its launch."""
    held: set[Path] = set()
    trees: list[tuple[str, list[Path]]] = []
    for run in runs:
        top = held_find(run)
        launch = pending.get(run)
        if top is None:
            if launch is None:
                return None
            continue
        role = counted_type(top, launch)
        if role is None:
            return None
        if launch is not None:
            held.add(top)
        trees.append((role, [top, *runs_under(top, pending, held)]))
    owner: dict[Path, tuple[int, str]] = {}
    for role, tree in trees:
        for p in tree:
            if p not in owner or len(tree) < owner[p][0]:
                owner[p] = (len(tree), role)
    return {p: role for p, (_, role) in owner.items()}


def counted_type(top: Path, launch: str | None) -> str | None:
    """The agent type the run of the transcript at `top` counts under: the
    one its transcript gives, or, where it gives none yet, `launch`, the
    agent type of its launch where it is still running."""
    return agent_type(top) or launch


@state_cache(DERIVED, notes="undecided", kept=Kept.DISK)
def cost_of(path: Path, undecided: list[str]) -> float | None:
    """The cost of the run of the transcript at `path`, as `run_cost`
    gives it, held while the run's entries stand."""
    return run_cost(run_entries(path), undecided)


def priced(owner: dict[Path, str], undecided: list[str]) -> Spend | None:
    """The spend of the transcripts `owner` gives, each under its agent
    type, or None where one has no price. A transcript with no timed entry
    spent nothing and adds no time."""
    total = 0.0
    spans: list[tuple[float, float]] = []
    by_role: dict[str, float] = {}
    for p, role in owner.items():
        start, end = first_time(p), last_time(p)
        if start is None or end is None:
            continue
        cost = cost_of(p, undecided)
        if cost is None:
            return None
        total += cost
        by_role[role] = by_role.get(role, 0.0) + cost
        spans.append((start, end))
    return Spend(total, union_seconds(spans), by_role)


def known_owners(runs: list[str], pending: Mapping[str, str]) -> dict[Path, str] | Unknown | None:
    """What `owners` gives for `runs` and `pending`, with `Unknown.SPEND`
    where it gives None, or None where a read is refused."""
    try:
        owner = owners(runs, pending)
    except Refused:
        return None
    return Unknown.SPEND if owner is None else owner


def spend(runs: list[str], pending: Mapping[str, str], undecided: list[str]) -> Spend | None:
    """The spend of the runs `runs` and of the runs under them, those that
    `pending` gives still running, as `owners` and `priced` give it, or
    None where a read is refused."""
    owner = known_owners(runs, pending)
    return priced(owner, undecided) if isinstance(owner, dict) else None


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
    runs its last `fixed` closing line gives, as `spend` gives it, or None
    where there is no such line or the line gives no run.
    The record under `SPENDS` it writes, where none is written yet, is no
    known spend where that line gives no run or `known_owners` gives
    `Unknown.SPEND`, and the spend once it is settled: `priced` gives it
    with no `undecided` line and each run it read has stopped."""
    found = recorded_spend(path)
    if found is not None:
        return None if found is Unknown.SPEND else found
    closing = [line for line in held_closed(path).log if line.status is Status.CLOSED
               and line.resolution is Resolution.FIXED]
    runs = closing[-1].note.split()[3:] if closing else []
    owner = None if not closing else known_owners(runs, {}) if runs else Unknown.SPEND
    lines = len(undecided)
    s = priced(owner, undecided) if isinstance(owner, dict) else None
    record = (owner if owner is Unknown.SPEND
              else s if s is not None and isinstance(owner, dict) and len(undecided) == lines
              and all_stopped(owner, closing[-1].time) else None)
    if record is not None:
        write_record(spend_record(path), None if record is Unknown.SPEND else asdict(record))
    return s


def all_stopped(owner: dict[Path, str], at: float) -> bool:
    """Whether each run of the transcripts `owner` gives has stopped since
    `at`, so its spend no longer grows: `stopped` holds, or its transcripts
    hold no entry timed after `at`."""
    return all(stopped(p) or (last_time(p) or 0.0) <= at for p in owner)


def write_record(record: Path, value: object) -> None:
    """Write `value` as JSON to the file `record` under `SPENDS`."""
    record.parent.mkdir(exist_ok=True)
    write_whole(record, (json.dumps(value, sort_keys=True) + "\n").encode())


def spend_record(path: Path) -> Path:
    """The file under `SPENDS` of the change at `path`."""
    return path.parent.parent / SPENDS / f"{ticket_name(path).number}.json"


def recorded_spend(path: Path) -> Recorded:
    """What the file under `SPENDS` of the change at `path` records."""
    record = spend_record(path)
    if stat_read(record) is None:
        return None
    value = json.loads(file_text(record))
    return Unknown.SPEND if value is None else Spend(**value)


@dataclass(frozen=True)
class Closed:
    """A ticket under `tickets/closed/` of kind `change`: its path, the
    roles its `editors` field gives (`ticket_reads.editors_field`), and the
    time of its last log line."""
    path: Path
    editors: tuple[Role, ...] | None
    at: float


@state_cache(DERIVED)
def closed_changes(tickets: Path) -> tuple[Closed, ...]:
    """Each ticket under `tickets/closed/` of kind `change`, as
    `ticket_reads.held_ticket` reads it."""
    out: list[Closed] = []
    for path in listed_tickets(tickets, Status.CLOSED):
        t = held_closed(path)
        if t.kind is Kind.CHANGE:
            out.append(Closed(path, t.editors, t.last_time))
    return tuple(out)


@state_cache(DERIVED)
def closed_spends(tickets: Path) -> tuple[tuple[Closed, Recorded], ...]:
    """Each change of `closed_changes`, with its `recorded_spend`, so that
    a read of the changes like a change reads again only the changes that
    no file records."""
    return tuple((c, recorded_spend(c.path)) for c in closed_changes(tickets))


def held_closed(path: Path) -> Ticket:
    """`ticket_reads.held_ticket` of `path`, refused (`ticket_log.moved`)
    where its file moved."""
    try:
        return held_ticket(path)
    except FileNotFoundError:
        raise moved(path)


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
    for c, recorded in closed_spends(tickets):
        if c.at >= before:
            continue
        s = change_spend(c.path, undecided) if recorded is None else recorded
        if isinstance(s, Spend):
            every.append((c.editors, s))
    like = [s for e, s in every if e is not None and frozenset(e) == editors]
    return like if len(like) >= FEWEST_LIKE else [s for _, s in every]


def budget(tickets: Path, editors: frozenset[Role], before: float,
           undecided: list[str]) -> Budget | None:
    """The budget of a change with the `editors` set `editors` taken at
    `before`, or None, with an `undecided` line, where no earlier change
    has a known spend."""
    like = like_changes(tickets, editors, before, undecided)
    if not like:
        undecided.append(mctx("budget unknown: no change closed `fixed` before the take has a "
                              "known spend"))
        return None
    return Budget(OVERRUN * statistics.median(s.dollars for s in like),
                  OVERRUN * statistics.median(s.seconds for s in like))
