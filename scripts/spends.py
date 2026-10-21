"""The spend of a change by role, recorded under `tickets/spends/` once it
is settled, and the budget of a change taken over the changes like
it."""

import json
import statistics
from collections.abc import Mapping
from dataclasses import asdict, dataclass, replace
from enum import Enum
from functools import partial
from pathlib import Path

import codex_reads
import codex_rollout

import read_interrupts
from agent_launches import runs_under
from agent_turns import first_time, has_ended, last_time
from run_reads import agent_type, run_entries
from file_reads import file_text, listed, stat_read, state_stat
from state_reads import DERIVED, Kept, state_cache
from ticket_files import listed_tickets, ticket_name
from ticket_log import moved
from ticket_reads import held_ticket
from token_prices import run_cost
from transcripts import chain, held_find, project_dirs
from entry_reads import entries_back
from transcript_snapshots import Refused

from controlled_markdown import mctx
from engine.memo import write_whole
from operations.roles import Role
from operations.state import (Budget, Spend, Ticket, CodexUsage, CodexSource, CodexSpend,
                              UnpricedSpend)
from ticketing.vocabulary import Kind, Resolution, Status


def union_seconds(spans: list[tuple[float, float]]) -> float:
    """The seconds the spans cover, counting an overlap once."""
    total, end = 0.0, float("-inf")
    for a, b in sorted(spans):
        read_interrupts.checkpoint()
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
    """A legacy record with no known dollar spend."""
    SPEND = "unknown"


type Recorded = Spend | UnpricedSpend | Unknown | None
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
        read_interrupts.checkpoint()
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
        children = runs_under(top, pending, held) if pending else closed_tree(top)
        trees.append((role, [top, *children]))
    owner: dict[Path, tuple[int, str]] = {}
    for role, tree in trees:
        read_interrupts.checkpoint()
        for p in tree:
            read_interrupts.checkpoint()
            if p not in owner or len(tree) < owner[p][0]:
                owner[p] = (len(tree), role)
    return {p: role for p, (_, role) in owner.items()}


@state_cache(None)
def closed_tree(top: Path) -> list[Path]:
    """The run tree shared by closed changes in this state, walked again
    in the next state in case a transcript appeared or a run resumed."""
    return runs_under(top)


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


def fingerprint(path: Path) -> tuple[str, int | None, int | None]:
    """A source revision in this state, including a missing source.

    Hundreds of old spends watch the same transcript directories. Share
    their stats with the other state reads instead of statting each again.
    """
    text = str(path)
    stat = state_stat(text)
    return (text, None, None) if stat is None else (text, stat.mtime_ns, stat.size)


def legacy_turn_records(records: list[dict], home: Path,
                        inputs: set[Path]) -> list[dict]:
    """Recover legacy call boundaries only when accepted record order is exact.
    A partial or unmatched accepted history cannot establish that correspondence.
    """
    recovered: list[dict] = []
    for thread in sorted({r["thread"] for r in records if isinstance(r.get("thread"), str)}):
        read_interrupts.checkpoint()
        accepted = []
        for record in records:
            read_interrupts.checkpoint()
            if record.get("thread") != thread or "turn" in record:
                continue
            try:
                events = [json.loads(line) for line in record["output"].splitlines()]
            except (KeyError, ValueError):
                continue
            if any(e.get("type") in ("turn.completed", "turn.failed") for e in events):
                accepted.append(record)
        if not accepted:
            continue
        try:
            inputs.add(codex_rollout.rollout_path(thread, home))
            turns = codex_rollout.turns(thread, home)
        except (OSError, ValueError, KeyError):
            continue
        if len(accepted) != len(turns):
            continue
        for record, turn in zip(accepted, turns):
            read_interrupts.checkpoint()
            recovered.append({**record, "turn": turn.turn,
                "usage": None if turn.usage is None else asdict(turn.usage),
                "running": turn.ended is None, "started": turn.started,
                "ended": turn.ended})
    return recovered


