"""The assembly of the state the procedures of the `operations` mod's loop
read, from the reads of the ticket tracker, of git and the main worktree,
of the loop's record, and of the transcripts of the session and of the
agents the loop launched."""

import os
import re
import sys
import time
from dataclasses import replace

from loop_reads import (
    ended_with,
    stalled_reports,
)
from open_agents import work_open
from ops_record import holder, read_record, record_agents, record_messages
from ticket_numbers import session_index, ticket_number
from ticket_reads import read_tickets
from ticket_settle import to_settle
from transcripts import Refused, find, new_state
from tree_reads import claims, code_review, commits, gate_outputs, main_tree, scratch, worktrees

from controlled_markdown import mctx
from operations.directives import named, passed_over
from operations.roles import LOOP_HOLDER as LOOP_HOLDER_FORM
from operations.state import State
from operations.tracker import worktree
from ticketing.vocabulary import Status

LOOP_HOLDER = re.compile(LOOP_HOLDER_FORM)

def read_state(loop: str) -> State:
    new_state()
    session = os.environ.get("CLAUDE_CODE_SESSION_ID")
    if not session:
        raise Refused(mctx("the shell gives no `CLAUDE_CODE_SESSION_ID`"))
    main = main_tree()
    tickets_dir = main / "tickets"
    undecided: list[str] = []
    history = commits(main)
    subjects: dict[str, float] = {}
    for c in history:
        subjects[c.subject] = max(subjects.get(c.subject, c.time), c.time)
    passes: dict[str, tuple[str, ...] | None] = {}
    me = holder(session)
    calls, recorded, messages = read_record(scratch(session), loop, me, subjects, undecided)
    agents = record_agents(calls, main, passes)
    messages += record_messages(me, scratch(session), session, agents, undecided)
    stalled = stalled_reports(agents, messages)
    agents = [ended_with(a, stalled[a.agent_id]) if a.pending and a.agent_id in stalled else a
              for a in agents]
    for line in dict.fromkeys(undecided):
        print(f"operate: undecided: {line}", file=sys.stderr)
    tickets = read_tickets(tickets_dir)
    index = session_index(tickets_dir, session)
    holders = {t.holder for t in tickets.values() if t.status is Status.ASSIGNED and t.holder}
    trees = worktrees(main)
    state = State(
        me=me, now=time.time(), session=session, index=index, main_tree=main,
        scratch=scratch(session),
        # The loop of a session holds its tickets while that loop runs, and no
        # transcript gives whether it runs.
        open_holders=frozenset(h for h in holders
                               if LOOP_HOLDER.fullmatch(h) or work_open(find(h), [])),
        tickets=tickets, agents=tuple(sorted(agents, key=lambda a: a.launched)),
        calls=tuple(calls), messages=tuple(messages),
        to_settle=(), worktrees=frozenset(trees), claims=claims(main),
        commits=history, code_review=code_review(main),
        pass_tickets=passes, stalled=stalled, made=tuple(recorded),
        branches={w: b for w, b in trees.items() if b is not None})
    given = [ticket_number(n) for n in named(state) if n in tickets]
    held = {w for t in tickets.values() if t.status is Status.ASSIGNED and t.holder == me
            and (w := worktree(t, state)) is not None}
    return replace(state,
                   to_settle=tuple(str(n) for n in to_settle(tickets_dir, index, given)
                                   if str(n) in tickets),
                   gate_outputs={w: gate_outputs(w) for w in held},
                   passed=passed_over(state))
