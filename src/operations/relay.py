"""The next step of an operator launcher (`next_step`), from what its own
transcript and those of the operators it launched give (`Relay`).

The coordinator gives the operators its lines by `operate.py send`, which
records them in the session's store, and sends the launcher
`constants.WAKE` alone (`directives`). The launcher's first operator takes
the launcher's brief. Each later message of the coordinator's goes to the
operator that runs when it reaches the launcher, or, where none runs, to
the brief of the next operator the launcher launches, each distinct text
once, and that brief is `constants.WAKE` where no message waits. While an
operator runs and no message of the coordinator's waits for it, the
launcher ends its turn, and the operator's end or the coordinator's next
message resumes it. Once an operator's final text reaches the launcher, a
text that opens with `final_reply.FOR_CONTEXT` gives the launch of the next
operator, or, past the launcher's bound, the launcher's final reply, which
asks the coordinator for a fresh operator launcher whose brief is that of
the next operator, and gives it.
A text that opens with `final_reply.FOR_WAIT` gives, while no message of the
coordinator's waits, the launcher's call of the command's `wait` in the
background and the end of its turn (`steps.Wait`), and, once that call has
completed or a message waits, the step as after `FOR_CONTEXT`. An operator's
end with no final reply after a failed call of `next` that printed no call
gives the launcher's final reply, with that call's output, and launches no
other operator until a message of the coordinator's reaches the launcher
after that reply. Any other end with no final reply gives the step as
after `FOR_CONTEXT` too, other than where the operator launched before it
also ended with none and each
of the two ended within `WAIT_SECONDS_IDLE` of its launch. Any other text,
and an operator's end with none in that case, goes to the coordinator,
after a line that gives the operator's agent id, and the launcher then
gives its final reply, unless a message of the coordinator's waits for the
next operator, which gives the next operator's launch, or, past the
launcher's bound, the final reply that asks for a fresh operator launcher
whose brief is that of the next operator."""

from dataclasses import dataclass

from controlled_markdown import mctx
from operations.constants import COORDINATOR, WAIT_SECONDS_IDLE, WAKE
from operations.final_reply import ending_step, for_context, for_wait
from operations.printing import final_message, wait_command
from operations.handled import sends_in
from operations.roles import Role
from operations.state import Call, Message, Tool
from operations.steps import EndTurn, Launch, Reply, Send, Step, Wait


@dataclass(frozen=True)
class Run:
    """An operator the launcher launched: its agent id, the time of its
    launch, whether its end has not reached the launcher (`Agent.pending`),
    the text of the final reply that the last message by which it
    sent the launcher its final reply gives (`final_reply.final_sends`,
    `final_reply.final_text`), or None where it sent none, and the time of
    its end: the time of the last timestamped entry of its transcript
    (`agent_turns.latest_time`), or of its launch where it has none, and the
    output of its last call of `next` where that call failed and printed
    no call (`printed_bash_check.prints_no_call`), or None otherwise."""
    agent_id: str | None
    launched: float
    pending: bool
    final: str | None
    ended: float
    failed: str | None = None


@dataclass(frozen=True)
class Relay:
    """What the launcher `me` reads: the coordinator's messages to it, its
    brief first, in the order they arrived, the operators it launched, in
    the order of their launch, its own calls, whether its context is
    past its bound, and whether a call of the command's `wait` by it runs."""
    me: str
    lines: tuple[Message, ...]
    runs: tuple[Run, ...]
    calls: tuple[Call, ...]
    past_bound: bool
    wait_runs: bool


FRESH_LAUNCHER = mctx("I ended for my context: launch a fresh operator launcher whose brief is "
                      "the text below.")
CARRIED = mctx("Operator {operator} ended with the final reply below.")
NO_REPLY = mctx("Operator {operator} ended with no final reply.")
FAILED = mctx("Operator {operator} ended after its last call of `operate.py next` failed with "
              "the output below, which prints no call, so I launch no other operator.")


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
    return Launch(Role.OPERATOR, f"{relay.me}-{len(relay.runs) + 1}", brief, occasion=str(len(relay.runs)))


