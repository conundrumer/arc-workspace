"""The assembly of the state the operator's procedures read, from the reads
of the ticket tracker, of git and the main worktree, and of the
transcripts of the session's operators."""

import os
import sys
import time
from dataclasses import replace

from context_bound_hook import past_bound
from controlled_markdown import mctx
from open_agents import work_open
from operator_reads import (ended_elsewhere, ended_with, operator_runs, read_operator,
                            stalled_reports, wait_task)
from run_reads import context_size
from ticket_numbers import session_index, ticket_number
from ticket_reads import read_tickets
from ticket_settle import to_settle
from transcripts import Refused, entries_back, find, new_state
from tree_reads import claims, code_review, commits, gate_outputs, main_tree, scratch, worktrees

from operating.directives import named
from operating.state import Agent, Call, Message, Report, State
from operating.steps import made, pass_overs, passed_over_line
from operating.tracker import worktree
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
    stalled = stalled_reports(agents, messages)
    ended: dict[str, Report | None] = {**ended_elsewhere(agents, me), **stalled}
    agents = [ended_with(a, ended[a.agent_id]) if a.pending and a.agent_id in ended else a
              for a in agents]
    known = {a.agent_id for a in agents if a.agent_id} | {aid for aid, _ in runs}
    for line in dict.fromkeys(undecided):
        if line.split(":", 1)[0] in known:
            print(f"operate: undecided: {line}", file=sys.stderr)
    tickets = read_tickets(tickets_dir)
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
        commits=history, code_review=code_review(main), wait_task=wait_task(me, my_path),
        pass_tickets=passes, stalled=stalled,
        passed={k: line for c in calls if c.tool == "Bash"
                for k, line in pass_overs(str(c.input.get("command", "")))
                if c.result is None or passed_over_line(k) in c.result},
        made=made(calls),
        branches={w: b for w, b in trees.items() if b is not None})
    given = [ticket_number(n) for n in named(state) if n in tickets]
    held = {w for t in tickets.values() if t.status is Status.ASSIGNED and t.holder == me
            and (w := worktree(t, state)) is not None}
    return replace(state,
                   to_settle=tuple(str(n) for n in to_settle(tickets_dir, index, given)
                                   if str(n) in tickets),
                   gate_outputs={w: gate_outputs(w) for w in held})
