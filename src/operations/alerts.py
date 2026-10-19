"""The alerts of the monitor's steps and the alerts that reach an operator, and the steps they give.

An alert opens with a line of the form `alert: <kind> <agent id>`
(`OPENING`), with the kind of `AlertKind` and the agent it is on. Each alert
of the monitor goes to the agent it is on, with its reading (`READING`) and
the message of its kind under it (`to_agent`), which gives the agent its
step.

An alert that reaches an operator is undecided, whichever agent it is on. A message from an agent an operator of the session launched
gives no step. A message from an agent no operator
launched that is no alert goes back to its sender once, with a request to
send it again as an alert, or to say that it is none, and is undecided
where the sender's next message is still no alert. An undecided alert or message goes to a ticket
analyst launched on it (`decisions`), other than one an operator already
handled (`handled.repeated`).

An alert or a message gives a step only to the operator `me` where it
reached `me`.

An agent of `TranscriptsRead.stalled`, whose final reply the operator took as its
report on its `stall` reading (`monitor`), or sends the coordinator once
where the coordinator launched it, is recorded in one `bug` ticket
of that kind, which records that its report reached no operator (`stalls`):
the first such agent's step files it, and each further one's writes a line
in it while it stands outside `tickets/closed/`.

A resume of an operator of the session after the next operator of the
session made its first entry (`TranscriptsRead.late_resumes`), as `resumed_at` in
`scripts/operator_reads.py` gives a resume, is recorded the same
way, in one `bug` ticket of its own kind (`late_resumes`): each line is on
one operator, and gives each of its resumes that no earlier line on it
gives.

A message on each agent of `TranscriptsRead.stuck` goes to the
coordinator once per stretch, with the agent's own work that still runs,
so that the coordinator ends that work or asks the session that runs it,
and the agent is recorded the same way, in one `bug` ticket of its own
kind (`stuck`).

A message on each ticket of `ticket_stall.stalled` goes to the coordinator once
per stall, with its agents and its log since the later of its last progress
and the time from which a step has been due on it, and the
ticket is recorded the same way, in one `bug` ticket of its own kind
(`ticket stall`), by `ticket_stalls`, with the paths of links
(`waits.paths`) of each change that waits on it (`waiting_paths`). The
message on a change whose paths hold a ticket that does not move goes to
the coordinator as `scripts/operate.py --help alerts` gives it
(`stuck_waits`). An idle held change (`idle_changes`) is recorded the
same way, in one `bug` ticket of its own kind (`idle`), and so is a
ticket that waits on nothing that moves it (`unwaited`), in one of the
kind `unwaited`. A kind's ticket
and its lines are on an agent, or, for
that kind, on a ticket."""

import re
from collections.abc import Collection, Mapping
from dataclasses import dataclass
from enum import Enum

from controlled_markdown import mctx
from operations import change_take, messages, ticket_stall, waits
from operations.arrivals import arrived, received
from operations.constants import COORDINATOR, stuck_reached
from operations.roles import AGENT_ID
from operations.state import Agent, LateResume, Message, Report, State, Stuck, Ticket
from operations.handled import ask_again, repeated
from operations.steps import Bash, Send, Step, Undecided
from operations.log_commands import AGENT, file_ticket, log
from ticketing.text import ticket_text
from ticketing.times import utc_stamp
from ticketing.vocabulary import DEFECT_SECTIONS, Domain, Kind, Status


class AlertKind(Enum):
    """The kinds of alert, one per reading of the monitor (`monitor`)."""
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


READING = {k: v.format(repeats=REPEATS) for k, v in {
    AlertKind.REPEATED: mctx("It ran the same Bash command with the same result at least "
                             "{repeats} times in a row"),
    AlertKind.STALL: mctx("Its turn ended while its work is open, and no report of it reached "
                          "its parent"),
}.items()}
"""Each reading of the monitor, as the alert to the agent and `monitor.ALERTS` give it."""


LEAD = mctx("A monitor's alert:")
REPEATED_MESSAGE = mctx("Run that command again only once something has changed that can "
                        "change its result.")
