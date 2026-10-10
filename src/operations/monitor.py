"""The monitor's steps, which the operator's command gives among its own
(`plan`): a launch of an `op-auditor`, the request to an auditor to write
its report again, a budget alert, and the step an auditor's finding gives
by its route (`route`). The command keeps no state of its own: it reads
back each audit from its launch's description by an operator of the
session, and each auditor's finding from its report file.

The watched agents are the agents an operator of the session launched,
other than the auditors, so no auditor, and no alert of one, is itself
audited: each whose work is open, and each whose work has closed while no
auditor was launched on it after its last ended turn, where that turn ended
after the start of the run of the operator launched right before the one
that reads the state, or of the reading one where it is the first, and
it gets no transcript review (`passes.reviewed`). An audit runs on a
watched agent once its turn ends, whether or not its work is still open,
until an auditor is launched on it after that turn, other than on an
agent that gets a transcript review, which reads the same transcript in
full; and once mid-run where a call of it has hung; on the
operator's own run before its final reply, once for each final reply (`own_audit`); and on a message
to the coordinator from an agent the coordinator did not launch. A budget
alert goes to the agent itself (`alerts.to_agent`), with no audit. A step
that goes to a watched agent itself, a budget alert or a finding's Send,
goes only to an agent whose work is open."""

import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from controlled_markdown import mctx
from operations import briefs
from operations.alerts import AlertKind, opened, opening, to_agent
from operations.roles import JUDGING, Role
from operations.handled import asked_again
from operations.steps import Launch, Send, Step
from ticketing.times import utc_stamp


class Facet(StrEnum):
    """What an audit's subject is on: a watched agent's run, an entry of
    the coordinator's transcript from a watched agent, or the operator's
    own run."""
    AGENT = "agent"
    MESSAGE = "message"
    OPERATOR = "operator"


@dataclass(frozen=True)
class Watched:
    """A watched agent at the time of the read. `activity` is the time of
    its latest new call, end of a call or end of its turn, and
    `hung` the time its oldest call in flight counted as hung
    (`hung_from`), or None where none has. `ended` is whether its
    turn has ended, and `open` whether its work is open. `over_budget` is whether its active time is past its
    budget, and `facts` the facts the command computed on it since its
    last audit, for an auditor's brief."""
    agent_id: str
    agent_type: str
    role: Role
    parent: str
    activity: float
    hung: float | None
    ended: bool
    open: bool
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
    raised or found again and the agent it is on, both None where it found
    no sign, and its one-line verdict."""
    alert: AlertKind | None
    agent: str | None
    verdict: str


NO_SIGN = "no sign"
VERDICT = "verdict: "

REPORT_FORM = mctx("- An auditor's report file holds a first line `{no_sign}`, or a first line "
                   "`alert: <kind> <agent id>`, with the kind of the alert it raised or the kind "
                   "the previous verdict alerted on, and the agent it is on. "
                   "The last line is `{verdict}<verdict>`, with its verdict on the agent on one "
                   "line. The file holds no other line.")
"""The form of an auditor's report, which the `--help` of `scripts/operate.py`
gives."""

ROUTES = mctx("- `next` gives each finding of an auditor its step by its kind and the agent "
              "it is on: a Send of the text of the alert file its brief gives to the agent, "
              "for a "
              "`departure`, `own-doing` or `outgrown` finding on an agent of type "
              "{judging} that an operator launched and whose work is open, as `uv run python "
              "scripts/profile_runs.py --open <agent id>` gives it; a Send of "
              "the line `alert: stall <agent id>` to the agent, for a `stall` finding on an "
              "agent an operator launched whose work is open and whose transcript holds no "
              "final reply since its launch; and no step for any other finding, on which the auditor's ticket "
              "stands alone. Where that transcript holds such a reply, the operator takes it "
              "as the agent's report, and files a `bug` ticket on the agent. A Send that a "
              "finding gives counts as made only where an operator sent it after the launch "
              "of that finding's auditor.").format(
                  judging=", ".join(f"`{r.agent_type}`" for r in sorted(JUDGING)))
"""The routes of `route`, which the `--help` of `scripts/operate.py` gives."""

REPORT_TEXT = REPORT_FORM.format(no_sign=NO_SIGN, verdict=VERDICT)
"""`REPORT_FORM` as `--help` of `scripts/operate.py` prints it, which an
auditor's brief and the request to write its report again give."""


