"""The ticket analysts the operator launches on untaken tickets, and the
labeled items of their replies for the coordinator.

The operator takes each `request` and `bug` from its first ticket analyst
on: once a ticket stands in the list `file_ticket.py to-settle` prints,
the command launches a ticket analyst with it, leaving out each ticket on a
task whose solver pipeline has yet to launch its own ticket analyst, which
`passes` gives that ticket. While an `Op scope: own.` line stands, or no
`Op scope:` line came (`directives.own_scope`), it launches one only with
the tickets of `taking.allowed` and of `taking.own_work`, and with those
of `taking.follow_ups` that `taking.judging` gives, whose brief has the
analyst settle each only where it judges that the session's line of work
needs it; and while an `Op pause.` line
stands (`directives.paused`), only with those of `taking.allowed`. A ticket
goes to no second analyst while one runs on it, nor again once one
returned, until the coordinator writes a line in its log after that analyst's launch, as where it records a decision of the
user or the user's later words on it, or the ticket moves from
`tickets/deferred/`, `tickets/blocked/` or `tickets/waiting/` into `tickets/reopened/` after it. A
ticket analyst that runs on the ticket gets the coordinator's line by
message, and then counts as given it. A ticket other than a `change` that
stands under `tickets/blocked/`, `tickets/waiting/` or `tickets/closed/` with such a line after the line that moved it there
moves to `tickets/reopened/` first. An analyst that no longer runs
and was launched before a ticket's last line of the form `taking.NOT_OWN`
counts as given that ticket no longer once `taking.scope_admits` admits
it.

The coordinator gets from a ticket analyst's reply only what goes to the
user. Where that reply ends with the part for the coordinator
(`reports.FOR_COORDINATOR`), the command reads the items of that part
labeled with their kind (`reports.LABELED`), in any case, markup or list
form:

- Its `decision:` items reach the coordinator once, as they arise, by a
  message that opens with `steps.DECISION`, read back by the analyst's
  agent id and the reply's time in any message to the coordinator.
- Its `tell:` items reach the coordinator together, in the final reply of
  the operator that gives that reply (`final_reply.carrier`).
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
from operations import briefs, changes, messages, taking
from operations.reports import Label, items_of, mislabeled
from operations.passes import awaits_analyst
from operations.roles import ANALYST_NAMES, Purpose, Role, analyst_subject, joined
from operations.state import Agent, LogLine, State, Ticket
from ticketing.vocabulary import SETTLED, Status
from operations.constants import COORDINATOR
from operations.final_reply import carrier, nested, replies_by_operator, session_operator
from operations.handled import repeated, sent
from operations.steps import Bash, Launch, Send, Step, Undecided, labeled
from operations.log_commands import AGENT, log
from operations.tracker import blocked_on_user, coordinator_lines, exits, final_run
from ticketing.exits import Exit, freed


GIVEN = (Purpose.TRIAGE, Purpose.PASS)
"""The purposes of the ticket analysts that tickets are given to."""


def given(state: State, number: str) -> bool:
    """An analyst launched before the event that freed `number`, and not
    sent that event's line, judged the ticket as it stood before it. An
    analyst that no longer runs and was launched before the last line of
    the form `taking.NOT_OWN` on it is not counted where
    `taking.scope_admits` admits it."""
    t = state.tracker.tickets[number]
    event = freed(t.log, t.kind, t.filed)
    line = event.line
    judged = max((ln.time for ln in t.log if taking.NOT_OWN_LINE.fullmatch(ln.note)), default=None)
    if judged is not None and not taking.scope_admits(state)(number):
        judged = None
    return any(number in nums and (judged is None or a.pending or a.launched > judged) and (
        a.pending or a.launched > event.time or (
            a.agent_id is not None and line is not None
            and sent(state, a.agent_id, messages.later_line(number, line.time, line.note))))
        for a, purpose, nums in state.analysts() if purpose in GIVEN)


def reopen(state: State) -> Step | None:
    """The move to `tickets/reopened/` of a ticket other than a `change` that
    stands under `tickets/blocked/`, `tickets/waiting/` or `tickets/closed/` with a line of the
    coordinator's after the line that moved it there, and after the last
    line since then whose note opens with a wait, citing that line. A
    `change` the user rules on comes back by an `Op merge:` or an `Op drafts to
    review:` line instead, and one that stands untaken is taken as a
    fresh change."""
    for t in sorted(state.tracker.tickets.values(), key=lambda t: t.order):
        if Exit.COORDINATOR_LINE not in exits(state, t).by:
            continue
        run, wait = final_run(t)
        start = run if wait is None else wait
        lines = coordinator_lines(t.log[start + 1:])
        if run < len(t.log) and lines:
            return Bash(log(t.number, Status.REOPENED, t.status,
                            f"the coordinator's line of {lines[-1].time:.0f}: {lines[-1].note}",
                            None), f"{t.number} reopen", occasion=str(lines[-1].time))
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
                    return Send(a.agent_id, message, f"{n} {ln.time}")
    return None


def unsettled_open(state: State) -> list[str]:
    """The tickets of the list that no analyst was given and no solver
    pipeline awaits."""
    return [n for n in state.computed.to_settle
            if not given(state, n) and not awaits_analyst(state, n)]


def selected(state: State) -> list[str]:
    """The tickets of `unsettled_open` that `taking.admits` and
    `taking.scope_admits` admit, and those `taking.judging` gives."""
    admitted = taking.admits(state)
    clear = taking.scope_admits(state)
    judge = taking.judging(state)
    return [n for n in unsettled_open(state) if (admitted(n) and clear(n)) or judge(n)]


def settle(state: State) -> Step | None:
    """The launch of a ticket analyst on the tickets of `selected`, which
    settles those `taking.scope_admits` does not admit only where it judges
    that the session's line of work needs them."""
    numbers = selected(state)
    if not numbers:
        return None
    clear = taking.scope_admits(state)
    return Launch(Role.TICKET_ANALYST, analyst_subject(Purpose.TRIAGE, joined(numbers)),
                  briefs.settle(numbers, [n for n in numbers if not clear(n)], state.me),
                  items=len(numbers),
                  occasion=str(max(state.tracker.tickets[n].last_time for n in numbers)))