def ending(relay: Relay, text: str) -> Step:
    """The launcher's final reply, whose text is `text`: the message that
    sends the coordinator `text`, where the launcher sent none since its
    last launch, then the reply."""
    since = relay.runs[-1].launched if relay.runs else 0.0
    return ending_step(COORDINATOR, text, since,
                       sent(relay, COORDINATOR, final_message(text), since))


def after(relay: Relay, lines: list[Message]) -> Step:
    """The step after the end of an operator, where `lines` wait for the
    next operator: its launch with the brief `brief` gives, or, past the
    launcher's bound, the launcher's final reply that gives that brief."""
    if not relay.past_bound:
        return operator_launch(relay, brief(lines))
    return ending(relay, "\n".join([FRESH_LAUNCHER, brief(lines)]))


def brief(lines: list[Message]) -> str:
    """The brief of the next operator, where `lines` wait for it: each
    distinct text of `lines` once, or `constants.WAKE` where none waits."""
    return "\n".join(dict.fromkeys(m.text for m in lines)) or WAKE


def waited_since(relay: Relay, since: float) -> bool:
    """Whether the launcher made a call of the command's `wait` after
    `since`."""
    return any(c.time > since and c.tool == Tool.BASH
               and str(c.input.get("command", "")).strip() == wait_command(relay.me)
               for c in relay.calls)


def quick(run: Run) -> bool:
    """Whether `run` ended with no final reply within `WAIT_SECONDS_IDLE`
    of its launch."""
    return not run.pending and run.final is None and run.ended - run.launched < WAIT_SECONDS_IDLE


def failed_step(relay: Relay, run: Run, lines: list[Message]) -> Step:
    """The step after `run` ended with no final reply after a failed call of
    `next` that printed no call: the launcher's final reply that gives that
    call's output, then the launch of the next operator for the messages of
    the coordinator's that reached the launcher after that reply, or the
    reply where none did."""
    text = FAILED.format(operator=run.agent_id) + "\n" + (run.failed or "")
    message = final_message(text)
    times = [c.time for c in sends_in(relay.calls, COORDINATOR)
             if c.time > run.launched and c.message.startswith(message)]
    if not times:
        return ending(relay, text)
    later = [m for m in lines if m.time > times[-1]]
    return after(relay, later) if later else Reply(COORDINATOR)


def next_step(relay: Relay) -> Step:
    if not relay.runs:
        return operator_launch(relay, relay.lines[0].text)
    run = relay.runs[-1]
    lines = waiting(relay)
    if run.pending and run.final is None:
        if not lines:
            return EndTurn()
        if run.agent_id is None:
            raise ValueError(f"the running operator launched at {run.launched} has no known "
                             "agent id")
        return Send(run.agent_id, lines[0].text, "line", since=lines[0].time, commanded=True)
    if run.final is not None and for_wait(run.final) and not lines:
        if relay.wait_runs:
            return Wait(relay.me, call=False)
        if not waited_since(relay, run.ended):
            return Wait(relay.me)
    if run.final is not None and (for_context(run.final) or for_wait(run.final)):
        return after(relay, lines)
    if run.final is None and run.failed is not None:
        return failed_step(relay, run, lines)
    if run.final is None and not (len(relay.runs) > 1 and quick(run) and quick(relay.runs[-2])):
        return after(relay, lines)
    carried = (CARRIED.format(operator=run.agent_id) + "\n" + run.final if run.final is not None
               else NO_REPLY.format(operator=run.agent_id))
    if not sent(relay, COORDINATOR, carried, run.launched):
        return Send(COORDINATOR, carried, f"carried {run.agent_id}")
    return after(relay, lines) if lines else Reply(COORDINATOR)
