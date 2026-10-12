"""A change from its take to its merge: the release of tickets, the take of
open changes, the editors, the review of the documents, the item checker
and the ticket analyst on what the editors leave; `doc_review` gives the
review of the documents. The steps carry out
[Carrying a change](prompts/agents/notes/changes.md#carrying-a-change);
`merging` gives the merge and what follows it.

The operators act on the tickets of the session and on those of the
sessions `State.adopted` gives, as `State.mine` gives them. Which session
is the main one, `file_ticket.py main --help` states; which sessions are
idle, `idle_sessions.read_sessions` gives.

The editors a change needs are those the `editors` field of its ticket
gives, which the ticket analyst that files it writes, and a change whose
ticket gives none is undecided. A change with no worktree gets one from
`scripts/change_worktree.py`, which logs its path on the ticket, so a
later operator continues the change there. Where a change's ticket is
revised after the log line that gives its worktree, the operator runs
`scripts/change_worktree.py` again, which carries in the untracked Scope
files that worktree lacks. Every editor and reviewer is
launched with no isolation, and its brief gives that worktree.

What the editors' and the doc reviewer's replies give is read by the fixed
forms of `reports`. An editor whose latest reply says its budget is passed
is sent a message to go on with the work that reply leaves, with the
budget the operators last gave it, and that reply goes to no ticket
analyst. Once each editor of a change has reported, the latest report of
each editor that has reported since the last item checker was launched on
the change, and the accepted gate outputs the change writes, go to one
item checker. That checker checks the items of each such editor's part,
and an editor it sends a message reports again. So the change merges only
once an item checker was launched after each editor's last report, or
the latest checker sent no editor a message and its `reports.WORKTREE`
line gives the `tracker.fingerprint` the worktree has now, as then the
worktree is in the state that checker read. The
checker gives under `reports.LEFT_FOR_DECISION` what those reports leave
for a decision.
Where no item checker is due, that part of the latest checker's reply,
where it follows the last ticket analyst's launch on the change, and the
open `question` tickets filed on the change go to one ticket analyst.
That analyst's reply leaves nothing more, unless its part for the
coordinator gives a `decision:` or an `unfinished:` item and no item
checker was launched since its launch: then the change is held on those
items, in place of its merge, and a ruling of another analyst gives that
analyst the latest checker's part, whatever its time.
Where they give a `decision:` item, the step waits on the coordinator,
which gets those items with the line that rules the step
(`triage.for_coordinator`), and otherwise it goes to a ticket analyst
(`decisions`).

Once a code editor or a `handbook-expanded` editor of a change has
reported, where the change adds or changes the text of an `mctx` fragment
(`State.fragments`) and no doc editor was launched since that report, the
fragments go to a doc editor launched for them: a change whose `editors`
field gives no doc editor first gets one in that field, with the budget of
its new `editors` set, and the doc editor the field then gives is
launched with the fragments; a change that gives one gets a doc editor
of the fragments alone (`briefs.FRAGMENTS_PART`), which is the latest
editor of its part beside the doc editor of the documents.

A change whose `editors` field gives a doc editor, the one that step adds
included, passes its review once the latest reply of its
doc reviewer opens with `no finding stands` and follows each editor's last
report, or precedes the last report only of editors that reviewer sent a
message, since such an editor sends that reviewer its fixes before each
reply. A reply that precedes the last report of any other editor is read
for no finding, and that reviewer is asked once to review the change
again, and the review is held where it has not replied since, apart from
the reply `doc_review` passes on the worktree's state. A reply in any
other form holds the review. The command launches no editor for a
reviewer's findings: that reviewer sends them to the editors of its
brief.

`change_budget` gives a change's cost budget. Once its spend passes
that budget, at the command's next call, whether or not an agent of the
change is at work, the command files the `performance` ticket on the
change that `change_budget` gives. Each agent of the change at work
before that ticket is told once to end (`messages.over_budget`), and none
other is launched but one item checker on each editor's latest report,
once none is at work. Where that checker leaves nothing for a decision,
the change merges; otherwise it moves to `tickets/draft/` with a line
that opens with `OVERRUN_FINDING`, which `drafts` reads as findings.

A next step of a change that is a message an operator already sent,
whose recipient answered it, leaves the change where it was, and the
command cannot place it.

A change that waits for a ticket under `tickets/blocked/` whose last
wait is on the user moves to `tickets/draft/` with a line whose note is
`STALL_FINDING` on that ticket, which `drafts` reads as findings, once
after each move of that ticket into `tickets/blocked/` (`stall`). A
change under `tickets/blocked/` is taken back on a `Merge:` line that
came after its last move there.

A step of a change that the command cannot place holds that change alone,
until a `Decision:` line rules it with one of the choices the step gives
(`directives.decided`)."""

