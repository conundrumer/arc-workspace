"""A change from its take to its merge: the release of tickets, the take of
open changes, the editors, the review of the documents and the ticket
analyst on what the editors leave. The steps carry out
[Carrying a change](prompts/agents/notes/changes.md#carrying-a-change);
`merging` gives the merge and what follows it.

The editors a change needs are those the `editors` field of its ticket
gives, which the ticket analyst that files it writes, and a change whose
ticket gives none is undecided. A change with no worktree gets one from
`scripts/change_worktree.py`, which logs its path on the ticket, so a
later loop continues the change there. Every editor and reviewer is
launched with no isolation, and its brief gives that worktree.

What the editors' and the doc reviewer's replies give is read by the fixed
forms of `reports`. An editor whose latest reply says its budget is passed
is sent a message to go on with the work that reply leaves, with the
budget the loop last gave it, and that reply goes to no ticket
analyst. Any other report of an editor that has not finished, a
`Review` section that gives a place as standing, an open `question` ticket
filed on the change, and the accepted gate outputs the change writes go to
one ticket analyst, which judges them. That analyst sends an editor its
judgments and decisions only where one of them gives that editor an edit,
or where the change has a doc editor, and otherwise sends that editor no
message. A report that analyst was launched after leaves nothing more,
unless the part of that analyst's reply for the coordinator gives a
`decision:` or an `unfinished:` item and no editor has reported since its
launch: then the change is held on those items, in place of its merge.
Where they give a `decision:` item, the step waits on the coordinator,
which gets those items with the line that rules the step
(`triage.for_coordinator`), and otherwise it goes to a ticket analyst
(`decisions`).

A change with a doc editor passes its review once the latest reply of its
doc reviewer opens with `no finding stands` and follows each editor's last
report, or precedes the last report only of editors that reviewer sent a
message, since such an editor sends that reviewer its fixes before each
reply. A reply that precedes the last report of any other editor is read
for no finding, and that reviewer is asked once to review the change
again, and the review is held where it has not replied since. A reply that gives neither that nor a finding in the form
`reports.FINDING` reads goes back to the doc reviewer once, with a request
to send it again in that form, and the review is held where its answer is
still in neither. A reply that gives findings brings a new doc editor for the
findings on documents and a new code editor for those on `.py` files, and
the command sends that reviewer their agent ids.

A step of a change that the command cannot place holds that change alone,
until a `Decision:` line rules it with one of the choices the step gives
(`directives.decided`)."""

import shlex
from pathlib import Path
from typing import Literal

from controlled_markdown import mctx
from operations import briefs, merging
from operations.directives import Decision, Directive, decided, held_on, named, numbers
from operations.reports import (
    OPEN_LABELS,
    Label,
    budget_passed,
    finding_paths,
    finished,
    items_of,
    no_finding,
    standing,
)
from operations.roles import EDITORS, Purpose, Role, analyst_of, analyst_subject
from operations.state import Agent, State, Ticket
from operations.steps import (
    Bash,
    Launch,
    Send,
    Step,
    Undecided,
    agent_ids,
    ask_again,
    repeated,
    sends_to,
    sent,
)
from operations.tracker import AGENT, COORDINATOR, closed, log, worktree
from ticketing.vocabulary import Domain, Kind, Status

PROSE_IN_CODE = ".py"
"""The suffix of the files a doc reviewer's finding on prose in code falls
on, which a code editor fixes."""


def scope(state: State) -> set[str]:
    """The tickets the loop releases and takes changes among: the
    session's, those the coordinator names to the loop, and each `change` one of those
    waits on through a chain of `depends-on`."""
    base = {n for n, t in state.tickets.items() if state.mine(t)} | named(state)
    todo = list(base)
    while todo:
        t = state.tickets.get(todo.pop())
        if t is None:
            continue
        for d in t.depends_on:
            if d not in base:
                base.add(d)
                todo.append(d)
    return base


