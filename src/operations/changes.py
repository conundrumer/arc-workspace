"""A change from its take to its merge: the release of tickets, the take of
open changes, the editors, the review of the documents, the item checker
and the ticket analyst on what the editors leave; `doc_review` gives the
review of the documents. The steps carry out
[Carrying a change](prompts/agents/notes/changes.md#carrying-a-change);
`merging` gives the merge and what follows it. `change_agents` gives the
agents of a change and the editors it needs, `item_check` the launch of
its item checker, `change_fragments` the doc editor of its `mctx`
fragments, and `change_overrun` a change past its cost budget and an
editor whose budget is passed.

The operators act on the tickets of the session and on those of the
sessions `SessionsRead.adopted` gives, as `State.mine` gives them. Which session
is the main one, `file_ticket.py main --help` states; which sessions are
idle, `idle_sessions.read_sessions` gives.

A change with no worktree gets one from
`scripts/change_worktree.py`, which logs its path on the ticket, so a
later operator continues the change there. Where a change's ticket is
revised after the log line that gives its worktree, the operator runs
`scripts/change_worktree.py` again, whose `--help` gives what it carries in.
Every editor and reviewer is
launched with no isolation, and its brief gives that worktree.

What the editors' and the doc reviewer's replies give is read by the fixed
forms of `reports`. Once each editor of a change has reported, the latest report of
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

A change whose `editors` field gives a doc editor, the one
`change_fragments` adds included, merges once its review passes as
`doc_review` gives.

A next step of a change that is a message an operator already sent,
whose recipient answered it, leaves the change where it was, and the
command cannot place it.

While a `Hold intake.` line holds intake (`directives.held_intake`), the
operator takes, of the changes it would take with no hold, only those of
`held_work`, so the work already held reaches its end, and those of
`through_hold`, the tickets an `Admit:` or an `Expedite:` line gives, and
each other change waits for a `Resume intake.` line.

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
from collections.abc import Callable
from pathlib import Path
from typing import Literal

from controlled_markdown import form, mctx
from operations import briefs, merging, messages
from operations.change_agents import (change_editors, editors_in, latest_editors, launched_on,
                                      of_change, unstaffed)
from operations.change_budget import TAKE_NOTE
from operations.change_fragments import drafter_ids, fragments_step
from operations.change_overrun import over_budget, over_budget_step
from operations.doc_review import doc_review, with_ids
from operations.directives import (Decision, Directive, admit_named, decided, held_intake, held_on,
                                   named, NUMBER, numbers)
from operations.item_check import check_items, latest_reports
from operations.reports import OPEN_LABELS, Label, items_of, left_for_decision, shows_current
from operations.roles import Purpose, Role, analyst_of, analyst_subject
from operations.state import Agent, State, Ticket
from operations.filing import editor_scratch
from operations.final_reply import live_holder
from operations.handled import answered, repeated, sent
from operations.steps import Bash, Launch, Send, Step, Undecided, key
from operations.tracker import (AGENT, blocked_on_user, closed, final_run, last_index, log,
                                wait_line, worktree, WORKTREE)
from ticketing.vocabulary import Domain, Kind, Note, Status


def scope(state: State) -> set[str]:
    """The tickets the operators release and take changes among: those
    `State.mine` gives, those the coordinator gives in a line to the operator `me`,
    and each ticket a chain of links reaches from one of those."""
    return reached(state, {n for n, t in state.tracker.tickets.items() if state.mine(t)} | named(state))


def reached(state: State, start: set[str]) -> set[str]:
    """`start` and each ticket a chain of links reaches from one of its
    tickets, a link as
    [Change tickets](prompts/agents/notes/tickets.md#change-tickets) defines
    one."""
    out = set(start)
    todo = sorted(out)
    while todo:
        t = state.tracker.tickets.get(todo.pop())
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


def admits(state: State) -> Callable[[str], bool]:
    """Whether the operator may take an open ticket: one the `takes` of
    the run scripts admit (`Computed.admitted`), or one of `expedited`,
    or any where no script defines `takes`; under a hold, only such a
    ticket that is also one of `held_work` or of `through_hold`."""
    admitted = state.computed.admitted()
    passing = None if admitted is None else admitted | expedited(state)
    held = held_work(state) | through_hold(state) if held_intake(state) else None
    return lambda n: ((passing is None or n in passing)
                      and (held is None or n in held))


def taken_before(t: Ticket) -> bool:
    """Whether a line of `t`'s log moves it into `tickets/assigned/`, so
    that taking it again is no new take: `release` moved it back to
    `tickets/open/` from a holder that is not live."""
    return any(ln.status is Status.ASSIGNED for ln in t.log)


def held_work(state: State) -> set[str]:
    """The work held, with each change it waits on."""
    return reached(state, {n for n, t in state.tracker.tickets.items()
                           if (t.kind is Kind.CHANGE and taken_before(t))
                           or (t.kind is Kind.INTERFERENCE and t.status is not Status.CLOSED)})


def through_hold(state: State) -> set[str]:
    """The tickets that pass a hold: each ticket a chain of links reaches
    from a ticket of `directives.admit_named`, and those of `expedited`."""
    return reached(state, admit_named(state)) | expedited(state)


RELEASED = mctx("released: holder {holder} is not live")


def release(state: State) -> Step | None:
    """The move back to `tickets/open/` of each ticket of `scope` under
    `tickets/assigned/` whose holder is not live (`live_holder`), in one
    command whose moves run apart (`moves`)."""
    return moves([log(n, Status.OPEN, Status.ASSIGNED,
                      RELEASED.format(holder=t.holder or 'none'), None)
                  for n in sorted(scope(state))
                  if (t := state.tracker.tickets.get(n)) is not None
                  and t.status is Status.ASSIGNED
                  and (t.holder is None or not live_holder(state, t.holder))])


def moves(commands: list[str]) -> Bash | None:
    """One step that runs each of `commands`, or None where there is none.
    The commands are joined with `;`, so a move that `file_ticket.py log`
    refuses leaves the others to run, and the next step reads the tracker
    as they left it."""
    return Bash(" ; ".join(commands)) if commands else None


def boosted(state: State) -> set[str]:
    """The changes that settle an `interference` ticket, which the
    operator takes ahead of the others."""
    out: set[str] = set()
    for t in state.tracker.tickets.values():
        line = wait_line(t) if t.kind is Kind.INTERFERENCE else None
        if line is not None and line.on_change is not None:
            out.add(line.on_change)
    return out


def takeable(state: State) -> list[Ticket]:
    lead = boosted(state) | expedited(state)
    admitted = admits(state)
    ts = [t for n in scope(state) if (t := state.tracker.tickets.get(n)) is not None
          and t.kind is Kind.CHANGE and t.status is Status.OPEN
          and all(closed(state, d) for d in t.depends_on)
          and (admitted(n) or taken_before(t))]
    return sorted(ts, key=lambda t: (t.number not in lead, -t.priority, t.order))


def waiting(state: State) -> list[tuple[str, list[str]]]:
    """Each open `change` of `scope` not taken for its `depends-on`, with
    the tickets it waits for."""
    return [(n, [d for d in t.depends_on if not closed(state, d)]) for n in sorted(scope(state))
            if (t := state.tracker.tickets.get(n)) is not None and t.kind is Kind.CHANGE
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
        t = state.tracker.tickets[n]
        for d in deps:
            u = state.tracker.tickets.get(d)
            if u is None or blocked_on_user(u) is None:
                continue
            since = blocked_since(u)
            if not any(ln.time >= since and (m := STALLED.match(ln.note)) is not None
                       and m["number"] == d for ln in t.log):
                return Bash(log(n, Status.DRAFT, Status.OPEN, STALL_FINDING.format(number=d),
                                state.me))
    return None


def take(state: State) -> Step | None:
    """The take of each change of `takeable`, in its order, up to the first
    whose budget `Computed.budgets` does not give."""
    commands: list[str] = []
    for t in takeable(state):
        b = state.computed.budgets.get(t.number)
        if b is None:
            if not commands:
                return Undecided(mctx("the budget of change {number} is unknown").format(
                    number=t.number))
            break
        commands.append(log(t.number, Status.ASSIGNED, Status.OPEN,
                            TAKE_NOTE.format(dollars=f"{b.dollars:.2f}",
                                             seconds=f"{b.seconds:.0f}"),
                            state.me))
    if commands:
        return moves(commands)
    for n, time in numbers(state, Directive.MERGE):
        t = state.tracker.tickets.get(n)
        if (t is not None and t.status is Status.BLOCKED and t.kind is Kind.CHANGE
                and time > blocked_since(t)):
            return Bash(log(n, Status.ASSIGNED, Status.BLOCKED,
                            "taking: the coordinator's Merge line rules the merge", state.me))
    return None


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
    needing = [a for a in latest if (r := a.last_report) is not None and r.time > checked]
    if needing and not unchanged_since(checkers, w):
        return check_items(state, t, w, needing, editors)
    questions = [q for q in state.tracker.tickets.values() if q.kind is Kind.QUESTION
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
        t.number, w, parts, [q.number for q in questions], editors, reports,
        state.me))


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
