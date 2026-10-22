"""The reads the assembly of the operator's state (`state_assembly`) takes
beside the reads of the tracker, git and the transcripts: the ends of the
operators' agents, with the quiet and the stuck ones."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from enum import StrEnum
from pathlib import Path

from filed_texts import gone_line
from monitor_reads import watched
from open_agents import Listed, quiet_since, turn_ended_idle
from agent_ends import ended_by, ended_elsewhere, ended_with, reply_to, stalled_reports
from transcripts import launched_find
from transcript_snapshots import SUBJECT_FAULTS

from controlled_markdown import mctx

from operations.monitor import Watched
from operations.plan import unknown_line
from operations.roles import Role, analyst_of, subjects
from operations.state import (
    Agent,
    Report,
    Ticket,
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
    """The operators' agents with their ends read (`ends_read`), the reports
    that end them, by agent id, or None where none does (`ended`), the
    part of those of stalled agents (`TranscriptsRead.stalled`), and
    `TranscriptsRead.quiet`, and the attempts held while their Codex turn
    runs or is unknown (`held`), which raise no stall alert."""
    agents: tuple[Agent, ...]
    ended: Mapping[str, Report | None]
    stalled: Mapping[str, Report]
    quiet: Mapping[str, float]
    held: frozenset[str] = frozenset()


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
              *, closes: Mapping[str, float]) -> EndsRead:
    """`agents`, each pending one ended where a stall alert fired on it, where
    it is of another operator whose work is no longer open
    (`ended_elsewhere`), or where it waits as at work or still running and
    its own transcript shows its turn ended with no work
    of its own still running (`turn_ended_idle`). An agent so ended is left
    out of the `quiet` it returns, so no stuck alert names it. A watched agent that
    no operator launched, and that the coordinator launched, has its stall
    read too. Work still running takes precedence over a turn-ending
    notification or a stall: that attempt stays pending. An ended Codex
    attempt is held while its turn runs or while that is unknown (`codex_end`).
    An agent each of whose subject's tickets closed after its launch is ended,
    and is not held, unless its work still runs (`outlived`)."""
    idle = turn_ended_idle(listing)
    live = {x.launch.agent for x in listing if x.launch.agent is not None
            and x.launch.agent not in idle}
    agents = tuple(replace(a, waits=Waits.STILL_RUNNING)
                   if a.agent_id in live and not a.pending else a for a in agents)
    done = {a.agent_id for a in agents
            if a.agent_id and a.agent_id not in live and outlived(a, closes)}
    launched = {a.agent_id for a in agents if a.agent_id}
    watched_ids = {w.agent_id for w in now_watched}
    coordinators = {aid: x.launch.since for x in listing
                    if (aid := x.launch.agent) in watched_ids and aid not in launched}
    stalled = stalled_reports(list(agents), coordinators,
                              [w.agent_id for w in now_watched
                               if w.stalled is not None and w.agent_id not in live], undecided)
    ended: dict[str, Report | None] = {
        aid: report for aid, report in
        {**ended_elsewhere(list(agents), me, undecided), **stalled}.items() if aid not in live}
    ended.update({a.agent_id: reply_to(ended_with(a, None), a.since, undecided) for a in agents
                  if a.pending and a.agent_id in done and a.agent_id not in ended
                  and a.agent_id is not None})
    quiet = quiet_read([a for a in agents if a.agent_id not in ended], listing, now, undecided)
    ended_idle = [a for a in agents if a.waits in (Waits.AT_WORK, Waits.STILL_RUNNING)
                  and a.agent_id is not None and a.agent_id not in ended and a.agent_id in idle]
    ended.update({a.agent_id: reply_to(ended_with(a, None), a.since, undecided) for a in ended_idle
                  if a.agent_id is not None})
    quiet = {aid: q for aid, q in quiet.items() if aid not in ended}
    closed = tuple(ended_by(agents, ended))
    by_id = {a.agent_id: a for a in agents if a.agent_id}
    held: set[str] = set()
    for a in closed:
        if a.pending or a.agent_id is None or a.agent_id in done:
            continue
        read = codex_end(a.agent_id)
        if read.end is not CodexEnd.DONE:
            undecided.append(codex_line(a.agent_id, read))
        if read.end in (CodexEnd.LIVE, CodexEnd.UNKNOWN):
            held.add(a.agent_id)
    closed = tuple(hold(by_id[a.agent_id]) if a.agent_id in held else a for a in closed)
    ended = {k: v for k, v in ended.items() if k not in held}
    stalled = {k: v for k, v in stalled.items() if k not in held}
    quiet = {k: v for k, v in quiet.items() if k not in held}
    return EndsRead(closed, ended, stalled, quiet, frozenset(held))


class CodexEnd(StrEnum):
    DONE = "done"
    DEAD = "dead"
    LIVE = "live"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class CodexRead:
    """An attempt's completion or thread state, with the failed walk's reason."""
    end: CodexEnd
    why: str = ""
    scratch: Path | None = None


def codex_end(agent: str, home: Path | None = None) -> CodexRead:
    """An enrolled attempt ends with a current receipt or a terminal store state.

    A completed walk ends a legacy attempt; otherwise its thread decides whether
    it can end: a turn its rollout gives as open runs only where the shared
    Codex daemon gives it in progress (`codex_daemon.turn_status`). A thread
    or a daemon that cannot be read, or a daemon that gives no such turn,
    holds the attempt."""
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
            return (CodexRead(CodexEnd.DONE) if receipt is not None else
                    CodexRead(CodexEnd.UNKNOWN, "native assignment has no current validated result",
                              native.assignment.scratch))
    except SUBJECT_FAULTS as exc:
        return CodexRead(CodexEnd.UNKNOWN, str(exc))

    path = launched_find(agent)
    if path is None:
        return CodexRead(CodexEnd.DONE)
    try:
        if agent_type(path) != CODEX_LAUNCHER:
            return CodexRead(CodexEnd.DONE)
        entries = list(entries_forward(path))
    except SUBJECT_FAULTS as exc:
        return CodexRead(CodexEnd.UNKNOWN, str(exc))
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
        return CodexRead(CodexEnd.LIVE if status == "inProgress" else CodexEnd.DEAD,
                         why, scratch)
    except SUBJECT_FAULTS as exc:
        return CodexRead(CodexEnd.UNKNOWN, f"{why}; {exc}", scratch)


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
            return mctx("{run}: whether a Codex turn runs for it is unknown ({why}), so the "
                        "attempt counts as running; `uv run python scripts/codex_agent.py "
                        "show <scratch>` shows its turn").format(run=agent, why=read.why)
        case CodexEnd.DONE:
            raise ValueError("a completed Codex attempt has no undecided line")


def hold(a: Agent) -> Agent:
    """Keep an attempt's state before ending it, pending while its turn may run."""
    return a if a.pending else replace(a, waits=Waits.STILL_RUNNING)


