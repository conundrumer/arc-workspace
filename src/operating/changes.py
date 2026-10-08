"""A change from its take to its merge: the release of tickets, the take of
open changes, the editors, the review of the documents and the ticket
analyst on what the editors leave. The steps carry out
[Carrying a change](prompts/agents/notes/changes.md#carrying-a-change);
`merging` gives the merge and what follows it.

The editors a change needs are those the `editors` field of its ticket
gives, which the ticket analyst that files it writes, and a change whose
ticket gives none is undecided. The first editor is launched with
a worktree of its own, whose path the agent id gives, and the command logs
that path on the ticket, so a later operator continues the change there,
with the editors and reviewers each operator launched in it.

What the editors' and the doc reviewer's replies give is read by the fixed
forms of `reports`. A report of an editor that has not finished, a
`Review` section that gives a place as standing, an open `question` ticket
filed on the change, and the accepted gate outputs the change writes go to
one ticket analyst, which judges them and sends the editors what it keeps.
A report that analyst was launched after leaves nothing more.

A change with a doc editor passes its review once the latest reply of its
doc reviewer opens with `no finding stands` and follows each editor's last
report. A reply that gives findings brings a new doc editor for the
findings on documents and a new code editor for those on `.py` files, and
the command sends that reviewer their agent ids.

A step of a change that the command cannot place holds that change alone,
until the coordinator rules it with one of the choices the step gives
(`directives.ruled`)."""

from pathlib import Path
from typing import Literal

from operating import briefs, merging
from operating.directives import Directive, Ruling, named, numbers, ruled
from operating.reports import finding_paths, finished, no_finding, standing
from operating.roles import EDITORS, Purpose, Role, analyst_subject
from operating.state import Agent, State, Ticket
from operating.steps import Bash, Launch, Send, Step, repeated, sent, undecided
from operating.tracker import COORDINATOR, closed, log, worktree
from ticketing.vocabulary import Domain, Kind, Status


PROSE_IN_CODE = ".py"
"""The suffix of the files a doc reviewer's finding on prose in code falls
on, which a code editor fixes."""


def scope(state: State) -> set[str]:
    """The tickets the operators release and take changes among: the
    session's, those the coordinator names to the operator `me`, and each `change` one of those
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
    operator takes ahead of the others."""
    out: set[str] = set()
    for t in state.tickets.values():
        if t.kind is Kind.INTERFERENCE and t.status is Status.BLOCKED and t.log:
            note = t.log[-1].note
            if note.startswith("change "):
                out.add(note.split()[1].rstrip(":,;"))
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
                            "taking: the user ruled, to merge", state.me))
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
    """A message that tells an agent at work on a change that no operator
    carries any more, or that another holder carries, to end."""
    for a in state.agents:
        if not a.pending or a.agent_id is None:
            continue
        number = a.subject.partition(":")[2] if a.role is Role.TICKET_ANALYST else a.subject
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


def own_worktree(state: State, a: Agent) -> Path:
    """The worktree the harness makes for an agent launched with
    `isolation: "worktree"`."""
    return state.main_tree / ".claude" / "worktrees" / f"agent-{a.agent_id}"


def in_worktree(state: State, a: Agent, w: Path) -> bool:
    return own_worktree(state, a) == w or str(w) in a.brief


def change_editors(t: Ticket) -> tuple[Role, ...] | Send:
    """The editors of the change `t`, those its `editors` field gives; a
    change whose ticket gives none is undecided."""
    if t.editors is None:
        return undecided(f"change {t.number} gives no `editors` field")
    return t.editors