def codex_spend(owner: dict[Path, str], before: float | None = None,
                home: Path | None = None) -> CodexSpend:
    """Count accepted turns once across the change's launcher calls.
    Missing or ambiguous boundaries remain explicit source components.
    """
    home = home or Path.home()
    sources: list[CodexSource] = []
    inputs: set[Path] = {p for path in owner for p in chain(path)}
    launches: dict[Path, list[codex_reads.Call]] = {}
    for path in owner:
        read_interrupts.checkpoint()
        try:
            gaps: list[str] = []
            for call in codex_reads.calls(list(run_entries(path)), gaps):
                read_interrupts.checkpoint()
                if before is None or call.started is None or call.started <= before:
                    launches.setdefault(call.scratch, []).append(replace(call, transcript=path))
            sources.extend(CodexSource(str(path), owner[path], None, None, None, gap)
                           for gap in gaps)
        except (OSError, ValueError, KeyError, IndexError) as exc:
            sources.append(CodexSource(str(path), owner[path], None, None, None,
                                       "launcher evidence unreadable: " + str(exc)))
    seen: dict[tuple[str, str], CodexSource] = {}
    for scratch, calls in launches.items():
        read_interrupts.checkpoint()
        calls.sort(key=lambda c: c.started if c.started is not None else float("inf"))
        record_path = scratch / "codex-events.jsonl"
        inputs.update((record_path, scratch / "codex-session"))
        try:
            records = codex_rollout.rows(record_path)
        except (OSError, ValueError) as exc:
            records = []
        recovered = legacy_turn_records(records, home, inputs)
        for index, call in enumerate(calls):
            read_interrupts.checkpoint()
            source = f"{call.transcript}:{call.call_id}"
            next_call = calls[index + 1].started if index + 1 < len(calls) else None
            limits = [t for t in (next_call, before) if t is not None]
            next_start = min(limits) if limits else None
            legacy_limits = [t for t in (next_start, call.until) if t is not None]
            legacy_end = min(legacy_limits) if legacy_limits else None
            timed = [r for batch, limit in ((records, next_start), (recovered, legacy_end))
                     for r in batch if isinstance(r.get("started"), (int, float))
                     and call.started is not None and r["started"] >= call.started
                     and (limit is None or r["started"] < limit)]
            if len(timed) == 1:
                record = timed[0]
            elif len(records) == len(calls) and not any("started" in r for r in records):
                record = records[index]
            else:
                sources.append(CodexSource(source, call.work_name, None, None, None,
                                           "call record missing or ambiguous", call.ended is None))
                continue
            if record.get("refused") is True:
                continue
            thread, turn = record.get("thread"), record.get("turn")
            usage = codex_rollout.tokens(record.get("usage"))
            running = record.get("running", False)
            reason = record.get("usage_reason", "turn usage unavailable")
            if thread is not None and (usage is None or turn is None or running):
                try:
                    rollout = codex_rollout.rollout_path(thread, home)
                    inputs.add(rollout)
                    start = record.get("started", call.started)
                    end = record.get("ended", legacy_end)
                    evidence = (codex_rollout.call_turn(thread, home, start, end, turn)
                                if start is not None and end is not None else None)
                    if evidence is not None:
                        turn, usage = evidence.turn, evidence.usage
                        running = evidence.ended is None
                except (OSError, ValueError, KeyError) as exc:
                    reason = "rollout evidence unavailable: " + str(exc)
                    # Watch existing directories for a later rollout arrival.
                    inputs.add(home / ".codex" / "sessions")
                    sessions = home / ".codex" / "sessions"
                    if sessions.exists():
                        inputs.update(p for p in sessions.rglob("*") if p.is_dir())
            if turn is None:
                usage = None
                reason = "accepted turn identity unavailable"
            elif usage is not None:
                reason = codex_rollout.usage_reason(usage, turn)
            item = CodexSource(source, call.work_name,
                               thread, turn, usage, reason, running)
            if thread is None or turn is None:
                sources.append(item)
            else:
                key = thread, turn
                previous = seen.get(key)
                if previous is None:
                    seen[key] = item
                elif previous.role != item.role or previous.usage != item.usage:
                    seen[key] = replace(previous, usage=None, reason="conflicting turn evidence")
    sources.extend(seen.values())
    return CodexSpend(tuple(sources), tuple(fingerprint(p) for p in sorted(inputs)))


