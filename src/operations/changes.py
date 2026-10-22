"""A change the operator holds, from its take to its merge: the editors, the review of the documents, the design review, the item checker
and the ticket analyst on what the editors leave; `doc_review` gives the
review of the documents. The steps perform
[Making a change](prompts/agents/notes/changes.md#making-a-change);
`taking` gives the release of tickets and the take of open changes,
`merging` the merge and what follows it. `change_agents` gives the
agents of a change and the editors it needs, `item_check` the launch of
its item checker, `design_review` the launch of its design reviewer, `change_fragments` the doc editor of its `mctx`
fragments, and `change_overrun` a change past its cost budget.

A change with no worktree gets one from
`scripts/change_worktree.py`, which logs its path on the ticket, so a
later operator continues the change there. Where a change's ticket is
revised after the log line that gives its worktree, the operator runs
`scripts/change_worktree.py` again, whose `--help` gives what it copies in.
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
launch and does not open with `reports.DONE`, the reply of the change's
doc reviewer that opens with `reports.AT_CAP`, where it follows that
launch, which a `merge` ruling on that analyst's items does not settle, and the
open `question` tickets filed on the change go to one ticket analyst.
A change whose only editor is that agent gets no item checker.
That analyst's reply gives each kept finding and each decided edit for an
editor under `reports.TO_EDITOR` for its role, and the command delivers
each such section once per reply to that role's running editor
(`deliver_decided`), or gives it in the brief of the editor launched in
its place (`undelivered`). That analyst's reply leaves nothing more, unless its part for the
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

A change past its cost budget that `change_overrun` gives as `Ended`
gets that step on what its agents leave, with that analyst's brief
giving the change past its cost budget, and merges once that step
leaves nothing, in place of the steps below.

An editor of a change with an agent id whose latest attempt ended with
no finished report since its launch or its last resume
(`completion.finished`), gets one message that
resumes it (`editor_resume`), once per attempt, so that it keeps its context.
While it runs, the change waits. Where it ends again with no finished
report, a new editor is launched in its place (`staff_editor`), and where
that one also ends with none after its own resume, the coordinator gets a message
(`completion.replacement`) and no further editor is launched until an
`Op override: give again` ruling. The steps
below wait for fresh reports.

Once no editor of a change with an editor that builds code runs, and
after the doc editor of its fragments is launched where `change_fragments`
gives one, a design reviewer is launched on it where `design_review` gives
one due, before the step on what the editors leave, so that the item
checker is launched while it runs. While a design reviewer of the change
runs, the change does not merge. `design_review` gives where its findings
go.

A code editor or a doc editor of a change launches, before its final
reply, each design reviewer, item checker, ticket analyst and doc
reviewer that these steps give with that editor ended and as the
launcher (`editor_step`). The operator reads each as one it launched,
so the steps go on from it.

A change whose `editors` field gives a doc editor, the one
`change_fragments` adds included, merges once its review passes as
`doc_review` gives.

A next step of a change that is a message an operator already sent,
whose recipient answered it, leaves the change where it was, and the
command cannot place it.

A step of a change that the command cannot place holds that change alone,
until an `Op decision:` line rules it with one of the choices the step gives
(`directives.ruling`)."""

import shlex
from functools import partial
from collections.abc import Callable
from pathlib import Path
from dataclasses import dataclass, replace

from controlled_markdown import mctx
from operations import briefs, merging, messages
from operations.change_budget import TAKEN
from operations.constants import AGAIN_SECONDS, COORDINATOR
from operations.journal import AGAIN_LIMIT, done_of, retired
from operations.change_agents import (REVIEWER_ROLES, change_editors, editors_in, elsewhere_on,
                                      latest_editors, launched_on, of_change, Reported, reported,
                                      reported_at, settled, unstaffed, with_before,
                                      with_elsewhere, worktree_occasion)
