"""The assembly of the state the operator's procedures read, from the reads
of the ticket tracker, of git and the main worktree, and of the
transcripts of the session's operators, and of the state the monitor's
steps read (`monitor_reads`); and the session's records of the times from
which an operator's step has been due on each ticket (`State.due_since`,
in the file `DUE_SINCE`) and from which each ticket has waited on no party
(`State.unwaited_since`, in the file `UNWAITED_SINCE`), read by `read_state`
(`record_read`) and written by `write_record`, and of the state the ticket
dashboard shows (`Shown`, in the file `SHOWN`), written by `write_shown`
and read by `shown_read`, each a JSON object in the session's
scratchpad."""

import atexit
import json
import math
import os
import time
from collections.abc import Mapping
from dataclasses import dataclass, replace
from pathlib import Path

import kept_reads
import step_journal
from agent_turns import last_time
from audit_window import window
from context_bound_hook import past_bound
from elsewhere_reads import editor_checks, elsewhere_agents
from git_session_reads import given_lines, read_git, sessions, started
from held_budgets import change_budgets, change_spend, doc_budgets
from idle_sessions import running
from machine_watch import alert_files
from monitor_reads import late_resumes
from open_agents import running_agents, work_open
from operator_reads import (
    AgentsRead,
    operator_runs,
    joined,
)
from operator_transcript import OperatorRead, read_operator
from refresh_locks import wait_free
from relay_reads import session_id
from run_reads import context_size, parent_id
from run_scripts import pace_reads, read_runs
from state_reads import new_state
from ticket_numbers import session_index, staged, ticket_number
from ticket_reads import read_tickets
from ticket_settle import to_settle
from transcripts import find
from entry_reads import entries_back
from transcript_snapshots import Refused
from tree_reads import (
    main_tree,
    scratch,
)
from usage_limit import read_usage

from handbook.reader_names import ReaderName
from handbook.readers import reader_calls
from operations import pacing
from operations.pacing import Scripted, Until, Usage
from operations.directives import Directive, given_again, named, own_scope, pace, paused, session_lines
from operations.taking import allowed, expedited
from operations.monitor import MonitorState
from operations.plan import taken_up
from operations.state import (
    AuditWindow,
    Computed,
    Deferred,
    DueEntry,
    GitRead,
    LateResume,
    NotComputed,
    Reader,
    Spend,
    State,
    Stuck,
    TrackerRead,
    TranscriptsRead,
)
from holder_reads import holders_read, read_held, with_quiet_holders
from operator_state import (EndsRead, ends_read, not_given, stuck_read, undecided_lines, watched_read,
                            work_of)

STARTED = time.time()
"""The start of the process: a step given to `me` before it, with no call
of it made, is one `me` ran `next` again before it made."""

DUE_SINCE = "due-since.json"
"""The name of the file, in the session's scratchpad, that holds
`State.due_since`."""

UNWAITED_SINCE = "unwaited-since.json"
"""The name of the file, in the session's scratchpad, that holds
`State.unwaited_since`."""

SHOWN = "shown-state.json"
"""The name of the file, in the session's scratchpad, that holds the
`Shown` of the operator's last read of the state."""

DEPRECATED = frozenset({ReaderName.ROLE, ReaderName.CONSOLE, ReaderName.SURVEY,
                        ReaderName.WORKFLOW})
"""The readers of the deprecated mechanisms, which no standing doc review
reads."""