def finding(text: str) -> Finding | None:
    """The finding of an auditor's report file, or None where its text is
    in no form `REPORT_FORM` gives."""
    lines = [line.strip() for line in text.strip().splitlines() if line.strip()]
    if len(lines) < 2 or not lines[-1].startswith(VERDICT):
        return None
    verdict = lines[-1].removeprefix(VERDICT)
    if len(lines) != 2:
        return None
    if lines[0] == NO_SIGN:
        return Finding(None, None, verdict)
    found = opened(lines[0])
    if found is None or found[0] is None:
        return None
    return Finding(found[0], found[1], verdict)


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
    command read of the latest, its finding where it read one, and the
    text of the alert file its brief gives, where that finding goes to an
    agent and the command read that file."""
    auditor: str
    facet: Facet
    agent_id: str
    on_time: int | None
    launched: float
    replies: tuple[float, ...]
    read: Read
    finding: Finding | None
    alert_text: str | None = None


@dataclass(frozen=True)
class MonitorState:
    """`sent` gives `handled.sent_with` over the calls of the session's
    operators, `transcript` the transcript of the operator `me`, `stalled` the
    agents of `State.stalled`, and `reviewed` the agents of `passes.reviewed`."""
    watched: tuple[Watched, ...]
    to_coordinator: tuple[ToCoordinator, ...]
    audits: tuple[Audit, ...]
    sent: Callable[[str, str], list[float]]
    transcript: Path
    stalled: frozenset[str]
    reviewed: frozenset[str]
    undecided: tuple[str, ...]
    """The lines on what the read of the state left unknown."""


NONE = mctx("none")

NO_FINDING = Finding(None, None, NONE)
"""The finding of an audit whose report the command could not read."""


def ask(state: MonitorState, a: Audit) -> Send | bool:
    """`handled.asked_again` on the latest report of `a`, which the command
    read in no form."""
    return asked_again(state.sent, a.auditor,
                       list(a.replies), REPORT_TEXT, briefs.OPERATOR)


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


TO_AGENT = frozenset({AlertKind.DEPARTURE, AlertKind.OWN_DOING, AlertKind.OUTGROWN})
"""The kinds of finding that go to a judging agent whose work is open."""


def route(state: MonitorState, a: Audit) -> Send | str | None:
    """The step the finding of `a` gives, as `ROUTES` gives it, or the line
    on it that `undecided` gives where that finding goes to an agent and
    the command read no alert file of it."""
    f = outcome(state, a)
    if f is None or f.alert is None or f.agent is None:
        return None
    w = next((w for w in state.watched if w.agent_id == f.agent), None)
    if w is None or not w.open:
        return None
    if f.alert is AlertKind.STALL:
        if w.agent_id in state.stalled:
            return None
        return Send(w.agent_id, opening(AlertKind.STALL, w.agent_id), a.launched)
    if f.alert not in TO_AGENT or w.role not in JUDGING:
        return None
    if a.alert_text is None:
        return mctx("{auditor}: its finding goes to {agent}, and the command read no alert "
                    "file of it, so the finding goes nowhere").format(
                        auditor=a.auditor, agent=w.agent_id)
    return Send(w.agent_id, a.alert_text, a.launched)


def undecided(state: MonitorState) -> list[str]:
    """The lines on what the read of the state left unknown, on the audits
    whose answer to the request to write their report again is still in
    no form, and on the findings `route` gives a line."""
    out = list(state.undecided)
    for a in state.audits:
        if a.read is Read.UNREAD and outcome(state, a) is NO_FINDING:
            out.append(mctx("{auditor}: its report is still in no form the command reads, so "
                            "its audit counts as done with no finding").format(auditor=a.auditor))
        if isinstance(line := route(state, a), str):
            out.append(line)
    return out


HUNG_FACTOR = 10
"""How many times a call's usual time a call in flight runs before it
counts as hung, once. A call whose usual time no run gives takes
`steps.BLOCK_SECONDS` as its usual time."""


def hung_from(start: float, usual: float) -> float:
    """The time at which a call that began at `start`, with `usual` as its
    label's usual time, counts as hung."""
    return start + HUNG_FACTOR * usual

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


def audits_on(audits: Iterable[Audit], facet: Facet, agent: str) -> list[Audit]:
    return sorted((a for a in audits if a.facet is facet and a.agent_id == agent),
                  key=lambda a: a.launched)


def latest_launch(past: list[Audit]) -> float | None:
    """The time of the latest launch among `past`, in the order of their
    launch."""
    return past[-1].launched if past else None


