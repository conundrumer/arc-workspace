"""A change the operator holds, from its take to its merge: the editors, the review of the documents, the design review, the item checker
and the ticket analyst on what the editors leave; `doc_review` gives the
review of the documents. The steps carry out
[Carrying a change](prompts/agents/notes/changes.md#carrying-a-change);
`taking` gives the release of tickets and the take of open changes,
`merging` the merge and what follows it. `change_agents` gives the
agents of a change and the editors it needs, `item_check` the launch of
its item checker, `design_review` the launch of its design reviewer, `change_fragments` the doc editor of its `mctx`
fragments, and `change_overrun` a change past its cost budget.

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
The brief of each such analyst, as of every agent launched on the change,
gives what the agents before it settled (`change_agents.settled`), the
earlier holds of the change a ruling gave `merge` included, so that a
later analyst whose reply would give those items again in other words
leaves them out, and the change is not held on them again.
Where they give a `decision:` item, the step waits on the coordinator,
which gets those items with the line that rules the step
(`triage.for_coordinator`), and otherwise it goes to a ticket analyst
(`decisions`).

Once no editor of a change with an editor that builds code runs, and
after the doc editor of its fragments is launched where `change_fragments`
gives one, a design reviewer is launched on it where `design_review` gives
one due, before the step on what the editors leave, so that the item
checker is launched while it runs. While a design reviewer of the change
runs, the change does not merge. Its findings are `question` tickets on
the change, which go to the ticket analyst above.

A change whose `editors` field gives a doc editor, the one
`change_fragments` adds included, merges once its review passes as
`doc_review` gives.

A next step of a change that is a message an operator already sent,
whose recipient answered it, leaves the change where it was, and the
command cannot place it.

A step of a change that the command cannot place holds that change alone,
until an `Op decision:` line rules it with one of the choices the step gives
(`directives.decided`)."""

import shlex
from pathlib import Path
from dataclasses import dataclass
from typing import Literal

from operations import briefs, merging, messages
from operations.change_agents import (change_editors, editors_in, elsewhere_on, latest_editors,
                                      launched_on, of_change, Reported, reported, settled,
                                      unstaffed, with_before, with_elsewhere)
from operations.change_holds import Hold, left_hold, questions_hold
from operations.change_fragments import drafter_ids, fragments_step
from operations.change_overrun import over_budget
from operations.design_review import design_review, open_questions, reviewing
from operations.doc_review import doc_review, with_ids
from operations.directives import Decision, decided, held_on, ruled
from operations.item_check import check_items, is_checked, latest_reports, unfinished
from operations.reports import Label, items_of, left_for_decision, shows_current
from operations.roles import Purpose, Role, analyst_of, analyst_subject
from operations.state import Agent, State, Ticket, last_reported
from operations.filing import editor_scratch
from operations.final_reply import live_holder
from operations.handled import answered, repeated, sent, unmoved
from operations.steps import Bash, Launch, Send, Step, Undecided, served
from operations.log_commands import AGENT
from operations.taking import take
from operations.tracker import last_index
from operations.worktrees import WORKTREE, worktree
from ticketing.vocabulary import Kind, Note, Status


def holds(t: Ticket, me: str) -> bool:
    return t.kind is Kind.CHANGE and t.status is Status.ASSIGNED and t.holder == me


def held(state: State) -> list[Ticket]:
    """The changes the operator holds: those `master` holds merged first,
    in ticket order, so that a merged change's close comes at the next step
    of the changes; then the others in ticket order rotated to start at
    the first that follows the change its latest printed step served
    (`last_served`), so that each held change with a ready step gets one
    step before any gets a second."""
    tickets = sorted((t for t in state.tracker.tickets.values() if holds(t, state.me)),
                     key=lambda t: t.order)
    landed = [t for t in tickets if merging.merged(state, t)]
    rest = [t for t in tickets if t not in landed]
    served = last_served(state)
    if served is None:
        return landed + rest
    after = [t for t in rest if t.order > served.order]
    return landed + after + [t for t in rest if t.order <= served.order]


