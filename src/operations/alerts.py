"""The alerts of the monitor's steps and the alerts that reach an operator, and the steps they give.

An alert opens with a line of the form `alert: <kind> <agent id>`
(`OPENING`), with the kind of `AlertKind` and the agent it is on. On an agent an
operator of the session launched whose work is open:

- A `budget` alert goes to the agent itself, as the monitor's own budget
  alert, from its kind and its agent alone; each alert of the monitor goes
  to it with its reading (`READING`) and the message of its kind under it
  (`to_agent`), which gives the agent its step.

Any other alert, and an alert on an agent no operator launched, are
undecided. A message from an agent an operator of the session launched
gives no step. A message from an agent no operator
launched that is no alert goes back to its sender once, with a request to
send it again as an alert, or to say that it is none, and is undecided
where the sender's next message is still no alert. An undecided alert or message goes to a ticket
analyst launched on it (`decisions`), other than one an operator already
handled (`handled.repeated`).

A `budget` alert on an agent an operator of the session
launched gives its step to the operator that carries the session's work
on, whichever operator of the session it reached, other than where it is
undecided. Every other alert and message gives a step only to the
operator `me` where it reached `me`.

An agent of `State.stalled`, whose final reply the operator took as its
report on its `stall` reading (`monitor`), or sends the coordinator once
where the coordinator launched it, is recorded in one `bug` ticket
of that kind, which records that its report reached no operator (`stalls`):
the first such agent's step files it, and each further one's writes a line
in it while it stands outside `tickets/closed/`."""

import re
import shlex
from dataclasses import dataclass
from enum import Enum

from controlled_markdown import mctx
from operations import briefs
from operations.constants import COORDINATOR
from operations.roles import AGENT_ID
from operations.state import Agent, Message, Report, State, Ticket
from operations.handled import ask_again, repeated
from operations.steps import Bash, Send, Step, Undecided
from operations.tracker import AGENT, FILE_TICKET, log
from ticketing.text import ticket_text
from ticketing.times import utc_stamp
from ticketing.vocabulary import DEFECT_SECTIONS, Domain, Kind, Status


class AlertKind(Enum):
    """The kinds of alert, one per reading of the monitor (`monitor`)."""
    BUDGET = "budget"
    HUNG = "hung"
    REPEATED = "repeated"
    STALL = "stall"


OPENING = re.compile(rf"\Aalert: (?P<kind>\S+) (?P<agent>{AGENT_ID})[ \t]*$", re.MULTILINE)


def opening(kind: AlertKind, agent: str) -> str:
    """The line `OPENING` reads."""
    return f"alert: {kind.value} {agent}"


@dataclass(frozen=True)
class Alert:
    message: Message
    kind: AlertKind | None
    """None where the opening gives a kind `AlertKind` does not hold."""
    agent: str


def parsed(m: Message) -> Alert | None:
    """The alert `m` gives, or None where it does not open with `OPENING`."""
    found = opened(m.text)
    if found is None:
        return None
    return Alert(m, found[0], found[1])


def opened(text: str) -> tuple[AlertKind | None, str] | None:
    """The kind and the agent of the alert `text` opens with, the kind None
    where `AlertKind` does not hold it, or None where `text` does not open
    with `OPENING`."""
    found = OPENING.match(text.strip())
    if found is None:
        return None
    kinds = {k.value: k for k in AlertKind}
    return kinds.get(found["kind"]), found["agent"]


REPEATS = 3
"""How many times in a row an agent runs the same Bash command with the same
result before it gets a `repeated` alert."""


HUNG_FACTOR = 10
"""How many times a call's usual time a call in flight runs before it
counts as hung, once. A call whose usual time no run gives takes
`steps.BLOCK_SECONDS` as its usual time."""


READING = {k: v.format(factor=HUNG_FACTOR, repeats=REPEATS) for k, v in {
    AlertKind.BUDGET: mctx("Its active time is past its budget"),
    AlertKind.HUNG: mctx("A call of it in flight has run {factor} times its usual time"),
    AlertKind.REPEATED: mctx("It ran the same Bash command with the same result at least "
                             "{repeats} times in a row"),
    AlertKind.STALL: mctx("Its turn ended while its work is open, and no report of it reached "
                          "its parent"),
}.items()}
"""Each reading of the monitor, as the alert to the agent and `monitor.ALERTS` give it."""


LEAD = mctx("A monitor's alert:")
BUDGET_MESSAGE = briefs.AT_BUDGET
HUNG_MESSAGE = mctx("That call may have ended by the time you read this. Where it still runs, "
                    "check whether it makes progress, and end it where it does not. Do not run "
                    "it again unchanged.")
REPEATED_MESSAGE = mctx("Run that command again only once something has changed that can "
                        "change its result.")
STALL_MESSAGE = mctx("Where your work is done, give your final reply again. Otherwise, carry on "
                     "your work.")


def to_agent(kind: AlertKind, agent: str) -> str:
    """The message to `agent` of the alert of `kind` on it: the alert, with
    its reading and, under them, the step the kind gives the agent."""
    match kind:
        case AlertKind.BUDGET:
            step = BUDGET_MESSAGE
        case AlertKind.HUNG:
            step = HUNG_MESSAGE
        case AlertKind.REPEATED:
            step = REPEATED_MESSAGE
        case AlertKind.STALL:
            step = STALL_MESSAGE
    return (LEAD + "\n\n" + opening(kind, agent) + "\n\n" + READING[kind] + ".\n\n"
            + step)


