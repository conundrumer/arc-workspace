"""The assembly of the state the operator's procedures read, from the reads
of the ticket tracker, of git and the main worktree, and of the
transcripts of the session's operators, and of the state the monitor's
steps read (`monitor_reads`)."""

import atexit
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path

import kept_reads
import step_journal
from agent_turns import last_time
from audit_window import window
from context_bound_hook import past_bound
from filed_texts import gone_line
from git_session_reads import given_lines, read_git, sessions, started
from held_budgets import change_budgets, change_spend, doc_budgets
from idle_sessions import running
from monitor_reads import late_resumes, watched
from open_agents import Listed, quiet_since, running_agents, work_open
from operator_reads import (
    AgentsRead,
    OperatorRead,
    ended_by,
    ended_elsewhere,
    operator_runs,
    joined,
    kept,
    read_operator,
    stalled_reports,
)
from relay_reads import run_index, session_id
from run_reads import context_size, parent_id
from run_scripts import pace_reads, read_runs
from state_reads import new_state
from ticket_numbers import session_index, ticket_number
from ticket_reads import read_tickets
from ticket_settle import to_settle
from transcripts import find, is_subagent
from transcript_entries import Refused, entries_back
from tree_reads import (
    fragments,
    gate_outputs,
    main_tree,
    scratch,
)
from usage_limit import read_usage

from controlled_markdown import mctx
from handbook.reader_names import ReaderName
from handbook.readers import reader_calls
from operations import pacing
from operations.pacing import Usage
from operations.directives import named, pace
from operations.change_agents import on_change
from operations.change_budget import left_draft
from operations.changes import holds
from operations.log_commands import AGENT
from operations.monitor import MonitorState, Watched
from operations.plan import elsewhere, taken_up, unknown_line
from operations.roles import Role
from operations.state import (
    Agent,
    AuditWindow,
    Call,
    Computed,
    Deferred,
    GitRead,
    HeldRead,
    LateResume,
    NotComputed,
    Reader,
    ReadOnUse,
    Report,
    Waits,
    State,
    Stuck,
    Ticket,
    TrackerRead,
    TranscriptsRead,
)
from operations.worktrees import worktree_in
from ticketing.vocabulary import Kind, Status

STARTED = time.time()
"""The start of the process: a step given to `me` before it, with no call
of it made, is one `me` ran `next` again before it made."""

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
    in any process that calls it."""
    if kept_reads.store() is None:
        kept_reads.open_store()
        atexit.register(kept_reads.flush)
    opened = new_state()
    session = session_id()
    main = main_tree()
    tickets_dir = main / "tickets"
    undecided: list[str] = []
    runs = runs_read(session, me)
    tree = read_git(main)
    read = operators_since(runs.runs, me, since)
    ops = operators_read(read, main, undecided, tree)
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
    watching.extend(undecided_lines(me, runs.runs, ops.calls, ends.agents, others.agents,
                                    took_up, ends.ended, undecided))
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
        limit_lifted=lifted,
        sessions=sessions(tickets_dir, index, session, now, sessions_running),
        journal=journal)
    state = with_quiet_holders(state, holders.found, listing, running_work)
    state = replace(state, computed=computed_read(state, tickets_dir, undecided, usage))
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


def watched_read(listing: list[Listed], agents: Sequence[Agent], undecided: list[str],
                 opened: float) -> list[Watched]:
    """`watched` of `listing`, with `agents` as the operators' launches."""
    return watched(listing, {a.agent_id for a in agents if a.agent_id}, undecided, opened)


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
    """`State.open_operators`: the operators after `me` in `runs` whose work
    is open."""
    return frozenset(aid for aid, p in runs[run_index(runs, me) + 1:] if work_open(p, []))


def work_of(listing: list[Listed]) -> dict[str, tuple[str, ...]]:
    """The command line of each span of the work still running of each
    agent of `listing`, by agent id."""
    return {aid: tuple(sp.command for sp in x.running)
            for x in listing if (aid := x.launch.agent) is not None}


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


def operators_read(read: list[tuple[str, Path]], main: Path, undecided: list[str],
                   tree: GitRead) -> OperatorRead:
    """What the transcripts of the operators `read`, by agent id and
    transcript, give together, as `OperatorRead` gives it of one, with the
    doc reviewers of their doc editors (`editor_reviewers`). A commit's
    subject stands at the latest time `tree` gives it."""
    subjects = commit_subjects(tree)
    ones = [read_operator(aid, path, main, undecided, subjects) for aid, path in read]
    launched = joined([one.launched for one in ones])
    reviewers = editor_reviewers(launched.agents, main, undecided)
    return OperatorRead(
        joined([launched, reviewers]), tuple(c for one in ones for c in one.calls),
        tuple(m for one in ones for m in one.messages),
        {k: v for one in ones for k, v in one.passes.items()})