STALL_MESSAGE = mctx("""
    - Where your work is done, give your final reply again.
    - Where it is not, continue your work.
    """)


def to_agent(kind: AlertKind, agent: str) -> str:
    """The message to `agent` of the alert of `kind` on it: the alert, with
    its reading and, under them, the step the kind gives the agent."""
    match kind:
        case AlertKind.REPEATED:
            step = REPEATED_MESSAGE
        case AlertKind.STALL:
            step = STALL_MESSAGE
    return (LEAD + "\n\n" + opening(kind, agent) + "\n\n" + READING[kind] + ".\n\n"
            + step)


def latest(state: State, agent: str) -> Agent | None:
    found = [a for a in state.transcripts.agents if a.agent_id == agent]
    return found[-1] if found else None


class BugKind(Enum):
    """The kinds of `bug` ticket the operator's command files."""
    STALL = "stall"
    LATE_RESUME = "late resume"
    STUCK = "stuck"
    TICKET_STALL = "ticket stall"
    IDLE = "idle"
    UNWAITED = "unwaited"


TICKETS = {
    BugKind.STALL: (
        mctx("the delivery of an agent's report to the operator that launched it: its final "
             "reply reached that operator as no report"),
        mctx("The operator read no report of it, and took the final reply in its transcript "
             "as its report.")),
    BugKind.LATE_RESUME: (
        mctx("the end of an operator's run: a message or a notification resumed it after a "
             "later operator of the session started"),
        mctx("The resumed operator ran on its old context after a later operator of the "
             "session had started on a fresh one.")),
    BugKind.STUCK: (
        mctx("the wait on an agent's work: the agent showed no sign of progress for "
             "`STUCK_SECONDS`"),
        mctx("The agent's work made no progress for `STUCK_SECONDS`, and then a message on "
             "the agent went to the coordinator.")),
    BugKind.TICKET_STALL: (
        mctx("the progress of a ticket: no step was made on it, and no agent worked on it, "
             "for `STUCK_SECONDS`"),
        mctx("The ticket made no progress for `STUCK_SECONDS` while a step of an operator "
             "was due on it, and then a message on the ticket went to the coordinator.")),
    BugKind.IDLE: (
        mctx("the steps of a held change: the operator's command gave it no step, with no agent "
             "at work on it, and it waits on no clock, coordinator or usage limit"),
        mctx("The change stood with no agent and no step, and then a message on it went to "
             "the coordinator.")),
    BugKind.UNWAITED: (
        mctx("the wait of a ticket outside `tickets/closed/`: no agent worked on it, and it "
             "waited on nothing that moves it"),
        mctx("The ticket stood with no agent, no step due and no party it waits on, and then "
             "a message on it went to the coordinator.")),
}
"""The title and the `Impact` of the `bug` ticket of each kind that files one,
by which the operator also finds that kind's ticket in the tracker."""

INSTANCE = "instance"
"""The word the note of the log line of a further subject of a `BugKind`
opens with, in that kind's ticket. A note that opened with an agent's id
would make that agent the holder of an `assigned` ticket."""


def instance(subject: str) -> str:
    """The opening of the note of `subject`'s log line in a kind's ticket."""
    return f"{INSTANCE} {subject}:"


def kind_tickets(state: State, kind: BugKind) -> list[Ticket]:
    """The tickets of `kind` an operator filed, in the tracker's order."""
    title = TICKETS[kind][0]
    return sorted((t for t in state.tracker.tickets.values()
                   if t.filer == AGENT and t.kind is Kind.BUG and t.title == title),
                  key=lambda t: t.order)


def handled(tickets: list[Ticket], domain: Domain, subject: str, since: float) -> bool:
    """Whether an operator filed one of `tickets` on `subject` of `domain`,
    or wrote its line in one, after `since`."""
    return any((t.domain is domain and t.subject == subject and t.filed >= since)
               or any(ln.agent == AGENT and ln.time >= since
                      and ln.note.startswith(instance(subject)) for ln in t.log)
               for t in tickets)