def last_audit(audits: Iterable[Audit], agent: str) -> float | None:
    """The time of the latest launch of an auditor on the run of `agent`."""
    return latest_launch(audits_on(audits, Facet.AGENT, agent))


def run_audits(state: MonitorState, w: Watched) -> list[Audit]:
    """The audits on the run of `w`, in the order of their launch."""
    return audits_on(state.audits, Facet.AGENT, w.agent_id)


def needs_audit(state: MonitorState, w: Watched) -> bool:
    """Whether `w` has an ended turn, where it gets no transcript review,
    or a call that became hung, since the launch of its last auditor, once
    that auditor's outcome is in."""
    past = run_audits(state, w)
    last = latest_launch(past)
    if past and outcome(state, past[-1]) is None:
        return False
    if w.ended:
        if w.agent_id in state.reviewed:
            return False
        return last is None or w.activity > last
    return w.hung is not None and (last is None or w.hung > last)


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
ON_OPERATOR = "\n".join([
    mctx("Audit `{agent}`, an operator, whose run is at its final reply: its run goes on "
         "only to wait for your report, and then gives that reply."),
    mctx("Its transcript is `{transcript}`, and you read it from {since} on."),
    mctx("The previous auditor's verdict on it: {verdict}")])
FIRST = mctx("its first entry")


def since_last(past: list[Audit]) -> str:
    return utc_stamp(past[-1].launched) if past else FIRST


def previous_verdict(state: MonitorState, past: list[Audit]) -> str:
    """The verdict of the latest audit in `past` whose outcome is in, or NONE."""
    found = [f for a in past if (f := outcome(state, a)) is not None]
    return found[-1].verdict if found else NONE


def brief(state: MonitorState, w: Watched) -> str:
    """The brief of an auditor on `w`."""
    past = run_audits(state, w)
    return "\n\n".join([
        BRIEF.format(agent=w.agent_id, agent_type=w.agent_type, parent=w.parent,
                     transcript=w.transcript, since=since_last(past), facts=w.facts,
                     verdict=previous_verdict(state, past)),
        REPORT_TEXT])


def message_brief(m: ToCoordinator) -> str:
    """The brief of an auditor on the entry `m`."""
    return "\n\n".join([
        ON_MESSAGE.format(time=utc_stamp(m.time), agent=m.agent_id, agent_type=m.agent_type,
                          parent=m.parent, transcript=m.transcript, text=m.text),
        REPORT_TEXT])


def own_audit(state: MonitorState, me: str, since: float) -> Launch | None:
    """The launch of an auditor on the run of the operator `me`, before its
    final reply, where no audit on it was launched after `since`, the time
    of the latest message that reached `me`."""
    past = audits_on(state.audits, Facet.OPERATOR, me)
    if past and past[-1].launched > since:
        return None
    return Launch(Role.OP_AUDITOR, subject(Facet.OPERATOR, me), "\n\n".join([
        ON_OPERATOR.format(agent=me, transcript=state.transcript, since=since_last(past),
                           verdict=previous_verdict(state, past)),
        REPORT_TEXT]))


def budget_alert(w: Watched) -> Send:
    """The budget alert on `w`, to `w` itself."""
    return Send(w.agent_id, to_agent(opening(AlertKind.BUDGET, w.agent_id) + "\n\n"
                                     + BUDGET_ALERT))


def step(state: MonitorState, handled: Callable[[Step], bool]) -> Step | None:
    """The monitor's next step, or None where none is ready, where
    `handled` holds for a step an operator already made."""
    for a in state.audits:
        if a.read is Read.UNREAD and isinstance(asked := ask(state, a), Send):
            return asked
    for w in state.watched:
        if w.open and w.over_budget and not handled(s := budget_alert(w)):
            return s
    for a in state.audits:
        if isinstance(s := route(state, a), Send) and not handled(s):
            return s
    for w in state.watched:
        if needs_audit(state, w):
            return Launch(Role.OP_AUDITOR, subject(Facet.AGENT, w.agent_id),
                          brief(state, w))
    for m in state.to_coordinator:
        if not any(a.facet is Facet.MESSAGE and a.agent_id == m.agent_id
                   and a.on_time == int(m.time) for a in state.audits):
            return Launch(Role.OP_AUDITOR, subject(Facet.MESSAGE, m.agent_id, m.time),
                          message_brief(m))
    return None