import re
import shlex
from pathlib import Path
from typing import Literal

from controlled_markdown import form, mctx
from operations import brief_reading, briefs, merging, messages
from operations.change_budget import (OVERRUN_FINDING, TAKE_NOTE, TIME_NOTE, TIME_OPENING,
                                      by_role, file_overrun, left_draft, overrun_ticket,
                                      past_budget, taken)
from operations.doc_review import doc_review, latest_reviewer, review_launch
from operations.directives import Decision, Directive, decided, held_on, named, NUMBER, numbers
from operations.reports import (OPEN_LABELS, Label, budget_passed, items_of,
                                left_for_decision, reviewed_state)
from operations.roles import EDITORS, Purpose, Role, analyst_of, analyst_subject
from operations.state import Agent, State, Ticket
from operations.filing import editor_scratch
from operations.final_reply import live_holder
from operations.handled import answered, repeated, sends_to, sent
from operations.steps import Bash, Launch, Send, Step, Undecided, agent_ids, key
from operations.tracker import (AGENT, add_editor, blocked_on_user, closed,
                                final_run, fingerprint, last_index, log, wait_line, worktree,
                                WORKTREE)
from ticketing.vocabulary import Domain, Kind, Note, Status


def scope(state: State) -> set[str]:
    """The tickets the operators release and take changes among: those
    `State.mine` gives, those the coordinator gives in a line to the operator `me`,
    and each ticket a chain of links reaches from one of those."""
    return reached(state, {n for n, t in state.tickets.items() if state.mine(t)} | named(state))


def reached(state: State, start: set[str]) -> set[str]:
    """`start` and each ticket a chain of links reaches from one of its
    tickets, a link as
    [Change tickets](prompts/agents/notes/tickets.md#change-tickets) defines
    one."""
    out = set(start)
    todo = sorted(out)
    while todo:
        t = state.tickets.get(todo.pop())
        if t is None:
            continue
        for d in links(t):
            if d not in out:
                out.add(d)
                todo.append(d)
    return out


def links(t: Ticket) -> list[str]:
    line = wait_line(t)
    on = line.on_change if line is not None else None
    return [*t.depends_on, *([on] if on is not None else [])]


def expedited(state: State) -> set[str]:
    """The tickets a chain of links reaches from a ticket an `Expedite:`
    line to the operator gives, which the operator takes ahead of the
    others."""
    return reached(state, {n for n, _ in numbers(state, Directive.EXPEDITE)})


def release(state: State) -> Step | None:
    """The move back to `tickets/open/` of a ticket of `scope` under
    `tickets/assigned/` whose holder is not live (`live_holder`)."""
    for n in sorted(scope(state)):
        t = state.tickets.get(n)
        if t is None or t.status is not Status.ASSIGNED:
            continue
        if t.holder is None or not live_holder(state, t.holder):
            return Bash(log(n, Status.OPEN, Status.ASSIGNED,
                            f"released: holder {t.holder or 'none'} is not live", None))
    return None


def boosted(state: State) -> set[str]:
    """The changes that settle an `interference` ticket, which the
    operator takes ahead of the others."""
    out: set[str] = set()
    for t in state.tickets.values():
        line = wait_line(t) if t.kind is Kind.INTERFERENCE else None
        if line is not None and line.on_change is not None:
            out.add(line.on_change)
    return out


def takeable(state: State) -> list[Ticket]:
    lead = boosted(state) | expedited(state)
    ts = [t for n in scope(state) if (t := state.tickets.get(n)) is not None
          and t.kind is Kind.CHANGE and t.status is Status.OPEN
          and all(closed(state, d) for d in t.depends_on)]
    return sorted(ts, key=lambda t: (t.number not in lead, -t.priority, t.order))


def waiting(state: State) -> list[tuple[str, list[str]]]:
    """Each open `change` of `scope` not taken for its `depends-on`, with
    the tickets it waits for."""
    return [(n, [d for d in t.depends_on if not closed(state, d)]) for n in sorted(scope(state))
            if (t := state.tickets.get(n)) is not None and t.kind is Kind.CHANGE
            and t.status is Status.OPEN and not all(closed(state, d) for d in t.depends_on)]


