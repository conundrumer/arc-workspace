"""The order in which the command takes the procedures' steps, its waits,
and the operator's final reply.

One operator carries the session's work at a time: an operator for which a
later one of the session runs ends at once, and the later one carries on
from the state, so two operators never act on one ticket. The coordinator's
lines, and the other agents' messages other than the alerts `alerts` acts
on for the operator that carries the work on, give steps only to the
operator they reached, so the work a line to an earlier operator left
unfinished reaches a later one only where the coordinator gives it again
(`passes.every`);
a `Decision:` line that rules a held step holds for every operator
(`directives`), and the items for the coordinator of a ticket analyst's
reply go to the final reply of the operator that carries that reply
(`steps.carrier`). An operator past its context bound ends at once
too, and once its work is no longer open, the operator the coordinator
launches next takes up, through `changes.release`, the changes of the
session and of the tickets named to it.

The steps come in this order: the coordinator's lines in no form the
command reads, each given back to the coordinator once; the monitor's
alerts; the request to a ticket analyst on a held step to give its decision
again; the decisions for the user, and the items of each ticket analyst's
reply for the coordinator; at launch, the release of tickets;
the move back to `tickets/open/` of the tickets the coordinator wrote on
under `tickets/blocked/` or `tickets/closed/`; the coordinator's later
lines to the ticket analysts that run on their tickets; the ticket
analysts on open tickets; the review
of drafts; the changes; the solver pipelines; After a batch. A step that
is a message an operator already sent is passed over, and so are an
undecided step an operator already handled (`steps.repeated`) and a step
an `Override: pass over` ruling passed over (`directives.passed`).

Where no step is ready and an agent the operator launched or last
resumed itself runs, other than one a notification said has not reported
yet, the command has the agent start its wait in the background and end
its turn, or end its turn where that wait already runs, since the agent's report wakes it; once
`steps.WAIT_CAP` waits in a row found nothing, the agent ends its turn
with no new wait. Where none runs, and an agent of an operator runs or a
ticket of the operators' waits on another holder whose work is open, the
agent runs the command again, which blocks in the foreground first. Otherwise the agent
stops its wait where one runs, then gives its final reply."""

from collections.abc import Callable

from controlled_markdown import mctx
from operations import alerts, batches, changes, decisions, drafts, passes, triage
from operations.directives import (
    NUMBER,
    TASK,
    Directive,
    Line,
    Pipeline,
    lines,
    passed,
    unread,
)
from operations.roles import Role, description
from operations.state import State, Ticket
from ticketing.vocabulary import Status
from operations.steps import (
    WAIT_CAP,
    WAIT_SECONDS,
    Bash,
    EndTurn,
    Launch,
    Poll,
    Reply,
    Step,
    StopWait,
    Undecided,
    Wait,
    bash_calls,
    decision_key,
    failure,
    is_wait,
    key,
    nested,
    only_command,
    repeated,
    unread_line,
)

ENDED_FOR_CONTEXT = "ended for my context"
GIVEN_AGAIN = "a line below that stands unfinished reaches it only where it is given to it again"


def first(state: State, *procedures: Callable[[State], Step | None]) -> Step | None:
    """The first step of `procedures` that is ready (`placed`)."""
    for procedure in procedures:
        s, _ = placed(state, procedure)
        if s is not None:
            return s
    return None


def placed(state: State, procedure: Callable[[State], Step | None]
           ) -> tuple[Step | None, Undecided | None]:
    """The step of `procedure` that is ready, where an undecided step is the
    launch of a ticket analyst on it (`decisions`), and the undecided step
    the procedure waits on, where it waits on one. A procedure whose step
    failed, as `refused` gives, or whose step a ruling passed over, waits
    until the state changes. A step passed over or failed is undecided,
    once, as one its procedure waits on, other than the launch of an
    analyst on an undecided step: where the line that passed it over
    answered that step, or that launch failed, the step stays held."""
    s = procedure(state)
    while s is not None:
        if repeated(s, state):
            return None, s if isinstance(s, Undecided) else None
        on_step = isinstance(s, Undecided)
        if isinstance(s, Undecided):
            s = decisions.launch(state, s)
        if (line := passed(s, state)) is not None:
            s = None if on_step else Undecided(mctx(
                "step {key}, which the line `{line}` passed over, holds up its "
                "procedure").format(key=key(s), line=line))
            continue
        if (failed := refused(state, s)) is None:
            return s, None
        s = None if on_step else failed
    return None, None