def release(state: State) -> Step | None:
    """The move back to `tickets/open/` of a ticket of `scope` under
    `tickets/assigned/` whose holder's work is not open, where its last
    line's note does not open with `coordinator`."""
    for n in sorted(scope(state)):
        t = state.tickets.get(n)
        if (t is None or t.status is not Status.ASSIGNED
                or (t.log and t.log[-1].note.startswith(COORDINATOR))):
            continue
        if t.holder is None or t.holder not in state.open_holders:
            return Bash(log(n, Status.OPEN, Status.ASSIGNED,
                            f"released: holder {t.holder or 'none'} has no open work", None))
    return None


def boosted(state: State) -> set[str]:
    """The changes that settle an `interference` ticket, which the
    loop takes ahead of the others."""
    out: set[str] = set()
    for t in state.tickets.values():
        if (t.kind is Kind.INTERFERENCE and t.status is Status.BLOCKED and t.log
                and (change := t.log[-1].on_change) is not None):
            out.add(change)
    return out


def takeable(state: State) -> list[Ticket]:
    lead = boosted(state)
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


def take(state: State) -> Step | None:
    for t in takeable(state):
        return Bash(log(t.number, Status.ASSIGNED, Status.OPEN, "taking", state.me))
    for n, _ in numbers(state, Directive.MERGE):
        t = state.tickets.get(n)
        if t is not None and t.status is Status.BLOCKED and t.kind is Kind.CHANGE:
            return Bash(log(n, Status.ASSIGNED, Status.BLOCKED,
                            "taking: the user decided, to merge", state.me))
    return None


def held(state: State) -> list[Ticket]:
    return sorted((t for t in state.tickets.values()
                   if t.kind is Kind.CHANGE and t.status is Status.ASSIGNED
                   and t.holder == state.me
                   and not (t.log and t.log[-1].note.startswith(COORDINATOR))),
                  key=lambda t: t.order)


def of_change(state: State, number: str) -> list[Agent]:
    """The editors, doc reviewers and ticket analysts launched on the
    change `number`."""
    roles = (*EDITORS, Role.DOC_REVIEWER)
    out = [a for a in state.agents if a.role in roles and a.subject == number]
    out += [a for a, p, nums in state.analysts() if p is Purpose.CHANGE and number in nums]
    return sorted(out, key=lambda a: a.launched)


def give_up(state: State) -> Step | None:
    """A message that tells an agent at work on a change that the loop
    carries no more, or that another holder carries, to end."""
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
        if t is None or t.kind is not Kind.CHANGE or a not in of_change(state, number):
            continue
        lost = t.status in (Status.DRAFT, Status.CLOSED) or (
            t.status is Status.ASSIGNED and t.holder not in (state.me, None)
            and t.holder in state.open_holders)
        message = briefs.stop_work(number)
        if lost and not sent(state, a.agent_id, message):
            return Send(a.agent_id, message)
    return None


WORKTREE_SCRIPT = "scripts/change_worktree.py"


def make_worktree(number: str, agent_id: str) -> str:
    """The Bash command that makes the worktree of the change `number`."""
    return shlex.join(["uv", "run", "python", WORKTREE_SCRIPT, number, AGENT, "--id", agent_id])


def in_worktree(a: Agent, w: Path) -> bool:
    return briefs.WORK_IN.format(worktree=w) in a.brief


def change_editors(t: Ticket) -> tuple[Role, ...] | Undecided:
    """The editors of the change `t`, those its `editors` field gives; a
    change whose ticket gives none is undecided."""
    if t.editors is None:
        return Undecided(mctx("change {number} gives no `editors` field").format(
            number=t.number))
    return t.editors

def carry(state: State, t: Ticket) -> Step | None:
    """The next step on the change `t` the loop holds, or None where it
    waits on an agent."""
    if merging.merged(state, t):
        return merging.close(state, t, of_change(state, t.number))
    editors = change_editors(t)
    if not isinstance(editors, tuple):
        return editors
    agents = of_change(state, t.number)
    launched = [a for a in agents if a.role in EDITORS]
    w = worktree(t, state)
    if w is None:
        return Bash(make_worktree(t.number, state.me))
    here = [a for a in launched if in_worktree(a, w)]
    for role in (r for r in EDITORS if r in editors):
        if not any(a.role is role for a in here):
            return Launch(role, t.number, briefs.editor(
                role, t.number, len(editors) > 1, w, state.scratch / t.number),
                model=t.model(role))
    if any(a.pending for a in here):
        return None
    latest = {a.role: a for a in here}
    if (step := past_budget(state, t, list(latest.values()))) is not None:
        return step
    if (step := leftover(state, t, w, list(latest.values()), agents)) is not False:
        return step
    if Role.DOC_EDITOR in editors and (
            step := doc_review(state, t, w, here, agents)) is not False:
        return step
    return merging.merge_steps(state, t, w, list(latest.values()))