from operations.change_holds import Hold, left_hold, open_questions, questions_given, questions_hold
from operations.change_fragments import drafter_ids, fragments_step
from operations.change_overrun import Ended, over_budget
from operations.design_review import design_review, reviewing
from operations.doc_review import doc_review, latest_reviewer, with_ids
from operations.directives import Decision, give_again_line, held_on, ruling
from operations.item_check import check_items, is_checked, latest_reports, unfinished
from operations.completion import occupies, replacement
from operations.reports import Label, at_cap, items_of, left_for_decision, shows_current, to_editor
from operations.roles import (CHECKS, LAUNCHING_EDITORS, Purpose, Role, analyst_of,
                              analyst_subject)
from operations.state import Agent, Report, State, Ticket, last_reported
from operations.filing import editor_scratch
from operations.final_reply import live_holder
from operations.handled import answered, held_aside, repeated, sent, unmoved
from operations.steps import (Bash, Launch, Pause, Poll, Repeatable, Send, Step, Undecided,
                              agent_ids, key, retirement_key, served)
from operations.log_commands import AGENT
from operations.change_take import take
from operations.taking import RELEASED_LINE, purview
from operations.tracker import last_index
from operations.worktrees import WORKTREE, worktree
from ticketing.times import utc_stamp
from ticketing.vocabulary import Domain, Kind, Note, Status


EDITOR_RESUME = mctx(
    "Your attempt on change {number} ended with no report, or with a report that gives "
    "work as unfinished. Finish that work as your documents give, run again each command "
    "whose output it waits on, then give your final reply.")


def holds(t: Ticket, me: str) -> bool:
    return t.kind is Kind.CHANGE and t.status is Status.ASSIGNED and t.holder == me


def held(state: State) -> list[Ticket]:
    """The changes the operator holds: those ready to close first,
    in ticket order, so that their close comes at the next step
    of the changes; then the others in ticket order rotated to start at
    the first that follows the change its latest printed step served
    (`last_served`), so that each held change with a ready step gets one
    step before any gets a second."""
    tickets = sorted((t for t in state.tracker.tickets.values() if holds(t, state.me)),
                     key=lambda t: t.order)
    landed = [t for t in tickets if merging.ready_to_close(state, t)]
    rest = [t for t in tickets if t not in landed]
    served = last_served(state)
    if served is None:
        return landed + rest
    after = [t for t in rest if t.order > served.order]
    return landed + after + [t for t in rest if t.order <= served.order]


def closing(state: State) -> list[Ticket]:
    """The unassigned merged changes of the operator's purview, in ticket
    order. These continue the closing sequence without being taken."""
    return sorted((t for n in purview(state)
                   if (t := state.tracker.tickets.get(n)) is not None
                   and t.kind is Kind.CHANGE
                   and t.status not in (Status.ASSIGNED, Status.CLOSED)
                   and merging.merged(state, t)), key=lambda t: t.order)


def last_served(state: State) -> Ticket | None:
    """The change of the latest step the journal gives the operator, of
    those that serve a change, or None where none does."""
    for e in reversed(state.journal.entries):
        if e.operator == state.me and e.change is not None:
            return state.tracker.tickets.get(e.change)
    return None


def give_up(state: State) -> Step | None:
    """A message that tells an agent at work on a change that no operator
    holds any more, or that another live holder (`live_holder`) holds,
    to end. A live holder among the session's operators has the same
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


def staff_editor(state: State, t: Ticket, w: Path, editors: tuple[Role, ...],
                 agents: list[Agent], finding: str | None = None) -> Step | None:
    """The launch of the first editor role of `editors` with no editor
    among `agents` in the worktree `w`, with `finding`, the message that
    gives a refused merge's output (`messages.merge_finding`), in its
    brief where it is given, or None where every role has an editor, or an
    editor of the role runs in another session or needs a decision first."""
    here = editors_in(agents, w)
    if not (missing := unstaffed(editors, here)):
        return None
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
    occasion = worktree_occasion(t, w)
    decided = undelivered(state, t, role, here)
    if decided is not None:
        finding = decided if finding is None else f"{finding}\n{decided}"
    return Launch(role, t.number, briefs.editor(
        editor, t.number, w,
        editor_scratch(t.number, role, state.scratch), state.me, known,
        before=None if before is None else briefs.Before(before[0].agent_id, before[1]),
        finding=finding),
        model=t.model(role), occasion=occasion if finding is None else f"{occasion} {finding}")


def decided_send(state: State, t: Ticket, analyst: Agent, role: Role,
                 editor: Agent | None) -> tuple[Send, str] | None:
    """The message that gives the editor `editor` of `role` the section of
    the last reply of the ticket analyst `analyst` addressed to that role
    (`reports.to_editor`), with that section, or None where the reply has
    none. The journal's key for it is one per reply and editor."""
    r = analyst.last_report
    text = to_editor(analyst, role)
    if r is None or text is None or analyst.agent_id is None:
        return None
    to = "" if editor is None or editor.agent_id is None else editor.agent_id
    return Send(to, messages.decided_edits(t.number, analyst.agent_id, text),
                f"decided {t.number} {analyst.agent_id} {role}", since=r.time,
                change=t.number), text


