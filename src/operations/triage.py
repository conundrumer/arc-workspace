"""The ticket analysts the operator launches on open tickets, and the
labeled items of their replies for the coordinator.

The operator takes each `request` and `bug` from its first ticket analyst
on: once a ticket stands in the list `file_ticket.py to-settle` prints,
the command launches a ticket analyst with it, leaving out each ticket on a
task whose solver pipeline has yet to launch its own ticket analyst, which
`passes` gives that ticket. While a `Pause.` line stands
(`directives.paused`), it launches one only with the tickets of
`changes.through_pause`. A ticket goes to no second analyst while one
runs on it, nor again once one returned, until the coordinator writes a line
in its log after that analyst's launch, as where it records a decision of the
user or the user's later words on it. A ticket analyst that runs on the
ticket gets that line by message, and then counts as given it. A ticket
other than a `change` that stands under `tickets/blocked/` or
`tickets/closed/` with such a line after the line that moved it there
moves back to `tickets/open/` first.

The coordinator gets from a ticket analyst's reply only what goes to the
user. Where that reply ends with the part for the coordinator
(`reports.FOR_COORDINATOR`), the command reads the items of that part
labeled with their kind (`reports.LABELED`), in any case, markup or list
form:

- Its `decision:` items reach the coordinator once, as they arise, by a
  message that opens with `steps.DECISION`, read back by the analyst's
  agent id and the reply's time in any message to the coordinator.
- Its `tell:` items reach the coordinator together, in the final reply of
  the operator that carries that reply (`final_reply.carrier`).
- Its `unfinished:` items, and its items that open with a label with no
  colon after it (`reports.MISLABELED`), are a step the command cannot
  decide, which goes to a ticket analyst launched on it (`decisions`),
  other than where an operator already gave the coordinator those items
  with the reply's key, in any message (`handled.repeated`).

A part that holds no labeled item gives no step.

The reply of an analyst on such a step gives its `unfinished:` and
mislabeled items in that final reply instead, so that no step goes from one
such analyst to the next. The `unfinished:` items of an analyst on what a
change's editors leave go to the step that holds that change
(`changes.leftover`), and its `decision:` items go to the coordinator with
the line that rules that step.

Otherwise, a `decision:` item is the note of the line that moved a ticket
into `tickets/blocked/` waiting on the user: the command sends it as a
`decision:` item once that line is written, where an operator wrote it,
or a ticket analyst an operator launched that has replied with no such
item, and reads back that it was sent by the ticket's number and that
line's time in the message. So a decision is sent by a later operator
where the one before it ended before it sent it.

Where `idle_sessions.read_sessions` gives an idle session that holds a
ticket and no main session runs an agent (`file_ticket.py main --help`),
the session whose id `tickets/main-wanted` holds sends the coordinator once a `decision:` item that asks the user to pick
a main (`main_wanted`)."""

from controlled_markdown import mctx
from operations import briefs, changes, messages
from operations.reports import Label, items_of, mislabeled
from operations.passes import awaits_analyst
from operations.roles import Purpose, Role, analyst_subject, joined
from operations.state import Agent, LogLine, State, Ticket
from ticketing.vocabulary import SETTLED, Kind, Status
from operations.constants import COORDINATOR
from operations.directives import paused
from operations.final_reply import carrier, nested
from operations.handled import repeated, sent
from operations.steps import DECISION, Bash, Launch, Send, Step, Undecided
from operations.tracker import AGENT, blocked_on_user, coordinator_line, coordinator_lines, final_run, log


GIVEN = (Purpose.TRIAGE, Purpose.PASS)
"""The purposes of the ticket analysts that tickets are given to."""


def given(state: State, number: str) -> bool:
    """Whether a ticket analyst runs on `number`, or one was launched with
    it, or sent it, after the coordinator's last line on it."""
    t = state.tracker.tickets[number]
    last = coordinator_lines(t.log)[-1:]
    return any(number in nums and (
        a.pending or a.launched > coordinator_line(t) or (
            a.agent_id is not None and bool(last)
            and sent(state, a.agent_id, messages.later_line(number, last[0].time, last[0].note))))
        for a, purpose, nums in state.analysts() if purpose in GIVEN)


