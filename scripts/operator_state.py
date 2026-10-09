"""The assembly of the state the operator's procedures read, from the reads
of the ticket tracker, of git and the main worktree, and of the
transcripts of the session's operators, and of the state the monitor's
steps read (`read_watch`), from those and from the session's running
agents and the coordinator's transcript."""

import contextlib
import io
import os
import statistics
import sys
import time
from dataclasses import replace
from functools import partial
from pathlib import Path

from agent_launches import session_launches
from agent_turns import first_time
from budgets import budgets_in_force
from context_bound_hook import OPERATOR, past_bound
from controlled_markdown import mctx
from filed_texts import report_file
from open_agents import Listed, running_agents, work_open
from operator_reads import (ended_elsewhere, ended_with, operator_runs, read_operator,
                            stalled_reports)
from run_prints import active_of, print_running
from run_reads import (MAIN, agent_messages, agent_type, context_size, notifications, run_entries,
                       session_agents)
from run_reads import Status as TaskStatus
from ticket_numbers import session_index, ticket_number
from ticket_reads import read_tickets
from ticket_settle import to_settle
from transcripts import Refused, entries_back, epoch, find, main_transcript, new_state, session_directory
from tree_reads import claims, code_review, commits, gate_outputs, main_tree, scratch, worktrees

from operations.directives import named
from operations.plan import taken_up
from operations import monitor
from operations.monitor import (HUNG_FACTOR, Audit, Facet, MonitorState, Read,
                                ToCoordinator, Watched)
from operations.alerts import AlertKind
from operations.roles import Role
from operations.state import Agent, Call, Message, Report, State
from operations.filing import alert_path
from operations.handled import made, sent_with
from operations.steps import BLOCK_SECONDS
from operations.tracker import worktree
from ticketing.vocabulary import Status


def read_state(me: str) -> State:
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
    stalled = stalled_reports(agents, stall_findings(agents))
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
        me=me, now=time.time(), session=session, index=index, main_tree=main,
        scratch=scratch(session), operators=tuple(aid for aid, _ in runs),
        open_operators=frozenset(aid for aid, p in runs[[a for a, _ in runs].index(me) + 1:]
                                 if work_open(p, [])),
        past_bound=past_bound(context_size(entries_back(my_path))),
        open_holders=frozenset(h for h in holders if work_open(find(h), [])),
        tickets=tickets, agents=tuple(sorted(agents, key=lambda a: a.launched)),
        calls=tuple(sorted(calls, key=lambda c: c.time)), messages=tuple(messages),
        to_settle=(), worktrees=frozenset(trees), claims=claims(main),
        commits=history, code_review=code_review(main),
        pass_tickets=passes, stalled=stalled,
        made=made(calls), unread=unread,
        branches={w: b for w, b in trees.items() if b is not None})
    state = replace(state, taken_up=taken_up(state))
    given = [ticket_number(n) for n in named(state) if n in tickets]
    held = {w for t in tickets.values() if t.status is Status.ASSIGNED and t.holder == me
            and (w := worktree(t, state)) is not None}
    return replace(state,
                   to_settle=tuple(str(n) for n in to_settle(tickets_dir, index, given)
                                   if str(n) in tickets),
                   gate_outputs={w: gate_outputs(w) for w in held})


UNWATCHED = frozenset({OPERATOR, Role.OP_AUDITOR.agent_type})
"""The agent types the monitor's steps do not watch."""


def usual(listed: Listed, listing: list[Listed], label: str) -> float:
    """The median duration of the ended calls of `listed` with `label`, or
    where it has none, of those of every run of `listing`, or where none
    has one, `BLOCK_SECONDS`."""
    def ended(runs: list[Listed]) -> list[float]:
        return [s.end - s.start for r in runs for s in r.run.spans
                if s.label == label and s.end is not None]
    durations = ended([listed]) or ended(listing)
    return statistics.median(durations) if durations else BLOCK_SECONDS


def hung_at(listed: Listed, listing: list[Listed]) -> float | None:
    """The earliest time a call of `listed` in flight passed `HUNG_FACTOR`
    times its label's usual time, or None where none has."""
    now = time.time()
    times = [at for s in listed.run.in_flight
             if (at := s.start + HUNG_FACTOR * usual(listed, listing, s.label)) <= now]
    return min(times, default=None)


def activity(listed: Listed) -> float:
    """The time of the latest call, end of a call, end of the turn or
    report of `listed`."""
    r = listed.run
    times = [s.start for s in r.spans] + [s.end for s in r.spans if s.end is not None]
    times += [rep.time for rep in listed.found or []]
    if listed.end is not None:
        times.append(listed.end)
    if r.start is not None:
        times.append(r.start)
    return max(times, default=0.0)


def facts(listed: Listed, since: float | None, undecided: list[str]) -> str:
    """The listing `profile_runs.py --running` prints of `listed`, with its
    calls since `since`."""
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        print_running([listed], time.time(), since, undecided)
    return out.getvalue().rstrip("\n")