def undelivered(state: State, t: Ticket, role: Role, here: list[Agent]) -> str | None:
    """The message that gives a new editor of `role` the text of the last
    ticket analyst's section for that role, where the text is undelivered:
    no done delivery of that reply and role is followed by a report of an
    editor of that role. None otherwise."""
    analysts = [a for a in of_change(state, t) if a.role is Role.TICKET_ANALYST]
    if not analysts:
        return None
    text = None
    for editor in (a for a in here if a.role is role):
        if (given := decided_send(state, t, analysts[-1], role, editor)) is None:
            return None
        send, text = given
        closes = [e.close.time for e in state.journal.of(key(send))
                  if e.done and e.close is not None]
        if closes and any((r := a.last_report) is not None and r.time > closes[0]
                          for a in here if a.role is role):
            return None
    if text is None:
        given = decided_send(state, t, analysts[-1], role, None)
        text = None if given is None else given[1]
    return None if text is None else messages.decided_edits(
        t.number, analysts[-1].agent_id or "", text)


def deliver_decided(state: State, t: Ticket, latest: list[Agent],
                    analysts: list[Agent]) -> Step | None:
    """The delivery to each running editor of `latest` of the section of
    the last report of the last of `analysts` addressed to its role, once
    per reply and role, or None where none is due. A role's doc editor of
    the documents takes precedence over the doc editor of the fragments."""
    reported_by = [a for a in analysts if a.last_report is not None]
    if not reported_by:
        return None
    for role in (Role.CODE_EDITOR, Role.DOC_EDITOR, Role.HANDBOOK_EXPANDED):
        of_role = [a for a in latest if a.role is role and occupies(a)]
        own = [a for a in of_role if briefs.FRAGMENTS_PART not in a.brief]
        for editor in (own or of_role)[:1]:
            given = decided_send(state, t, reported_by[-1], role, editor)
            if given is not None and given[1] not in editor.brief \
                    and not repeated(given[0], state):
                return given[0]
    return None


def carry(state: State, t: Ticket) -> Step | None:
    """The next step on the change `t` the operator holds, or None where it
    waits on an agent."""
    if merging.ready_to_close(state, t):
        return merging.close(state, t, of_change(state, t),
                             merging.NO_MERGE_EVIDENCE if not merging.merged(state, t) else None)
    editors = change_editors(t)
    if not isinstance(editors, tuple):
        return editors
    agents = of_change(state, t)
    w = worktree(t, state)
    if w is None or revised_since_worktree(t):
        return Bash(make_worktree(t.number, state.me), f"{t.number} worktree", occasion=str(t.last_time))
    staff = partial(staff_editor, state, t, w, editors, agents)
    match over_budget(state, t, w, agents):
        case Ended(ended):
            latest = list(ended)
            match leftover(state, t, w, latest, agents, True, state.me):
                case Pause.CLEAR:
                    return merging.merge(state, t, w, latest, staff)
                case Pause.WAIT:
                    return None
                case left:
                    return left
        case Pause.WAIT:
            return None
        case Pause.CLEAR:
            pass
        case step:
            return step
    here = editors_in(agents, w)
    if (resume := editor_resume(state, t, editors, here)) is not None:
        return resume
    if unstaffed(editors, here):
        return staff_editor(state, t, w, editors, agents,
                            merging.unreceived_finding(state, t, w, here))
    if any(a.pending for a in here):
        return None
    match reported_step(state, t, w, editors, here, agents, state.me):
        case Pause.CLEAR:
            return merging.merge(state, t, w, latest_editors(here), staff)
        case Pause.WAIT:
            return None
        case step:
            return step