def ticket_step(state: State, kind: BugKind, domain: Domain, subject: str, since: float,
                line: str, evidence: str) -> Step | None:
    """The step on `subject` of `domain`, of `kind` from `since` on: none
    where `handled`, the line of `subject` in the first of that kind's
    tickets outside `tickets/closed/`, with `line` after `instance`, and
    otherwise the command that files that kind's ticket, with `evidence` as
    its Evidence."""
    tickets = kind_tickets(state, kind)
    if handled(tickets, domain, subject, since):
        return None
    about = f"{kind.value} {domain.value} {subject}"
    standing = [t for t in tickets if t.status is not Status.CLOSED]
    if standing:
        t = standing[0]
        return Bash(log(t.number, t.status, t.status, instance(subject) + " " + line, None),
                    about, occasion=str(since))
    title, impact_text = TICKETS[kind]
    impact, evidence_section = DEFECT_SECTIONS
    text = ticket_text(Kind.BUG, title, {impact: impact_text, evidence_section: evidence})
    return file_ticket(domain, subject, text, about, occasion=str(since))


def stall_step(state: State, agent: str, since: float, reply: Report) -> Step | None:
    """`ticket_step` on `agent`, an agent of `TranscriptsRead.stalled` whose final
    reply in its transcript is `reply`."""
    time = utc_stamp(reply.time)
    return ticket_step(
        state, BugKind.STALL, Domain.AGENT, agent, since,
        mctx("its final reply in its transcript stands at {time}").format(time=time),
        mctx("The final reply of {agent}, in its transcript at {time}:").format(
            agent=agent, time=time) + "\n" + reply.text)


def stalls(state: State) -> Step | None:
    """The first step on an agent of `TranscriptsRead.stalled`: for an agent no
    operator launched, which the coordinator launched, the message that
    gives the coordinator its final reply, once after that reply, and then
    for each, the step `ticket_step` gives, from its launch, or for an
    agent the coordinator launched, from that reply."""
    for agent, reply in sorted(state.transcripts.stalled.items()):
        a = latest(state, agent)
        if a is not None:
            since = a.launched
        else:
            since = reply.time
            sent = Send(COORDINATOR, reply.text, f"stall {agent}", since)
            if not repeated(sent, state):
                return sent
        if (s := stall_step(state, agent, since, reply)) is not None:
            return s
    return None


STUCK_RULE = mctx("no entry of its transcript, or of an agent under it, falls within {stretch}, "
                  "or each of its Bash calls in {stretch} repeats the call before it with the "
                  "same result, a command led by `: 'unattended-wait:` included")
"""What makes an agent stuck over the stretch `{stretch}` gives, which
`stuck_text` and `monitor.ALERTS` both give."""


def stuck_text(agent: str, s: Stuck) -> str:
    """The text on `agent`, stuck as `s` gives, of the message to the
    coordinator and of the `bug` ticket's Evidence."""
    stretch = mctx("the time since then")
    head = mctx("Agent {agent} of session {session} has made no progress since {time}: "
                "{rule}.").format(agent=agent, session=s.session, time=utc_stamp(s.since),
                                  rule=STUCK_RULE.format(stretch=stretch))
    if not s.running:
        return head + " " + mctx("No work of its own still runs.")
    return (head + " " + mctx("Its work of its own that still runs:") + "\n"
            + "\n".join(f"- `{c}`" for c in s.running))


def stuck(state: State) -> Step | None:
    """The first step on an agent of `TranscriptsRead.stuck`: the message
    that gives the coordinator `stuck_text`, once after the start of its
    stretch, then the step `ticket_step` gives from that start."""
    for agent, s in sorted(state.transcripts.stuck.items()):
        text = stuck_text(agent, s)
        sent = Send(COORDINATOR, text + "\n" + mctx("End its work, or ask the session that "
                                                     "runs it."), f"stuck {agent}", s.since)
        if not repeated(sent, state):
            return sent
        t = ticket_step(state, BugKind.STUCK, Domain.AGENT, agent, s.since,
                        mctx("no progress since {time}").format(time=utc_stamp(s.since)),
                        text)
        if t is not None:
            return t
    return None