STALL_FINDING = mctx("finding: {number} waits on the user")
"""The note of the line that moves to `tickets/draft/` a change that waits
for the ticket `number`, which waits on the user."""

STALLED = re.compile(form(STALL_FINDING, {"number": rf"(?P<number>{NUMBER.pattern})"}))


def blocked_since(t: Ticket) -> float:
    """The time of the last move of `t`, which stands under
    `tickets/blocked/`, into `tickets/blocked/`."""
    return t.log[final_run(t)[0]].time if t.log else t.filed


def stall(state: State) -> Step | None:
    """The move to `tickets/draft/` of a change of `waiting` that waits for
    a ticket that waits on the user (`blocked_on_user`), where no line of
    its log since that ticket's last move into `tickets/blocked/` gives
    `STALL_FINDING` on it."""
    for n, deps in waiting(state):
        t = state.tickets[n]
        for d in deps:
            u = state.tickets.get(d)
            if u is None or blocked_on_user(u) is None:
                continue
            since = blocked_since(u)
            if not any(ln.time >= since and (m := STALLED.match(ln.note)) is not None
                       and m["number"] == d for ln in t.log):
                return Bash(log(n, Status.DRAFT, Status.OPEN, STALL_FINDING.format(number=d),
                                state.me))
    return None


def next_take(state: State) -> Ticket | None:
    """The first ticket of `takeable`, or None where it gives none."""
    return next(iter(takeable(state)), None)


def take(state: State) -> Step | None:
    t = next_take(state)
    if t is not None:
        b = state.budgets.get(t.number)
        if b is None:
            return Undecided(mctx("the budget of change {number} is unknown").format(
                number=t.number))
        return Bash(log(t.number, Status.ASSIGNED, Status.OPEN,
                        TAKE_NOTE.format(dollars=f"{b.dollars:.2f}", seconds=f"{b.seconds:.0f}"),
                        state.me))
    for n, time in numbers(state, Directive.MERGE):
        t = state.tickets.get(n)
        if (t is not None and t.status is Status.BLOCKED and t.kind is Kind.CHANGE
                and time > blocked_since(t)):
            return Bash(log(n, Status.ASSIGNED, Status.BLOCKED,
                            "taking: the coordinator's Merge line rules the merge", state.me))
    return None


def held(state: State) -> list[Ticket]:
    return sorted((t for t in state.tickets.values()
                   if t.kind is Kind.CHANGE and t.status is Status.ASSIGNED
                   and t.holder == state.me),
                  key=lambda t: t.order)


def launched_on(state: State, number: str) -> list[Agent]:
    """The editors, doc reviewers, item checkers and ticket analysts
    launched on the change `number`."""
    roles = (*EDITORS, Role.DOC_REVIEWER, Role.ITEM_CHECKER)
    out = [a for a in state.agents if a.role in roles and a.subject == number]
    out += [a for a, p, nums in state.analysts() if p is Purpose.CHANGE and number in nums]
    return sorted(out, key=lambda a: a.launched)


def of_change(state: State, number: str) -> list[Agent]:
    """The agents `launched_on` gives for the change `number` since its
    last move out of `tickets/draft/`."""
    t = state.tickets.get(number)
    since = 0.0 if t is None else left_draft(t)
    return [a for a in launched_on(state, number) if a.launched > since]


def give_up(state: State) -> Step | None:
    """A message that tells an agent at work on a change that no operator
    carries any more, or that another live holder (`live_holder`) carries,
    to end. A live holder among the session's operators carries the same
    agents, so their work goes on."""
    for a in state.agents:
        if not a.pending or a.agent_id is None:
            continue
        if a.role is Role.TICKET_ANALYST:
            parsed = analyst_of(a.subject)
            if parsed is None:
                continue
            number = parsed[1]
        else:
            number = a.subject
        t = state.tickets.get(number)
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


def in_worktree(a: Agent, w: Path) -> bool:
    return briefs.WORK_IN.format(worktree=w) in a.brief


def editors_in(agents: list[Agent], w: Path) -> list[Agent]:
    """The editors among `agents` launched in the worktree `w`."""
    return [a for a in agents if a.role in EDITORS and in_worktree(a, w)]