def reported_step(state: State, t: Ticket, w: Path, editors: tuple[Role, ...],
                  here: list[Agent], agents: list[Agent],
                  launcher: str) -> Step | Pause:
    """The step of the change `t`, whose editors are `editors`, once each
    of its editors in its worktree `w`, `here`, has ended, with
    `launcher` as the launcher of each check it launches, or `Pause.CLEAR`
    where the change merges. `agents` are the change's agents."""
    if (step := fragments_step(state, t, w, here)) is not None:
        return step
    latest = latest_editors(here)
    if (hold := editor_replacement(state, t, w, latest)) is not None:
        return hold
    context = StageContext(state, t, w, editors, here, latest,
                            with_elsewhere(state, t.number, agents, REVIEWER_ROLES), launcher)
    for stage in STAGES:
        if (given := stage(context)) is not Pause.CLEAR:
            return given
    return Pause.CLEAR


@dataclass(frozen=True)
class StageContext:
    """The input of the review stages of the change `t`: its editors
    `editors`, those in its worktree `w` `here`, the latest of them
    `latest`, its agents with the reviewers of other sessions (`agents`),
    and the launcher of each check a stage launches."""
    state: State
    t: Ticket
    w: Path
    editors: tuple[Role, ...]
    here: list[Agent]
    latest: list[Agent]
    agents: list[Agent]
    launcher: str


def design_stage(r: StageContext) -> Step | Pause:
    return design_review(r.state, r.t, r.w, r.editors, r.here, r.agents, r.launcher)


def leftover_stage(r: StageContext) -> Step | Pause:
    return leftover(r.state, r.t, r.w, r.latest, r.agents, False, r.launcher)


def doc_stage(r: StageContext) -> Step | Pause:
    """The step of the review of the change's documents, where its editors
    include a doc editor."""
    if Role.DOC_EDITOR not in r.editors:
        return Pause.CLEAR
    return doc_review(r.state, r.t, r.w, r.here, r.agents, r.launcher)


def reviewing_stage(r: StageContext) -> Step | Pause:
    """The hold of the merge while a design reviewer of the change runs."""
    return Pause.WAIT if reviewing(r.agents) else Pause.CLEAR


STAGES: tuple[Callable[[StageContext], Step | Pause], ...] = (
    design_stage, leftover_stage, doc_stage, reviewing_stage)
"""The review stages of a change, in the order `reported_step` walks
them: each gives its step, `Pause.WAIT`, or `Pause.CLEAR`, which goes on
to the next stage."""


NO_OPERATOR = mctx("{agent} is no code editor or doc editor that an operator of the session "
                   "launched: give your final reply.")
"""The line `editor_step` gives an agent that is none of `LAUNCHING_EDITORS`
an operator launched."""


def editor_step(state: State, editor: str,
                written: Callable[[Path], str | None]) -> Step | str:
    """The step the editor `editor` takes at the end of its turn, where
    `written` gives the text of a report file: the `Launch` of a check of
    `CHECKS` it launches, `steps.Poll`, on which it runs the command again,
    an `Undecided`, or the line it is given. It reads its change
    (`editor_change`), lines that hand the change's next step to the
    operator (`handed_on`), the editors it waits on (`peers_ended`), and
    the check it launches (`check_or_line`). The cases in which `review`
    prints each line or blocks are those `scripts/operate.py --help review`
    gives."""
    change = editor_change(state, editor, written)
    if not isinstance(change, EditorChange):
        return change
    if (line := handed_on(state, change)) is not None:
        return line
    agents = peers_ended(change, written)
    if not isinstance(agents, list):
        return agents
    return check_or_line(state, change, agents)


@dataclass(frozen=True)
class EditorChange:
    """The change `t` of the editor `editor`, with its editors `editors`,
    its worktree `w`, and its agents, the editor read as ended with its
    report at `at`."""
    editor: str
    t: Ticket
    editors: tuple[Role, ...]
    w: Path
    at: float
    agents: list[Agent]