def read_state(me: str, since: float | None = None) -> tuple[State, MonitorState]:
    """The state the operator's procedures read, and the state the
    monitor's steps read. Where `since` is given, the transcripts read for
    launches, calls, messages and late resumes are only those of `me` and
    of the operators whose last entry is at or after `since`: an agent
    launched since then is launched by one of those. `elsewhere_agents`
    gives `TranscriptsRead.elsewhere`.

    Where the process has opened no store of `kept_reads`, the call opens
    the default store and writes the store's records at the process's
    exit, so the reads kept on disk are read from the store, not computed,
    in any process that calls it. Before it opens it, it waits for the
    session's refresh lock to be free (`refresh_locks.wait_free`), so that
    the reads `scripts/kept_refresh.py` writes for the session are read, not
    computed a second time."""
    session = session_id()
    if kept_reads.store() is None:
        wait_free(session)
        kept_reads.open_store()
        atexit.register(kept_reads.flush)
    opened = new_state()
    main = main_tree()
    tickets_dir = main / "tickets"
    undecided: list[str] = []
    runs = runs_read(session, me)
    tree = read_git(main)
    read = operators_since(runs.runs, me, since)
    ops = operators_read(read, me, main, undecided, tree)
    paths = dict(runs.runs)
    journal, journaled = step_journal.read(
        scratch(session), ops.calls,
        lambda e: e.given >= STARTED if e.operator == me
        else e.operator in paths and work_open(paths[e.operator], undecided),
        time.time(), since is None)
    ops = replace(ops, calls=(*ops.calls, *step_journal.run_calls(
        journaled, commit_subjects(tree), undecided)))
    late = late_resumes(read, undecided)
    watching: list[str] = []
    listing = running_agents(find(session), watching)
    now_watched = watched_read(listing, ops.agents, watching, opened)
    now = time.time()
    ends = ends_read(ops.agents, me, listing, now_watched, now, undecided)
    running_work = work_of(listing)
    stuck = stuck_read(session, ends.quiet, now_watched, running_work)
    tickets, unread = read_tickets(tickets_dir)
    others = elsewhere_agents(tickets, me, frozenset(runs.operators), main, undecided)
    transcripts = transcripts_read(ops, ends, late, stuck, others)
    took_up = taken_up(me, runs.operators, transcripts.calls, runs.parents)
    given = given_lines(runs.runs, me, list(ops.calls))

    def ungiven(lines: list[str]) -> list[str]:
        return not_given(lines, given)

    watching.extend(undecided_lines(me, runs.runs, ends.agents, others.agents, took_up,
                                    ends.ended, ungiven(undecided)))
    index = session_index(tickets_dir, session)
    main_path = find(session)
    sessions_running = running(session)
    holders = holders_read(tickets, session, main_path, sessions_running)
    lifted, usage = read_usage(now, watching)
    state = State(
        me=me, now=now, session=session, started=started(session),
        transcripts_dir=main_path.parent, main_tree=main,
        scratch=scratch(session), operators=runs.operators, parents=runs.parents,
        open_operators=open_operators(runs.runs, me),
        past_bound=bound_read(runs.runs, me),
        open_holders=holders.open, session_holders=holders.session,
        tracker=TrackerRead(tickets, unread, index), transcripts=transcripts,
        git=tree, taken_up=took_up, held=read_held(tickets, me, tree),
        readers=readers_read(),
        limit_lifted=lifted, machine_alerts=alert_files(main, session),
        sessions=sessions(tickets_dir, index, session, now, sessions_running),
        journal=journal, listing=ops.listing, due_since=record_read(scratch(session), DUE_SINCE),
        unwaited_since=record_read(scratch(session), UNWAITED_SINCE))
    state = replace(state, journal=state.journal.since(given_again(state)))
    state = with_quiet_holders(state, holders.found, listing, running_work)
    computed_lines: list[str] = []
    state = replace(state, computed=computed_read(state, tickets_dir, computed_lines, usage))
    watching.extend(ungiven(computed_lines))
    return state, MonitorState(watched=tuple(now_watched), stalled=frozenset(ends.stalled),
                               undecided=tuple(watching))


def record_read(here: Path, name: str) -> dict[str, DueEntry]:
    """The record the file `name` under `here` gives, or empty where that
    file is missing or holds no JSON object whose values are each a pair of
    finite numbers, the `since` and the `last` of a `DueEntry`."""
    try:
        record = json.loads((here / name).read_text())
    except (OSError, ValueError):
        return {}
    if not isinstance(record, dict) or not all(
            isinstance(v, list) and len(v) == 2
            and all(isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)
                    for x in v)
            for v in record.values()):
        return {}
    return {n: DueEntry(float(v[0]), float(v[1])) for n, v in record.items()}


def write_record(here: Path, name: str, times: Mapping[str, DueEntry]) -> None:
    """Replaces the file `name` under `here` with `times`, each entry as the
    pair its `DueEntry` gives."""
    replaced(here, name, {n: [e.since, e.last] for n, e in sorted(times.items())})


def replaced(here: Path, name: str, record: object) -> None:
    """Replaces the file `name` under `here` with the JSON of `record`, at
    once."""
    with staged(here, json.dumps(record)) as tmp:
        os.replace(tmp, here / name)