def change_editors(t: Ticket) -> tuple[Role, ...] | Undecided:
    """The editors of the change `t`, those its `editors` field gives; a
    change whose ticket gives none is undecided."""
    if t.editors is None:
        return Undecided(mctx("change {number} gives no `editors` field").format(
            number=t.number))
    return t.editors

def unstaffed(editors: tuple[Role, ...], here: list[Agent]) -> list[Role]:
    """The editor roles of `editors` with no agent among `here`, the
    editors in the change's worktree, in the order of `EDITORS`."""
    return [r for r in EDITORS if r in editors and not any(a.role is r for a in here)]


DRAFTERS = (Role.CODE_EDITOR, Role.HANDBOOK_EXPANDED)
"""The editors that draft the text of the fragments their code needs."""


def latest_editors(here: list[Agent]) -> list[Agent]:
    """The latest editor of `here` of each role, with the doc editor of
    the fragments (`briefs.FRAGMENTS_PART`) apart from the doc editor of
    the documents."""
    return list({(a.role, briefs.FRAGMENTS_PART in a.brief): a for a in here}.values())


def drafter_ids(here: list[Agent]) -> list[str] | Undecided:
    """The agent ids of the latest drafters of `here`, which the brief of a
    doc editor gives for the code changes a move of a fragment's text
    needs."""
    return agent_ids([a for a in latest_editors(here) if a.role in DRAFTERS])


def lacking_doc_editor(t: Ticket, w: Path | None,
                       state: State) -> tuple[Role, ...] | None:
    """The `editors` field of the held change `t`, where it gives no doc
    editor while the `fragments` of `t`'s worktree `w` are not empty, and
    otherwise None."""
    if (t.editors is None or Role.DOC_EDITOR in t.editors or w is None
            or not state.fragments.get(w)):
        return None
    return t.editors


def fragments_step(state: State, t: Ticket, w: Path,
                   here: list[Agent]) -> Step | None:
    """The step that gives the fragments whose text the change adds or
    changes to a doc editor launched for them, once a drafter of the change
    has reported and no doc editor was launched since its latest report:
    the addition of `doc-editor` to the `editors` field of a change that
    gives none, and otherwise the launch of a doc editor on the
    fragments."""
    places = state.fragments.get(w, ())
    reported = [r.time for a in here if a.role in DRAFTERS and (r := a.last_report) is not None]
    if not places or not reported or any(
            a.role is Role.DOC_EDITOR and a.launched > max(reported) for a in here):
        return None
    if lacking_doc_editor(t, w, state) is not None:
        if t.number not in state.doc_budgets:
            return Undecided(mctx("the budget of change {number} with a doc editor is "
                                  "unknown").format(number=t.number))
        return Bash(add_editor(t.number, Role.DOC_EDITOR, state.me))
    drafters = drafter_ids(here)
    if isinstance(drafters, Undecided):
        return drafters
    return Launch(Role.DOC_EDITOR, t.number, briefs.editor(
        Role.DOC_EDITOR, t.number, True, w,
        editor_scratch(t.number, Role.DOC_EDITOR, state.scratch), state.me,
        places, tuple(drafters), of_fragments=True), model=t.model(Role.DOC_EDITOR))


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
            state.fragments.get(w, ()), tuple(drafters)), model=t.model(role))
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
    return merge(state, t, w, latest)


NO_OPERATOR = mctx("{agent} is no doc editor that an operator of the session launched, so no "
                   "launch is printed: give your final reply.")
"""The line `editor_review` gives an agent that is no doc editor an operator
launched."""


def editor_review(state: State, editor: str) -> Step | str:
    """The launch of the doc reviewer of the change of the doc editor
    `editor`, launched by it. In its place it gives a line: where
    `editor` is no doc editor an operator launched, `NO_OPERATOR`; where the change has a doc
    reviewer, whoever launched it, the line that names the latest one, so
    the editor launches no other; and where an editor role of the change
    has no agent in its worktree or another editor there is pending, the
    line that says the operator launches the review."""
    mine = [a for a in state.agents if a.agent_id == editor and a.role is Role.DOC_EDITOR]
    if not mine:
        return NO_OPERATOR.format(agent=editor)
    t = state.tickets.get(mine[-1].subject)
    if t is None:
        return Undecided(mctx("the ticket of change {number} of doc editor {agent} is not "
                              "read").format(number=mine[-1].subject, agent=editor))
    editors = change_editors(t)
    if not isinstance(editors, tuple):
        return editors
    w = worktree(t, state)
    if w is None:
        return Undecided(mctx("change {number} gives no worktree").format(number=t.number))
    agents = of_change(state, t.number)
    if (reviewer := latest_reviewer(agents)) is not None:
        ids = agent_ids([reviewer])
        if isinstance(ids, Undecided):
            return ids
        return mctx("Change {number} already has doc reviewer {agent}, so launch no other "
                    "doc reviewer.").format(number=t.number, agent=ids[0])
    here = editors_in(agents, w)
    if (unstaffed(editors, here)
            or any(a.pending for a in here if a.agent_id != editor)):
        return mctx("Another editor of change {number} has not reported, so the operator "
                    "launches the review: give your final reply.").format(number=t.number)
    return review_launch(t, w, here, editor)