def editor_change(state: State, editor: str,
                  written: Callable[[Path], str | None]) -> EditorChange | Undecided | str:
    """The change of the editor `editor`, one of `LAUNCHING_EDITORS` an
    operator launched, with its report the text `written` gives of the
    report file its brief gives (`state.Agent.report_file`), at its
    `Agent.reviewing`, or at `State.now` where that is None, so each later
    call of a run of its calls of the command keeps the time of the first.
    Only a pending editor owns the checks; after it ends, the operator
    owns them. Where the editor is none of those, or its report file is not there,
    it gives the line for that, and where its ticket, the ticket's
    editors, the change's worktree or its report file is not read, an
    `Undecided`."""
    mine = [a for a in state.transcripts.agents
            if a.agent_id == editor and a.role in LAUNCHING_EDITORS]
    if not mine:
        return NO_OPERATOR.format(agent=editor)
    if not mine[-1].pending:
        return mctx("Your work has ended, so the operator takes the change's next step: "
                    "give your final reply.")
    t = state.tracker.tickets.get(mine[-1].subject)
    if t is None:
        return Undecided(mctx("the ticket of change {number} of {role} {agent} is not "
                              "read").format(number=mine[-1].subject, role=mine[-1].role,
                                             agent=editor))
    editors = change_editors(t)
    if not isinstance(editors, tuple):
        return editors
    w = worktree(t, state)
    if w is None:
        return Undecided(mctx("change {number} gives no worktree").format(number=t.number))
    path = mine[-1].report_file
    if path is None:
        return Undecided(mctx("the brief of {role} {agent} gives no report file").format(
            role=mine[-1].role, agent=editor))
    text = written(path)
    if text is None:
        return mctx("Your report file {path} does not exist: write your report to it, then run "
                    "this command again.").format(path=path)
    at = mine[-1].reviewing if mine[-1].reviewing is not None else state.now
    agents = [as_ended(a, at, text, path) if a.agent_id == editor else a
              for a in of_change(state, t)]
    return EditorChange(editor, t, editors, w, at, agents)


def as_ended(a: Agent, at: float, text: str, path: Path) -> Agent:
    """The editor `a` read as ended with the report `text` of its report
    file `path` at `at`, as `editor_step` reads an editor that has
    reported."""
    return replace(a, waits=None, reports=(*a.reports, Report(at, text, path)))


def peers_ended(c: EditorChange, written: Callable[[Path], str | None]
                ) -> list[Agent] | Poll | Undecided:
    """The agents of the change `c` with each other pending editor in its
    worktree read as ended, each with the text `written` gives of its
    report file as its report at its `change_agents.reported_at`, where
    each has such a report and that of `c.editor` is the latest of theirs,
    or of the latest the one of the first agent id in sort order; and
    `steps.Poll` where one has none, another's is later, or a check another
    editor there launched is pending."""
    here = editors_in(c.agents, c.w)
    others = [a for a in here if a.pending]
    peers = {a.agent_id for a in here} - {c.editor}
    if any(a.pending and a.operator in peers for a in c.agents):
        return Poll()
    if not others:
        return c.agents
    other_ids = agent_ids(others)
    if isinstance(other_ids, Undecided):
        return other_ids
    times = [(-c.at, c.editor)]
    ended: dict[str, Agent] = {}
    for a, i in zip(others, other_ids, strict=True):
        since = reported_at(a)
        other_text = None if a.report_file is None else written(a.report_file)
        if since is None or a.report_file is None or other_text is None:
            return Poll()
        times.append((-since, i))
        ended[i] = as_ended(a, since, other_text, a.report_file)
    if min(times) != (-c.at, c.editor):
        return Poll()
    return [ended.get(a.agent_id or "", a) for a in c.agents]


