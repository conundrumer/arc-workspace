"""The reads the assembly of the operator's state (`state_assembly`) takes
beside the reads of the tracker, git and the transcripts: the ends of the
operators' agents, with the quiet and the stuck ones."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path

from filed_texts import filed_report, gone_line
from monitor_reads import watched
from open_agents import Listed, latest_write, turn_ended_idle
from agent_ends import elsewhere_ended, ended_with, reply_to, stalled_reports
from transcripts import launched_find
from transcript_snapshots import SUBJECT_FAULTS

from controlled_markdown import mctx

from operations.completion import latest_sends, refusal_of
from operations.constants import STUCK_SECONDS, stuck_reached
from operations.liveness import (
    AttemptFacts, CodexEnd, CodexRead, Written, attempt_state, unknown_text)
from operations.monitor import Watched
from operations.plan import unknown_line
from operations.roles import Role, analyst_of, subjects
from operations.state import (
    Agent,
    Call,
    Ended,
    Report,
    Running,
    Ticket,
    Unknown,
    Waits,
    Stuck,
)
from ticketing.vocabulary import Status


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
    reports that end those whose sign was pending, by agent id, or None
    where an end adds none (`ended`), the part of those of stalled agents
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


def ends_read(agents: Sequence[Agent], me: str, listing: list[Listed],
              now_watched: Sequence[Watched], now: float, undecided: list[str],
              *, closes: Mapping[str, float], calls: Sequence[Call] = ()) -> EndsRead:
    """`agents` with each one's state decided (`attempt_reads`), where the
    stall alerts of `now_watched` and the listing give its facts. A watched
    agent that no operator launched, and that the coordinator launched, has
    its stall read too: `stalled` gives it with the stalled attempts. An
    attempt that ends is left out of the `quiet` it returns, so no stuck
    alert names it."""
    idle = turn_ended_idle(listing)
    live = frozenset(x.launch.agent for x in listing if x.launch.agent is not None
                     and x.launch.agent not in idle)
    waiting = [replace(a, state=Running(Waits.STILL_RUNNING))
               if a.agent_id in live and not a.pending else a for a in agents]
    launched = {a.agent_id for a in agents if a.agent_id}
    watched_ids = {w.agent_id for w in now_watched}
    coordinators = {aid: x.launch.since for x in listing
                    if (aid := x.launch.agent) in watched_ids and aid not in launched}
    stalls = stalled_reports(waiting, coordinators,
                             [w.agent_id for w in now_watched
                              if w.stalled is not None and w.agent_id not in live], undecided)
    read = attempt_reads(agents, me, calls, undecided, listing=listing, closes=closes,
                         stalls=stalls, idle=idle, live=live)
    signed = {a.agent_id for a in waiting if a.pending}
    ended = {a.agent_id: a.state.report for a in read.agents
             if isinstance(a.state, Ended) and a.agent_id in signed and a.agent_id is not None}
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
    Codex turn runs or is unknown."""
    agents: tuple[Agent, ...]
    held: frozenset[str]


def attempt_reads(agents: Sequence[Agent], me: str, calls: Sequence[Call], undecided: list[str],
                  *, listing: list[Listed] | None = None, closes: Mapping[str, float] | None = None,
                  stalls: Mapping[str, Report] | None = None,
                  idle: frozenset[str] = frozenset(),
                  live: frozenset[str] = frozenset()) -> AttemptsRead:
    """`agents`, each with its `state` decided by `attempt_state` from the
    facts the reads gather on it: the `listing` of the running agents, of
    which `live` are those with work running and `idle` those whose turn
    ended idle; `closes` (`closes_of`), the `stalls` the stall alerts gave
    reports for, whether each is of an operator other than `me` whose work
    is no longer open (`elsewhere_ended`), its Codex read (`codex_end`),
    its write times (`latest_write`), and the SendMessage `calls`
    (`completion.refusal_of`). An attempt that ends with a sign that was
    pending takes the report its end gives (`Ended.report`)."""
    held: set[str] = set()
    out: list[Agent] = []
    sends = latest_sends(calls)
    for a in agents:
        state = attempt_state(attempt_facts(a, me, sends, undecided, listing or [], closes or {},
                                            stalls or {}, idle, live, held))
        if isinstance(state, Ended) and a.pending:
            ending = filed_report(ended_with(a, state.report))
            out.append(replace(ending, state=state))
        else:
            out.append(replace(a, state=state))
    return AttemptsRead(tuple(out), frozenset(held))


