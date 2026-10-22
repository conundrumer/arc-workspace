"""The held changes that are idle, and the step on each.

A change the operator holds is idle (`idle`) where, at a read of the
state, it has no step (`changes.due_step`), no agent of it is pending, no
step on it is in flight, and it waits on no named party: the clock, where
its step backs off after a refusal (`journal.backoff`); the coordinator,
where a message on it went to the coordinator, or it was handed to the
coordinator (`merging.handed_off`), after its last progress
(`ticket_stall.progress`); and the usage limit, where it stopped an agent
of it that has not run since (`TranscriptsRead.limited`). The check reads
only these, and no cause that left the change so, for the decision to
alert; the reason `changes.due_step` gives (`steps.NoStep`) goes in the
message to the coordinator and in the line of the bug's instance.

An idle change gets a message to the coordinator once per idle stretch,
with its log since its last progress and its agents, and is then
recorded in one `bug` ticket of its own kind (`alerts.BugKind.IDLE`), by
`step`. `changes.step` gives that step in the place of the step of a
held change that has none, and `order` passes it `step`.

This module stands apart from `changes`, since `alerts` and
`ticket_stall` import `triage`, which imports `changes`."""

from controlled_markdown import mctx
from operations import alerts, merging
from operations.change_agents import elsewhere_on, launched_on
from operations.constants import AGAIN_SECONDS, COORDINATOR
from operations.directives import NUMBER
from operations.handled import decided_by, held_aside
from operations.journal import backoff
from operations.state import State, Ticket
from operations.steps import NoStep, Send, Step, Undecided, entry_key, key
from operations.ticket_stall import progress
from ticketing.times import utc_stamp


def message(state: State, t: Ticket, since: float, waiting: NoStep) -> Send:
    """The message to the coordinator on the change `t`, idle since
    `since`, with the reason `waiting` gives."""
    return alerts.stall_message(
        state, t, since, mctx("Change {number} {reason}.").format(
            number=t.number, reason=waiting.reason) + "\n\n", f"idle {t.number}",
        change=t.number)


def idle(state: State, t: Ticket, s: Step | NoStep, waiting: NoStep) -> float | None:
    """The last progress of the change `t` the operator holds, whose
    `next_step` is `s` and whose `due_step` is `waiting`, where `t` is idle
    at this read, and None otherwise."""
    if step_waits(state, s):
        return None
    since = progress(state, t)
    if since is None:
        return None
    agents = [*launched_on(state, t.number), *elsewhere_on(state, t.number)]
    if isinstance(s, Undecided):
        agents += decided_by(state, s)
    if any(a.pending for a in agents):
        return None
    if any(a.agent_id in state.transcripts.limited for a in agents):
        return None
    if any(e.change == t.number and (e.close is None or state.now - e.close.time < AGAIN_SECONDS)
           for e in state.journal.entries):
        return None
    if any(c.result is None for c in merging.merge_calls(state, t)):
        return None
    own = key(message(state, t, since, waiting))
    if any(e.key != own and e.close is not None and e.close.time > since
           and (e.change == t.number or t.number in NUMBER.findall(e.text))
           for e in state.journal.sent(COORDINATOR)):
        return None
    if t.log and merging.handed_off(t.log[-1]):
        return None
    return since


def step_waits(state: State, s: Step | NoStep) -> bool:
    """Whether `s`, the step `next_step` gives a held change, comes later
    by itself: a step `order.batch` set aside, or one that backs off after
    a refusal until a time after this read."""
    if isinstance(s, NoStep):
        return False
    if held_aside(state, s):
        return True
    until = backoff(state.journal.of(entry_key(s)))
    return until is not None and state.now < until


def step(state: State, t: Ticket, s: Step | NoStep, waiting: NoStep) -> Step | None:
    """The step on the change `t`, whose `next_step` is `s` and whose
    `due_step` is `waiting`, where it is idle: the message that gives the
    coordinator `message`, once after its last progress, then the step
    `alerts.ticket_step` gives from that time."""
    since = idle(state, t, s, waiting)
    if since is None:
        return None
    return alerts.ticket_stall_step(state, message(state, t, since, waiting), t, since,
                                    alerts.BugKind.IDLE,
                                    mctx("idle since {time}; {reason}").format(
                                        time=utc_stamp(since), reason=waiting.reason))
