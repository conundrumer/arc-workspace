"""The reads the assembly of the operator's state (`state_assembly`) takes
beside the reads of the tracker, git and the transcripts: the states of the
operators' agents, which `operations.liveness.attempt_state` decides from the
record of each attempt (`operations.attempts`) with the facts these reads
gather beside it, and the quiet and the stuck ones."""

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path

from attempt_record import Record
from monitor_reads import watched
from open_agents import Listed, latest_write, turn_ended_idle
from agent_ends import stalled_reports
from transcripts import launched_find
from transcript_snapshots import SUBJECT_FAULTS

from controlled_markdown import mctx

from operations import attempt_view
from operations import attempts as events
from operations.attempt_view import refused_at
from operations.attempts import Attempt, fold
from operations.constants import STUCK_SECONDS, stuck_reached
from operations.liveness import (
    AttemptFacts, CodexEnd, CodexRead, Written, attempt_state, unknown_text)
from operations.monitor import Watched
from operations.plan import unknown_line
from operations.roles import Role, analyst_of, subjects
from operations.state import (
    Agent,
    AttemptState,
    Ended,
    Report,
    Running,
    Ticket,
    Unknown,
    Waits,
    Stuck,
)
from ticketing.vocabulary import Status

from filed_texts import gone_line


def watched_read(listing: list[Listed], agents: Sequence[Agent], undecided: list[str],
                 opened: float) -> list[Watched]:
    """`watched` of `listing`, with `agents` as the operators' launches."""
    return watched(listing, {a.agent_id for a in agents if a.agent_id}, undecided, opened)


def work_of(listing: list[Listed]) -> dict[str, tuple[str, ...]]:
    """The command line of each span of the work still running of each
    agent of `listing`, by agent id."""
    return {aid: tuple(sp.command for sp in x.running)
            for x in listing if (aid := x.launch.agent) is not None}


@dataclass(frozen=True)
class EndsRead:
    """The operators' agents with their states read (`ends_read`), the
    reports that end those this read ends whose result had not reached
    their operator (`Agent.awaited`), by agent id, or None where an end adds
    none (`ended`), the part of those of stalled agents
    (`TranscriptsRead.stalled`), `TranscriptsRead.quiet`, the attempts held
    while their Codex turn runs or is unknown (`held`), which raise no
    stall alert, and `unknown`, the diagnostic (`Unknown.reason`) of each
    quiet attempt of unknown state, by agent id. `quiet` gives an attempt
    that is `Running` or `Unknown` at the start of its stretch past its
    lease (`Running.until`), other than one the usage limit stopped, since
    `limit_resume` covers it."""
    agents: tuple[Agent, ...]
    ended: Mapping[str, Report | None]
    stalled: Mapping[str, Report]
    quiet: Mapping[str, float]
    held: frozenset[str] = frozenset()
    unknown: Mapping[str, str] = field(default_factory=dict)


def ticket_numbers(a: Agent) -> list[str]:
    """The ticket numbers of an agent's subject, with an analyst's purpose removed."""
    if a.role is Role.TICKET_ANALYST:
        parsed = analyst_of(a.subject)
        return subjects(parsed[1]) if parsed is not None else []
    return subjects(a.subject)


def closes_of(tickets: Mapping[str, Ticket]) -> dict[str, float]:
    """The time of the last CLOSED log line of each closed ticket that has one."""
    return {n: line.time for n, ticket in tickets.items() if ticket.status is Status.CLOSED
            for line in ticket.log if line.status is Status.CLOSED}


def outlived(a: Agent, closes: Mapping[str, float]) -> bool:
    """Whether each ticket of an agent's subject closed after its launch."""
    numbers = ticket_numbers(a)
    return bool(numbers) and all(n in closes and closes[n] > a.launched for n in numbers)


