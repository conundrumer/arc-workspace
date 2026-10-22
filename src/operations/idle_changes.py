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
alert; the line of the bug's instance names the message the change waits
on (`waits_on`).

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
from operations.state import State, Ticket, Tool
from operations.steps import Send, Step, Undecided, key
from operations.ticket_stall import progress
from ticketing.times import utc_stamp


def message(state: State, t: Ticket, since: float) -> Send:
    """The message to the coordinator on the change `t`, idle since
    `since`."""
    return alerts.stall_message(state, t, since, "", f"idle {t.number}", change=t.number)


def idle(state: State, t: Ticket, s: Step | None) -> float | None:
    """The last progress of the change `t` the operator holds, whose
    `next_step` is `s`, where `t` is idle at this read, and None
    otherwise."""
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
    own = key(message(state, t, since))
    if any(e.key != own and e.close is not None and e.close.time > since
           and (e.change == t.number or t.number in NUMBER.findall(e.text))
           for e in state.journal.sent(COORDINATOR)):
        return None
    if t.log and merging.handed_off(t.log[-1]):
        return None
    return since


def step_waits(state: State, s: Step | None) -> bool:
    """Whether `s`, the step `next_step` gives a held change, comes later
    by itself: a step `order.batch` set aside, or one that backs off after
    a refusal until a time after this read."""
    if s is None:
        return False
    if held_aside(state, s):
        return True
    until = backoff(state.journal.of(key(s)))
    return until is not None and state.now < until


def waits_on(state: State, t: Ticket) -> str | None:
    """The line that names the message the change `t` waits on, where its
    latest done message to an agent other than the coordinator has no
    report of that agent after it: the agent, the step's key and the time
    it was sent, and, where the harness refused it (`Agent.refused`), that
    refusal. None where there is no such message."""
    sends = [e for e in state.journal.entries
             if e.change == t.number and e.tool is Tool.SEND_MESSAGE and e.done
             and e.to not in (None, COORDINATOR) and e.close is not None]
    if not sends:
        return None
    e = max(sends, key=lambda e: e.close.time if e.close else 0.0)
    agent = next((a for a in [*launched_on(state, t.number), *elsewhere_on(state, t.number)]
                  if a.agent_id == e.to), None)
    sent_at = e.close.time if e.close else e.given
    if agent is None or any(r.time > sent_at for r in agent.reports):
        return None
    line = mctx("waits on {agent} for {key} since {time}").format(
        agent=e.to, key=e.key, time=utc_stamp(sent_at))
    if agent.refused is not None:
        line += mctx(", and the harness refused it at {time}").format(
            time=utc_stamp(agent.refused))
    return line


def step(state: State, t: Ticket, s: Step | None) -> Step | None:
    """The step on the change `t`, whose `next_step` is `s`, where it is
    idle: the message that gives the coordinator `message`, once after
    its last progress, then the step `alerts.ticket_step` gives from that
    time."""
    since = idle(state, t, s)
    if since is None:
        return None
    return alerts.ticket_stall_step(state, message(state, t, since), t, since,
                                    alerts.BugKind.IDLE,
                                    "; ".join(filter(None, [
                                        mctx("idle since {time}").format(time=utc_stamp(since)),
                                        waits_on(state, t)])))