def handed_on(state: State, c: EditorChange) -> str | None:
    """The line that has the editor of the change `c` give its final reply
    as the operator takes the change's next step: where
    `change_overrun.over_budget` gives a step, `Ended` or `Pause.WAIT`, or
    where an editor role of the change has no agent in its worktree or
    another editor there ended with no report since its launch or its last
    resume; or None."""
    if not isinstance(budget := over_budget(state, c.t, c.w, c.agents), Undecided) \
            and budget is not Pause.CLEAR:
        return mctx("Change {number} is past its cost budget, so the operator takes its next "
                    "step: give your final reply.").format(number=c.t.number)
    here = editors_in(c.agents, c.w)
    if unstaffed(c.editors, here) or any(a.unreported for a in latest_editors(here)):
        return mctx("Another editor of change {number} has not reported, so the operator "
                    "takes its next step: give your final reply.").format(
                        number=c.t.number)
    return None


def check_or_line(state: State, c: EditorChange, agents: list[Agent]) -> Step | str:
    """The launch of the check of `CHECKS` that `reported_step` gives the
    change `c`, with `agents` as its agents and its editor as the
    launcher; where it gives none and a check the editor launched is
    pending, the line that has it wait on that check; and otherwise the
    line that has it give its final reply."""
    here = editors_in(agents, c.w)
    step = reported_step(state, c.t, c.w, c.editors, here, agents, c.editor)
    if isinstance(step, Launch) and step.role in CHECKS:
        return step
    waited = [a for a in agents if a.operator == c.editor and a.pending]
    if step is Pause.WAIT and waited:
        ids = agent_ids(waited)
        if isinstance(ids, Undecided):
            return ids
        return mctx("Wait on {agents}, which you launched, and each time one of them gives its "
                    "final reply, run this command again.").format(agents=", ".join(ids))
    return mctx("No check of change {number} is due from you: give your final reply.").format(
        number=c.t.number)


def editor_resume(state: State, t: Ticket, editors: tuple[Role, ...],
                  here: list[Agent]) -> Send | None:
    """One recovery message per editor attempt without a finished report,
    or None where no such message is due."""
    for a in latest_editors([a for a in here if briefs.FRAGMENTS_PART not in a.brief]):
        if a.role not in editors or a.agent_id is None or occupies(a) or a.refused is not None:
            continue
        step = Send(a.agent_id, EDITOR_RESUME.format(number=t.number),
                    f"resume {t.number} {a.agent_id}", since=a.launched, change=t.number)
        if not repeated(step, state):
            return step
    return None