def latest(state: State, agent: str) -> Agent | None:
    found = [a for a in state.agents if a.agent_id == agent]
    return found[-1] if found else None


TICKETS = {
    AlertKind.STALL: (
        mctx("the delivery of an agent's report to the operator that launched it: its final "
             "reply reached that operator as no report"),
        mctx("The operator read no report of it, and took the final reply in its transcript "
             "as its report.")),
}
"""The title and the `Impact` of the `bug` ticket of each kind that files one,
by which the operator also finds that kind's ticket in the tracker."""

INSTANCE = "instance"
"""The word the note of the log line of a further agent of an alert kind
opens with, in that kind's ticket. A note that opened with the agent's id
would make that agent the holder of an `assigned` ticket."""


def instance(agent: str) -> str:
    """The opening of the note of `agent`'s log line in a kind's ticket."""
    return f"{INSTANCE} {agent}:"


def kind_tickets(state: State, kind: AlertKind) -> list[Ticket]:
    """The tickets of `kind` an operator filed, in the tracker's order."""
    title = TICKETS[kind][0]
    return sorted((t for t in state.tickets.values()
                   if t.filer == AGENT and t.kind is Kind.BUG and t.title == title),
                  key=lambda t: t.order)


def handled(tickets: list[Ticket], agent: str, launched: float) -> bool:
    """Whether an operator filed one of `tickets` on `agent`, or wrote its
    line in one, after `launched`, the time of its launch."""
    return any((t.domain is Domain.AGENT and t.subject == agent and t.filed >= launched)
               or any(ln.agent == AGENT and ln.time >= launched
                      and ln.note.startswith(instance(agent)) for ln in t.log)
               for t in tickets)


def ticket_step(state: State, kind: AlertKind, agent: str, launched: float,
                reply: Report) -> Step | None:
    """The step on `agent`, an agent of `kind` launched at `launched` whose final
    reply in its transcript is `reply`: none where `handled`, the line of `agent` in the
    first of that kind's tickets outside `tickets/closed/`, and otherwise
    the command that files that kind's ticket."""
    tickets = kind_tickets(state, kind)
    if handled(tickets, agent, launched):
        return None
    time = utc_stamp(reply.time)
    standing = [t for t in tickets if t.status is not Status.CLOSED]
    if standing:
        t = standing[0]
        return Bash(log(t.number, t.status, t.status,
                        instance(agent) + " "
                        + mctx("its final reply in its transcript stands at {time}").format(
                            time=time),
                        None))
    title, impact_text = TICKETS[kind]
    impact, evidence = DEFECT_SECTIONS
    text = ticket_text(Kind.BUG, title, {
        impact: impact_text,
        evidence: mctx("The final reply of {agent}, in its transcript at {time}:").format(
            agent=agent, time=time) + "\n" + reply.text})
    return Bash(shlex.join([*FILE_TICKET, Domain.AGENT.value, agent, AGENT])
                + " <<'TICKET'\n" + text + "TICKET")


def stalls(state: State) -> Step | None:
    """The first step on an agent of `State.stalled`: for an agent no
    operator launched, which the coordinator launched, the message that
    gives the coordinator its final reply, once after that reply, and then
    for each, the step `ticket_step` gives, from its launch, or for an
    agent the coordinator launched, from that reply."""
    for agent, reply in sorted(state.stalled.items()):
        a = latest(state, agent)
        if a is not None:
            since = a.launched
        else:
            since = reply.time
            sent = Send(COORDINATOR, reply.text, since)
            if not repeated(sent, state):
                return sent
        if (s := ticket_step(state, AlertKind.STALL, agent, since, reply)) is not None:
            return s
    return None


def on(state: State, alert: Alert, a: Agent) -> Step | None:
    """The step `alert` gives on `a`, an agent an operator launched."""
    match alert.kind:
        case AlertKind.BUDGET:
            return Send(alert.agent, to_agent(AlertKind.BUDGET, alert.agent)) if a.pending else None
        case _:
            return Undecided(mctx("an alert the command does not act on:") + "\n"
                             + alert.message.text)


def step(state: State) -> Step | None:
    """The first step the alerts and the other agents' messages give the
    operator `me`."""
    launched = {a.agent_id for a in state.agents if a.agent_id}
    for m in state.arrived:
        if m.sender is None or m.sender in launched:
            continue
        alert = parsed(m)
        if alert is None:
            if m.operator != state.me:
                continue
            replies = [x.time for x in state.received if x.sender == m.sender and x.time <= m.time]
            asked = ask_again(state, m.sender, replies, briefs.ALERT_FORM)
            if asked is False:
                continue
            s: Step | None = asked if isinstance(asked, Send) else Undecided(
                mctx("a message from {sender} in no form the command reads:").format(
                    sender=m.sender) + "\n" + m.text)
        elif (a := latest(state, alert.agent)) is None:
            s = Undecided(mctx("an alert on an agent no operator launched:") + "\n" + m.text)
        else:
            s = on(state, alert, a)
        if m.operator != state.me and isinstance(s, Undecided):
            continue
        if s is not None and not repeated(s, state):
            return s
    return None
