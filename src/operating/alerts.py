"""A supervisor's alerts that reach an operator, and the steps they give.

An alert opens with a line of the form `alert: <kind> <agent id>`
(`OPENING`), with the kind of `AlertKind` and the agent it is on. On an agent an
operator of the session launched whose work is open:

- A `budget` alert goes to the agent itself, under `BUDGET_MESSAGE`.
- An `outgrown` alert goes to the agent itself, under `OUTGROWN_MESSAGE`.
  Where the agent's next report opens with `reports.HAND_OVER`, a fresh
  agent of its role and subject takes over in its worktree, with its brief
  and that report (`briefs.take_over`).
- A `stall` alert on an agent whose final reply reached no operator as a
  report makes the final reply in its transcript its report
  (`State.stalled`), and a `bug` ticket on the agent records that it
  reached none. Where its transcript holds no final reply, the alert goes
  to the coordinator.

Any other alert, an alert on an agent no operator launched, and a message
from an agent no operator launched that is no alert, go to the coordinator
as undecided.

The alerts and messages read are those that reached the operator `me`."""

import re
from dataclasses import dataclass
from enum import Enum

from controlled_markdown import mctx
from operating import briefs
from operating.changes import own_worktree
from operating.reports import HAND_OVER, handed_over
from operating.roles import AGENT_ID
from operating.state import Agent, Message, State
from operating.steps import Bash, Launch, Send, Step, undecided
from operating.tracker import AGENT
from ticketing.vocabulary import Domain, Kind


class AlertKind(Enum):
    """The kinds of alert, as the supervisor's verifier gives them, with
    `budget` and the alert on a message to the coordinator."""
    OWN_DOING = "own-doing"
    OBSTACLE = "obstacle"
    OUTGROWN = "outgrown"
    CLAIM = "claim"
    STALL = "stall"
    DEPARTURE = "departure"
    BUDGET = "budget"
    MESSAGE = "message"


OPENING = re.compile(rf"\Aalert: (?P<kind>\S+) (?P<agent>{AGENT_ID})[ \t]*$", re.MULTILINE)


@dataclass(frozen=True)
class Alert:
    message: Message
    kind: AlertKind | None
    """None where the opening gives a kind `AlertKind` does not hold."""
    agent: str


def parsed(m: Message) -> Alert | None:
    """The alert `m` gives, or None where it does not open with `OPENING`."""
    found = OPENING.match(m.text.strip())
    if found is None:
        return None
    kinds = {k.value: k for k in AlertKind}
    return Alert(m, kinds.get(found["kind"]), found["agent"])


BUDGET_MESSAGE = mctx(
    "A supervisor's alert: your active time is past your budget. Act as your documents have "
    "you act where your budget is passed, where they say it, and otherwise finish the step "
    "you are on and end your turn with your report, with each item not done and its reason.")

OUTGROWN_MESSAGE = mctx(
    "A supervisor's alert, below, finds that your run has outgrown its task. End as your "
    "documents have you end for your context, where they say it, and otherwise end with your "
    "open work in your reply. Open that reply with `{opening}`.")


def to_agent(alert: Alert) -> str:
    """The message to the agent of a `budget` or an `outgrown` alert, with
    the alert under it."""
    head = BUDGET_MESSAGE if alert.kind is AlertKind.BUDGET else OUTGROWN_MESSAGE.format(
        opening=HAND_OVER)
    return head + "\n\n" + alert.message.text


def latest(state: State, agent: str) -> Agent | None:
    found = [a for a in state.agents if a.agent_id == agent]
    return found[-1] if found else None


def stall_ticket(alert: Alert) -> str:
    """The command that files the `bug` ticket on a stalled agent."""
    return "\n".join([
        f"uv run python scripts/file_ticket.py {Domain.AGENT.value} {alert.agent} {AGENT} "
        "<<'TICKET'",
        "---", f"kind: {Kind.BUG.value}", "---",
        mctx("# {agent}: its final reply reached the operator that launched it as no "
             "report").format(agent=alert.agent),
        "", "## Impact",
        mctx("The operator read no report of it, and took the final reply in its transcript "
             "as its report."),
        "", "## Evidence", alert.message.text, "TICKET"])


def filed(state: State, alert: Alert) -> bool:
    return any(t.domain is Domain.AGENT and t.subject == alert.agent and t.filer == AGENT
               and t.kind is Kind.BUG and t.filed >= alert.message.time
               for t in state.tickets.values())


def on(state: State, alert: Alert, a: Agent) -> Step | None:
    """The step `alert` gives on `a`, an agent an operator launched."""
    since = alert.message.time
    match alert.kind:
        case AlertKind.BUDGET:
            return Send(alert.agent, to_agent(alert)) if a.pending else None
        case AlertKind.OUTGROWN:
            text = to_agent(alert)
            if not state.sent(alert.agent, text):
                return Send(alert.agent, text) if a.pending else None
            r = a.last_report
            if a.pending or r is None or r.time < since or not handed_over(a):
                return None
            if any(b.role is a.role and b.subject == a.subject and b.launched > r.time
                   for b in state.agents):
                return None
            tree = own_worktree(state, a)
            return Launch(a.role, a.subject, briefs.take_over(
                a.brief, tree if tree in state.worktrees else None, alert.agent, r.text))
        case AlertKind.STALL:
            if alert.agent in state.stalled:
                return None if filed(state, alert) else Bash(stall_ticket(alert))
            if a.pending:
                return undecided(f"a stall alert on {alert.agent}, whose transcript holds no "
                                 f"final reply:\n{alert.message.text}")
            return None
        case _:
            return undecided(f"an alert the command does not act on:\n{alert.message.text}")


def step(state: State) -> Step | None:
    """The first step the alerts and the other agents' messages to the
    operator give."""
    launched = {a.agent_id for a in state.agents if a.agent_id}
    for m in state.received:
        if m.sender is None or m.sender in launched:
            continue
        alert = parsed(m)
        if alert is None:
            s: Step | None = undecided(f"a message from {m.sender} in no form the command "
                                       f"reads:\n{m.text}")
        elif (a := latest(state, alert.agent)) is None:
            s = undecided(f"an alert on an agent no operator launched:\n{m.text}")
        else:
            s = on(state, alert, a)
        if s is not None and not (isinstance(s, Send) and state.sent(s.to, s.message)):
            return s
    return None