def quiet_read(agents: Sequence[Agent], listing: list[Listed], now: float,
               undecided: list[str]) -> dict[str, float]:
    """`TranscriptsRead.quiet` of `agents`. An agent the usage limit stopped
    is left out, since `limit_resume` covers it, and so is an agent whose
    transcript is not found or cannot be read."""
    out: dict[str, float] = {}
    for a in agents:
        if a.agent_id is None or a.waits in (None, Waits.LIMITED):
            continue
        try:
            path = launched_find(a.agent_id)
            if path is None:
                continue
            q = quiet_since(a.agent_id, path, listing, now)
        except SUBJECT_FAULTS as exc:
            undecided.append(mctx("{run}: its quiet time cannot be read ({error}), "
                                  "so it is left out of quiet agents"
                                  ).format(run=a.agent_id, error=exc))
            continue
        if q is not None:
            out[a.agent_id] = q
    return out


def stuck_read(session: str, quiet: Mapping[str, float], now_watched: Sequence[Watched],
               running_work: Mapping[str, tuple[str, ...]]) -> dict[str, Stuck]:
    """`TranscriptsRead.stuck` of the agents of `quiet` and `now_watched`,
    where `running_work` gives the command lines of each agent's work
    still running. A watched agent's `Watched.stuck` stands in place of
    its time in `quiet`."""
    return {aid: Stuck(session, q, running_work.get(aid, ()))
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