def ends_read(agents: Sequence[Agent], listing: list[Listed],
              now_watched: Sequence[Watched], now: float, undecided: list[str],
              *, closes: Mapping[str, float]) -> EndsRead:
    """`agents` with each one's state decided (`attempt_reads`), where the
    listing gives the work of its own that runs. A watched agent that no
    operator launched, and that the coordinator launched, has no record, so
    its stall read stands in its place: `stalled` gives its final reply. An
    attempt that ends is left out of the `quiet` it returns, so no stuck
    alert names it."""
    idle = turn_ended_idle(listing)
    live = frozenset(x.launch.agent for x in listing if x.launch.agent is not None
                     and x.launch.agent not in idle)
    launched = {a.agent_id for a in agents if a.agent_id}
    watched_ids = {w.agent_id for w in now_watched}
    coordinators = {aid: x.launch.since for x in listing
                    if (aid := x.launch.agent) in watched_ids and aid not in launched}
    stalls = stalled_reports(coordinators,
                             [w.agent_id for w in now_watched
                              if w.stalled is not None and w.agent_id not in live], undecided)
    read = attempt_reads(agents, listing=listing, closes=closes, live=live, undecided=undecided)
    awaited = {a.agent_id for a in agents if a.awaited}
    ended = {a.agent_id: a.last_report for a in read.agents
             if isinstance(a.state, Ended) and a.agent_id in awaited and a.agent_id is not None}
    quiet: dict[str, float] = {}
    unknown: dict[str, str] = {}
    for a in read.agents:
        match a.state:
            case Running(waits, until) if waits is not Waits.LIMITED and until is not None:
                reason = None
            case Unknown(reason, until) if until is not None:
                pass
            case _:
                continue
        since = until - STUCK_SECONDS
        if a.agent_id is not None and stuck_reached(since, now):
            quiet[a.agent_id] = since
            if reason is not None:
                unknown[a.agent_id] = reason
    return EndsRead(read.agents, ended, {k: v for k, v in stalls.items() if k not in read.held},
                    quiet, read.held, unknown)


@dataclass(frozen=True)
class AttemptsRead:
    """`agents` with each state decided, and the attempts `held` while their
    Codex turn runs or their record does not show whether they ended."""
    agents: tuple[Agent, ...]
    held: frozenset[str]


def projection(ids: Iterable[str]) -> dict[str, Attempt]:
    """The record of each attempt of `ids`, with the attempts launched under
    them and the endpoints of their messages, by agent id: the one
    projection of the lifecycle that every reader of an attempt shares."""
    return fold(Record().events(ids))


def attempt_reads(agents: Sequence[Agent], *, listing: list[Listed] | None = None,
                  closes: Mapping[str, float] | None = None,
                  live: frozenset[str] = frozenset(), home: Path | None = None,
                  undecided: list[str] | None = None) -> AttemptsRead:
    """`agents`, each with its `state` decided by `attempt_state` from its
    record and from the facts the reads gather beside it: the `listing` of
    the running agents, of which `live` are those with work of their own
    running, `closes` (`closes_of`), its accepted turn (`turn_read`), its
    write times (`latest_write`), and whether the usage limit stopped it
    (`Waits.LIMITED` of the state it was built with). The state of an
    agent the harness refused a message to has that refusal in its `Ended`
    (`attempt_view.refused_at`), where its reports do not follow it."""
    reads = StateReads(projection([a.agent_id for a in agents if a.agent_id]),
                       listing or [], live, home, [] if undecided is None else undecided,
                       {a.agent_id: a for a in agents if a.agent_id}, closes or {})
    out: list[Agent] = []
    for a in agents:
        if a.agent_id is None:
            out.append(a)
            continue
        state = reads.state(a.agent_id)
        if isinstance(state, Ended):
            attempt = reads.attempts.get(a.agent_id)
            refused = None if attempt is None else refused_at(attempt, a.since, a.reports)
            state = Ended(refused=refused)
        out.append(replace(a, state=state))
    return AttemptsRead(tuple(out), frozenset(reads.held))