@dataclass(frozen=True)
class ScriptAdmits:
    """The pace of an `Op pace: <path>` line, as `Shown` keeps it: whether
    the script admits a step that starts an agent's run."""
    admits: bool


type ShownPace = Until | ScriptAdmits | NotComputed


@dataclass(frozen=True)
class Shown:
    """The values of a read of the state that the ticket dashboard shows:
    the time of the read, the text of the `Op pace:` line in force, or None
    where the pace is the default, the pace computed, whether the session
    is paused and keeps to its own scope, the tickets expedited and
    allowed, and the spend of each change the operator holds by its
    dollars and its roles."""
    at: float
    pace_line: str | None
    pace: ShownPace
    paused: bool
    own_scope: bool
    expedited: tuple[str, ...]
    allowed: tuple[str, ...]
    spent: Mapping[str, tuple[float, tuple[str, ...]]]


def shown(state: State) -> Shown:
    """The `Shown` of `state`."""
    lines = [ln.text for ln in session_lines(state) if ln.kind is Directive.PACE]
    kept: ShownPace
    match state.computed.pace:
        case Scripted(_, admits):
            kept = ScriptAdmits(admits)
        case other:
            kept = other
    return Shown(state.now, lines[-1] if lines and pace(state) is not None else None, kept,
                 paused(state), own_scope(state), tuple(sorted(expedited(state))),
                 tuple(sorted(allowed(state))),
                 {n: (s.dollars, tuple(sorted(s.by_role))) for n, s in sorted(state.computed.spent.items())})


def write_shown(here: Path, state: State) -> None:
    """Replaces the file `SHOWN` under `here` with the `Shown` of `state`."""
    s = shown(state)
    match s.pace:
        case Until(at, cap):
            pace_json: dict[str, object] = {"until": at, "cap": cap}
        case ScriptAdmits(admits):
            pace_json = {"script_admits": admits}
        case NotComputed(why):
            pace_json = {"not_computed": why}
    replaced(here, SHOWN, {
        "at": s.at, "pace_line": s.pace_line, "pace": pace_json, "paused": s.paused,
        "own_scope": s.own_scope, "expedited": list(s.expedited), "allowed": list(s.allowed),
        "spent": {n: {"dollars": d, "roles": list(r)} for n, (d, r) in s.spent.items()}})


def shown_read(here: Path) -> Shown | str:
    """The `Shown` the file `SHOWN` under `here` holds, or why there is
    none: the file is missing, or does not hold the JSON `write_shown`
    writes."""
    try:
        r = json.loads((here / SHOWN).read_text())
    except OSError:
        return f"no read of the state is recorded ({here / SHOWN} is missing)"
    except ValueError as e:
        return f"the record {here / SHOWN} does not parse: {e}"
    try:
        p = r["pace"]
        kept: ShownPace
        if "until" in p:
            kept = Until(float(p["until"]), None if p["cap"] is None else int(p["cap"]))
        elif "script_admits" in p:
            kept = ScriptAdmits(bool(p["script_admits"]))
        else:
            kept = NotComputed(str(p["not_computed"]))
        return Shown(float(r["at"]), None if r["pace_line"] is None else str(r["pace_line"]), kept,
                     bool(r["paused"]), bool(r["own_scope"]), tuple(map(str, r["expedited"])),
                     tuple(map(str, r["allowed"])),
                     {str(n): (float(v["dollars"]), tuple(map(str, v["roles"])))
                      for n, v in r["spent"].items()})
    except (KeyError, TypeError, ValueError, AttributeError) as e:
        return f"the record {here / SHOWN} does not hold a read of the state: {e!r}"


@dataclass(frozen=True)
class RunsRead:
    """The runs of the session's operators, `me` among them, by agent id
    and transcript, in the order of `operator_runs`, with their agent ids
    (`State.operators`) and their parents (`State.parents`)."""
    runs: list[tuple[str, Path]]
    operators: tuple[str, ...]
    parents: Mapping[str, str]


def runs_read(session: str, me: str) -> RunsRead:
    """`RunsRead` of `session`, where `me` is one of its operators."""
    runs = operator_runs(session, me)
    if me not in dict(runs):
        runs.append((me, find(me)))
    return RunsRead(runs, tuple(aid for aid, _ in runs),
                    {aid: parent_id(p) for aid, p in runs})