def editor_replacement(state: State, t: Ticket, w: Path,
                      latest: list[Agent]) -> Step | None:
    """Resume an editor whose last attempt ended without a result
    (`editor_resume`), or, once that resume was sent, replace it."""
    if any(not occupies(a) for a in latest if briefs.FRAGMENTS_PART not in a.brief):
        editors = change_editors(t)
        if isinstance(editors, Undecided):
            return editors
        if (resume := editor_resume(state, t, editors, latest)) is not None:
            return resume
        return staff_editor(state, t, w, editors, of_change(state, t))
    return None


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
    unfinished (`item_check.unfinished`), the open `question` tickets
    on the change, and the agent id and reply of its doc reviewer at the
    round cap (`cap_reply`)."""
    part: str | None
    part_given: float
    unfinished: tuple[Agent, ...]
    reported: float
    questions: tuple[Ticket, ...]
    capped: tuple[str, Report] | None

    @property
    def questions_given(self) -> float:
        return max((q.filed for q in self.questions), default=0.0)

    @property
    def given(self) -> float:
        return max(self.part_given, self.reported, self.questions_given,
                   0.0 if self.capped is None else self.capped[1].time)

    def fresh(self, judged: float) -> str | None:
        return self.part if self.part_given > judged else None


def left(state: State, t: Ticket, latest: list[Agent], checkers: list[Agent],
         reviewer: Agent | None, judged: float) -> Left:
    """`Left` of the change `t`, with the unfinished items and the reply
    of its doc reviewer `reviewer` at the round cap given after `judged`,
    the launch of the last analyst on it."""
    checker = checkers[-1] if checkers else None
    report = checker.last_report if checker is not None else None
    return Left(left_for_decision(checker) if checker is not None else None,
                report.time if report is not None else 0.0,
                tuple(unfinished(latest, judged)), last_reported(latest),
                tuple(open_questions(state, t.number)), cap_reply(reviewer, judged))


def leftover(state: State, t: Ticket, w: Path, latest: list[Agent],
             agents: list[Agent], past_budget: bool, launcher: str) -> Step | Pause:
    """The step on what the editors leave, with `launcher` as the launcher
    of the agent it launches, or `Pause.CLEAR` where they leave nothing;
    `past_budget` gives that the change is past its cost budget."""
    checkers = [a for a in agents if a.role is Role.ITEM_CHECKER and occupies(a)]
    analysts = [a for a in agents if a.role is Role.TICKET_ANALYST and occupies(a)]
    if any(a.pending for a in checkers + analysts):
        return Pause.WAIT
    if (delivery := deliver_decided(state, t, latest, analysts)) is not None:
        return delivery
    editors = with_ids(latest)
    if isinstance(editors, Undecided):
        return editors
    checked = max((a.launched for a in checkers), default=0.0)
    needing = [a for a in latest if is_checked(a) and (r := a.last_report) is not None
               and r.time > checked]
    if needing and not unchanged_since(state, checkers, w):
        return check_items(state, t, w, needing, editors, launcher)
    judged = max((a.launched for a in analysts), default=0.0)
    given = left(state, t, latest, checkers, latest_reviewer(agents, w), judged)
    fresh = given.fresh(judged)

    def launch(parts: str | None, at: float) -> Step:
        """The launch of the ticket analyst on what the editors leave, with
        `parts`, the item checker's part it takes, and `at`, the time of the
        ruling it is launched on, or 0.0."""
        reports = latest_reports(latest)
        if isinstance(reports, Undecided):
            return reports
        return Launch(Role.TICKET_ANALYST, analyst_subject(Purpose.CHANGE, t.number),
                      briefs.findings(
            t.number, w, parts, [q.number for q in given.questions], editors, reports,
            [i for a, i in editors if a in given.unfinished], launcher,
            settled(state, t, Role.TICKET_ANALYST, None),
            briefs.round_of(checkers[-1], t.number) if checkers else briefs.Round.OPEN,
            None if given.capped is None else (given.capped[0], given.capped[1].text),
            past_budget),
            occasion=str(max(given.given, at)))

    def on_hold(hold: Hold, on_user: bool, parts: str | None) -> Step | Pause:
        """The step on `hold`, by its ruling: a wait where it is not ruled
        and the hold is on the user, `on_user`."""
        r = ruling(state, hold.text, hold.choices)
        if isinstance(r, Undecided):
            return Pause.WAIT if on_user else r
        if r.choice is not Decision.MERGE:
            return launch(parts, r.time)
        return Pause.CLEAR if given.capped is None else launch(fresh, r.time)

    if analysts and judged > checked and (hold := left_hold(analysts[-1], t.number)):
        return on_hold(hold, items_of(analysts[-1], [Label.DECISION]) is not None, given.part)
    if fresh is None and given.capped is None and not given.questions and not given.unfinished:
        return Pause.CLEAR
    if fresh is None and given.capped is None and not given.unfinished \
            and analysts and questions_given(analysts[-1], list(given.questions)):
        return on_hold(questions_hold(analysts[-1], t.number), False, fresh)
    return launch(fresh, 0.0)


def cap_reply(reviewer: Agent | None, judged: float) -> tuple[str, Report] | None:
    """The agent id and reply of the change's doc reviewer `reviewer`,
    where that reply opens with `reports.AT_CAP` and follows `judged`, the
    last ticket analyst's launch on the change."""
    if reviewer is None or reviewer.agent_id is None or not at_cap(reviewer):
        return None
    r = reviewer.last_report
    return (reviewer.agent_id, r) if r is not None and r.time > judged else None