def refused(state: State, step: Step) -> Undecided | None:
    """The undecided step on `step`, where the last call of `step` by
    `state.me` failed and no report reached an
    operator since, as where the harness or the permission classifier
    denied it, so that a denied call is not printed again and again."""
    match step:
        case Launch(role, subject):
            what = description(role, subject)
            same = [c for c in state.calls if c.operator == state.me
                    and c.tool == "Agent" and c.input.get("description") == what]
        case Bash(command):
            what = command
            same = [c for c in bash_calls(state, command)
                    if c.operator == state.me and c.result is not None]
        case _:
            return None
    if not same or not same[-1].error:
        return None
    last = same[-1]
    if any(r.time > last.time for a in state.agents for r in a.reports):
        return None
    return Undecided(mctx("the call `{what}` failed: {why}").format(what=what,
                                                                     why=failure(last)))


def unread_lines(state: State) -> Step | None:
    for ln in unread(state):
        s = unread_line(ln.text)
        if not repeated(s, state):
            return s
    return None


def launching(state: State) -> Step | None:
    """The release of tickets, before the operator's first launch."""
    if any(c.operator == state.me and c.tool == "Agent" for c in state.calls):
        return None
    return changes.release(state)


def pipelines(state: State) -> Step | None:
    return passes.step(state)[0]


def elsewhere(state: State) -> list[str]:
    """The tickets of the operators' scope that another holder whose work
    is open holds."""
    return [n for n in sorted(changes.scope(state))
            if (t := state.tickets.get(n)) is not None and t.status is Status.ASSIGNED
            and t.holder not in (None, state.me) and t.holder in state.open_holders]


EARLY: tuple[Callable[[State], Step | None], ...] = (
    unread_lines, alerts.step, decisions.asks, triage.decisions, triage.for_coordinator,
    triage.unfinished)
LATE: tuple[Callable[[State], Step | None], ...] = (
    launching, triage.reopen, triage.later_lines, triage.settle, drafts.step, changes.step,
    pipelines, batches.step)
PROCEDURES = EARLY + LATE


def next_step(state: State) -> Step:
    mine = state.operators.index(state.me) if state.me in state.operators else -1
    later = [o for o in state.operators[mine + 1:] if o in state.open_operators]
    if later:
        return Reply(mctx("Operator {operator} carries the work on, from the state; "
                          "{given}.").format(operator=later[-1], given=GIVEN_AGAIN)
                     + "\n" + "\n".join(reply_lines(state)))
    s = first(state, *EARLY)
    if s is not None:
        return s
    if state.past_bound:
        return Reply(mctx("I {ended}; the next operator takes up the work from the state, "
                          "and {given}.").format(ended=ENDED_FOR_CONTEXT, given=GIVEN_AGAIN)
                     + "\n" + "\n".join(reply_lines(state)))
    s = first(state, *LATE)
    if s is not None:
        return s
    mine = [a for a in state.agents if a.pending and a.operator == state.me and a.notifies]
    if mine and not all(a.still_running for a in mine):
        if state.wait_task:
            return EndTurn()
        return EndTurn(capped=True) if idle_waits(state) >= WAIT_CAP else Wait()
    if any(a.pending for a in state.agents) or elsewhere(state):
        return Poll()
    if state.wait_task:
        return StopWait(state.wait_task)
    return Reply(final(state))


def idle_waits(state: State) -> int:
    """How many of the operator's waits in a row started with no message,
    no report of its agents and no other call of its between them. Waits
    that start within half of `WAIT_SECONDS` of the one counted before them
    ended together, and count as one."""
    own = [c for c in state.calls if c.operator == state.me]
    waits = [c for c in own
             if c.tool == "Bash" and is_wait(str(c.input.get("command", "")), state.me)]
    events = [m.time for m in state.received]
    events += [r.time for a in state.agents if a.operator == state.me for r in a.reports]
    events += [c.time for c in own if not (c.tool == "Bash" and only_command(
        str(c.input.get("command", "")), state.me))]
    since = max(events, default=0.0)
    count, last = 0, -WAIT_SECONDS
    for c in waits:
        if c.time > since and c.time - last >= WAIT_SECONDS / 2:
            count, last = count + 1, c.time
    return count


def pipeline_state(o: passes.Outcome | None) -> str | None:
    """Why a pipeline is unfinished, or None where it ran to its end."""
    if o is None:
        return "its pipeline has not started"
    if not o.ended:
        return "its pipeline runs"
    return f"its pipeline stopped: {o.stopped}" if o.stopped else None


def stands_under(t: Ticket) -> str:
    return f"stands under `tickets/{t.status.value}/`"