def merge(state: State, t: Ticket, w: Path, latest: list[Agent]) -> Step | None:
    """The line that gives the change's agent-running time since its take,
    where none follows that take and that time reads, and then the merge."""
    take_line = taken(t)
    start = take_line.time if take_line is not None else left_draft(t)
    spent = state.spent.get(t.number)
    if spent is not None and not any(ln.time >= start and ln.note.startswith(TIME_OPENING)
                                     for ln in t.log):
        return Bash(log(t.number, Status.ASSIGNED, Status.ASSIGNED,
                        TIME_NOTE.format(seconds=spent.seconds), state.me))
    return merging.merge_steps(state, t, w, latest)


def over_budget(state: State, t: Ticket, w: Path,
                agents: list[Agent]) -> Step | None | Literal[False]:
    """The step on the change `t` past the budget its take gives, or False
    where it is not past it or no take gives a budget."""
    take_line = taken(t)
    if take_line is None:
        return False
    since, limit, _ = take_line
    spent = state.spent.get(t.number)
    if spent is None:
        return Undecided(mctx("the spend of change {number} since its take is unknown").format(
            number=t.number))
    if not past_budget(take_line, spent):
        return False
    trip = overrun_ticket(state, t, since)
    if trip is None:
        budget = state.budgets.get(t.number)
        if budget is None:
            return Undecided(mctx("the median spend by role of the changes the budget of "
                                  "change {number} is taken over is unknown").format(
                                      number=t.number))
        return file_overrun(t, spent, budget, limit, agents)
    for a in agents:
        if a.pending and a.agent_id is not None and a.launched < trip.filed:
            message = messages.over_budget(t.number, a.role is Role.DOC_REVIEWER)
            if not sent(state, a.agent_id, message):
                return Send(a.agent_id, message)
    if any(a.pending for a in agents):
        return None
    latest = latest_editors(editors_in(agents, w))
    reported = max((r.time for a in latest if (r := a.last_report) is not None), default=0.0)
    checkers = [a for a in agents if a.role is Role.ITEM_CHECKER
                and a.launched > trip.filed and a.launched > reported]
    if not checkers:
        editors = agent_ids(latest)
        if isinstance(editors, Undecided):
            return editors
        return check_items(state, t, w, latest, editors, past=True)
    checker = checkers[-1]
    if checker.last_report is None:
        return Undecided(mctx("item checker {agent} on change {number}, past its cost budget, "
                              "returned no report").format(agent=checker.agent_id,
                                                          number=t.number))
    if left_for_decision(checker) is None:
        return merge(state, t, w, latest)
    return Bash(log(t.number, Status.DRAFT, Status.ASSIGNED, mctx(
        "{opening} of {limit} dollars: spent {spent} dollars, {roles}; item checker {agent} "
        "leaves items for a decision").format(
            opening=OVERRUN_FINDING, limit=f"{limit:.2f}", spent=f"{spent.dollars:.2f}",
            roles=by_role(spent.by_role), agent=checker.agent_id), state.me))


def over_budget_step(state: State, t: Ticket, latest: list[Agent]) -> Step | None:
    """The message to the first editor of `latest` whose latest reply says
    its budget is passed, or None where no such reply is."""
    for a in latest:
        r = a.last_report
        if r is None or a.agent_id is None or not budget_passed(a):
            continue
        given = [a.brief] + [c.message for c in sends_to(state, a.agent_id)]
        stated = next((s for text in reversed(given) if (s := brief_reading.budgets(text))), set[float]())
        if len(stated) != 1:
            return Undecided(mctx("editor {agent} of change {number} says its budget is "
                                  "passed, and the latest brief or operator's message to it "
                                  "that states a budget states {count}").format(
                agent=a.agent_id, number=t.number, count=len(stated)))
        return Send(a.agent_id, messages.go_on(r.time, stated.pop()))
    return None


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
    """Whether the latest of a change's item `checkers` sent no editor a
    message and its reply gives the worktree `w` in the state it is in."""
    if not checkers or checkers[-1].messaged != frozenset():
        return False
    seen = reviewed_state(checkers[-1])
    return seen is not None and seen == fingerprint(w)