def past_budget(state: State, t: Ticket, latest: list[Agent]) -> Step | None:
    """The message to the first editor of `latest` whose latest reply says
    its budget is passed, or None where no such reply is."""
    for a in latest:
        r = a.last_report
        if r is None or a.agent_id is None or not budget_passed(a):
            continue
        given = [a.brief] + [str(c.input.get("message", "")) for c in sends_to(state, a.agent_id)]
        stated = next((s for text in reversed(given) if (s := briefs.budgets(text))), set[float]())
        if len(stated) != 1:
            return Undecided(mctx("editor {agent} of change {number} says its budget is "
                                  "passed, and the latest brief or message of the loop to it "
                                  "that states a budget states {count}").format(
                agent=a.agent_id, number=t.number, count=len(stated)))
        return Send(a.agent_id, briefs.go_on(r.time, stated.pop()))
    return None


LEFT_CHOICES = {
    Decision.MERGE: mctx("go on to the merge; the close of the change closes its open question "
                       "tickets"),
    Decision.AGAIN: mctx("launch another ticket analyst on what the editors leave")}
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


def leftover(state: State, t: Ticket, w: Path, latest: list[Agent],
             agents: list[Agent]) -> Step | None | Literal[False]:
    """The step on what the editors leave, or False where they leave
    nothing."""
    analysts = [a for a in agents if a.role is Role.TICKET_ANALYST]
    if any(a.pending for a in analysts):
        return None
    judged = max((a.launched for a in analysts), default=0.0)
    left = [a for a in latest if not finished(a) or standing(a)]
    needing = [a for a in left if (r := a.last_report) is not None and r.time > judged]
    questions = [q for q in state.tickets.values() if q.kind is Kind.QUESTION
                 and q.domain is Domain.CHANGE and q.subject == t.number
                 and q.status in (Status.OPEN, Status.ASSIGNED)]
    reported = max((r.time for a in latest if (r := a.last_report) is not None), default=0.0)
    outputs = list(state.gate_outputs.get(w, ()))
    gate = outputs if reported > judged else []
    hold: str | None = None
    on_user = False
    if analysts and reported <= judged and (hold := left_hold(analysts[-1], t.number)):
        on_user = items_of(analysts[-1], [Label.DECISION]) is not None
        needing, gate = left, outputs
    elif not needing and not questions and not gate:
        return False
    elif questions and not needing and not gate and judged > max(q.filed for q in questions):
        hold = mctx("ticket analyst {agent} returned on change {number}, and its question "
                    "tickets stand open").format(agent=analysts[-1].agent_id, number=t.number)
    if hold is not None:
        choice = decided(state, hold, LEFT_CHOICES)
        if isinstance(choice, Undecided):
            return None if on_user else choice
        if choice is Decision.MERGE:
            return False
    reporting = [(a, r) for a in needing if (r := a.last_report) is not None]
    reporters = agent_ids(a for a, _ in reporting)
    editors = agent_ids(latest)
    if isinstance(reporters, Undecided):
        return reporters
    if isinstance(editors, Undecided):
        return editors
    reports = [(i, r.text) for i, (_, r) in zip(reporters, reporting, strict=True)]
    return Launch(Role.TICKET_ANALYST, analyst_subject(Purpose.CHANGE, t.number), briefs.findings(
        t.number, w, reports, [q.number for q in questions], gate, editors))


