"""The alerts of the monitor's steps and the alerts that reach an operator, and the steps they give.

An alert opens with a line of the form `alert: <kind> <agent id>`
(`OPENING`), with the kind of `AlertKind` and the agent it is on. On an agent an
operator of the session launched whose work is open:

- A `budget` alert goes to the agent itself, under `BUDGET_MESSAGE`.

Any other alert, and an alert on an agent no operator launched, are
undecided. A message from an agent an operator of the session launched,
an auditor included, gives no step: the command reads an auditor's report
from its launch's reports alone (`monitor`). A message from an agent no operator
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
report on an auditor's `stall` finding, gets a `bug` ticket that records
that its report reached no operator (`stalls`)."""

import re
import shlex
from dataclasses import dataclass
from enum import Enum

from controlled_markdown import mctx
from operations import briefs
from operations.roles import AGENT_ID
from operations.state import Agent, Message, Report, State
from operations.handled import ask_again, repeated
from operations.steps import Bash, Send, Step, Undecided
from operations.tracker import AGENT, FILE_TICKET
from ticketing.times import utc_stamp
from ticketing.vocabulary import DEFECT_SECTIONS, Domain, Kind


class AlertKind(Enum):
    """The kinds of alert, as an auditor gives them, with `budget`."""
    OWN_DOING = "own-doing"
    OBSTACLE = "obstacle"
    OUTGROWN = "outgrown"
    CLAIM = "claim"
    STALL = "stall"
    DEPARTURE = "departure"
    BUDGET = "budget"
    MESSAGE = "message"


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


BUDGET_MESSAGE = (mctx("A monitor's alert: your active time is past your budget.") + " "
                  + briefs.AT_BUDGET)


def to_agent(alert: str) -> str:
    """The message to the agent of the `budget` alert `alert`, with the
    alert under it."""
    return BUDGET_MESSAGE + "\n\n" + alert


def latest(state: State, agent: str) -> Agent | None:
    found = [a for a in state.agents if a.agent_id == agent]
    return found[-1] if found else None


def stall_ticket(agent: str, reply: Report) -> str:
    """The command that files the `bug` ticket on the stalled agent `agent`,
    whose final reply in its transcript is `reply`."""
    impact, evidence = DEFECT_SECTIONS
    return "\n".join([
        shlex.join([*FILE_TICKET, Domain.AGENT.value, agent, AGENT]) + " <<'TICKET'",
        "---", f"kind: {Kind.BUG.value}", "---",
        mctx("# {agent}: its final reply reached the operator that launched it as no "
             "report").format(agent=agent),
        "", f"## {impact}",
        mctx("The operator read no report of it, and took the final reply in its transcript "
             "as its report."),
        "", f"## {evidence}",
        mctx("Its final reply, in its transcript at {time}:").format(time=utc_stamp(reply.time)),
        reply.text, "TICKET"])


def filed(state: State, a: Agent) -> bool:
    """Whether an operator filed a `bug` ticket on `a` after its launch."""
    return any(t.domain is Domain.AGENT and t.subject == a.agent_id and t.filer == AGENT
               and t.kind is Kind.BUG and t.filed >= a.launched
               for t in state.tickets.values())


def stalls(state: State) -> Step | None:
    """The first `bug` ticket on an agent of `State.stalled` that no
    operator filed yet."""
    for agent, reply in sorted(state.stalled.items()):
        if (a := latest(state, agent)) is not None and not filed(state, a):
            return Bash(stall_ticket(agent, reply))
    return None


def on(state: State, alert: Alert, a: Agent) -> Step | None:
    """The step `alert` gives on `a`, an agent an operator launched."""
    match alert.kind:
        case AlertKind.BUDGET:
            return Send(alert.agent, to_agent(alert.message.text)) if a.pending else None
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