def ticket_stall_text(state: State, t: Ticket, since: float) -> str:
    """The text on `t`, stalled since `since`, of the message to the
    coordinator and of the `bug` ticket's Evidence."""
    head = mctx("Ticket {number}, under `tickets/{status}/` and held by {holder}, has had no "
                "step, and no agent at work on it, since {time}.").format(
        number=t.number, status=t.status.value, holder=t.holder or "no agent",
        time=utc_stamp(since))
    lines = [f"- {utc_stamp(ln.time)} {ln.status.value} [{ln.agent_id or ln.agent}]: {ln.note}"
             for ln in t.log if ln.time > since]
    agents = [mctx("- {agent} ({role} on {subject}): last report {report}").format(
        agent=a.agent_id or "unknown", role=a.role.value, subject=a.subject,
        report=utc_stamp(r.time) if (r := a.last_report) is not None else "none")
        for a in ticket_stall.agents_of(state, t.number)]
    return "\n".join([head,
                      mctx("Its log since then:") if lines else mctx("Its log has no line since then."),
                      *lines,
                      mctx("The agents the operators launched on it:") if agents
                      else mctx("No operator launched an agent on it."),
                      *agents])


FIND_STEP = mctx("Find the step it waits for, from its log and the last reports of its agents, "
                 "then have the agent whose work that step is make it.")
"""The line of the message to the coordinator on a stalled ticket or an
idle change that gives the coordinator its step."""


def ticket_stalls(state: State) -> Step | None:
    """The first step on a ticket of `ticket_stall.stalled`: the message that
    gives the coordinator `ticket_stall_text`, once after the time
    `ticket_stall.stalled` gives for it, then the step `ticket_step`
    gives from that time. The message gives `waiting_paths` on it."""
    stalls = ticket_stall.stalled(state)
    for n, since in sorted(stalls.items()):
        t = state.tracker.tickets[n]
        sent = stall_message(state, t, since, waiting_paths(state, n, stalls), f"ticket stall {n}")
        s = ticket_stall_step(state, sent, t, since, BugKind.TICKET_STALL,
                              mctx("no progress since {time}").format(time=utc_stamp(since)))
        if s is not None:
            return s
    return None


def stall_message(state: State, t: Ticket, since: float, paths: str, about: str,
                  change: str | None = None) -> Send:
    """The message to the coordinator on `t`, stalled since `since`:
    `ticket_stall_text`, then `paths`, then `FIND_STEP`, with `about` and
    `change` as `Send` gives them."""
    return Send(COORDINATOR, ticket_stall_text(state, t, since) + "\n" + paths + FIND_STEP,
                about, since, change=change)


def ticket_stall_step(state: State, sent: Send, t: Ticket, since: float, kind: BugKind,
                      line: str) -> Step | None:
    """The step on `t`, stalled since `since`, whose message to the
    coordinator is `sent`: `sent`, once after `since`, then the step
    `ticket_step` gives on `t` for `kind` from that time, with `line`."""
    if not repeated(sent, state):
        return sent
    return ticket_step(state, kind, Domain.TICKET, t.number, since, line,
                       ticket_stall_text(state, t, since))


def waiting_paths(state: State, number: str, stalls: Mapping[str, float]) -> str:
    """The paths (`waits.paths`) of each change of `change_take.waiting` that
    reach ticket `number`, each under a line that leads them, or the empty
    text where none reaches it."""
    roots = [waits.paths(state, n, stalls) for n, _ in change_take.waiting(state)]
    trees = [r for r in roots if any(x.number == number for x in waits.nodes(r))]
    return "".join(mctx("The paths of links from change {change}, which waits on it:").format(
        change=r.number) + "\n" + waits.rendered(state, r) + "\n" for r in trees)


def told(state: State, node: "waits.Node", entries: Collection[str]) -> bool:
    """Whether the mark of `node`, on the paths of a change whose open
    `depends-on` entries are `entries`, makes `next` send the coordinator
    the message of `stuck_waits`, as `--help alerts` of `operate.py` gives
    it (`ticket_stall.Acting.told`)."""
    return ticket_stall.Acting(state, node.number, node.mark, node.number in entries).told


