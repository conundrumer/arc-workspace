"""The assembly of the state the operator's procedures read, from the reads
of the ticket tracker, of git and the main worktree, and of the
transcripts of the session's operators, and of the state the monitor's
steps read (`monitor_reads`)."""

import time
from dataclasses import replace
from pathlib import Path

from agent_turns import first_time, last_time
from context_bound_hook import past_bound
from held_budgets import change_budgets, change_spend, doc_budgets
from idle_sessions import main_wanted, read_sessions, running, want_main
from monitor_reads import late_resumes, watched
from open_agents import running_agents, work_open
from operator_reads import (
    ended_elsewhere,
    ended_with,
    operator_runs,
    read_operator,
    stalled_reports,
)
from relay_reads import run_index, session_id
from run_reads import context_size, parent_id
from run_scripts import read_runs
from state_reads import new_state
from ticket_numbers import session_index, ticket_number
from ticket_reads import read_tickets
from ticket_settle import to_settle
from transcripts import Refused, entries_back, find, is_subagent
from tree_reads import (
    claims,
    code_review,
    commits,
    doc_reviews,
    fragments,
    gate_outputs,
    main_tree,
    read_seen,
    scratch,
    worktrees,
)
from usage_limit import limit_lifted

from controlled_markdown import mctx
from engine.checkout import agents_of
from handbook.reader_names import ReaderName
from handbook.readers import reader_calls
from operations import change_fragments
from operations.directives import named
from operations.final_reply import final_sends_in, for_context, sent_final_text
from operations.handled import made
from operations.monitor import MonitorState
from operations.plan import taken_up, unknown_line
from operations.roles import Role
from operations.state import (
    Agent,
    Call,
    Computed,
    Deferred,
    GitRead,
    HeldRead,
    Message,
    Reader,
    ReadOnUse,
    Report,
    SessionsRead,
    State,
    TrackerRead,
    TranscriptsRead,
)
from operations.worktrees import worktree_in
from ticketing.vocabulary import Status

DEPRECATED = frozenset({ReaderName.ROLE, ReaderName.CONSOLE, ReaderName.SURVEY,
                        ReaderName.WORKFLOW})
"""The readers of the deprecated mechanisms, which no standing doc review
reads."""


def read_state(me: str, since: float | None = None) -> tuple[State, MonitorState]:
    """The state the operator's procedures read, and the state the
    monitor's steps read. Where `since` is given, the transcripts read for
    launches, calls, messages and late resumes are only those of `me` and
    of the operators whose last entry is at or after `since`: an agent
    launched since then is launched by one of those."""
    opened = new_state()
    session = session_id()
    main = main_tree()
    tickets_dir = main / "tickets"
    undecided: list[str] = []
    runs = operator_runs(session, me)
    if me not in dict(runs):
        runs.append((me, find(me)))
    agents: list[Agent] = []
    calls: list[Call] = []
    messages: list[Message] = []
    passes: dict[str, tuple[str, ...] | None] = {}
    tree = read_git(main)
    subjects: dict[str, float] = {}
    for c in tree.commits:
        subjects[c.subject] = max(subjects.get(c.subject, c.time), c.time)
    read = [(aid, path) for aid, path in runs
            if since is None or aid == me or (t := last_time(path)) is not None and t >= since]
    for aid, path in read:
        one = read_operator(aid, path, main, undecided, subjects)
        agents += one.agents
        calls += one.calls
        messages += one.messages
        passes.update(one.passes)
    agents += editor_reviewers(agents, main, undecided)
    late = late_resumes(read, undecided)
    launched = {a.agent_id for a in agents if a.agent_id}
    watching: list[str] = []
    listing = running_agents(find(session), watching)
    now_watched = watched(listing, launched, watching, opened)
    watched_ids = {w.agent_id for w in now_watched}
    coordinators = {aid: x.launch.since for x in listing
                    if (aid := x.launch.agent) in watched_ids and aid not in launched}
    stalled = stalled_reports(agents, coordinators,
                              [w.agent_id for w in now_watched if w.stalled is not None])
    ended: dict[str, Report | None] = {**ended_elsewhere(agents, me, undecided), **stalled}
    agents = [ended_with(a, ended[a.agent_id]) if a.pending and a.agent_id in ended else a
              for a in agents]
    known = {a.agent_id for a in agents if a.agent_id} | {aid for aid, _ in runs}
    given = given_lines(runs, me, calls)
    watching.extend(line for line in dict.fromkeys(undecided)
                    if line.split(":", 1)[0] in known and unknown_line(line) not in given)
    tickets, unread = read_tickets(tickets_dir)
    index = session_index(tickets_dir, session)
    holders = {t.holder for t in tickets.values() if t.status is Status.ASSIGNED and t.holder}
    my_path = dict(runs)[me]
    holding = {t.number: w for t in tickets.values() if t.status is Status.ASSIGNED
               and t.holder == me and (w := worktree_in(t, tree.worktrees)) is not None}
    sorted_calls = tuple(sorted(calls, key=lambda c: c.time))
    parents = {aid: parent_id(p) for aid, p in runs}
    operators = tuple(aid for aid, _ in runs)
    now = time.time()
    main_path = find(session)
    session_dir = main_path.parent / session
    found = {h: find(h, recheck=True) for h in sorted(holders)}
    sessions_running = running(session)
    open_paths = {h: p for h, p in found.items()
                  if (h in sessions_running if sessions_running is not None and not is_subagent(p)
                      else work_open(p, []))}
    state = State(
        me=me, now=now, session=session, started=started(session),
        transcripts_dir=main_path.parent, main_tree=main,
        scratch=scratch(session), operators=operators, parents=parents,
        open_operators=frozenset(aid for aid, p in runs[run_index(runs, me) + 1:]
                                 if work_open(p, [])),
        past_bound=past_bound(context_size(entries_back(my_path))),
        open_holders=frozenset(open_paths),
        session_holders=frozenset(h for h, p in open_paths.items()
                                  if p == main_path or p.is_relative_to(session_dir)),
        tracker=TrackerRead(tickets, unread, index),
        transcripts=TranscriptsRead(
            agents=tuple(sorted(agents, key=lambda a: a.launched)),
            calls=sorted_calls, messages=tuple(messages),
            made=made(calls), late_resumes=late, stalled=stalled, pass_tickets=passes),
        git=tree, taken_up=taken_up(me, operators, sorted_calls, parents),
        held=read_held(holding, scratch(session)),
        readers=Deferred(lambda: tuple(Reader(name, tuple(args)) for name, args in reader_calls()
                                       if name not in DEPRECATED)),
        limit_lifted=limit_lifted(now, watching),
        sessions=sessions(tickets_dir, index, session, now))
    given = [ticket_number(n) for n in named(state) if n in tickets]
    spent = change_spend(state, undecided)
    run_starts, run_takes = read_runs(state)
    state = replace(state, computed=Computed(
        to_settle=tuple(str(n) for n in to_settle(tickets_dir, index, state.sessions.adopted, given)
                        if str(n) in tickets),
        spent=spent, budgets=change_budgets(state, spent, tickets_dir, undecided),
        doc_budgets=doc_budgets(state, tickets_dir, undecided),
        run_starts=run_starts, run_takes=run_takes))
    return state, MonitorState(watched=tuple(now_watched), stalled=frozenset(stalled),
                               undecided=tuple(watching))


