"""The spend of a change by role, recorded under `tickets/spends/` once it
is settled. `spend_history` computes budgets from those records."""

import json
from collections.abc import Mapping
from dataclasses import asdict, replace
from enum import Enum
from functools import partial
from pathlib import Path

import codex_reads
import codex_rollout
from codex_spends import codex_spend, fingerprint

import read_interrupts
from agent_launches import runs_under
from agent_turns import first_time, has_ended, last_time
from run_reads import agent_type, run_entries
from file_reads import file_text, listed, stat_read
from state_reads import DERIVED, Kept, state_cache
from ticket_files import ticket_name
from ticket_log import moved
from ticket_reads import held_ticket
from token_prices import run_cost
from transcripts import chain, held_find, project_dirs
from entry_reads import entries_back
from transcript_snapshots import Refused, SUBJECT_FAULTS

from controlled_markdown import mctx
from engine.memo import write_whole
from operations.roles import Role
from operations.codex_spend import CodexSource, CodexSpend
from operations.state import Spend, Ticket, UnpricedSpend
from ticketing.subscription import CLAUDE_LIST_TO_SUBSCRIPTION
from ticketing.vocabulary import Resolution, Status


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
    """A record with no known dollar spend."""
    SPEND = "unknown"
    UNMIGRATED = "unmigrated"
    """A record whose Codex sources hold no `model` key, the form before
    Codex costs counted in subscription dollars. Its spend is unknown, and
    no reader re-measures or overwrites it before its migration, which
    gives each source its model or an explicit null."""


type Recorded = Spend | UnpricedSpend | Unknown | None
"""What the file under `SPENDS` of a change records: its spend, no known
spend, or, as None, no file."""


def owners(runs: list[str], pending: Mapping[str, str]) -> dict[Path, str] | None:
    """The transcript of each of the runs `runs` and of the runs under them,
    with the agent type it counts under, or None where a run has no
    transcript or no agent type, other than a native Codex agent whose store
    root is a transcribed run of `runs`: `codex_spend` measures that store
    through the root, so such an agent counts as measured and adds no
    transcript. Each transcript counts once, under the
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
    unresolved: list[str] = []
    for run in runs:
        read_interrupts.checkpoint()
        top = held_find(run)
        launch = pending.get(run)
        if top is None:
            if launch is None:
                unresolved.append(run)
            continue
        role = counted_type(top, launch)
        if role is None:
            return None
        if launch is not None:
            held.add(top)
        children = runs_under(top, pending, held) if pending else closed_tree(top)
        trees.append((role, [top, *children]))
    if unresolved:
        natives = native_agents(runs)
        if not all(measured_through_root(natives, runs, run) for run in unresolved):
            return None
    owner: dict[Path, tuple[int, str]] = {}
    for role, tree in trees:
        read_interrupts.checkpoint()
        for p in tree:
            read_interrupts.checkpoint()
            if p not in owner or len(tree) < owner[p][0]:
                owner[p] = (len(tree), role)
    return {p: role for p, (_, role) in owner.items()}


def native_agents(runs: list[str]) -> dict[str, "codex_reads.Native"]:
    """Each native Codex agent in the stores of the sessions of the
    transcribed runs of `runs`, by agent id."""
    from run_reads import session_of
    from tree_reads import scratch

    natives = {}
    for run in runs:
        top = held_find(run)
        if top is not None:
            for item in codex_reads.native_assignments(scratch(session_of(top).name),
                                                       include_history=True):
                natives[item.assignment.agent] = item
    return natives


def measured_through_root(natives: "dict[str, codex_reads.Native]", runs: list[str],
                          run: str) -> bool:
    """Whether `run` is a native Codex agent below the root of its store,
    and that root is a run of `runs` with a transcript."""
    item = natives.get(run)
    if item is None or item.state["parent"] is None:
        return False
    seen = {run}
    while item.state["parent"] is not None:
        parent = item.state["parent"]
        if parent in seen or parent not in natives:
            return False
        seen.add(parent)
        item = natives[parent]
    return item.assignment.agent in runs and held_find(item.assignment.agent) is not None


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



def priced(owner: dict[Path, str], undecided: list[str],
           before: float | None = None) -> Spend | UnpricedSpend:
    """Claude and Codex measurements of the owned transcripts, the Claude
    cost in subscription dollars.
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


def spend(runs: list[str], pending: Mapping[str, str], undecided: list[str]) -> Spend | UnpricedSpend | None:
    """The spend of the runs `runs` and of the runs under them, those that
    `pending` gives still running, as `owners` and `priced` give it, or
    None where ownership is unavailable or a read is refused."""
    owner = known_owners(runs, pending)
    return priced(owner, undecided) if isinstance(owner, dict) else None


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
    if found is Unknown.UNMIGRATED:
        return None
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
    """The record of a spend: what was measured, the Claude cost at list
    prices and the Codex counts by source with each source's model, so that a
    refinement of `CLAUDE_WEEK_LIST` and the Codex rates reach every record."""
    value = {"dollars": list_price(spend.claude) if isinstance(spend, Spend) else None,
             "seconds": spend.seconds,
             "by_role": {r: list_price(d) for r, d in spend.claude_by_role.items()}
             if isinstance(spend, Spend) else None, "codex": None}
    if spend.codex is not None:
        value["codex"] = {**asdict(spend.codex), "status": spend.codex.status,
            "totals": asdict(spend.codex.totals()),
            "by_role": {role: asdict(spend.codex.totals(role))
                        for role in sorted({s.role for s in spend.codex.sources})}}
    return value


def list_price(dollars: float) -> float:
    """The Claude list-price cost of `dollars` subscription dollars."""
    return round(dollars / CLAUDE_LIST_TO_SUBSCRIPTION, 9)


def recorded_spend(path: Path) -> Recorded:
    """Read records without assuming missing usage is zero. A record whose
    Codex sources lack a `model` key is `Unknown.UNMIGRATED`."""
    record = spend_record(path)
    if stat_read(record) is None:
        return None
    value = json.loads(file_text(record))
    if value is None:
        return Unknown.SPEND
    codex = value.get("codex")
    if codex is not None and any("model" not in s for s in codex["sources"]):
        return Unknown.UNMIGRATED
    measurement = None if codex is None else CodexSpend(tuple(
        CodexSource(**{**s, "usage": codex_rollout.tokens(s["usage"])})
        for s in codex["sources"]), tuple(tuple(row) for row in codex["inputs"]))
    if value["dollars"] is None:
        if measurement is None:
            return Unknown.SPEND
        return UnpricedSpend(value["seconds"], measurement)
    return Spend(value["dollars"] * CLAUDE_LIST_TO_SUBSCRIPTION, value["seconds"],
                 {r: d * CLAUDE_LIST_TO_SUBSCRIPTION for r, d in value["by_role"].items()},
                 measurement)


def held_closed(path: Path) -> Ticket:
    """`ticket_reads.held_ticket` of `path`, refused (`ticket_log.moved`)
    where its file moved."""
    try:
        return held_ticket(path)
    except FileNotFoundError:
        raise moved(path)

