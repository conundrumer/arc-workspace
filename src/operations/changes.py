"""A change the operator holds, from its take to its merge: the editors, the review of the documents, the item checker
and the ticket analyst on what the editors leave; `doc_review` gives the
review of the documents. The steps carry out
[Carrying a change](prompts/agents/notes/changes.md#carrying-a-change);
`taking` gives the release of tickets and the take of open changes,
`merging` the merge and what follows it. `change_agents` gives the
agents of a change and the editors it needs, `item_check` the launch of
its item checker, `change_fragments` the doc editor of its `mctx`
fragments, and `change_overrun` a change past its cost budget and an
editor whose budget is passed.

A change with no worktree gets one from
`scripts/change_worktree.py`, which logs its path on the ticket, so a
later operator continues the change there. Where a change's ticket is
revised after the log line that gives its worktree, the operator runs
`scripts/change_worktree.py` again, whose `--help` gives what it carries in.
Every editor and reviewer is
launched with no isolation, and its brief gives that worktree.

What the editors' and the doc reviewer's replies give is read by the fixed
forms of `reports`. Once each editor of a change has reported, the latest report of
each editor other than the `handbook-expanded` agent that has reported since the last item checker was launched on
the change, and the accepted gate outputs the change writes, other than,
on a change with that agent, those of a `run_dl.py` command
(`item_check.checked_outputs`), go to one item checker. That checker checks the items of each such editor's part,
and an editor it sends a message reports again. So the change merges only
once an item checker was launched after the last report of each editor other than that agent, or
the latest checker sent no editor a message and its `reports.WORKTREE`
line gives the `worktrees.fingerprint` the worktree has now, as then the
worktree is in the state that checker read. The
checker gives under `reports.LEFT_FOR_DECISION` what those reports leave
for a decision.
Where no item checker is due, that part of the latest checker's reply,
where it follows the last ticket analyst's launch on the change, the
latest report of the `handbook-expanded` agent, where it follows that
launch and does not open with `reports.DONE`, and the
open `question` tickets filed on the change go to one ticket analyst.
A change whose only editor is that agent gets no item checker.
That analyst's reply leaves nothing more, unless its part for the
coordinator gives a `decision:` or an `unfinished:` item and no item
checker was launched since its launch: then the change is held on those
items, in place of its merge, and a ruling of another analyst gives that
analyst the latest checker's part, whatever its time.
Where they give a `decision:` item, the step waits on the coordinator,
which gets those items with the line that rules the step
(`triage.for_coordinator`), and otherwise it goes to a ticket analyst
(`decisions`).

A change whose `editors` field gives a doc editor, the one
`change_fragments` adds included, merges once its review passes as
`doc_review` gives.

A next step of a change that is a message an operator already sent,
whose recipient answered it, leaves the change where it was, and the
command cannot place it.

A step of a change that the command cannot place holds that change alone,
until a `Decision:` line rules it with one of the choices the step gives
(`directives.decided`)."""

import shlex
from pathlib import Path
from typing import Literal

from controlled_markdown import mctx
from operations import briefs, merging, messages
from operations.change_agents import (change_editors, editors_in, latest_editors, launched_on,
                                      of_change, unstaffed)
from operations.change_fragments import drafter_ids, fragments_step
from operations.change_overrun import over_budget, over_budget_step
from operations.doc_review import doc_review, with_ids
from operations.directives import (Decision, decided, held_on)
from operations.item_check import check_items, is_checked, latest_reports, unfinished
from operations.reports import OPEN_LABELS, Label, items_of, left_for_decision, shows_current
from operations.roles import Purpose, Role, analyst_of, analyst_subject
from operations.state import Agent, State, Ticket
from operations.filing import editor_scratch
from operations.final_reply import live_holder
from operations.handled import answered, repeated, sent, unmoved
from operations.steps import Bash, Launch, Send, Step, Undecided
from operations.log_commands import AGENT
from operations.taking import take
from operations.tracker import last_index
from operations.worktrees import WORKTREE, worktree
from ticketing.vocabulary import Domain, Kind, Note, Status