def doc_review(state: State, t: Ticket, w: Path, here: list[Agent],
               agents: list[Agent]) -> Step | None | Literal[False]:
    """The step of the review of the change's documents, or False where it
    has passed."""
    reviewers = [a for a in agents if a.role is Role.DOC_REVIEWER]
    if not reviewers:
        return review_launch(t, w, here, state)
    r = reviewers[-1]
    if r.pending:
        return None
    reply = r.last_report
    if reply is not None and (late := [a for a in here if (rep := a.last_report) is not None
                                       and rep.time > reply.time]):
        return review_stale(state, t, w, here, r, reply.time, late)
    if reply is not None and no_finding(r):
        return False
    since = reply.time if reply is not None else r.launched
    paths = finding_paths(r)
    if not paths:
        if r.agent_id is not None and reply is not None:
            asked = ask_again(state, r.agent_id, [x.time for x in r.reports], briefs.REVIEW_FORM)
            if isinstance(asked, Send):
                return asked
        return review_decided(state, t, w, here, mctx(
            "the reply of doc reviewer {agent} on change {number} gives no finding in the form "
            "the command reads").format(agent=r.agent_id, number=t.number))
    code = [p for p in paths if p.endswith(PROSE_IN_CODE)]
    needed = ([Role.DOC_EDITOR] if len(code) < len(paths) else []) + (
        [Role.CODE_EDITOR] if code else [])
    fixers = [a for a in here if a.role in needed and a.launched > since]
    for role in needed:
        if not any(a.role is role for a in fixers):
            reviewer = agent_ids([r])
            if isinstance(reviewer, Undecided):
                return reviewer
            return Launch(role, t.number, briefs.review_fix(
                role, t.number, w, reviewer[0], code if role is Role.CODE_EDITOR else [],
                state.scratch / t.number), model=t.model(role))
    fixer_ids = agent_ids(fixers)
    if isinstance(fixer_ids, Undecided):
        return fixer_ids
    for f in fixer_ids:
        message = briefs.new_editor(f)
        if r.agent_id and not sent(state, r.agent_id, message):
            return Send(r.agent_id, message)
    return review_decided(state, t, w, here, unreplied(r, t))


def unreplied(r: Agent, t: Ticket) -> str:
    return mctx("doc reviewer {agent} of change {number} has not replied since its editors "
                "ended").format(agent=r.agent_id, number=t.number)


def review_stale(state: State, t: Ticket, w: Path, here: list[Agent], r: Agent, since: float,
                 late: list[Agent]) -> Step | Literal[False]:
    """The step on the reply at `since` of the doc reviewer `r`, which
    precedes the last report of the editors `late`: False where it opens
    with `no finding stands` and `r` sent each of them a message, and
    otherwise the message that asks `r` to review the change again."""
    if no_finding(r):
        if r.messaged is None:
            return Undecided(mctx("the transcript of doc reviewer {agent} of change {number} "
                                  "is unknown, so the command cannot read whom it sent a "
                                  "message").format(agent=r.agent_id, number=t.number))
        ids = agent_ids(late)
        if isinstance(ids, Undecided):
            return ids
        if all(i in r.messaged for i in ids):
            return False
    message = briefs.review_again(since)
    if r.agent_id is not None and not sent(state, r.agent_id, message):
        return Send(r.agent_id, message)
    return review_decided(state, t, w, here, unreplied(r, t))


def review_decided(state: State, t: Ticket, w: Path, here: list[Agent],
                 what: str) -> Step | Literal[False]:
    """The step on a review held for `what`, by its decision:
    False where the review passes."""
    choice = decided(state, what, {Decision.PASSES: mctx("the review passes"),
                                 Decision.AGAIN: mctx("launch another doc reviewer")})
    if isinstance(choice, Undecided):
        return choice
    if choice is Decision.PASSES:
        return False
    return review_launch(t, w, here, state)


def review_launch(t: Ticket, w: Path, here: list[Agent], state: State) -> Step:
    """The launch of a doc reviewer on the change, with its editors."""
    ids = agent_ids(here)
    if isinstance(ids, Undecided):
        return ids
    return Launch(Role.DOC_REVIEWER, t.number, briefs.doc_review(
        t.number, w, [(a.role, i) for a, i in zip(here, ids, strict=True)]))


def step(state: State) -> Step | None:
    """The next step of the changes: a message to an agent on a change no
    longer carried, a take, then a step of each change the loop
    holds."""
    if (s := give_up(state)) is not None:
        return s
    if (s := take(state)) is not None:
        return s
    for t in held(state):
        if (s := carry(state, t)) is not None and not repeated(s, state):
            return s
    return None