@dataclass(frozen=True)
class EndsRead:
    """The operators' agents with their ends read (`ends_read`), the reports
    that end them, by agent id, or None where none does (`ended`), the
    part of those of stalled agents (`TranscriptsRead.stalled`), and
    `TranscriptsRead.quiet`."""
    agents: tuple[Agent, ...]
    ended: Mapping[str, Report | None]
    stalled: Mapping[str, Report]
    quiet: Mapping[str, float]


def ends_read(agents: Sequence[Agent], me: str, listing: list[Listed],
              now_watched: Sequence[Watched], now: float, undecided: list[str]) -> EndsRead:
    """`agents`, each pending one ended where a stall alert fired on it, where
    it is of another operator whose work is no longer open
    (`ended_elsewhere`), or where it stopped with work of its own still
    running and is quiet. A watched agent that no operator launched, and
    that the coordinator launched, has its stall read too."""
    launched = {a.agent_id for a in agents if a.agent_id}
    watched_ids = {w.agent_id for w in now_watched}
    coordinators = {aid: x.launch.since for x in listing
                    if (aid := x.launch.agent) in watched_ids and aid not in launched}
    stalled = stalled_reports(list(agents), coordinators,
                              [w.agent_id for w in now_watched if w.stalled is not None])
    ended: dict[str, Report | None] = {**ended_elsewhere(list(agents), me, undecided), **stalled}
    quiet = quiet_read([a for a in agents if a.agent_id not in ended], listing, now)
    ended.update(dict.fromkeys(aid for a in agents if a.waits is Waits.STILL_RUNNING
                               and (aid := a.agent_id) is not None and aid in quiet))
    return EndsRead(tuple(ended_by(agents, ended)), ended, stalled, quiet)


def quiet_read(agents: Sequence[Agent], listing: list[Listed], now: float) -> dict[str, float]:
    """`TranscriptsRead.quiet` of `agents`. An agent the usage limit stopped
    is left out, since `limit_resume` covers it, and so is an agent whose
    transcript is not found."""
    out: dict[str, float] = {}
    for a in agents:
        if a.agent_id is None or a.waits in (None, Waits.LIMITED):
            continue
        try:
            path = find(a.agent_id)
        except Refused:
            continue
        q = quiet_since(a.agent_id, path, listing, now)
        if q is not None:
            out[a.agent_id] = q
    return out


def stuck_read(session: str, quiet: Mapping[str, float], now_watched: Sequence[Watched],
               running_work: Mapping[str, tuple[str, ...]]) -> dict[str, Stuck]:
    """`TranscriptsRead.stuck` of the agents of `quiet` and `now_watched`,
    where `running_work` gives the command lines of each agent's work
    still running. A watched agent's `Watched.stuck` stands in place of
    its time in `quiet`."""
    return {aid: Stuck(session, q, running_work.get(aid, ()))
            for aid, q in [*quiet.items(), *((w.agent_id, w.stuck) for w in now_watched)]
            if q is not None}


def undecided_lines(me: str, runs: list[tuple[str, Path]], calls: Sequence[Call],
                    agents: Sequence[Agent], others: Sequence[Agent], took_up: frozenset[str],
                    ended: Mapping[str, Report | None], undecided: list[str]) -> list[str]:
    """The lines of `undecided` that `MonitorState.undecided` gives: each
    on a run or an agent the read knows, that no final reply of an
    earlier operator gave (`given_lines`), and whose text a step of `me`
    still reads (`text_readers`) or is not gone."""
    known = {a.agent_id for a in (*agents, *others) if a.agent_id} | {aid for aid, _ in runs}
    given = given_lines(runs, me, list(calls))
    readers = text_readers(me, took_up, ended, agents)
    return [line for line in dict.fromkeys(undecided)
            if (where := line.split(":", 1)[0]) in known and unknown_line(line) not in given
            and (where in readers or not gone_line(line))]


@dataclass(frozen=True)
class HoldersRead:
    """The transcript of each holder of an assigned ticket (`found`), those
    of them whose work is open (`State.open_holders`), and
    `State.session_holders`."""
    found: Mapping[str, Path]
    open: frozenset[str]
    session: frozenset[str]


def holders_read(tickets: Mapping[str, Ticket], session: str, main_path: Path,
                 sessions_running: frozenset[str] | None) -> HoldersRead:
    """`HoldersRead` of `tickets`, where `main_path` is the transcript of
    `session`. A holder that is a session is open where
    `sessions_running` gives it, and any other where its work is open."""
    holders = {t.holder for t in tickets.values() if t.status is Status.ASSIGNED and t.holder}
    found = {h: find(h) for h in sorted(holders)}
    open_paths = {h: p for h, p in found.items()
                  if (h in sessions_running if sessions_running is not None
                      and not is_subagent(p) else work_open(p, []))}
    return HoldersRead(found, frozenset(open_paths), frozenset(
        h for h, p in open_paths.items()
        if p == main_path or p.is_relative_to(main_path.parent / session)))