def read_git(main: Path) -> GitRead:
    """The read of git and of the main tree `main`."""
    trees = worktrees(main)
    return GitRead(commits(main), frozenset(trees),
                   {w: b for w, b in trees.items() if b is not None}, claims(main),
                   code_review(main), doc_reviews(main),
                   {d.stem: d.stat().st_mtime for d in sorted(agents_of(main).glob("*.md"))})


def sessions(tickets: Path, index: int, session: str, now: float) -> SessionsRead:
    """The read of `idle_sessions`. Where an index is idle and no main is
    live, the read first creates `tickets/main-wanted` with the session's
    id where no file holds that name, so that one session asks the user to
    pick a main (`triage.main_wanted`)."""
    read = read_sessions(tickets, index, now)
    if read.idle and not read.main and not read.main_live:
        want_main(tickets, session)
    return SessionsRead(read.idle, read.adopted, read.main_live, main_wanted(tickets))


def editor_reviewers(agents: list[Agent], main: Path, undecided: list[str]) -> list[Agent]:
    """The doc reviewers that the doc editors among `agents` launched, read
    from those editors' transcripts as an operator's launches are read,
    with the doc editor as their `operator`."""
    out: list[Agent] = []
    for a in agents:
        if a.role is not Role.DOC_EDITOR or a.agent_id is None:
            continue
        theirs = read_operator(a.agent_id, find(a.agent_id), main, undecided, {}).agents
        out += [r for r in theirs if r.role is Role.DOC_REVIEWER]
    return out


def read_held(holding: dict[str, Path], scratch: Path) -> HeldRead:
    """The read of the changes `me` holds, where `holding` gives the
    worktree of each by its number, and `scratch` is the session's
    scratchpad."""
    trees = set(holding.values())
    return HeldRead(gate_outputs=ReadOnUse(sorted(trees), gate_outputs),
                    fragments=ReadOnUse(sorted(trees), fragments),
                    seen={n: read_seen(change_fragments.seen_dir(n, scratch)) for n in holding})


def given_lines(runs: list[tuple[str, Path]], me: str, calls: list[Call]) -> set[str]:
    """The lines of each final reply that an operator of `runs` before `me`
    sent its parent, other than one that ends it for its context: a line
    one of them gave reaches the coordinator in no later reply."""
    out: set[str] = set()
    for aid, path in runs[:run_index(runs, me)]:
        for c in final_sends_in(calls, aid, parent_id(path)):
            text = sent_final_text(c)
            if text is not None and not for_context(text):
                out.update(text.split("\n"))
    return out


def started(aid: str) -> float:
    t = first_time(find(aid))
    if t is None:
        raise Refused(mctx("the transcript of {agent} gives no time").format(agent=aid))
    return t