def held(state: State) -> list[Ticket]:
    return sorted((t for t in state.tracker.tickets.values()
                   if t.kind is Kind.CHANGE and t.status is Status.ASSIGNED
                   and t.holder == state.me),
                  key=lambda t: t.order)


def give_up(state: State) -> Step | None:
    """A message that tells an agent at work on a change that no operator
    carries any more, or that another live holder (`live_holder`) carries,
    to end. A live holder among the session's operators carries the same
    agents, so their work goes on."""
    for a in state.transcripts.agents:
        if not a.pending or a.agent_id is None:
            continue
        if a.role is Role.TICKET_ANALYST:
            parsed = analyst_of(a.subject)
            if parsed is None:
                continue
            number = parsed[1]
        else:
            number = a.subject
        t = state.tracker.tickets.get(number)
        if t is None or t.kind is not Kind.CHANGE or a not in launched_on(state, number):
            continue
        lost = t.status in (Status.DRAFT, Status.CLOSED) or (
            t.status is Status.ASSIGNED and t.holder not in (state.me, None)
            and live_holder(state, t.holder)
            and t.holder not in state.operators)
        message = messages.stop_work(number)
        if lost and not sent(state, a.agent_id, message):
            return Send(a.agent_id, message)
    return None


WORKTREE_SCRIPT = "scripts/change_worktree.py"


def make_worktree(number: str, agent_id: str) -> str:
    """The Bash command that makes the worktree of the change `number`."""
    return shlex.join(["uv", "run", "python", WORKTREE_SCRIPT, number, AGENT, "--id", agent_id])


def revised_since_worktree(t: Ticket) -> bool:
    given = max((i for i, line in enumerate(t.log) if WORKTREE.search(line.note)), default=-1)
    return last_index(t, (Note.FILED, Note.REVISED)) > given


def carry(state: State, t: Ticket) -> Step | None:
    """The next step on the change `t` the operator holds, or None where it
    waits on an agent."""
    if merging.merged(state, t):
        return merging.close(state, t, of_change(state, t.number))
    editors = change_editors(t)
    if not isinstance(editors, tuple):
        return editors
    agents = of_change(state, t.number)
    w = worktree(t, state)
    if w is None or revised_since_worktree(t):
        return Bash(make_worktree(t.number, state.me))
    if (step := over_budget(state, t, w, agents)) is not False:
        return step
    here = editors_in(agents, w)
    if missing := unstaffed(editors, here):
        role = missing[0]
        drafters = drafter_ids(here)
        if isinstance(drafters, Undecided):
            return drafters
        return Launch(role, t.number, briefs.editor(
            role, t.number, len(editors) > 1, w,
            editor_scratch(t.number, role, state.scratch), state.me,
            state.held.fragments.get(w, ()), tuple(drafters)), model=t.model(role))
    if any(a.pending for a in here):
        return None
    if (step := fragments_step(state, t, w, here)) is not None:
        return step
    latest = latest_editors(here)
    if (step := over_budget_step(state, t, latest)) is not None:
        return step
    if (step := leftover(state, t, w, latest, agents)) is not False:
        return step
    if Role.DOC_EDITOR in editors and (
            step := doc_review(state, t, w, here, agents)) is not False:
        return step
    return merging.merge(state, t, w, latest)


LEFT_CHOICES = {
    Decision.MERGE: mctx("go on to the merge; the close of the change closes its open question "
                       "tickets"),
    Decision.AGAIN: mctx("launch another ticket analyst on what the item checker leaves for a "
                       "decision")}
"""The choices of a step held on what the editors of a change leave."""


def left_hold(a: Agent, number: str) -> str | None:
    """The step held on the `decision:` and `unfinished:` items of the
    latest reply of `a`, the ticket analyst on what the editors of change
    `number` leave, or None where that reply gives none."""
    items = items_of(a, OPEN_LABELS)
    if items is None:
        return None
    return mctx("ticket analyst {agent} on change {number} leaves these items for the "
                "coordinator:").format(agent=a.agent_id, number=number) + (
                    "\n" + items + "\n" + mctx("The change is held on them"))