def attempt_facts(a: Agent, me: str, sends: Mapping[str, Call], undecided: list[str],
                  listing: list[Listed], closes: Mapping[str, float],
                  stalls: Mapping[str, Report], idle: frozenset[str], live: frozenset[str],
                  held: set[str]) -> AttemptFacts:
    """`AttemptFacts` of `a`, for `attempt_reads`, with the latest SendMessage
    calls `sends` (`completion.latest_sends`), which `held` gets the
    agent id of where its Codex read is `LIVE` or `UNKNOWN`."""
    aid = a.agent_id
    listed = aid is not None and aid in live
    sign = a.waits
    elsewhere = (not listed and sign is not None and a.operator != me
                 and elsewhere_ended(a, me, undecided))
    stalled = aid is not None and aid in stalls

    def report() -> Report | None:
        if aid is not None and aid in stalls:
            return stalls[aid]
        if sign is None:
            return None
        return reply_to(ended_with(a, None), a.launched if elsewhere else a.since, undecided)

    cached: list[CodexRead] = []

    def codex() -> CodexRead:
        if cached:
            return cached[0]
        read = codex_end(aid) if aid is not None else CodexRead(CodexEnd.DONE)
        if aid is not None and read.end is not CodexEnd.DONE:
            undecided.append(codex_line(aid, read))
        if read.end in (CodexEnd.LIVE, CodexEnd.UNKNOWN) and aid is not None:
            held.add(aid)
        cached.append(read)
        return read

    def written(rollout: Path | None, unknown: bool) -> Written:
        fault = None
        try:
            path = launched_find(aid) if aid is not None else None
        except SUBJECT_FAULTS as exc:
            path, fault = None, exc
        native = None
        if path is None and fault is None and aid is not None:
            import codex_reads
            native = codex_reads.native_find(aid)
        if rollout is None and native is not None and native.state.get("native"):
            rollout = rollout_of(native.state["native"], None)
        w = latest_write(aid or "", path, listing, rollout,
                         a.since if unknown or native is not None else None)
        if fault is None:
            return w
        if not unknown:
            undecided.append(mctx("{run}: its quiet time cannot be read ({error}), "
                                  "so it is left out of quiet agents").format(run=aid, error=fault))
        missing = mctx("its transcript was not found")
        return Written(w.time, (mctx("its transcript cannot be read ({error})").format(error=fault),
                                *(x for x in w.limits if x != missing)))

    refused = refusal_of(aid, a.since, a.reports, sends) if aid is not None else None
    if aid is not None and refused is not None and (ending := report()) is not None:
        refused = refusal_of(aid, a.since, (*a.reports, ending), sends)
    return AttemptFacts(sign, report, codex, written, refused, listed,
                        idle=aid is not None and aid in idle, stalled=stalled,
                        outlived=aid is not None and outlived(a, closes), elsewhere=elsewhere)