def leftover(state: State, t: Ticket, w: Path, latest: list[Agent],
             agents: list[Agent]) -> Step | None | Literal[False]:
    """The step on what the editors leave, or False where they leave
    nothing."""
    checkers = [a for a in agents if a.role is Role.ITEM_CHECKER]
    analysts = [a for a in agents if a.role is Role.TICKET_ANALYST]
    if any(a.pending for a in checkers + analysts):
        return None
    editors = agent_ids(latest)
    if isinstance(editors, Undecided):
        return editors
    checked = max((a.launched for a in checkers), default=0.0)
    needing = [a for a in latest if (r := a.last_report) is not None and r.time > checked]
    if needing and not unchanged_since(checkers, w):
        return check_items(state, t, w, needing, editors)
    questions = [q for q in state.tickets.values() if q.kind is Kind.QUESTION
                 and q.domain is Domain.CHANGE and q.subject == t.number
                 and q.status in (Status.OPEN, Status.ASSIGNED)]
    judged = max((a.launched for a in analysts), default=0.0)
    left = left_for_decision(checkers[-1]) if checkers else None
    fresh = left if left is not None and (r := checkers[-1].last_report) is not None \
        and r.time > judged else None
    parts = fresh
    hold: str | None = None
    on_user = False
    if analysts and judged > checked and (hold := left_hold(analysts[-1], t.number)):
        on_user = items_of(analysts[-1], [Label.DECISION]) is not None
        parts = left
    elif fresh is None and not questions:
        return False
    elif fresh is None and judged > max(q.filed for q in questions):
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
        t.number, w, parts, [q.number for q in questions], editors, reports, state.me))


def latest_reports(agents: list[Agent]) -> list[tuple[str, str]] | Undecided:
    """The agent id and latest report text of each of `agents` that has a
    report."""
    reporting = [(a, r) for a in agents if (r := a.last_report) is not None]
    reporters = agent_ids(a for a, _ in reporting)
    if isinstance(reporters, Undecided):
        return reporters
    return [(i, r.text) for i, (_, r) in zip(reporters, reporting, strict=True)]


def check_items(state: State, t: Ticket, w: Path, needing: list[Agent],
                editors: list[str], past: bool = False) -> Step:
    """The launch of an item checker on the latest reports of the editors
    `needing`, which have reported since the last item checker was launched
    on the change `t`, and on the accepted gate outputs the change writes,
    with the latest report of each ticket analyst launched on `t` that has
    reported, in launch order, so the checker leaves out what they already
    decided. `past` gives that the change is past its cost budget."""
    reports = latest_reports(needing)
    if isinstance(reports, Undecided):
        return reports
    decisions = [(a.agent_id, r.text) for a in of_change(state, t.number)
                 if a.role is Role.TICKET_ANALYST and a.agent_id is not None
                 and (r := a.last_report) is not None]
    return Launch(Role.ITEM_CHECKER, t.number, briefs.item_check(
        t.number, w, reports, decisions, list(state.gate_outputs.get(w, ())), editors, state.me,
        past))


def step(state: State) -> Step | None:
    """The next step of the changes: a message to an agent on a change no
    longer carried, a take, then a step of each change the operator
    holds."""
    if (s := give_up(state)) is not None:
        return s
    if (s := take(state)) is not None:
        return s
    for t in held(state):
        if (s := carry(state, t)) is None:
            continue
        if not repeated(s, state):
            return s
        if isinstance(s, Send) and answered(s, state) and not repeated(u := unmoved(t, s), state):
            return u
    return None


def unmoved(t: Ticket, s: Send) -> Undecided:
    """The step of the change `t` whose next step `s` is a message its
    recipient already answered, with the change where it was."""
    return Undecided(mctx("the next step of change {number} is the message {key} to {agent}, "
                          "which an operator already sent and {agent} answered, and the "
                          "change has not moved since").format(
        number=t.number, key=key(s), agent=s.to))