def bound_read(runs: list[tuple[str, Path]], me: str) -> bool:
    """`State.past_bound` of the run of `me` in `runs`."""
    return past_bound(context_size(entries_back(dict(runs)[me])))


def readers_read() -> Deferred[tuple[Reader, ...]]:
    """`State.readers`: the doc readers outside `DEPRECATED`, read on use."""
    return Deferred(lambda: tuple(Reader(name, tuple(args)) for name, args in reader_calls()
                                  if name not in DEPRECATED))


def operators_since(runs: list[tuple[str, Path]], me: str,
                    since: float | None) -> list[tuple[str, Path]]:
    """The runs of `runs` that `read_state` reads at `since`."""
    return [(aid, path) for aid, path in runs
            if since is None or aid == me or (t := last_time(path)) is not None and t >= since]


def open_operators(runs: list[tuple[str, Path]], me: str) -> frozenset[str]:
    """`State.open_operators`: the operators of `runs` other than `me`
    whose work is open."""
    return frozenset(aid for aid, p in runs if aid != me and work_open(p, []))


def transcripts_read(ops: OperatorRead, ends: "EndsRead",
                     late: Mapping[str, tuple[LateResume, ...]], stuck: Mapping[str, Stuck],
                     others: AgentsRead) -> TranscriptsRead:
    """`TranscriptsRead` of the steps' reads."""
    both = joined([ops.launched, others])
    return TranscriptsRead(
        agents=tuple(sorted(ends.agents, key=lambda a: a.launched)),
        calls=tuple(sorted(ops.calls, key=lambda c: c.time)), messages=tuple(ops.messages),
        late_resumes=late, stalled=ends.stalled, quiet=ends.quiet,
        stuck=stuck, pass_reports=ops.passes, elsewhere=others.agents,
        messaged=both.messaged, limited=both.limited)


def commit_subjects(tree: GitRead) -> dict[str, float]:
    """The time of the latest commit of `master` with each subject."""
    subjects: dict[str, float] = {}
    for c in tree.commits:
        subjects[c.subject] = max(subjects.get(c.subject, c.time), c.time)
    return subjects


def operators_read(read: list[tuple[str, Path]], me: str, main: Path, undecided: list[str],
                   tree: GitRead) -> OperatorRead:
    """What the transcripts of the operators `read`, by agent id and
    transcript, give together, as `OperatorRead` gives it of one, with the
    checks their editors launched (`editor_checks`), and the
    listing of `me`'s. A commit's subject stands at the latest time `tree`
    gives it."""
    subjects = commit_subjects(tree)
    ones = [read_operator(aid, path, main, undecided, subjects) for aid, path in read]
    launched = joined([one.launched for one in ones])
    reviewers = editor_checks(launched.agents, main, undecided)
    return OperatorRead(
        joined([launched, reviewers]), tuple(c for one in ones for c in one.calls),
        tuple(m for one in ones for m in one.messages),
        {k: v for one in ones for k, v in one.passes.items()},
        next((one.listing for (aid, _), one in zip(read, ones) if aid == me), None))


def computed_read(state: State, tickets_dir: Path, undecided: list[str],
                  usage: Usage) -> Computed:
    """`State.computed` of `state`, at the usage `usage`, adding to
    `undecided` the `undecided` lines of its reads."""
    tickets = state.tracker.tickets
    given = [ticket_number(n) for n in named(state) | allowed(state) if n in tickets]
    spent = change_spend(state, undecided)
    run_starts, run_takes = read_runs(state)
    given_pace = pace(state)
    return Computed(
        to_settle=tuple(str(n) for n in to_settle(tickets_dir, state.tracker.index,
                                                  state.sessions.adopted, given)
                        if str(n) in tickets),
        spent=spent, budgets=change_budgets(state, spent, tickets_dir, undecided),
        doc_budgets=doc_budgets(state, tickets_dir, undecided),
        run_starts=run_starts, run_takes=run_takes,
        pace=(pacing.with_five_hour(pace_reads(given_pace, usage), usage) if isinstance(given_pace, Path)
              else (given_pace or pacing.DEFAULT)(usage)),
        audit_window=audit_window_read(state, undecided))


def audit_window_read(state: State, undecided: list[str]) -> AuditWindow | NotComputed:
    """The window of the next cost audit under the session's transcript
    directory, or why it does not read."""
    try:
        return window(state.transcripts_dir, state.started, undecided)
    except Refused as exc:
        return NotComputed(str(exc))