def carry(state: State, t: Ticket) -> Step | None:
    """The next step on the change `t` the operator holds, or None where it
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
        for a in reversed(launched):
            if own_worktree(state, a) in state.worktrees:
                return Bash(log(t.number, Status.ASSIGNED, Status.ASSIGNED,
                                f"worktree {own_worktree(state, a)}", state.me))
        if any(a.pending for a in launched):
            return None
        taken = max((ln.time for ln in t.log if ln.status is Status.ASSIGNED), default=0.0)
        tried = sum(a.launched > taken for a in launched)
        if tried >= 2:
            choice = ruled(state, f"change {t.number} has no worktree after {tried} first editors",
                           {Ruling.AGAIN: "launch another first editor"})
            if isinstance(choice, Send):
                return choice
        first = next(r for r in EDITORS if r in editors)
        return Launch(first, t.number, briefs.editor(
            first, t.number, len(editors) > 1, None, state.scratch / t.number, state.me),
            worktree=True, model=t.model(first))
    here = [a for a in launched if in_worktree(state, a, w)]
    for role in (r for r in EDITORS if r in editors):
        if not any(a.role is role for a in here):
            return Launch(role, t.number, briefs.editor(
                role, t.number, len(editors) > 1, w, state.scratch / t.number, state.me),
                model=t.model(role))
    if any(a.pending for a in here):
        return None
    latest = {a.role: a for a in here}
    if (step := leftover(state, t, w, list(latest.values()), agents)) is not False:
        return step
    if Role.DOC_EDITOR in editors and (
            step := doc_review(state, t, w, here, agents)) is not False:
        return step
    return merging.merge_steps(state, t, w, list(latest.values()))


def leftover(state: State, t: Ticket, w: Path, latest: list[Agent],
             agents: list[Agent]) -> Step | None | Literal[False]:
    """The step on what the editors leave, or False where they leave
    nothing. A report a ticket analyst was launched after leaves nothing
    more: that analyst judged it, and sent the editor what it kept."""
    analysts = [a for a in agents if a.role is Role.TICKET_ANALYST]
    if any(a.pending for a in analysts):
        return None
    judged = max((a.launched for a in analysts), default=0.0)
    needing = [a for a in latest if (not finished(a) or standing(a))
               and (r := a.last_report) is not None and r.time > judged]
    questions = [q for q in state.tickets.values() if q.kind is Kind.QUESTION
                 and q.domain is Domain.CHANGE and q.subject == t.number
                 and q.status in (Status.OPEN, Status.ASSIGNED)]
    reported = max((r.time for a in latest if (r := a.last_report) is not None), default=0.0)
    gate = list(state.gate_outputs.get(w, ())) if reported > judged else []
    if not needing and not questions and not gate:
        return False
    if questions and not needing and not gate and judged > max(q.filed for q in questions):
        choice = ruled(state, f"ticket analyst {analysts[-1].agent_id} returned on change "
                              f"{t.number}, and its question tickets stand open",
                       {Ruling.MERGE: "go on to the merge; the close of the change closes them",
                        Ruling.AGAIN: "launch another ticket analyst on them"})
        if isinstance(choice, Send):
            return choice
        if choice is Ruling.MERGE:
            return False
    reports = [(a.agent_id or "", r.text) for a in needing if (r := a.last_report) is not None]
    return Launch(Role.TICKET_ANALYST, analyst_subject(Purpose.CHANGE, t.number), briefs.findings(
        t.number, w, reports, [q.number for q in questions], gate,
        [a.agent_id or "" for a in latest], state.me))


def doc_review(state: State, t: Ticket, w: Path, here: list[Agent],
               agents: list[Agent]) -> Step | None | Literal[False]:
    """The step of the review of the change's documents, or False where it
    has passed."""
    reviewers = [a for a in agents if a.role is Role.DOC_REVIEWER]
    if not reviewers:
        return Launch(Role.DOC_REVIEWER, t.number, briefs.doc_review(
            t.number, w, [(a.role, a.agent_id or "") for a in here], state.me))
    r = reviewers[-1]
    if r.pending:
        return None
    reply = r.last_report
    last_edit = max((rep.time for a in here if (rep := a.last_report) is not None), default=0.0)
    if reply is not None and no_finding(r) and reply.time >= last_edit:
        return False
    since = reply.time if reply is not None else r.launched
    paths = finding_paths(r)
    if not paths:
        return review_ruled(state, t, w, here, f"the reply of doc reviewer {r.agent_id} on "
                                               f"change {t.number} gives no finding in the form "
                                               f"the command reads")
    code = [p for p in paths if p.endswith(PROSE_IN_CODE)]
    needed = ([Role.DOC_EDITOR] if len(code) < len(paths) else []) + (
        [Role.CODE_EDITOR] if code else [])
    fixers = [a for a in here if a.role in needed and a.launched > since]
    for role in needed:
        if not any(a.role is role for a in fixers):
            return Launch(role, t.number, briefs.review_fix(
                role, t.number, w, r.agent_id or "", code if role is Role.CODE_EDITOR else [],
                state.scratch / t.number, state.me), model=t.model(role))
    for f in fixers:
        message = briefs.new_editor(f.agent_id or "")
        if r.agent_id and not sent(state, r.agent_id, message):
            return Send(r.agent_id, message)
    return review_ruled(state, t, w, here, f"doc reviewer {r.agent_id} of change {t.number} has "
                                           f"not replied since its editors ended")


def review_ruled(state: State, t: Ticket, w: Path, here: list[Agent],
                 what: str) -> Step | Literal[False]:
    """The step on a review held for `what`, by the coordinator's ruling:
    False where the review passes."""
    choice = ruled(state, what, {Ruling.PASSES: "the review passes",
                                 Ruling.AGAIN: "launch another doc reviewer"})
    if isinstance(choice, Send):
        return choice
    if choice is Ruling.PASSES:
        return False
    return Launch(Role.DOC_REVIEWER, t.number, briefs.doc_review(
        t.number, w, [(a.role, a.agent_id or "") for a in here], state.me))


def step(state: State) -> Step | None:
    """The next step of the changes: a message to an agent on a change no
    longer carried, a take, then a step of each change the operator
    holds."""
    if (s := give_up(state)) is not None:
        return s
    if (s := take(state)) is not None:
        return s
    for t in held(state):
        if (s := carry(state, t)) is not None and not repeated(s, state):
            return s
    return None