def codex_end(agent: str, home: Path | None = None) -> CodexRead:
    """An enrolled attempt ends with a current receipt or a terminal store state.

    A completed walk ends a legacy attempt, and a validated receipt ends a
    native one; otherwise its thread decides whether
    it can end: a turn its rollout gives as open runs only where the shared
    Codex daemon gives it in progress (`codex_daemon.turn_status`). A thread
    or a daemon that cannot be read, or a daemon that gives no such turn,
    holds the attempt. A native attempt with no accepted turn ends only once
    its reservation is `STUCK_SECONDS` old."""
    import codex_daemon
    import codex_reads
    import codex_rollout
    from codex_ticket import Phase
    from entry_reads import entries_forward
    from operations.roles import CODEX_LAUNCHER
    from run_reads import agent_type, role_type

    try:
        native = codex_reads.native_find(agent)
        if native is not None:
            try:
                receipt = codex_reads.native_receipt(native, home)
            except SUBJECT_FAULTS:
                receipt = None
            if receipt is None and native.state["phase"] == Phase.ENDED:
                return CodexRead(CodexEnd.DEAD, native.state["status"], native.assignment.scratch)
            if receipt is not None:
                return CodexRead(CodexEnd.DONE)
            scratch = native.assignment.scratch
            thread, turn = native.state["native"], native.state["turn"]
            if thread is None or turn is None:
                import time
                from operations.constants import stuck_reached
                why = "native assignment has no accepted turn"
                reserved = native.state.get("reserved")
                dead = reserved is not None and stuck_reached(reserved, time.time())
                if dead:
                    return CodexRead(CodexEnd.DEAD, why, scratch)
                return unknown_read(why, scratch, None, home)
            try:
                status = codex_daemon.turn_status(thread, turn)
            except SUBJECT_FAULTS as exc:
                return unknown_read(
                    f"native assignment has no current validated result; {exc}", scratch, thread,
                    home)
            live = status == "inProgress"
            return CodexRead(CodexEnd.LIVE if live else CodexEnd.DEAD,
                             "native assignment has no current validated result", scratch,
                             rollout_of(thread, home) if live else None)
    except SUBJECT_FAULTS as exc:
        return unknown_read(str(exc), None, None, home)

    path = launched_find(agent)
    if path is None:
        return CodexRead(CodexEnd.DONE)
    try:
        if agent_type(path) != CODEX_LAUNCHER:
            return CodexRead(CodexEnd.DONE)
        entries = list(entries_forward(path))
    except SUBJECT_FAULTS as exc:
        return unknown_read(str(exc), None, None, home)
    try:
        kind = role_type(path)
        if kind is None:
            raise ValueError("the Codex role is unknown")
        codex_reads.walk_entries(entries, kind)
        return CodexRead(CodexEnd.DONE)
    except SUBJECT_FAULTS as exc:
        why = str(exc)
    scratch = None
    try:
        dirs = [d for e in entries for _, _, d in codex_reads.commands(e)]
        if not dirs:
            return CodexRead(CodexEnd.DEAD, why)
        scratch = dirs[-1]
        if not (scratch / "codex-session").exists():
            return CodexRead(CodexEnd.DEAD, why, scratch)
        rollout = codex_rollout.read(scratch, home or Path.home())
        if rollout.turn is None:
            return CodexRead(CodexEnd.DEAD, why, scratch)
        status = codex_daemon.turn_status(rollout.thread, rollout.turn)
        live = status == "inProgress"
        return CodexRead(CodexEnd.LIVE if live else CodexEnd.DEAD, why, scratch,
                         rollout_of(rollout.thread, home) if live else None)
    except SUBJECT_FAULTS as exc:
        return unknown_read(f"{why}; {exc}", scratch, None, home)


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
    """The stable undecided line for an attempt without a completed walk."""
    match read.end:
        case CodexEnd.DEAD:
            return mctx("{run}: its Codex launch has no completed turn record ({why}), "
                        "and no Codex turn runs on its thread, so the attempt counts as ended"
                        ).format(run=agent, why=read.why)
        case CodexEnd.LIVE:
            return mctx("{run}: the Codex daemon gives a turn in progress on its thread "
                        "in {scratch} after its launcher ended, so the attempt counts as running"
                        ).format(run=agent, scratch=read.scratch)
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
