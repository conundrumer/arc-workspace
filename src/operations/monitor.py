"""The steps of the monitor loop of the `operations` mod, as
`scripts/monitor.py` gives them: a launch of an `op-auditor` on an agent
or on a message to the coordinator, a budget alert or an escalation as a
Send step, or a wait. The command keeps no state of its own: it reads back
each audit from its launch's description, each alert it sent from the
monitor loop's record, each auditor's alert from its report file, and the
runs of the operations loop from that loop's record.

Which messages to the coordinator get an audit, by the runs of the
operations loop, is the rule `scripts/monitor.py --help` gives.

The watched agents are the agents of the session other than the monitor
and the auditors it launched, so no auditor, and no alert of one, is
itself audited."""

import re
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from controlled_markdown import mctx
from operations.alerts import AlertKind, opened, opening
from operations.constants import COORDINATOR
from operations.reports import FOR_COORDINATOR, Label
from operations.roles import Role
from operations.steps import Launch, Poll, Send, Step, asked_again
from ticketing.times import utc_stamp


class Facet(StrEnum):
    """What an audit's subject is on: an agent's new activity, or an entry
    of the coordinator's transcript from a watched agent."""
    AGENT = "agent"
    MESSAGE = "message"


@dataclass(frozen=True)
class Watched:
    """A watched agent at the time of the read. `activity` is the time of
    its latest new call, end of a call, end of its turn or report, and
    `hung` the time its oldest call in flight passed `HUNG_FACTOR` times
    that call's usual time, or None where none has. `over_budget` is
    whether its active time is past its budget, and `facts` the facts the
    command computed on it since its last audit, for an auditor's brief."""
    agent_id: str
    agent_type: str
    parent: str
    activity: float
    hung: float | None
    over_budget: bool
    facts: str
    transcript: Path


@dataclass(frozen=True)
class ToCoordinator:
    """A message to the coordinator from a watched agent, or a completion
    notification of one, that the coordinator's transcript gained."""
    agent_id: str
    agent_type: str
    parent: str
    transcript: Path
    time: float
    text: str


@dataclass(frozen=True)
class Finding:
    """What an auditor's report file gives: the kind of the alert it
    raised or found again, None where it found no sign, the recipient of
    that alert where it sent it, and its one-line verdict."""
    alert: AlertKind | None
    recipient: str | None
    verdict: str


NO_SIGN = "no sign"
TO = "to: "
VERDICT = "verdict: "

REPORT_FORM = mctx("- An auditor's report file holds a first line `{no_sign}`, or a first line "
                   "`alert: <kind> <agent id>`, with the kind of the alert it raised or the kind "
                   "the previous verdict alerted on, and the agent it is on. Where it sent that "
                   "alert, a second line `{to}<recipient>` gives the agent id or `main` it sent "
                   "it to. The last line is `{verdict}<verdict>`, with its verdict on the agent "
                   "on one line.")
"""The form of an auditor's report, which the `--help` of `scripts/monitor.py`
gives."""

REPORT_POINTER = mctx("Write your report file in the form `uv run python scripts/monitor.py "
                      "--help` gives for an auditor's report.")


def finding(text: str) -> Finding | None:
    """The finding of an auditor's report file, or None where its text is
    in no form `REPORT_FORM` gives."""
    lines = [line.strip() for line in text.strip().splitlines() if line.strip()]
    if len(lines) < 2 or not lines[-1].startswith(VERDICT):
        return None
    verdict = lines[-1].removeprefix(VERDICT)
    if lines[0] == NO_SIGN and len(lines) == 2:
        return Finding(None, None, verdict)
    found = opened(lines[0])
    if found is None or found[0] is None:
        return None
    if len(lines) == 2:
        return Finding(found[0], None, verdict)
    if len(lines) != 3 or not lines[1].startswith(TO):
        return None
    return Finding(found[0], lines[1].removeprefix(TO), verdict)