def step(state: State,
         idle: Callable[[State, Ticket, Step | None], Step | None]) -> Step | None:
    """The next step of the changes: a message to an agent on a change no
    longer held, a take, then the closing sequence of each unassigned
    merged change (`closing`), then the step of each change the operator
    holds (`due_step`), or, where it has none, the step `idle` gives for
    it, other than a step an operator already made or handled
    (`repeated`). Where each step is such a step, the step is that of the
    message or the take, so the procedure waits on it."""
    before = [s for s in (give_up(state), take(state)) if s is not None]
    for s in before:
        if not repeated(s, state):
            return s
    for t in [*closing(state), *held(state)]:
        s = next_step(state, t)
        if (due := due_step(state, t, s)) is not None:
            return due
        if (other := idle(state, t, s)) is not None and not repeated(other, state):
            return other
    return before[0] if before else None


def due_step(state: State, t: Ticket, s: Step | None) -> Step | None:
    """The step of the change `t` the operator holds, whose `next_step`
    is `s`: `s`, or, where `repeated` passes it over, the one `no_step`
    gives in its place, where `repeated` does not pass that over. None
    otherwise."""
    if s is None:
        return None
    s = replacement(state, s)
    if not repeated(s, state):
        return s
    if (other := no_step(state, t, s)) is not None and not repeated(other, state):
        return other
    return None


def no_step(state: State, t: Ticket, s: Step) -> Step | None:
    """The step in place of `s`, the step of the held change `t` that
    `repeated` passes over, where the journal gives it as done and no
    other read holds it back: `s` once more, once its done entry closed
    `AGAIN_SECONDS` before, or, once it is done more than
    `journal.AGAIN_LIMIT` times so, or retired, the
    message to the coordinator on the change (`stuck`). None otherwise."""
    if not isinstance(s, Repeatable) or held_aside(state, s):
        return None
    k = key(s)
    if retired(state.journal, retirement_key(s)):
        return stuck(t, s, retired_step=True)
    entries = state.journal.of(k)
    if any(e.close is None for e in entries):
        return None
    done = done_of(entries)
    if done.last is None or state.now - done.last < AGAIN_SECONDS:
        return None
    return replace(s, again=True) if done.count <= AGAIN_LIMIT else stuck(t, s, retired_step=False)


DONE_TWICE = mctx("it was done twice, and the line gives its key, which takes in the version of the "
                  "change's inputs")
"""Why `next` gives the step of `stuck` no more, where it was done twice."""

RETIRED = mctx("it was retired, which holds at each version of the change's inputs, and the line "
               "gives its key without that version")
"""Why `next` gives the step of `stuck` no more, where it was retired."""


def stuck(t: Ticket, s: Launch | Bash, *, retired_step: bool) -> Send:
    """The message to the coordinator on the change `t`, whose procedure
    gives `s`, a step the journal gives as retired, or else as done
    twice."""
    k = retirement_key(s) if retired_step else key(s)
    line = give_again_line(k)
    return Send(COORDINATOR, mctx("Change {number} has no step: `{origin}` still gives its step "
                                  "{key}, which `next` gives no more, since {why}. The line "
                                  "`{line}` makes that step due once more.").format(
        number=t.number, key=k, origin=s.origin, line=line,
        why=RETIRED if retired_step else DONE_TWICE), f"no step {k}", change=t.number)


def version(state: State, t: Ticket) -> float:
    """The version of the inputs of the change `t`, as
    `scripts/operate.py --help journal` gives it. The launches of its
    agents stay out: a launch is the effect of the step it answers, and
    the launches `order.made` adds to a batch's state would move the keys
    within one batch."""
    return max([t.filed,
                *(r.time for a in [*of_change(state, t), *elsewhere_on(state, t.number)]
                  for r in a.reports),
                *(q.filed for q in state.tracker.tickets.values()
                  if q.domain is Domain.CHANGE and q.subject == t.number),
                *(ln.time for ln in t.log
                  if ln.agent != AGENT and TAKEN.fullmatch(ln.note) is None
                  and RELEASED_LINE.fullmatch(ln.note) is None)])


def next_step(state: State, t: Ticket) -> Step | None:
    """The step of the change `t` the operator holds: the one `carry`
    gives, or, where that is a message its recipient already answered,
    the one `unmoved` gives, with the version of the change's inputs
    (`version`)."""
    v = version(state, t)
    s = served(carry(state, t), t, v)
    if isinstance(s, Send) and answered(s, state):
        return served(unmoved(t, s), t, v)
    return s