def priced(owner: dict[Path, str], undecided: list[str],
           before: float | None = None) -> Spend | UnpricedSpend:
    """Independent Claude dollars and Codex tokens of the owned transcripts.
    A missing Claude price preserves measured tokens in UnpricedSpend.
    A transcript with no timed entry adds no time.
    """
    total = 0.0
    known = True
    spans: list[tuple[float, float]] = []
    by_role: dict[str, float] = {}
    for p, role in owner.items():
        read_interrupts.checkpoint()
        start, end = first_time(p), last_time(p)
        if start is None or end is None:
            continue
        cost = cost_of(p, undecided)
        if cost is None:
            known = False
        else:
            total += cost
            by_role[role] = by_role.get(role, 0.0) + cost
        spans.append((start, end))
    codex = codex_spend(owner, before)
    seconds = union_seconds(spans)
    return Spend(total, seconds, by_role, codex) if known else UnpricedSpend(seconds, codex)


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
    result = priced(owner, undecided) if isinstance(owner, dict) else None
    return result if isinstance(result, Spend) else None


def stopped(path: Path) -> bool:
    """Whether the run at `path` does nothing until a message resumes it:
    it has ended its turn, or its last entry is an API error entry."""
    if has_ended(path):
        return True
    for p in reversed(chain(path)):
        read_interrupts.checkpoint()
        for e in entries_back(p):
            read_interrupts.checkpoint()
            return e.get("isApiErrorMessage") is True
    return False


@state_cache(DERIVED)
def transcript_directories(directory: Path) -> frozenset[Path]:
    """The directories to watch for missing transcripts under `directory`.
    Share their discovery across spends, resting on each directory's listing
    so that a later state sees directories added or removed. Include links
    to directories without descending them, as `Path.rglob` does.
    """
    found = {directory}
    todo = [directory]
    while todo:
        parent = todo.pop()
        for entry in listed(parent):
            read_interrupts.checkpoint()
            if entry.is_dir:
                child = parent / entry.name
                found.add(child)
                if not entry.is_link:
                    todo.append(child)
    return frozenset(found)


def unresolved_spend(path: Path, runs: list[str], before: float) -> UnpricedSpend:
    """Preserve attributable components while another run's evidence is absent."""
    known = [run for run in runs if isinstance(known_owners([run], {}), dict)]
    owner = known_owners(known, {})
    measured = codex_spend(owner, before) if isinstance(owner, dict) else CodexSpend()
    sources = [*measured.sources, *(CodexSource(run, "unknown", None, None, None,
                    "run transcript or role unavailable") for run in runs if run not in known)]
    if not runs:
        sources.append(CodexSource(str(path), "unknown", None, None, None,
                                   "closing line gives no change runs"))
    watched = {path}
    for directory in project_dirs():
        read_interrupts.checkpoint()
        watched.update(transcript_directories(directory))
    for run in runs:
        read_interrupts.checkpoint()
        transcript = held_find(run)
        if transcript is not None:
            watched.add(transcript)
            watched.add(transcript.with_suffix(".meta.json"))
    inputs = tuple(sorted({*measured.inputs, *(fingerprint(p) for p in watched)}))
    return UnpricedSpend(None, CodexSpend(tuple(sources), inputs))


