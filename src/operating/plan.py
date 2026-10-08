"""The order in which the command takes the procedures' steps, its waits,
and the operator's final reply.

One operator carries the session's work at a time: an operator for which a
later one of the session runs ends at once, and the later one carries on
from the state, so two operators never act on one ticket. The coordinator's
lines and the other agents' messages give steps only to the operator they
reached, so the work a line to an earlier operator left unfinished reaches
a later one only where the coordinator gives it again. An operator past
its context bound ends at once too, and the operator the coordinator
launches next takes up its changes once its work is no longer open, as
`changes.release` gives.

The steps come in this order: the coordinator's lines in no form the
command reads, each given back to the coordinator once; the supervisor's
alerts; the decisions for the user, and the part of each ticket analyst's
reply for the coordinator; at launch, the release of tickets;
the move back to `tickets/open/` of the tickets the coordinator wrote on
under `tickets/blocked/` or `tickets/closed/`; the coordinator's later
lines to the ticket analysts that run on their tickets; the ticket
analysts on open tickets; the review
of drafts; the changes; the solver pipelines; After a batch. A step that
is a message an operator already sent is passed over, and so is a step an
operator passed over by `operate.py pass-over`.

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

from operating import alerts, batches, changes, drafts, passes, settling
from operating.directives import (
    NUMBER,
    TASK,
    Directive,
    Line,
    Pipeline,
    lines,
    unread,
)
from operating.roles import Role, description
from operating.state import State, Ticket
from ticketing.vocabulary import Status
from operating.steps import (
    COORDINATOR,
    UNDECIDED,
    WAIT_CAP,
    WAIT_SECONDS,
    Again,
    Bash,
    EndTurn,
    Launch,
    Reply,
    Send,
    Step,
    Stop,
    Wait,
    bash_calls,
    is_wait,
    key,
    only_command,
    passed,
    repeated,
    undecided,
)

ENDED_FOR_CONTEXT = "ended for my context"
GIVEN_AGAIN = "a line below that stands unfinished reaches it only where it is given to it again"


def first(state: State, *procedures: Callable[[State], Step | None]) -> Step | None:
    """The first step of `procedures` that is ready. A procedure whose step
    failed, as `refused` gives, or whose step an operator passed over,
    waits until the state changes, and the procedures after it go on. A
    step passed over goes to the coordinator, once, as one its procedure
    waits on, other than a step that gives the coordinator a step as
    undecided, which the line that passed it over answered."""
    for procedure in procedures:
        s = procedure(state)
        if s is None or repeated(s, state):
            continue
        if (line := passed(s, state)) is not None:
            if isinstance(s, Send) and s.to == COORDINATOR and s.message.startswith(UNDECIDED):
                continue
            held = undecided(f"step {key(s)}, which the line `{line}` passed over, holds up "
                             f"its procedure")
            if not repeated(held, state):
                return held
            continue
        if (failed := refused(state, s)) is None:
            return s
        if not repeated(failed, state):
            return failed
    return None


def refused(state: State, step: Step) -> Step | None:
    """The step that gives the coordinator `step` as undecided, where the
    operator's last call of `step` failed and no report reached an
    operator since, as where the harness or the permission classifier
    denied it, so that a denied call is not printed again and again."""
    match step:
        case Launch(role, subject):
            what = description(role, subject)
            same = [c for c in state.calls if c.tool == "Agent"
                    and c.input.get("description") == what]
        case Bash(command):
            what = command
            same = [c for c in bash_calls(state, command) if c.result is not None]
        case _:
            return None
    if not same or not same[-1].error:
        return None
    last = same[-1]
    if any(r.time > last.time for a in state.agents for r in a.reports):
        return None
    reason = (last.result or "").strip().splitlines()
    return undecided(f"the call `{what}` failed: {reason[0] if reason else 'no result text'}")


def unread_lines(state: State) -> Step | None:
    for ln in unread(state):
        s = undecided(f"a line of the coordinator's in no form the command reads: {ln.text}")
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


def next_step(state: State) -> Step:
    mine = state.operators.index(state.me) if state.me in state.operators else -1
    later = [o for o in state.operators[mine + 1:] if o in state.open_operators]
    if later:
        return Reply(f"Operator {later[-1]} carries the work on, from the state; "
                     f"{GIVEN_AGAIN}.\n" + "\n".join(line_states(state)))
    s = first(state, unread_lines, alerts.step, settling.decisions, settling.for_coordinator)
    if s is not None:
        return s
    if state.past_bound:
        return Reply(f"I {ENDED_FOR_CONTEXT}; the next operator takes up the work from the "
                     f"state, and {GIVEN_AGAIN}.\n" + "\n".join(line_states(state)))
    s = first(state, launching, settling.reopen, settling.later_lines, settling.settle,
              drafts.step, changes.step, pipelines, batches.step)
    if s is not None:
        return s
    mine = [a for a in state.agents if a.pending and a.operator == state.me and a.notifies]
    if mine and not all(a.still_running for a in mine):
        on = ", ".join(sorted(a.agent_id or a.role.value for a in mine))
        if state.wait_task:
            return EndTurn(on)
        return EndTurn(on, capped=True) if idle_waits(state) >= WAIT_CAP else Wait(on)
    held = sorted(a.agent_id or a.role.value for a in state.agents if a.pending) + elsewhere(state)
    if held:
        return Again(", ".join(held))
    if state.wait_task:
        return Stop(state.wait_task)
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
            reasons = [f"draft {n} stands under `tickets/draft/`" for n in numbers if n in under]
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
            reasons = [f"ticket {n} stands open after its ticket analyst returned"
                       for n in settling.unsettled(state)]
        case None:
            reasons = ["it is in no form the command reads, and went to the coordinator"]
        case _:
            pass
    head = f"- `{ln.text}`: "
    return head + ("done" if not reasons else "unfinished: " + "; ".join(reasons))


def line_states(state: State) -> list[str]:
    """Each line of the operator's brief and of the coordinator's later
    messages to it, as done or as unfinished with its reasons."""
    _, outcomes = passes.step(state)
    return [line_state(state, ln, outcomes) for ln in lines(state)]


def final(state: State) -> str:
    """The operator's final reply: what stands at its end."""
    out = ["Done: no procedure has a step left.", *line_states(state)]
    for n, deps in changes.waiting(state):
        out.append(f"- Change {n} not taken: it waits for {', '.join(deps)}")
    for t in drafts.unended(state):
        out.append(f"- Draft {t.number} stands under `tickets/draft/`")
    for n in settling.unsettled(state):
        out.append(f"- Ticket {n} stands open after its ticket analyst returned")
    for t in changes.held(state):
        out.append(f"- Change {t.number} stays under `tickets/assigned/`")
    for a in state.agents_of(Role.AFTER_MERGE):
        if a.operator == state.me and (r := a.last_report) is not None:
            out.append(f"- The checks after the merge of change {a.subject}, by {a.agent_id}:")
            out += [f"    {line}" for line in r.text.strip().splitlines()]
    return "\n".join(out)