@dataclass
class StateReads:
    """The states `attempt_state` decides for the attempts of `attempts`,
    each once (`state`), with the facts of each attempt: whether a
    descendant of it runs, the `listing` and its `live` agents, the `agents`
    that were read for it, and the `closes` of tickets. `held` gets the agent
    id of an attempt whose Codex turn runs or whose state is unknown."""
    attempts: dict[str, Attempt]
    listing: list[Listed]
    live: frozenset[str]
    home: Path | None
    undecided: list[str]
    agents: dict[str, Agent] = field(default_factory=dict)
    closes: Mapping[str, float] = field(default_factory=dict)
    held: set[str] = field(default_factory=set)
    states: dict[str, AttemptState] = field(default_factory=dict)
    deciding: set[str] = field(default_factory=set)

    def state(self, aid: str) -> AttemptState:
        """The state of the attempt `aid`, decided once."""
        if aid in self.states:
            return self.states[aid]
        if aid in self.deciding:
            raise ValueError(f"the launches of attempt {aid} form a cycle")
        self.deciding.add(aid)
        attempt = self.attempts.get(aid)
        descendants = any(
            not isinstance(self.state(child.agent), Ended) for child in self.attempts.values()
            if child.launch is not None and child.launch.parent == aid)
        state = attempt_state(attempt, self.facts(aid, attempt, descendants))
        if isinstance(state, Unknown):
            self.held.add(aid)
        self.deciding.discard(aid)
        self.states[aid] = state
        return state

    def facts(self, aid: str, attempt: Attempt | None, descendants: bool) -> AttemptFacts:
        """`AttemptFacts` of the attempt `aid`, whose record is `attempt`."""
        a = self.agents.get(aid)
        since = a.since if a is not None else (attempt_view.since(attempt) if attempt else None)
        cached: list[CodexRead] = []

        def turn() -> CodexRead:
            if cached:
                return cached[0]
            assert attempt is not None
            read = turn_read(attempt, self.home)
            self.undecided.append(codex_line(aid, read))
            if read.end in (CodexEnd.LIVE, CodexEnd.UNKNOWN):
                self.held.add(aid)
            cached.append(read)
            return read

        return AttemptFacts(
            turn, lambda rollout, unknown: self.written(aid, since, rollout, unknown),
            descendants=descendants, working=aid in self.live,
            outlived=a is not None and outlived(a, self.closes),
            limited=a is not None and a.waits is Waits.LIMITED)

    def written(self, aid: str, since: float | None, rollout: Path | None, unknown: bool) -> Written:
        """The latest write of the sources of the attempt `aid`, floored at
        `since` where it is unknown or native."""
        fault = None
        try:
            path = launched_find(aid)
        except SUBJECT_FAULTS as exc:
            path, fault = None, exc
        native = None
        if path is None and fault is None:
            import codex_reads
            native = codex_reads.native_find(aid)
        if rollout is None and native is not None and native.state.get("native"):
            rollout = rollout_of(native.state["native"], self.home)
        w = latest_write(aid, path, self.listing, rollout,
                         since if unknown or native is not None else None)
        if fault is None:
            return w
        if not unknown:
            self.undecided.append(mctx("{run}: its quiet time cannot be read ({error}), "
                                       "so it is left out of quiet agents").format(run=aid, error=fault))
        missing = mctx("its transcript was not found")
        return Written(w.time, (mctx("its transcript cannot be read ({error})").format(error=fault),
                                *(x for x in w.limits if x != missing)))


def launcher_ended(aid: str, home: Path | None = None) -> bool:
    """Whether the record of the attempt `aid` shows it ended, by the state
    `attempt_state` decides with no transcript fact beside it."""
    return isinstance(StateReads(projection([aid]), [], frozenset(), home, []).state(aid), Ended)


def turn_read(attempt: Attempt, home: Path | None = None) -> CodexRead:
    """The read of the accepted turns of `attempt` that its record gives no
    end. A held work lock of its seat, or a turn in progress that the shared
    Codex daemon gives (`codex_daemon.turn_status`), is `LIVE`; a thread or a
    daemon that cannot be read, or a lock that cannot be probed, is `UNKNOWN`;
    and a daemon that gives each turn done, or omits it with no other turn in
    progress, is terminal evidence, `DEAD`. A turn in progress holds it over
    an unreadable turn, which holds it over terminal evidence."""
    import codex_daemon
    from attempt_record import lock_held, seat_path

    assert attempt.launch is not None
    scratch = Path(attempt.launch.scratch) if attempt.launch.scratch else None
    open_turns = [e for e in attempt.events
                  if isinstance(e, events.Accepted) and e.reservation in attempt.unresolved]
    try:
        if lock_held(seat_path(attempt.launch.seat)):
            return CodexRead(CodexEnd.LIVE, mctx("its work lock is held"), scratch,
                             rollout_of(open_turns[-1].thread, home))
    except SUBJECT_FAULTS as exc:
        return unknown_read(mctx("its work lock cannot be read; {error}").format(error=exc), scratch,
                            open_turns[-1].thread, home)
    unreadable: CodexRead | None = None
    for turn in open_turns:
        try:
            status = codex_daemon.turn_status(turn.thread, turn.turn)
        except SUBJECT_FAULTS as exc:
            unreadable = unreadable or unknown_read(
                mctx("its record shows no end of its turn; {error}").format(error=exc),
                scratch, turn.thread, home)
            continue
        if status == "inProgress":
            return CodexRead(CodexEnd.LIVE, mctx("the Codex daemon gives its turn in progress"),
                             scratch, rollout_of(turn.thread, home))
    return unreadable or CodexRead(
        CodexEnd.DEAD, mctx("the Codex daemon gives each turn its record shows open as over, "
                            "or does not list it"), scratch)