class Read(StrEnum):
    """What the command read of an auditor's latest report: none yet, a
    finding, a text in no form `REPORT_FORM` gives, or a report file that
    is gone."""
    PENDING = "pending"
    READ = "read"
    UNREAD = "unread"
    GONE = "gone"


@dataclass(frozen=True)
class Audit:
    """An auditor the monitor launched: its agent id, its facet, the agent
    it is on, the time of the message an audit on a message is on, the
    time of its launch, the times of its reports, in order, what the
    command read of the latest, and its finding where it read one."""
    auditor: str
    facet: Facet
    agent_id: str
    on_time: int | None
    launched: float
    replies: tuple[float, ...]
    read: Read
    finding: Finding | None


@dataclass(frozen=True)
class Sending:
    """A SendMessage call of the monitor that the harness gave no error:
    its recipient, its message and its time."""
    to: str
    text: str
    time: float


@dataclass(frozen=True)
class Sent:
    """An alert the monitor sent: its kind, the agent it is on, its
    recipient and its time."""
    kind: AlertKind
    agent_id: str
    to: str
    time: float


@dataclass(frozen=True)
class Run:
    """A run of the operations loop: the time of its start, the time of its
    stop where the record gives one, and the time of the latest call that
    either loop's record gives from its start until the next start."""
    start: float
    stop: float | None
    last: float


@dataclass(frozen=True)
class MonitorState:
    watched: tuple[Watched, ...]
    to_coordinator: tuple[ToCoordinator, ...]
    audits: tuple[Audit, ...]
    sendings: tuple[Sending, ...]
    runs: tuple[Run, ...]
    """In the order they started."""
    undecided: tuple[str, ...]
    """The lines on what the read of the state left unknown."""


def run_before(runs: tuple[Run, ...], t: float) -> tuple[Run, float | None] | None:
    """The latest run that started at or before `t`, with the start of the
    run after it where one did, or None where no run started by `t`."""
    out: tuple[Run, float | None] | None = None
    for r in runs:
        if r.start > t:
            return None if out is None else (out[0], r.start)
        out = (r, None)
    return out


def running_at(state: MonitorState, t: float) -> bool | None:
    """Whether the operations loop ran at `t`, or None where `t` falls
    after the latest call of a run whose stop the record does not give,
    and before the next start."""
    found = run_before(state.runs, t)
    if found is None:
        return False
    r, later = found
    if r.stop is not None:
        return t <= r.stop
    return True if later is None or t <= r.last else None


def sent_alerts(state: MonitorState) -> list[Sent]:
    out: list[Sent] = []
    for s in state.sendings:
        found = opened(s.text)
        if found is not None and found[0] is not None:
            out.append(Sent(found[0], found[1], s.to, s.time))
    return out


def sent_times(state: MonitorState, to: str, message: str) -> list[float]:
    return [s.time for s in state.sendings if s.to == to and message in s.text]


MONITOR = mctx("the monitor")
"""The reader `briefs.restate` names in the monitor's command."""

NONE = mctx("none")

NO_FINDING = Finding(None, None, NONE)
"""The finding of an audit whose report the command could not read."""


def ask(state: MonitorState, a: Audit) -> Send | bool:
    """`steps.asked_again` on the latest report of `a`, which the command
    read in no form."""
    return asked_again(lambda to, message: sent_times(state, to, message), a.auditor,
                       list(a.replies), REPORT_POINTER, MONITOR)


def outcome(state: MonitorState, a: Audit) -> Finding | None:
    """The finding of `a`, `NO_FINDING` where its report file is gone or
    its answer to the request to write it again is still in no form, or
    None while it is still to report."""
    match a.read:
        case Read.READ:
            return a.finding
        case Read.GONE:
            return NO_FINDING
        case Read.UNREAD:
            return NO_FINDING if ask(state, a) is True else None
        case Read.PENDING:
            return None