STUCK_WAITS = mctx("Change {change} waits on its `depends-on`, and these tickets on its paths "
                   "of links do not move: {stuck}. Its paths of links:")
STUCK_STEP = mctx("Cut a link whose result the waiting change's Design does not read, have the "
                  "stuck ticket moved, or bring the user the decision.")


def stuck_waits(state: State) -> Step | None:
    """The first message to the coordinator on a change of
    `change_take.waiting`, with its paths (`waits.paths`) and the step to take,
    where and as often as `--help alerts` of `operate.py` gives that `next`
    sends one."""
    found = change_take.waiting(state)
    if not found:
        return None
    stalls = ticket_stall.stalled(state)
    for n, deps in found:
        t = state.tracker.tickets[n]
        if not stuck_reached(t.last_time, state.now):
            continue
        root = waits.paths(state, n, stalls)
        stuck = [x for x in waits.nodes(root) if told(state, x, deps)]
        if not stuck:
            continue
        text = "\n".join([STUCK_WAITS.format(change=n, stuck=", ".join(x.number for x in stuck)),
                          waits.rendered(state, root), STUCK_STEP])
        cycles = {tuple(sorted(c)): c for x in stuck if (c := waits.cycle(state, x.number)) is not None}
        if cycles:
            sends = [Send(COORDINATOR, text, "stuck waits cycle " + " ".join(k),
                          max(state.tracker.tickets[m].last_time for m in c))
                     for k, c in sorted(cycles.items())]
        else:
            sends = [Send(COORDINATOR, text, f"stuck waits {n} " + " ".join(sorted(x.number for x in stuck)),
                          t.last_time)]
        sent = next((s for s in sends if not repeated(s, state)), None)
        if sent is not None:
            return sent
    return None


def resume_text(r: LateResume) -> str:
    return mctx("a resume at {time}, after {later} made its first entry at {first}").format(
        time=utc_stamp(r.time), later=r.later, first=utc_stamp(r.later_first))


def late_resumes(state: State) -> Step | None:
    """The first step on an operator of `TranscriptsRead.late_resumes`, in the order
    of `State.operators`: `ticket_step` from its earliest resume that
    `handled` leaves out, with each of its resumes from that one on."""
    tickets = kind_tickets(state, BugKind.LATE_RESUME)
    for agent in state.operators:
        left = [r for r in state.transcripts.late_resumes.get(agent, ())
                if not handled(tickets, Domain.AGENT, agent, r.time)]
        if not left:
            continue
        texts = [resume_text(r) for r in left]
        s = ticket_step(state, BugKind.LATE_RESUME, Domain.AGENT, agent, left[0].time, "; ".join(texts),
                        mctx("The resumes of {agent}, from its transcript:").format(agent=agent)
                        + "".join(f"\n- {t}" for t in texts))
        if s is not None:
            return s
    return None


def step(state: State) -> Step | None:
    """The first step the alerts and the other agents' messages give the
    operator `me`."""
    launched = {a.agent_id for a in state.transcripts.agents if a.agent_id}
    for m in arrived(state):
        if m.sender is None or m.sender in launched or m.operator != state.me:
            continue
        alert = parsed(m)
        if alert is None:
            replies = [x.time for x in received(state) if x.sender == m.sender and x.time <= m.time]
            asked = ask_again(state, m.sender, replies, messages.ALERT_FORM)
            if asked is False:
                continue
            s: Step | None = asked if isinstance(asked, Send) else Undecided(
                mctx("a message from {sender} in no form the command reads:").format(
                    sender=m.sender) + "\n" + m.text)
        elif latest(state, alert.agent) is None:
            s = Undecided(mctx("an alert on an agent no operator launched:") + "\n" + m.text)
        else:
            s = Undecided(mctx("an alert the command does not act on:") + "\n" + m.text)
        if s is not None and not repeated(s, state):
            return s
    return None
