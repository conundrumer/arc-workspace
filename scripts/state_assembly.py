"""The assembly of the state the operator's procedures read, from the reads
of the ticket tracker, of git and the main worktree, and of the
transcripts of the session's operators, with the session's records of
due and unwaited times (`session_records`), and of the state the
monitor's steps read (`monitor_reads`)."""

import atexit
import time
from contextvars import ContextVar
from collections.abc import Mapping
from dataclasses import dataclass, replace
from pathlib import Path

import kept_reads
import step_journal
from agent_turns import last_time
from audit_window import window
from context_bound_hook import context_bound, past_bound
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
from ticket_numbers import session_index, ticket_number
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
from session_records import DUE_SINCE, UNWAITED_SINCE, record_read

from handbook.reader_names import ReaderName
from handbook.readers import reader_calls
from operations import pacing
from operations.pacing import Usage
from operations.directives import given_again, named, pace
from operations.taking import allowed
from operations.monitor import MonitorState
from operations.plan import taken_up
from operations.state import (
    AuditWindow,
    Computed,
    Deferred,
    GitRead,
    LateResume,
    NotComputed,
    Reader,
    State,
    Stuck,
    TrackerRead,
    TranscriptsRead,
)
from holder_reads import holders_read, read_held, with_quiet_holders
from operator_state import (EndsRead, ends_read, not_given, stuck_read, undecided_lines, watched_read,
                            work_of)

STARTED = time.time()
REQUEST_STARTED: ContextVar[float] = ContextVar("request_started", default=STARTED)
"""The call cutoff for journal entries, with process start for standalone reads."""

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
        lambda e: e.given >= REQUEST_STARTED.get() if e.operator == me
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
        past_bound=bound_read(runs.runs, me, main),
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


def bound_read(runs: list[tuple[str, Path]], me: str, main: Path) -> bool:
    """`State.past_bound` of the run of `me` in `runs`, against the bound in
    force under the main tree `main`."""
    return past_bound(context_size(entries_back(dict(runs)[me])), context_bound(main))


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
        spent=spent, budgets=change_budgets(state, tickets_dir, undecided),
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