def undecided(state: MonitorState) -> list[str]:
    """The lines on what the read of the state left unknown, on the runs
    of the operations loop whose stop is unknown where a message to the
    coordinator falls after their latest call, and on the audits whose
    answer to the request to write their report again is still in no
    form."""
    out = list(state.undecided)
    for m in state.to_coordinator:
        if running_at(state, m.time) is None and (found := run_before(state.runs, m.time)):
            r, later = found
            assert later is not None
            out.append(mctx("the operations loop's run that started at {start} has no recorded "
                            "stop, so the messages to the coordinator after {last}, its latest "
                            "call, and before {later}, the next start, are not audited").format(
                                start=utc_stamp(r.start), last=utc_stamp(r.last),
                                later=utc_stamp(later)))
    for a in state.audits:
        if a.read is Read.UNREAD and outcome(state, a) is NO_FINDING:
            out.append(mctx("{auditor}: its report is still in no form the command reads, so "
                            "its audit counts as done with no finding").format(auditor=a.auditor))
    return out


HUNG_FACTOR = 10
"""How many times a call's usual time a call in flight runs before it
counts as new activity, once. A call whose usual time no run gives takes
`steps.BLOCK_SECONDS` as its usual time."""

SUBJECT = re.compile(r"\A(?P<facet>[a-z]+):(?P<agent>\S+?)(?:@(?P<time>\d+))?\Z")


def subject(facet: Facet, agent: str, time: float | None = None) -> str:
    """The subject of an audit's description: its facet, its agent and,
    for a message, the time of the message, so each launch reads back."""
    return f"{facet}:{agent}" if time is None else f"{facet}:{agent}@{int(time)}"


def subject_of(text: str) -> tuple[Facet, str, int | None] | None:
    m = SUBJECT.match(text)
    if m is None:
        return None
    try:
        facet = Facet(m["facet"])
    except ValueError:
        return None
    return facet, m["agent"], None if m["time"] is None else int(m["time"])


BUDGET_ALERT = mctx("Its active time is past its budget.")
ESCALATION = mctx("An alert on this agent got no answer: the agent shows no new activity "
                  "since, or the next audit gave the same alert.")


def audits_on(state: MonitorState, facet: Facet, agent: str) -> list[Audit]:
    return sorted((a for a in state.audits if a.facet is facet and a.agent_id == agent),
                  key=lambda a: a.launched)


def escalated_to(recipient: str, agent: Watched) -> str | None:
    """The recipient one level above `recipient`, for an alert on `agent`,
    or None where it is the coordinator."""
    if recipient == agent.agent_id:
        return agent.parent
    if recipient != COORDINATOR:
        return COORDINATOR
    return None


def escalation(state: MonitorState, w: Watched) -> Send | None:
    """The escalation one level of the alert an auditor sent on `w`, where
    `w` shows no new activity since the latest audit gave its kind, or the
    next audit on `w` gives the same kind again. Of the audits that give
    that kind in a row, the alert escalated is the latest one sent before
    the latest audit, or where none was, the latest audit's own."""
    done = [(a, f) for a in audits_on(state, Facet.AGENT, w.agent_id)
            if (f := outcome(state, a)) is not None]
    if not done or done[-1][1].alert is None:
        return None
    last, f = done[-1]
    kind = f.alert
    run: list[Finding] = []
    for _, g in reversed(done):
        if g.alert is not kind:
            break
        run.insert(0, g)
    if len(run) < 2 and w.activity > last.launched:
        return None
    sent = [g for g in run[:-1] if g.recipient is not None] or [
        g for g in run[-1:] if g.recipient is not None]
    if not sent or kind is None:
        return None
    recipient = sent[-1].recipient
    assert recipient is not None
    to = escalated_to(recipient, w)
    if to is None or any(s.agent_id == w.agent_id and s.kind is kind and s.to == to
                         for s in sent_alerts(state)):
        return None
    return Send(to, opening(kind, w.agent_id) + "\n\n" + ESCALATION)