def computed_read(state: State, tickets_dir: Path, undecided: list[str],
                  usage: Usage) -> Computed:
    """`State.computed` of `state`, at the usage `usage`."""
    tickets = state.tracker.tickets
    given = [ticket_number(n) for n in named(state) if n in tickets]
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
        pace=(pace_reads(given_pace, usage) if isinstance(given_pace, Path)
              else (given_pace or pacing.DEFAULT)(usage)),
        audit_window=audit_window_read(state, undecided))


def audit_window_read(state: State, undecided: list[str]) -> AuditWindow | NotComputed:
    """The window of the next cost audit under the session's transcript
    directory, or why it does not read."""
    try:
        return window(state.transcripts_dir, state.started, undecided)
    except Refused as exc:
        return NotComputed(str(exc))


def with_quiet_holders(state: State, found: Mapping[str, Path], listing: list[Listed],
                       running_work: Mapping[str, tuple[str, ...]]) -> State:
    """`state` with each live holder of a ticket of `plan.elsewhere` that is
    quiet in `TranscriptsRead.stuck`, where `found` gives each holder's
    transcript."""
    stuck = state.transcripts.stuck
    holders = dict.fromkeys(h for n in elsewhere(state)
                            if (h := state.tracker.tickets[n].holder) is not None
                            and h not in stuck)
    quiet = {h: q for h in holders
             if (q := quiet_since(h, found[h], listing, state.now)) is not None}
    added = stuck_read(state.session, quiet, (), running_work)
    return replace(state, transcripts=replace(state.transcripts, stuck={**stuck, **added}))


def text_readers(me: str, took_up: frozenset[str], ended: Mapping[str, Report | None],
                 agents: Sequence[Agent]) -> frozenset[str]:
    """The runs and agents whose texts a step of `me` still reads: `me`, the
    operators it takes up, the agents whose report the read hands to `me`,
    and each agent one of those launched. A gone file of any other text
    leaves no `undecided` line in the reply."""
    out = {me, *took_up, *ended}
    while added := {a.agent_id for a in agents
                    if a.agent_id and a.agent_id not in out and a.operator in out}:
        out |= added
    return frozenset(out)


def editor_reviewers(agents: Sequence[Agent], main: Path, undecided: list[str]) -> AgentsRead:
    """The doc reviewers that the doc editors among `agents` launched, read
    from those editors' transcripts as an operator's launches are read,
    with the doc editor as their `operator`."""
    out: list[Agent] = []
    reads: list[AgentsRead] = []
    for a in agents:
        if a.role is not Role.DOC_EDITOR or a.agent_id is None:
            continue
        theirs = read_operator(a.agent_id, find(a.agent_id), main, undecided, {})
        out += [r for r in theirs.agents if r.role is Role.DOC_REVIEWER]
        reads.append(theirs.launched)
    return kept(out, reads)


def elsewhere_agents(tickets: Mapping[str, Ticket], me: str, operators: frozenset[str],
                     main: Path, undecided: list[str]) -> AgentsRead:
    """`TranscriptsRead.elsewhere` over the changes of `tickets` `me` holds, where
    `operators` gives the operators of the session. Each agent kept whose
    work is no longer open ends with its final reply, as `ended_elsewhere`
    gives it. Where the transcript of such an operator is not found, an
    `undecided` line names it."""
    out: list[Agent] = []
    reads: list[AgentsRead] = []
    for t in (t for t in tickets.values() if holds(t, me)):
        since = left_draft(t)
        others = dict.fromkeys(ln.agent_id for ln in t.log
                               if ln.time > since and ln.agent == AGENT and ln.agent_id
                               and ln.agent_id not in operators)
        for oid in others:
            try:
                path = find(oid)
            except Refused:
                undecided.append(mctx("{run}: no transcript of operator {agent} of another "
                                      "session is found, so its agents on change {number} are "
                                      "not read").format(run=me, agent=oid, number=t.number))
                continue
            one = read_operator(oid, path, main, undecided, {})
            theirs = [a for a in one.agents if a.launched > since and on_change(a, t.number)]
            reviewers = editor_reviewers(theirs, main, undecided)
            reads += [one.launched, reviewers]
            theirs += [r for r in reviewers.agents
                       if r.launched > since and on_change(r, t.number)]
            out += ended_by(theirs, ended_elsewhere(theirs, me, undecided))
    return kept(sorted(out, key=lambda a: a.launched), reads)


def read_held(tickets: Mapping[str, Ticket], me: str, tree: GitRead) -> HeldRead:
    """The read of the worktrees of the tickets of `tickets` that `me`
    holds."""
    trees = {w for t in tickets.values() if holds(t, me)
             and (w := worktree_in(t, tree.worktrees)) is not None}
    return HeldRead(gate_outputs=ReadOnUse(sorted(trees), gate_outputs),
                    fragments=ReadOnUse(sorted(trees), fragments))
