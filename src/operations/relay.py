"""The next step of an operator launcher (`next_step`), from what its own
transcript and those of the operators it launched give (`Relay`).

The launcher's first operator takes the launcher's brief. Each later line
of the coordinator's goes to the operator that runs when it reaches the
launcher, or, where none runs, to the brief of the next operator the
launcher launches, each distinct text once. While an operator runs and no line of the
coordinator's waits for it, the launcher ends its turn, and the operator's
end or the coordinator's next line resumes it. Once an operator's final text reaches the launcher, a
text that opens with `final_reply.FOR_CONTEXT` gives the launch of the next
operator, or, past the launcher's bound, the launcher's final reply, which
asks the coordinator for a fresh operator launcher whose brief is the lines
of the coordinator's that wait for the next operator, each distinct text once, and gives them; any other text, and an
operator's end with none, goes to the coordinator, after a line that gives
the operator's agent id, and the launcher then gives its final reply,
unless a line of the coordinator's waits for the next operator, which gives
the next operator's launch, or, past the launcher's bound, the final reply
that asks for a fresh operator launcher whose brief is those lines."""

from dataclasses import dataclass

from controlled_markdown import mctx
from operations.constants import COORDINATOR
from operations.final_reply import ending_step, for_context
from operations.printing import final_message
from operations.handled import sends_in
from operations.roles import Role
from operations.state import Call, Message
from operations.steps import EndTurn, Launch, Reply, Send, Step


@dataclass(frozen=True)
class Run:
    """An operator the launcher launched: its agent id, the time of its
    launch, whether its end has not reached the launcher (`Agent.pending`),
    and the text of the final reply that the first message by which it
    sent the launcher its final reply gives (`final_reply.final_sends`,
    `final_reply.final_text`), or None where it sent none."""
    agent_id: str | None
    launched: float
    pending: bool
    final: str | None


@dataclass(frozen=True)
class Relay:
    """What the launcher `me` reads: the coordinator's messages to it, its
    brief first, in the order they arrived, the operators it launched, in
    the order of their launch, its own calls, and whether its context is
    past its bound."""
    me: str
    lines: tuple[Message, ...]
    runs: tuple[Run, ...]
    calls: tuple[Call, ...]
    past_bound: bool


FRESH_LAUNCHER = mctx("I ended for my context: launch a fresh operator launcher with no lines, "
                      "which takes up from the state.")
WITH_HELD = mctx("I ended for my context: launch a fresh operator launcher whose brief is the "
                 "lines below, which reached no operator.")
CARRIED = mctx("Operator {operator} ended with the final reply below.")
NO_REPLY = mctx("Operator {operator} ended with no final reply.")


def sent(relay: Relay, to: str, message: str, since: float) -> bool:
    """Whether the launcher sent `to` a message that opens with `message`
    after `since`."""
    return any(c.time > since and c.message.startswith(message)
               for c in sends_in(relay.calls, to))


def waiting(relay: Relay) -> list[Message]:
    """The coordinator's lines after the brief that reached the launcher
    after its last launch, and that it sent no operator: the lines of the
    next operator's brief, or of the running operator's next message."""
    last = relay.runs[-1].launched if relay.runs else float("inf")
    return [m for m in relay.lines[1:] if m.time > last
            and not any(sent(relay, r.agent_id, m.text, m.time) for r in relay.runs
                        if r.agent_id is not None)]


def operator_launch(relay: Relay, brief: str) -> Launch:
    """The launch of the launcher's next operator, with the brief `brief`."""
    return Launch(Role.OPERATOR, f"{relay.me}-{len(relay.runs) + 1}", brief)


def ending(relay: Relay, text: str) -> Step:
    """The launcher's final reply, whose text is `text`: the message that
    sends the coordinator `text`, where the launcher sent none since its
    last launch, then the reply."""
    since = relay.runs[-1].launched if relay.runs else 0.0
    return ending_step(COORDINATOR, text,
                       sent(relay, COORDINATOR, final_message(text), since))


def after(relay: Relay, run: Run, brief: str) -> Step:
    """The step after the end of the operator `run`, where the brief `brief`
    waits for the next operator: its launch, or, past the launcher's bound,
    the launcher's final reply that gives `brief`."""
    if not relay.past_bound:
        return operator_launch(relay, brief)
    return ending(relay, "\n".join([WITH_HELD.format(operator=run.agent_id), brief]))


def next_step(relay: Relay) -> Step:
    if not relay.runs:
        return operator_launch(relay, relay.lines[0].text)
    run = relay.runs[-1]
    lines = waiting(relay)
    brief = "\n".join(dict.fromkeys(m.text for m in lines))
    if run.pending and run.final is None:
        if not lines:
            return EndTurn()
        if run.agent_id is None:
            raise ValueError(f"the running operator launched at {run.launched} has no known "
                             "agent id")
        return Send(run.agent_id, lines[0].text, since=lines[0].time, commanded=True)
    if run.final is not None and for_context(run.final):
        if relay.past_bound and not lines:
            return ending(relay, FRESH_LAUNCHER)
        return after(relay, run, brief)
    carried = (CARRIED.format(operator=run.agent_id) + "\n" + run.final if run.final is not None
               else NO_REPLY.format(operator=run.agent_id))
    if not sent(relay, COORDINATOR, carried, run.launched):
        return Send(COORDINATOR, carried)
    return after(relay, run, brief) if lines else Reply(COORDINATOR)