def needs_audit(state: MonitorState, w: Watched) -> bool:
    """Whether `w` has new activity since its last audit: new calls, an
    ended turn, a report, or a call that became hung since."""
    past = audits_on(state, Facet.AGENT, w.agent_id)
    if not past:
        return True
    last = past[-1]
    if outcome(state, last) is None:
        return False
    return w.activity > last.launched or (w.hung is not None and w.hung > last.launched)


BRIEF = "\n".join([
    mctx("Audit `{agent}`, an agent of type `{agent_type}` whose parent is `{parent}`."),
    mctx("Its transcript is `{transcript}`, and you read it from {since} on."),
    mctx("The facts the monitor computed on it follow."), "", "{facts}", "",
    mctx("The previous auditor's verdict on it: {verdict}")])
ON_MESSAGE = "\n".join([
    mctx("Audit the entry below, which the coordinator's transcript gained at {time}: a "
         "message from `{agent}`, an agent of type `{agent_type}` whose parent is "
         "`{parent}`, or a notification of it."),
    mctx("Its transcript is `{transcript}`."), "", "{text}"])
FIRST = mctx("its first entry")


def brief(state: MonitorState, w: Watched, verdict: str | None) -> str:
    """The brief of an auditor on `w`."""
    past = audits_on(state, Facet.AGENT, w.agent_id)
    since = utc_stamp(past[-1].launched) if past else FIRST
    return "\n\n".join([
        BRIEF.format(agent=w.agent_id, agent_type=w.agent_type, parent=w.parent,
                     transcript=w.transcript, since=since, facts=w.facts,
                     verdict=verdict or NONE),
        REPORT_POINTER])


def message_brief(m: ToCoordinator) -> str:
    """The brief of an auditor on the entry `m`."""
    return "\n\n".join([
        ON_MESSAGE.format(time=utc_stamp(m.time), agent=m.agent_id, agent_type=m.agent_type,
                          parent=m.parent, transcript=m.transcript, text=m.text),
        REPORT_POINTER])


def unfinished(state: MonitorState) -> str:
    """The part for the coordinator of the operations loop's final reply,
    with an `unfinished` item on each line `undecided` gives, or nothing
    where it gives none."""
    lines = list(dict.fromkeys(undecided(state)))
    if not lines:
        return ""
    return "\n".join([FOR_COORDINATOR, *(f"- {Label.UNFINISHED}: {line}" for line in lines)])


def step(state: MonitorState) -> Step:
    """The monitor's next step."""
    for a in state.audits:
        if a.read is Read.UNREAD and isinstance(asked := ask(state, a), Send):
            return asked
    alerts = sent_alerts(state)
    for w in state.watched:
        if w.over_budget and not any(s.kind is AlertKind.BUDGET and s.agent_id == w.agent_id
                                     for s in alerts):
            return Send(w.parent, opening(AlertKind.BUDGET, w.agent_id) + "\n\n" + BUDGET_ALERT)
    for w in state.watched:
        if (s := escalation(state, w)) is not None:
            return s
    for w in state.watched:
        if needs_audit(state, w):
            found = [f for a in audits_on(state, Facet.AGENT, w.agent_id)
                     if (f := outcome(state, a)) is not None]
            verdict = found[-1].verdict if found else None
            return Launch(Role.OP_AUDITOR, subject(Facet.AGENT, w.agent_id),
                          brief(state, w, verdict))
    for m in state.to_coordinator:
        if running_at(state, m.time) is True and not any(
                a.facet is Facet.MESSAGE and a.agent_id == m.agent_id
                and a.on_time == int(m.time) for a in state.audits):
            return Launch(Role.OP_AUDITOR, subject(Facet.MESSAGE, m.agent_id, m.time),
                          message_brief(m))
    return Poll()