def last_served(state: State) -> Ticket | None:
    """The change of the latest step the journal gives the operator, of
    those that serve a change, or None where none does."""
    for e in reversed(state.journal.entries):
        if e.operator == state.me and e.change is not None:
            return state.tracker.tickets.get(e.change)
    return None


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
            return Send(a.agent_id, message, f"stop {number}")
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
        return merging.close(state, t, of_change(state, t))
    editors = change_editors(t)
    if not isinstance(editors, tuple):
        return editors
    agents = of_change(state, t)
    w = worktree(t, state)
    if w is None or revised_since_worktree(t):
        return Bash(make_worktree(t.number, state.me), f"{t.number} worktree", occasion=str(t.last_time))
    if (step := over_budget(state, t, w, agents)) is not False:
        return step
    here = editors_in(agents, w)
    if missing := unstaffed(editors, here):
        theirs = editors_in(elsewhere_on(state, t.number), w)
        free = [r for r in missing if not any(a.pending and a.role is r for a in theirs)]
        if not free:
            return None
        role = free[0]
        drafters = drafter_ids(here)
        if isinstance(drafters, Undecided):
            return drafters
        part = briefs.part_taken(role, len(editors) > 1)
        known = settled(state, t, role, part)
        before = editor_before([a for a in theirs
                                if a.role is role and briefs.part_of(a) is part])
        if before is not None:
            known = with_before(known, before[0])
        editor = part if isinstance(part, briefs.EditorPart) else briefs.DocEditor(
            part, state.held.fragments.get(w, ()), tuple(drafters))
        return Launch(role, t.number, briefs.editor(
            editor, t.number, w,
            editor_scratch(t.number, role, state.scratch), state.me, known,
            before=None if before is None else briefs.Before(before[0].agent_id, before[1])),
            model=t.model(role), occasion=f"{w} {t.last_time}")
    if any(a.pending for a in here):
        return None
    if (step := fragments_step(state, t, w, here)) is not None:
        return step
    latest = latest_editors(here)
    reviewed = with_elsewhere(state, t.number, agents,
                              (Role.ITEM_CHECKER, Role.DOC_REVIEWER, Role.DESIGN_REVIEWER))
    if (step := design_review(state, t, w, editors, here, reviewed)) is not False:
        return step
    if (step := leftover(state, t, w, latest, reviewed)) is not False:
        return step
    if Role.DOC_EDITOR in editors and (
            step := doc_review(state, t, w, here, reviewed)) is not False:
        return step
    if reviewing(reviewed):
        return None
    return merging.merge(state, t, w, latest)


def editor_before(theirs: list[Agent]) -> tuple[Reported, Path] | None:
    """The latest report and the scratch directory of the last of `theirs`,
    the editors of one role and one part in a change's worktree that an
    operator of another session launched, that has an agent id, a report
    and a scratch directory, for the brief of the editor launched in its
    place (`briefs.editor`), or None where none of them does."""
    for a in reversed(theirs):
        scratch = briefs.scratch_of(a.brief)
        if scratch is not None and (r := reported([a])):
            return r[0], scratch
    return None


def left_decision(a: Agent, number: str) -> str | None:
    """The step held on the items `a` leaves (`left_hold`), with the line
    that rules it, which goes to the coordinator with the `decision:` items
    of `a`."""
    hold = left_hold(a, number)
    return None if hold is None else held_on(hold.text, hold.choices).text


def unchanged_since(state: State, checkers: list[Agent], w: Path) -> bool:
    if not checkers or state.transcripts.sent_by(checkers[-1]) != frozenset():
        return False
    return shows_current(checkers[-1], w)


@dataclass(frozen=True)
class Left:
    """The inputs of the ticket analyst on what a change's editors leave,
    each with the time it was last given: the item checker's part
    (`reports.left_for_decision`), given by that checker's latest report,
    the editors' latest reports, which give the editors that leave items
    unfinished (`item_check.unfinished`), and the open `question` tickets
    on the change."""
    part: str | None
    part_given: float
    unfinished: tuple[Agent, ...]
    reported: float
    questions: tuple[Ticket, ...]

    @property
    def questions_given(self) -> float:
        return max((q.filed for q in self.questions), default=0.0)

    @property
    def given(self) -> float:
        return max(self.part_given, self.reported, self.questions_given)

    def fresh(self, judged: float) -> str | None:
        return self.part if self.part_given > judged else None


def left(state: State, t: Ticket, latest: list[Agent], checkers: list[Agent],
         judged: float) -> Left:
    """`Left` of the change `t`, with the unfinished items given after
    `judged`, the launch of the last analyst on it."""
    checker = checkers[-1] if checkers else None
    report = checker.last_report if checker is not None else None
    return Left(left_for_decision(checker) if checker is not None else None,
                report.time if report is not None else 0.0,
                tuple(unfinished(latest, judged)), last_reported(latest),
                tuple(open_questions(state, t.number)))


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
    if needing and not unchanged_since(state, checkers, w):
        return check_items(state, t, w, needing, editors)
    judged = max((a.launched for a in analysts), default=0.0)
    given = left(state, t, latest, checkers, judged)
    fresh = given.fresh(judged)
    parts = fresh
    hold: Hold | None = None
    on_user = False
    if analysts and judged > checked and (hold := left_hold(analysts[-1], t.number)):
        on_user = items_of(analysts[-1], [Label.DECISION]) is not None
        parts = given.part
    elif fresh is None and not given.questions and not given.unfinished:
        return False
    elif fresh is None and not given.unfinished and judged > given.questions_given:
        hold = questions_hold(analysts[-1], t.number)
    if hold is not None:
        choice = decided(state, hold.text, hold.choices)
        if isinstance(choice, Undecided):
            return None if on_user else choice
        if choice is Decision.MERGE:
            return False
    at = ruled(state, hold.text) if hold is not None else 0.0
    reports = latest_reports(latest)
    if isinstance(reports, Undecided):
        return reports
    return Launch(Role.TICKET_ANALYST, analyst_subject(Purpose.CHANGE, t.number), briefs.findings(
        t.number, w, parts, [q.number for q in given.questions], editors, reports,
        [i for a, i in editors if a in given.unfinished], state.me,
        settled(state, t, Role.TICKET_ANALYST, None)),
        occasion=str(max(given.given, at)))


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
    s = served(carry(state, t), t)
    if isinstance(s, Send) and answered(s, state):
        return served(unmoved(t, s), t)
    return s