REOPENED = (Status.BLOCKED, Status.CLOSED)
"""The statuses a ticket moves back to `tickets/open/` from on a line of
the coordinator's."""


def reopen(state: State) -> Step | None:
    """The move to `tickets/open/` of a ticket other than a `change` that
    stands under `tickets/blocked/` or `tickets/closed/` with a line of the
    coordinator's after the line that moved it there, and after the last
    line since then whose note opens with a wait, citing that line. A
    `change` the user rules on comes back by a `Merge:` or a `Drafts to
    review:` line instead, and one under `tickets/open/` is taken as a
    fresh change."""
    for t in sorted(state.tracker.tickets.values(), key=lambda t: t.order):
        if t.status not in REOPENED or t.kind is Kind.CHANGE:
            continue
        run, wait = final_run(t)
        start = run if wait is None else wait
        lines = coordinator_lines(t.log[start + 1:])
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
            t = state.tracker.tickets.get(n)
            if t is None or t.status is Status.DRAFT:
                continue
            for ln in coordinator_lines(t.log):
                message = messages.later_line(n, ln.time, ln.note)
                if ln.time > a.launched and not sent(state, a.agent_id, message):
                    return Send(a.agent_id, message)
    return None


def settle(state: State) -> Step | None:
    admitted = changes.admits(state)
    passing = changes.through_pause(state) if paused(state) else None
    numbers = [n for n in state.computed.to_settle
               if not given(state, n) and not awaits_analyst(state, n)
               and admitted(n) and (passing is None or n in passing)]
    if not numbers:
        return None
    return Launch(Role.TICKET_ANALYST, analyst_subject(Purpose.TRIAGE, joined(numbers)),
                  briefs.settle(numbers, state.me), items=len(numbers))


def unsettled(state: State) -> list[str]:
    """The tickets the list holds that an analyst returned on and left
    open, for the final reply."""
    return [n for n in state.computed.to_settle if given(state, n)
            and not any(n in nums and a.pending for a, _, nums in state.analysts())]


def decision_key(number: str, time: float) -> str:
    return f"ticket {number}, logged at {time:.0f}"


def carried(state: State, t: Ticket, line: LogLine) -> bool:
    """Whether the reply of the ticket analyst that wrote `line` on `t`
    carries its decision to the coordinator: the analyst still runs, or
    its reply after `line` gives a `decision:` item."""
    return any(a.pending or (
        (r := a.last_report) is not None and r.time >= line.time
        and items_of(a, [Label.DECISION]) is not None)
        for a, _, nums in state.analysts()
        if a.agent_id == line.agent_id or (line.agent_id is None and t.number in nums))


def decisions(state: State) -> Step | None:
    known = {a.agent_id for a in state.transcripts.agents if a.agent_id} | set(state.operators)
    briefed = {n for _, _, nums in state.analysts() for n in nums}
    for t in sorted(state.tracker.tickets.values(), key=lambda t: t.order):
        line = blocked_on_user(t)
        if line is None:
            continue
        by_ours = line.agent_id in known or (
            line.agent in (Role.TICKET_ANALYST.value, AGENT) and t.number in briefed)
        key = decision_key(t.number, line.time)
        step = Send(COORDINATOR, labeled(key, mctx("- decision: {note}").format(note=line.note)))
        if by_ours and not carried(state, t, line) and not sent(state, step.to, step.message, key):
            return step
    return None


MAIN_WANTED = mctx("""
    - decision: no session in which an agent runs is the main session, so no agent acts on these tickets: {tickets}. Option: `uv run python scripts/file_ticket.py main <session id>`, with the id of the session the user picks.
    """)


