"""The assembly of the state the operator's procedures read, from the reads
of the ticket tracker, of git and the main worktree, and of the
transcripts of the session's operators, and of the state the monitor's
steps read, from the session's running agents and their transcripts."""

import os
import sys
import time
from dataclasses import replace

from agent_reports import parent_transcripts
from agent_turns import first_time, last_time
from budgets import budgets_in_force
from context_bound_hook import OPERATOR, past_bound
from controlled_markdown import mctx
from open_agents import Listed, hung_time, running_agents, work_open
from operator_reads import (ended_elsewhere, ended_with, operator_runs, read_operator,
                            stalled_reports)
from run_prints import active_of
from run_reads import bash_spans, context_size, repeated_runs, run_entries
from ticket_numbers import session_index, ticket_number
from ticket_reads import read_tickets
from ticket_settle import to_settle
from transcripts import Refused, entries_back, find, new_state
from tree_reads import (claims, code_review, commits, doc_reviews, gate_outputs, main_tree,
                        scratch, worktrees)

from handbook.reader_names import ReaderName
from handbook.readers import reader_calls

from operations.directives import named
from operations.plan import taken_up
from operations import monitor
from operations.monitor import MonitorState, Watched
from operations.state import Agent, Call, Message, Reader, Report, State
from operations.handled import made
from operations.tracker import worktree
from ticketing.vocabulary import Status


DEPRECATED = frozenset({ReaderName.ROLE, ReaderName.CONSOLE, ReaderName.SURVEY,
                        ReaderName.WORKFLOW})
"""The readers of the deprecated mechanisms, which no standing doc review
reads."""


def read_state(me: str) -> tuple[State, MonitorState]:
    """The state the operator's procedures read, and the state the
    monitor's steps read."""
    new_state()
    session = os.environ.get("CLAUDE_CODE_SESSION_ID")
    if not session:
        raise Refused(mctx("the shell gives no `CLAUDE_CODE_SESSION_ID`"))
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
    history = commits(main)
    subjects: dict[str, float] = {}
    for c in history:
        subjects[c.subject] = max(subjects.get(c.subject, c.time), c.time)
    for aid, path in runs:
        read_operator(aid, path, main, undecided, agents, calls, messages, passes, subjects)
    launched = {a.agent_id for a in agents if a.agent_id}
    watching: list[str] = []
    now_watched = watched(running_agents(find(session), watching), launched, watching)
    stalled = stalled_reports(agents, [w.agent_id for w in now_watched if w.stalled is not None])
    ended: dict[str, Report | None] = {**ended_elsewhere(agents, me), **stalled}
    agents = [ended_with(a, ended[a.agent_id]) if a.pending and a.agent_id in ended else a
              for a in agents]
    known = {a.agent_id for a in agents if a.agent_id} | {aid for aid, _ in runs}
    for line in dict.fromkeys(undecided):
        if line.split(":", 1)[0] in known:
            print(f"operate: undecided: {line}", file=sys.stderr)
    tickets, unread = read_tickets(tickets_dir)
    index = session_index(tickets_dir, session)
    holders = {t.holder for t in tickets.values() if t.status is Status.ASSIGNED and t.holder}
    my_path = dict(runs)[me]
    trees = worktrees(main)
    state = State(
        me=me, now=time.time(), session=session, started=started(session), index=index, main_tree=main,
        scratch=scratch(session), operators=tuple(aid for aid, _ in runs),
        open_operators=frozenset(aid for aid, p in runs[[a for a, _ in runs].index(me) + 1:]
                                 if work_open(p, [])),
        past_bound=past_bound(context_size(entries_back(my_path))),
        open_holders=frozenset(h for h in holders if work_open(find(h), [])),
        tickets=tickets, agents=tuple(sorted(agents, key=lambda a: a.launched)),
        calls=tuple(sorted(calls, key=lambda c: c.time)), messages=tuple(messages),
        to_settle=(), worktrees=frozenset(trees), claims=claims(main),
        commits=history, code_review=code_review(main),
        readers=tuple(Reader(name, tuple(args)) for name, args in reader_calls()
                      if name not in DEPRECATED),
        doc_reviews=doc_reviews(main),
        pass_tickets=passes, stalled=stalled,
        made=made(calls), unread=unread,
        branches={w: b for w, b in trees.items() if b is not None})
    state = replace(state, taken_up=taken_up(state))
    given = [ticket_number(n) for n in named(state) if n in tickets]
    held = {w for t in tickets.values() if t.status is Status.ASSIGNED and t.holder == me
            and (w := worktree(t, state)) is not None}
    state = replace(state,
                    to_settle=tuple(str(n) for n in to_settle(tickets_dir, index, given)
                                    if str(n) in tickets),
                    gate_outputs={w: gate_outputs(w) for w in held})
    return state, MonitorState(watched=tuple(now_watched), stalled=frozenset(state.stalled),
                               undecided=tuple(watching))


UNWATCHED = frozenset({OPERATOR})
"""The agent types the monitor's steps do not watch."""


def hung_at(listed: Listed, listing: list[Listed]) -> float | None:
    """The earliest time a call of `listed` in flight counted as hung, or
    None where none has."""
    now = time.time()
    times = [at for s in listed.run.in_flight
             if (at := hung_time(listed.run, [x.run for x in listing], s)) <= now]
    return min(times, default=None)


def stalled_at(listed: Listed, listing: list[Listed]) -> float | None:
    """The end of the turn of `listed` where it stalled, as
    `monitor.ALERTS` gives a stall, or None."""
    aid = listed.launch.agent
    if (not listed.ended or listed.found != [] or listed.running
            or any(x.parent == aid for x in listing)):
        return None
    end = listed.end if listed.end is not None else activity(listed)
    answered = [t for p in parent_transcripts(listed.path)
                if (t := last_time(p, lambda e: e.get("type") == "assistant")) is not None]
    return end if any(t > end for t in answered) else None


def activity(listed: Listed) -> float:
    """The time of the latest call, end of a call or end of the turn of
    `listed`."""
    r = listed.run
    times = [s.start for s in r.spans] + [s.end for s in r.spans if s.end is not None]
    if listed.end is not None:
        times.append(listed.end)
    if r.start is not None:
        times.append(r.start)
    return max(times, default=0.0)


def repeated(listed: Listed) -> tuple[float, ...]:
    """The `repeated` readings of `listed` (`run_reads.repeated_runs`)."""
    entries = run_entries(listed.path)
    calls = [(s.call, s.command, s.start) for s in bash_spans(listed.run.spans, entries)]
    return tuple(repeated_runs(calls, entries, monitor.REPEATS))


def watched(listing: list[Listed], launched: set[str],
            undecided: list[str]) -> list[Watched]:
    """The agents of `listing`, whose work is open, that an operator
    launched, by `launched`, their agent ids."""
    out: list[Watched] = []
    now = time.time()
    for listed in listing:
        r = listed.run
        aid = listed.launch.agent
        if aid is None or r.agent_type in UNWATCHED or aid not in launched:
            continue
        budget = next(reversed(budgets_in_force(r, undecided)), None)
        active = active_of(listed, now)
        out.append(Watched(
            agent_id=aid, hung=hung_at(listed, listing),
            over_budget=budget is not None and active is not None and active > budget * 60,
            stalled=stalled_at(listed, listing), repeated=repeated(listed)))
    return out


def started(aid: str) -> float:
    t = first_time(find(aid))
    if t is None:
        raise Refused(mctx("the transcript of {agent} gives no time").format(agent=aid))
    return t