@state_cache(None, notes="undecided")
def change_spend(path: Path, undecided: list[str]) -> Spend | None:
    """Dollar spend of a closed fixed change, with independent tokens recorded.
    Legacy records refresh from source runs while their dollars and time stand.
    Source revisions invalidate settled and unresolved measurements. Each
    state checks a change once, shared by the budgets of all editor sets.
    """
    found = recorded_spend(path)
    codex = found.codex if isinstance(found, (Spend, UnpricedSpend)) else None
    if codex is not None and all(fingerprint(Path(p)) == (p, m, n) for p, m, n in codex.inputs):
        return found if isinstance(found, Spend) else None
    closing = [line for line in held_closed(path).log if line.status is Status.CLOSED
               and line.resolution is Resolution.FIXED]
    runs = closing[-1].note.split()[3:] if closing else []
    owner = None if not closing else known_owners(runs, {}) if runs else Unknown.SPEND
    lines = len(undecided)
    measured = priced(owner, undecided, closing[-1].time) if isinstance(owner, dict) else None
    if measured is None and closing:
        measured = unresolved_spend(path, runs, closing[-1].time)
    if isinstance(found, Spend) and measured is not None:
        measured = replace(found, codex=measured.codex)
    if measured is not None and len(undecided) == lines and (
            not isinstance(owner, dict) or all_stopped(owner, closing[-1].time)):
        write_record(spend_record(path), encoded(measured))
    return measured if isinstance(measured, Spend) else None


def all_stopped(owner: dict[Path, str], at: float) -> bool:
    """Whether each run of the transcripts `owner` gives has stopped since
    `at`, so its spend no longer grows: `stopped` holds, or its transcripts
    hold no entry timed after `at`."""
    return all(stopped(p) or (last_time(p) or 0.0) <= at for p in owner)


@partial(read_interrupts.deferred, force=False)
def write_record(record: Path, value: object) -> None:
    """Write `value` as JSON to the file `record` under `SPENDS`."""
    record.parent.mkdir(exist_ok=True)
    write_whole(record, (json.dumps(value, sort_keys=True) + "\n").encode())


def spend_record(path: Path) -> Path:
    """The file under `SPENDS` of the change at `path`."""
    return path.parent.parent / SPENDS / f"{ticket_name(path).number}.json"


def encoded(spend: Spend | UnpricedSpend) -> dict:
    """The dollar record and the independent Codex measurement."""
    value = asdict(spend)
    if isinstance(spend, UnpricedSpend):
        value.update(dollars=None, by_role=None)
    if spend.codex is not None:
        value["codex"].update(status=spend.codex.status, totals=asdict(spend.codex.totals()),
            by_role={role: asdict(spend.codex.totals(role))
                     for role in sorted({s.role for s in spend.codex.sources})})
    return value


def recorded_spend(path: Path) -> Recorded:
    """Read legacy and extended records without assuming missing usage is zero."""
    record = spend_record(path)
    if stat_read(record) is None:
        return None
    value = json.loads(file_text(record))
    if value is None:
        return Unknown.SPEND
    codex = value.get("codex")
    measurement = None if codex is None else CodexSpend(tuple(
        CodexSource(**{**s, "usage": codex_rollout.tokens(s["usage"])})
        for s in codex["sources"]), tuple(tuple(row) for row in codex["inputs"]))
    if value["dollars"] is None:
        if measurement is None:
            return Unknown.SPEND
        return UnpricedSpend(value["seconds"], measurement)
    return Spend(value["dollars"], value["seconds"], value["by_role"], measurement)


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
        read_interrupts.checkpoint()
        t = held_closed(path)
        if t.kind is Kind.CHANGE:
            out.append(Closed(path, t.editors, t.last_time))
    return tuple(out)


@state_cache(DERIVED)
def closed_spends(tickets: Path) -> tuple[tuple[Closed, Recorded], ...]:
    """Closed changes and their recorded spends, held by record revisions."""
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
    for c, _ in closed_spends(tickets):
        read_interrupts.checkpoint()
        if c.at >= before:
            continue
        s = change_spend(c.path, undecided)
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
                              "known dollar spend"))
        return None
    return Budget(OVERRUN * statistics.median(s.dollars for s in like),
                  OVERRUN * statistics.median(s.seconds for s in like))