def watched(listing: list[Listed], launched: dict[str, Role], audits: list[Audit],
            undecided: list[str]) -> list[Watched]:
    """The agents of `listing` that an operator launched, by `launched`,
    their roles by agent id, other than the auditors."""
    out: list[Watched] = []
    now = time.time()
    for listed in listing:
        r = listed.run
        aid = listed.launch.agent
        if aid is None or r.agent_type in UNWATCHED or (role := launched.get(aid)) is None:
            continue
        past = [a.launched for a in audits if a.facet is Facet.AGENT and a.agent_id == aid]
        budget = next(reversed(budgets_in_force(r, undecided)), None)
        active = active_of(listed, now)
        out.append(Watched(
            agent_id=aid, agent_type=r.agent_type, role=role, parent=listed.parent,
            activity=activity(listed), hung=hung_at(listed, listing), ended=listed.ended,
            over_budget=budget is not None and active is not None and active > budget * 60,
            facts=facts(listed, max(past, default=None), undecided), transcript=r.path))
    return out


def audit_of(a: Agent, undecided: list[str]) -> Audit | None:
    """The audit the launch `a` gives, or None where it is no auditor's, or
    where its subject is in no form `monitor.subject` gives: that launch
    counts as no audit, so the activity it was to audit stays new, and
    `undecided` gains a line on it. A latest report that still has a report
    file's path as its text is one whose file `agent_reports.reports_after`
    found gone."""
    if a.role is not Role.OP_AUDITOR or a.agent_id is None:
        return None
    given = monitor.subject_of(a.subject)
    if given is None:
        undecided.append(mctx("{agent}: this auditor's launch has the subject `{subject}`, in "
                              "no form the command gives, so it counts as no audit")
                         .format(agent=a.agent_id, subject=a.subject))
        return None
    replies = tuple(r.time for r in a.reports)
    read, found, alert = Read.PENDING, None, None
    if a.last_report is not None and not a.pending:
        text, path = a.last_report.text, a.last_report.file
        if path is None and report_file(text) is not None:
            read = Read.GONE
        else:
            found = monitor.finding(text)
            read = Read.UNREAD if found is None else Read.READ
            if found is not None and found.alert in monitor.TO_AGENT and path is not None:
                given_file = alert_path(path)
                alert = given_file.read_text().strip() if given_file.is_file() else None
    return Audit(a.agent_id, *given, a.launched, replies, read, found, alert)


def stall_findings(agents: list[Agent]) -> list[str]:
    """The agents the `stall` findings of the auditors of `agents` are on.
    The lines `audit_of` gives on what it left unknown go to `read_watch`
    alone."""
    return [f.agent for x in agents if (a := audit_of(x, [])) is not None
            and (f := a.finding) is not None and f.alert is AlertKind.STALL
            and f.agent is not None]


def to_coordinator(session: Path, since: float, undecided: list[str]) -> list[ToCoordinator]:
    """The messages to the coordinator from a watched agent of the session
    that the coordinator did not launch, and the notifications of the end
    of one, that the coordinator's transcript gained since `since`."""
    parents = {kid: launcher for launcher, kids in session_launches(session)[1].items()
               for kid in kids}
    agents: dict[str, tuple[str, str, Path]] = {}
    for aid, p in session_agents(session).items():
        kind = agent_type(p)
        if kind is None or kind in UNWATCHED:
            continue
        if aid not in parents:
            undecided.append(mctx("{agent}: no `.meta.json` gives its parent, so its messages "
                                  "to the coordinator are not audited").format(agent=aid))
            continue
        if parents[aid] != MAIN:
            agents[aid] = (kind, parents[aid], p)
    out: list[ToCoordinator] = []
    for e in run_entries(main_transcript(session)):
        stamp = e.get("timestamp")
        if e.get("type") != "user" or not stamp or (t := epoch(stamp)) <= since:
            continue
        for sender, text in agent_messages(e):
            if sender in agents:
                out.append(ToCoordinator(sender, *agents[sender], t, text))
        for n in notifications(e):
            if n.status is TaskStatus.RUNNING:
                continue
            text = n.result or n.note
            for aid in n.ids:
                if aid not in agents:
                    continue
                if not text:
                    undecided.append(mctx("{agent}: a notification of its end gives neither "
                                          "a result nor a note, so it is not audited").format(
                                              agent=aid))
                else:
                    out.append(ToCoordinator(aid, *agents[aid], t, text))
    return out


def read_watch(state: State) -> MonitorState:
    """The state the monitor's steps read, for the session's operators of
    `state`."""
    undecided: list[str] = []
    audits = [a for x in state.agents if (a := audit_of(x, undecided)) is not None]
    start = first_time(find(state.operators[0]))
    if start is None:
        raise Refused(mctx("the transcript of {agent} gives no time").format(
            agent=state.operators[0]))
    session = find(state.session)
    launched = {a.agent_id: a.role for a in state.agents if a.agent_id}
    return MonitorState(
        watched=tuple(watched(running_agents(session, undecided), launched, audits, undecided)),
        to_coordinator=tuple(to_coordinator(session_directory(session), start, undecided)),
        audits=tuple(audits), sent=partial(sent_with, state),
        transcript=find(state.me), stalled=frozenset(state.stalled), undecided=tuple(undecided))