def rollout_of(thread: str, home: Path | None) -> Path | None:
    """The Codex rollout of `thread` under `home`, or None where the lookup
    cannot find it."""
    import codex_rollout

    try:
        return codex_rollout.rollout_path(thread, home or Path.home())
    except SUBJECT_FAULTS:
        return None


def unknown_read(why: str, scratch: Path | None, thread: str | None,
                 home: Path | None) -> CodexRead:
    """The `CodexEnd.UNKNOWN` read of an attempt for `why`, with the scratch
    directory `scratch` and Codex thread `thread` recovered so far, and
    from them its rollout, where the rollout lookup finds it: the thread of
    `scratch` where `thread` is None. What it could not recover is in its
    `limits`."""
    import codex_rollout

    limits: list[str] = []
    rollout = None
    try:
        if thread is None and scratch is not None:
            thread = codex_rollout.saved_thread(scratch)
        if thread is None:
            limits.append(mctx("its Codex rollout is not known"))
        else:
            rollout = codex_rollout.rollout_path(thread, home or Path.home())
    except SUBJECT_FAULTS as exc:
        limits.append(mctx("its Codex rollout cannot be located ({error})").format(error=exc))
    return CodexRead(CodexEnd.UNKNOWN, why, scratch, rollout, tuple(limits))


def codex_line(agent: str, read: CodexRead) -> str:
    """The stable undecided line for an attempt whose accepted turn has no
    recorded end."""
    match read.end:
        case CodexEnd.DEAD:
            return mctx("{run}: {why}, so the attempt counts as ended"
                        ).format(run=agent, why=read.why)
        case CodexEnd.LIVE:
            return mctx("{run}: its Codex turn runs ({why}), so the attempt counts as running"
                        ).format(run=agent, why=read.why)
        case CodexEnd.UNKNOWN:
            return f"{agent}: {unknown_text(read)}"
        case CodexEnd.DONE:
            raise ValueError("a completed Codex attempt has no undecided line")


def stuck_read(session: str, quiet: Mapping[str, float], now_watched: Sequence[Watched],
               running_work: Mapping[str, tuple[str, ...]],
               unknown: Mapping[str, str] | None = None) -> dict[str, Stuck]:
    """`TranscriptsRead.stuck` of the agents of `quiet` and `now_watched`,
    where `running_work` gives the command lines of each agent's work
    still running, and `unknown`, where given, the diagnostic of each held
    attempt of unknown state (`EndsRead.unknown`). A watched agent's
    `Watched.stuck` stands in place of its time in `quiet`."""
    known = unknown or {}
    return {aid: Stuck(session, q, running_work.get(aid, ()), known.get(aid))
            for aid, q in [*quiet.items(), *((w.agent_id, w.stuck) for w in now_watched)]
            if q is not None}


def undecided_lines(me: str, runs: list[tuple[str, Path]], agents: Sequence[Agent],
                    others: Sequence[Agent], took_up: frozenset[str],
                    ended: Mapping[str, Report | None], ungiven: list[str]) -> list[str]:
    """The lines of `ungiven`, the undecided lines that no final reply of
    an earlier operator gave (`not_given`), that `MonitorState.undecided`
    gives: each on a run or an agent the read knows, and whose text a step
    of `me` still reads (`text_readers`) or is not gone."""
    known = {a.agent_id for a in (*agents, *others) if a.agent_id} | {aid for aid, _ in runs}
    readers = text_readers(me, took_up, ended, agents)
    return [line for line in ungiven
            if (where := line_where(line)) in known and (where in readers or not gone_line(line))]


def not_given(lines: list[str], given: set[str]) -> list[str]:
    """Each line of `lines` once, other than one whose `unknown_line` the
    lines `given` of earlier final replies hold."""
    return [line for line in dict.fromkeys(lines) if unknown_line(line) not in given]


def line_where(line: str) -> str:
    """The run or the agent the `undecided` line `line` is on: the text
    before its first `:`."""
    return line.split(":", 1)[0]


def text_readers(me: str, took_up: frozenset[str], ended: Mapping[str, Report | None],
                 agents: Sequence[Agent]) -> frozenset[str]:
    """The runs and agents whose texts a step of `me` still reads: `me`, the
    operators it takes up, the agents whose report the read hands to `me`,
    and each agent one of those launched. A gone file of any other text
    leaves no `undecided` line in the reply."""
    out = {me, *took_up, *ended}
    while added := {a.agent_id for a in agents
                    if a.agent_id and a.agent_id not in out and a.operator in out}:
        out |= added
    return frozenset(out)