def unsettled(state: State) -> list[str]:
    """The tickets the list holds that an analyst returned on and left
    open, for the final reply."""
    return [n for n in state.computed.to_settle if given(state, n)
            and not any(n in nums and a.pending for a, _, nums in state.analysts())]


def decision_key(number: str, time: float) -> str:
    return f"ticket {number}, logged at {time:.0f}"


def carried(state: State, t: Ticket, line: LogLine) -> bool:
    """Whether the reply of the ticket analyst that wrote `line` on `t`
    gives its decision to the coordinator: the analyst still runs, or
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
            line.agent in ANALYST_NAMES | {AGENT} and t.number in briefed)
        key = decision_key(t.number, line.time)
        step = Send(COORDINATOR, labeled(key, mctx("- decision: {note}").format(note=line.note)),
                    key)
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
             if t.session in state.sessions.idle and t.status not in SETTLED]
    key = f"main session, asked at {state.sessions.main_wanted[1]:.0f}"
    step = Send(COORDINATOR, labeled(key, MAIN_WANTED.format(tickets=", ".join(stuck))), key)
    return None if sent(state, step.to, step.message, key) else step


def for_coordinator_key(agent: str, time: float) -> str:
    return f"{replies_of(agent)} {time:.0f}"


def replies_of(agent: str) -> str:
    """The part of `for_coordinator_key` that names the ticket analyst
    `agent`, the same at each of its replies."""
    return f"ticket analyst {agent}, reply at"


def part_of(key: str) -> str:
    """The opening of the step of `unfinished` on the reply `key`, or,
    with `replies_of`, on any reply of its analyst."""
    return mctx("the part for the coordinator of {key}").format(key=key)


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
        step = Send(COORDINATOR, labeled(key, part), key)
        if not sent(state, step.to, step.message, key):
            return step
    return None


def unfinished(state: State) -> Step | None:
    """The undecided step on the `unfinished:` items of the part of a
    ticket analyst's reply for the coordinator, with its items that open
    with a label with no colon after it, other than those of an analyst on
    a held step, which go to the final reply (`told`), and the
    `unfinished:` items of an analyst on what a change's editors leave. Its
    subject is the analyst, so the step on a later reply waits while an
    analyst on the step of an earlier one runs (`steps.Undecided`). It
    passes over an analyst with no agent id, of which `replied` gives
    none, so that the type checker reads the agent id as known."""
    for a, purpose, _, key in replied(state):
        if a.agent_id is None or purpose is Purpose.STEP or items_of(a, list(Label)) is None:
            continue
        open_items = None if purpose is Purpose.CHANGE else items_of(a, [Label.UNFINISHED])
        items = [*([open_items] if open_items else []), *mislabeled(a)]
        if not items:
            continue
        text = "\n".join(items)
        s = Undecided(mctx("{part} leaves these items:").format(part=part_of(key)) + "\n" + text,
                      (key, *(ln.strip() for ln in text.splitlines() if ln.strip())),
                      subject=part_of(replies_of(a.agent_id)))
        if not repeated(s, state):
            return s
    return None


def told(state: State) -> list[str]:
    """The lines of the final reply of the operator `me` that give the
    coordinator the `tell:` items of each ticket analyst's reply that `me`
    gives (`final_reply.carrier`), and of the reply of an analyst on a held
    step, its `unfinished:` items and its items that open with a label with
    no colon after it. An analyst whose `final_reply.session_operator` is
    None gives no lines."""
    out: list[str] = []
    replies = replies_by_operator(state)
    for a, purpose, _, key in replied(state):
        r = a.last_report
        op = session_operator(state, a)
        if r is None or op is None or carrier(state, op, r.time, replies) != state.me:
            continue
        on_step = purpose is Purpose.STEP
        part = items_of(a, [Label.TELL, Label.UNFINISHED] if on_step else [Label.TELL])
        items = [*([part] if part else []), *(mislabeled(a) if on_step else [])]
        if items:
            out.append(f"- {key}:")
            out += nested("\n".join(items))
    return out
