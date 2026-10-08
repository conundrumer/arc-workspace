"""The ticket analysts the operator launches on open tickets, and the
decisions for the user it sends the coordinator.

The operator takes each `request` and `bug` from its first ticket analyst
on: once a ticket stands in the list `file_ticket.py to-settle` prints,
the command launches a ticket analyst with it, leaving out each ticket on a
task whose solver pipeline has yet to launch its own ticket analyst, which
`passes` gives that ticket. A ticket goes to no second analyst while one
runs on it, nor again once one returned, until the coordinator writes a line
in its log after that analyst's launch, as where it records a ruling of the
user or the user's later words on it. A ticket analyst that runs on the
ticket gets that line by message, and then counts as given it. A ticket
other than a `change` that stands under `tickets/blocked/` or
`tickets/closed/` with such a line after the line that moved it there
moves back to `tickets/open/` first.

A decision for the user reaches the coordinator once, by one of two
messages. Where a ticket analyst's reply ends with the part for the
coordinator (`reports.FOR_COORDINATOR`), the command sends that part,
read back by the analyst's agent id and the reply's time. Otherwise, the
decision is the note of the line that moved a ticket into
`tickets/blocked/` waiting on the user: the command sends it once that
line is written, where an operator wrote it, or a ticket analyst an
operator launched that has replied with no such part, and reads back that
it was sent by the ticket's number and that line's time in the message.
So a decision is sent by a later operator where the one before it ended
before it sent it."""

from operating import briefs
from operating.reports import for_coordinator as analyst_part
from operating.passes import awaits_analyst
from operating.roles import Purpose, Role, analyst_subject, joined
from operating.state import LogLine, State, Ticket
from ticketing.vocabulary import Domain, Kind, Status
from operating.steps import COORDINATOR, DECISION, Bash, Launch, Send, Step, sent
from operating.tracker import AGENT, blocked_on_user, coordinator_line, coordinator_lines, log


GIVEN = (Purpose.SETTLE, Purpose.PASS)
"""The purposes of the ticket analysts that tickets are given to."""


def given(state: State, number: str) -> bool:
    """Whether a ticket analyst runs on `number`, or one was launched with
    it, or sent it, after the coordinator's last line on it."""
    t = state.tickets[number]
    last = coordinator_lines(t.log)[-1:]
    return any(number in nums and (
        a.pending or a.launched > coordinator_line(t) or (
            a.agent_id is not None and bool(last)
            and sent(state, a.agent_id, briefs.later_line(number, last[0].time, last[0].note))))
        for a, purpose, nums in state.analysts() if purpose in GIVEN)


def awaits_pipeline(state: State, number: str) -> bool:
    """Whether `number` is a ticket on a task whose pipeline has a pass
    with no ticket analyst launched after it."""
    t = state.tickets[number]
    if t.domain is not Domain.TASK:
        return False
    return awaits_analyst(state, t.subject)


REOPENED = (Status.BLOCKED, Status.CLOSED)
"""The statuses a ticket moves back to `tickets/open/` from on a line of
the coordinator's."""


def reopen(state: State) -> Step | None:
    """The move to `tickets/open/` of a ticket other than a `change` that
    stands under `tickets/blocked/` or `tickets/closed/` with a line of the
    coordinator's after the line that moved it there, citing that line. A
    `change` the user rules on comes back by a `Merge:` or a `Drafts to
    review:` line instead, and one under `tickets/open/` is taken as a
    fresh change."""
    for t in sorted(state.tickets.values(), key=lambda t: t.order):
        if t.status not in REOPENED or t.kind is Kind.CHANGE:
            continue
        run = len(t.log)
        while run > 0 and t.log[run - 1].status is t.status:
            run -= 1
        lines = coordinator_lines(t.log[run + 1:])
        if run < len(t.log) and lines:
            return Bash(log(t.number, Status.OPEN, t.status,
                            f"the coordinator's line of {lines[-1].time:.0f}: {lines[-1].note}",
                            None))
    return None


def later_lines(state: State) -> Step | None:
    """The message that gives a running ticket analyst each line the
    coordinator wrote, after the analyst's launch, on a ticket other than
    a draft that it was given."""
    for a, purpose, nums in state.analysts():
        if not a.pending or a.agent_id is None or purpose not in GIVEN:
            continue
        for n in nums:
            t = state.tickets.get(n)
            if t is None or t.status is Status.DRAFT:
                continue
            for ln in coordinator_lines(t.log):
                message = briefs.later_line(n, ln.time, ln.note)
                if ln.time > a.launched and not sent(state, a.agent_id, message):
                    return Send(a.agent_id, message)
    return None


def settle(state: State) -> Step | None:
    numbers = [n for n in state.to_settle
               if not given(state, n) and not awaits_pipeline(state, n)]
    if not numbers:
        return None
    return Launch(Role.TICKET_ANALYST, analyst_subject(Purpose.SETTLE, joined(numbers)),
                  briefs.settle(numbers, state.me))


def unsettled(state: State) -> list[str]:
    """The tickets the list holds that an analyst returned on and left
    open, for the final reply."""
    return [n for n in state.to_settle if given(state, n)
            and not any(n in nums and a.pending for a, _, nums in state.analysts())]


def decision_key(number: str, time: float) -> str:
    return f"ticket {number}, logged at {time:.0f}"


def carried(state: State, t: Ticket, line: LogLine) -> bool:
    """Whether the reply of the ticket analyst that wrote `line` on `t`
    carries its decision to the coordinator: the analyst still runs, or
    its reply after `line` has a part for the coordinator."""
    return any(a.pending or (
        (r := a.last_report) is not None and r.time >= line.time
        and analyst_part(a) is not None)
        for a, _, nums in state.analysts()
        if a.agent_id == line.agent_id or (line.agent_id is None and t.number in nums))


def decisions(state: State) -> Step | None:
    known = {a.agent_id for a in state.agents if a.agent_id} | set(state.operators)
    briefed = {n for _, _, nums in state.analysts() for n in nums}
    for t in sorted(state.tickets.values(), key=lambda t: t.order):
        line = blocked_on_user(t)
        if line is None:
            continue
        by_ours = line.agent_id in known or (
            line.agent in (Role.TICKET_ANALYST.value, AGENT) and t.number in briefed)
        key = decision_key(t.number, line.time)
        step = Send(COORDINATOR, f"{DECISION} {key}: {line.note}")
        if by_ours and not carried(state, t, line) and not sent(state, step.to, step.message, key):
            return step
    return None


def for_coordinator_key(agent: str, time: float) -> str:
    return f"ticket analyst {agent}, reply at {time:.0f}"


def for_coordinator(state: State) -> Step | None:
    """The part of a ticket analyst's reply for the coordinator, sent once,
    read back by the analyst's agent id and its reply's time."""
    for a in state.agents_of(Role.TICKET_ANALYST):
        part = analyst_part(a)
        r = a.last_report
        if part is None or r is None or a.agent_id is None:
            continue
        key = for_coordinator_key(a.agent_id, r.time)
        step = Send(COORDINATOR, f"{DECISION} {key}:\n{part}")
        if not sent(state, step.to, step.message, key):
            return step
    return None