def left_decision(a: Agent, number: str) -> str | None:
    """The step held on the items `a` leaves (`left_hold`), with the line
    that rules it, which goes to the coordinator with the `decision:` items
    of `a`."""
    hold = left_hold(a, number)
    return None if hold is None else held_on(hold, LEFT_CHOICES).what


def unchanged_since(checkers: list[Agent], w: Path) -> bool:
    if not checkers or checkers[-1].messaged != frozenset():
        return False
    return shows_current(checkers[-1], w)


def leftover(state: State, t: Ticket, w: Path, latest: list[Agent],
             agents: list[Agent]) -> Step | None | Literal[False]:
    """The step on what the editors leave, or False where they leave
    nothing."""
    checkers = [a for a in agents if a.role is Role.ITEM_CHECKER]
    analysts = [a for a in agents if a.role is Role.TICKET_ANALYST]
    if any(a.pending for a in checkers + analysts):
        return None
    editors = with_ids(latest)
    if isinstance(editors, Undecided):
        return editors
    checked = max((a.launched for a in checkers), default=0.0)
    needing = [a for a in latest if is_checked(a) and (r := a.last_report) is not None
               and r.time > checked]
    if needing and not unchanged_since(checkers, w):
        return check_items(state, t, w, needing, editors)
    questions = [q for q in state.tracker.tickets.values() if q.kind is Kind.QUESTION
                 and q.domain is Domain.CHANGE and q.subject == t.number
                 and q.status in (Status.OPEN, Status.ASSIGNED)]
    judged = max((a.launched for a in analysts), default=0.0)
    left_open = unfinished(latest, judged)
    left = left_for_decision(checkers[-1]) if checkers else None
    fresh = left if left is not None and (r := checkers[-1].last_report) is not None \
        and r.time > judged else None
    parts = fresh
    hold: str | None = None
    on_user = False
    if analysts and judged > checked and (hold := left_hold(analysts[-1], t.number)):
        on_user = items_of(analysts[-1], [Label.DECISION]) is not None
        parts = left
    elif fresh is None and not questions and not left_open:
        return False
    elif fresh is None and not left_open and judged > max(q.filed for q in questions):
        hold = mctx("ticket analyst {agent} returned on change {number}, and its question "
                    "tickets stand open").format(agent=analysts[-1].agent_id, number=t.number)
    if hold is not None:
        choice = decided(state, hold, LEFT_CHOICES)
        if isinstance(choice, Undecided):
            return None if on_user else choice
        if choice is Decision.MERGE:
            return False
    reports = latest_reports(latest)
    if isinstance(reports, Undecided):
        return reports
    return Launch(Role.TICKET_ANALYST, analyst_subject(Purpose.CHANGE, t.number), briefs.findings(
        t.number, w, parts, [q.number for q in questions], editors, reports,
        [i for a, i in editors if a in left_open], state.me))


def step(state: State) -> Step | None:
    """The next step of the changes: a message to an agent on a change no
    longer carried, a take, then a step of each change the operator
    holds, other than a step an operator already made or handled
    (`repeated`). Where each step is such a step, the step is that of the
    message or the take, so the procedure waits on it."""
    before = [s for s in (give_up(state), take(state)) if s is not None]
    for s in before:
        if not repeated(s, state):
            return s
    for t in held(state):
        if (s := next_step(state, t)) is not None and not repeated(s, state):
            return s
    return before[0] if before else None


def next_step(state: State, t: Ticket) -> Step | None:
    """The step of the change `t` the operator holds: the one `carry`
    gives, or, where that is a message its recipient already answered,
    the one `unmoved` gives."""
    s = carry(state, t)
    if isinstance(s, Send) and answered(s, state):
        return unmoved(t, s)
    return s