def main_wanted(state: State) -> Step | None:
    """The message that asks the coordinator, once, to have the user pick a
    main session, where `tickets/main-wanted` holds the session's id."""
    if state.sessions.main_wanted is None or state.sessions.main_wanted[0] != state.session:
        return None
    stuck = [t.number for t in sorted(state.tracker.tickets.values(), key=lambda t: t.order)
             if t.session in state.sessions.idle_indexes and t.status not in SETTLED]
    key = f"main session, asked at {state.sessions.main_wanted[1]:.0f}"
    step = Send(COORDINATOR, labeled(key, MAIN_WANTED.format(tickets=", ".join(stuck))))
    return None if sent(state, step.to, step.message, key) else step


def labeled(key: str, body: str) -> str:
    """A message to the coordinator on `key`, with the items of `body`."""
    return mctx("{label} {key}:").format(label=DECISION, key=key) + "\n" + body


def for_coordinator_key(agent: str, time: float) -> str:
    return f"ticket analyst {agent}, reply at {time:.0f}"


def replied(state: State) -> list[tuple[Agent, Purpose, list[str], str]]:
    """Each ticket analyst that replied, with its purpose, the ticket
    numbers or the task its subject gives, and the key of its latest reply
    (`for_coordinator_key`)."""
    return [(a, purpose, nums, for_coordinator_key(a.agent_id, r.time))
            for a, purpose, nums in state.analysts()
            if a.agent_id is not None and (r := a.last_report) is not None]


def for_coordinator(state: State) -> Step | None:
    """The `decision:` items of the part of a ticket analyst's reply for the
    coordinator, in one message, sent once, read back by the analyst's
    agent id and its reply's time in any message to the coordinator. The
    items of an analyst on what a change's editors leave go with the step
    that holds that change, and the line that rules it
    (`changes.left_decision`)."""
    for a, purpose, nums, key in replied(state):
        part = items_of(a, [Label.DECISION])
        if part is None:
            continue
        if purpose is Purpose.CHANGE and (decision := changes.left_decision(a, nums[0])):
            part += "\n\n" + decision
        step = Send(COORDINATOR, labeled(key, part))
        if not sent(state, step.to, step.message, key):
            return step
    return None


def unfinished(state: State) -> Step | None:
    """The undecided step on the `unfinished:` items of the part of a
    ticket analyst's reply for the coordinator, with its items that open
    with a label with no colon after it, other than those of an analyst on
    a held step, which go to the final reply (`told`), and the
    `unfinished:` items of an analyst on what a change's editors leave."""
    for a, purpose, _, key in replied(state):
        if purpose is Purpose.STEP or items_of(a, list(Label)) is None:
            continue
        open_items = None if purpose is Purpose.CHANGE else items_of(a, [Label.UNFINISHED])
        items = [*([open_items] if open_items else []), *mislabeled(a)]
        if not items:
            continue
        text = "\n".join(items)
        s = Undecided(mctx("the part for the coordinator of {key} leaves these items:").format(
            key=key) + "\n" + text, (key, *(ln.strip() for ln in text.splitlines() if ln.strip())))
        if not repeated(s, state):
            return s
    return None


def told(state: State) -> list[str]:
    """The lines of the final reply of the operator `me` that give the
    coordinator the `tell:` items of each ticket analyst's reply that `me`
    carries (`final_reply.carrier`), and of the reply of an analyst on a held
    step, its `unfinished:` items and its items that open with a label with
    no colon after it."""
    out: list[str] = []
    for a, purpose, _, key in replied(state):
        r = a.last_report
        if r is None or carrier(state, a.operator, r.time) != state.me:
            continue
        on_step = purpose is Purpose.STEP
        part = items_of(a, [Label.TELL, Label.UNFINISHED] if on_step else [Label.TELL])
        items = [*([part] if part else []), *(mislabeled(a) if on_step else [])]
        if items:
            out.append(f"- {key}:")
            out += nested("\n".join(items))
    return out