def line_state(state: State, ln: Line, outcomes: list[tuple[Pipeline, passes.Outcome]]) -> str:
    """A line of the coordinator's to the operator, as done or as
    unfinished with its reasons."""
    numbers = NUMBER.findall(ln.rest)
    reasons: list[str] = []
    match ln.kind:
        case Directive.SOLVE:
            by_task = {p.task: o for p, o in outcomes}
            reasons = [f"{m['task']}: {r}" for m in TASK.finditer(ln.rest)
                       if (r := pipeline_state(by_task.get(m["task"]))) is not None]
        case Directive.QUEUE:
            own = [(p, o) for p, o in outcomes if p.since == ln.message.time]
            if not own:
                own = [(p, o) for p, o in outcomes if p.since < ln.message.time and p.queued]
            reasons = [f"{p.task or 'the queue'}: {r}" for p, o in own
                       if (r := pipeline_state(o)) is not None]
        case Directive.DRAFTS:
            under = {t.number for t in drafts.unended(state)}
            reasons = [draft_stands(n) for n in numbers if n in under]
        case Directive.NAMED:
            reasons = [f"ticket {n} {stands_under(t)}" for n in numbers
                       if (t := state.tickets.get(n)) is not None
                       and t.status in (Status.OPEN, Status.ASSIGNED)]
        case Directive.MERGED:
            if not any(a.launched > ln.message.time for a in state.agents_of(Role.BATCH_PROFILE)):
                reasons = ["After a batch has not run since it was given"]
        case Directive.MERGE:
            reasons = [f"change {n} {stands_under(t)}" for n in numbers
                       if (t := state.tickets.get(n)) is not None and t.status is not Status.CLOSED]
        case Directive.OPEN:
            reasons = [settled_open(n) for n in triage.unsettled(state)]
        case None:
            reasons = ["it is in no form the command reads, and went to the coordinator"]
        case _:
            pass
    head = f"- `{ln.text}`: "
    return head + ("done" if not reasons else "unfinished: " + "; ".join(reasons))


def draft_stands(number: str) -> str:
    return mctx("draft {number} stands under `tickets/draft/`").format(number=number)


def settled_open(number: str) -> str:
    return mctx("ticket {number} stands open after its ticket analyst returned").format(
        number=number)


def sentence(clause: str) -> str:
    return clause[:1].upper() + clause[1:]


def line_states(state: State) -> list[str]:
    """Each line of the operator's brief and of the coordinator's later
    messages to it, as done or as unfinished with its reasons."""
    _, outcomes = passes.step(state)
    return [line_state(state, ln, outcomes) for ln in lines(state)]


def reply_lines(state: State) -> list[str]:
    """The lines each reply of the operator that ends it gives: its lines
    (`line_states`), the items for the coordinator it carries
    (`triage.told`), and the held steps no decision reached
    (`decisions.undecided`, `decisions.failed`)."""
    return [*line_states(state), *triage.told(state),
            *decisions.undecided(state, holding(state)), *decisions.failed(state)]


def holding(state: State) -> set[str]:
    """The decision keys of the undecided steps the procedures wait on, as
    `placed` gives them."""
    return {decision_key(u.what) for procedure in PROCEDURES
            if (u := placed(state, procedure)[1]) is not None}


def stands(state: State, head: str, step: Step | None) -> tuple[str, bool]:
    """The line of the final reply on a draft or a change that stands, by
    `head`, with its step: where that step is undecided and went to a
    ticket analyst, the line gives that step, which its procedure waits
    on, and the second value holds."""
    if isinstance(step, Undecided) and repeated(step, state):
        return head + mctx(": it waits on a decision of the step: {what}").format(
            what=step.what), True
    return head, False


def final(state: State) -> str:
    """The operator's final reply: what stands at its end."""
    out = reply_lines(state)
    for n, deps in changes.waiting(state):
        waited = ", ".join(deps)
        out.append("- " + mctx("Change {n} not taken: it waits for {waited}").format(
            n=n, waited=waited))
    standing = [stands(state, f"- {sentence(draft_stands(t.number))}",
                       drafts.draft_step(state, t, [], [])) for t in drafts.unended(state)]
    standing += [(f"- {sentence(settled_open(n))}", False)
                 for n in triage.unsettled(state)]
    standing += [stands(state, "- " + mctx("Change {n} stays under `tickets/assigned/`").format(
                            n=t.number),
                        changes.carry(state, t)) for t in changes.held(state)]
    out += [line for line, _ in standing]
    head = (mctx("Done: no procedure has a step left other than those that wait on a "
                 "decision, as the lines below give.")
            if any(asked for _, asked in standing)
            else mctx("Done: no procedure has a step left."))
    out.insert(0, head)
    for a in state.agents_of(Role.AFTER_MERGE):
        if a.operator == state.me and (r := a.last_report) is not None:
            out.append("- " + mctx("The checks after the merge of change {number}, by "
                                   "{agent}:").format(number=a.subject, agent=a.agent_id))
            out += nested(r.text)
    return "\n".join(out)
