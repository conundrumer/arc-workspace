"""The reads the assembly of the operator's state (`state_assembly`) takes
beside the reads of the tracker, git and the transcripts: the ends of the
operators' agents, with the quiet and the stuck ones."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from filed_texts import gone_line
from monitor_reads import watched
from open_agents import Listed, quiet_since, turn_ended_idle
from agent_ends import ended_by, ended_elsewhere, ended_with, reply_to, stalled_reports
from transcripts import launched_find

from operations.monitor import Watched
from operations.plan import unknown_line
from operations.state import (
    Agent,
    Report,
    Waits,
    Stuck,
)


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
    `TranscriptsRead.quiet`."""
    agents: tuple[Agent, ...]
    ended: Mapping[str, Report | None]
    stalled: Mapping[str, Report]
    quiet: Mapping[str, float]


def ends_read(agents: Sequence[Agent], me: str, listing: list[Listed],
              now_watched: Sequence[Watched], now: float, undecided: list[str]) -> EndsRead:
    """`agents`, each pending one ended where a stall alert fired on it, where
    it is of another operator whose work is no longer open
    (`ended_elsewhere`), or where it waits as at work or still running and
    its own transcript shows its turn ended with no work
    of its own still running (`turn_ended_idle`). An agent so ended is left
    out of the `quiet` it returns, so no stuck alert names it. A watched agent that
    no operator launched, and that the coordinator launched, has its stall
    read too."""
    launched = {a.agent_id for a in agents if a.agent_id}
    watched_ids = {w.agent_id for w in now_watched}
    coordinators = {aid: x.launch.since for x in listing
                    if (aid := x.launch.agent) in watched_ids and aid not in launched}
    stalled = stalled_reports(list(agents), coordinators,
                              [w.agent_id for w in now_watched if w.stalled is not None])
    ended: dict[str, Report | None] = {**ended_elsewhere(list(agents), me, undecided), **stalled}
    quiet = quiet_read([a for a in agents if a.agent_id not in ended], listing, now)
    idle = turn_ended_idle(listing)
    ended_idle = [a for a in agents if a.waits in (Waits.AT_WORK, Waits.STILL_RUNNING)
                  and a.agent_id is not None and a.agent_id not in ended and a.agent_id in idle]
    ended.update({a.agent_id: reply_to(ended_with(a, None), a.since, undecided) for a in ended_idle
                  if a.agent_id is not None})
    quiet = {aid: q for aid, q in quiet.items() if aid not in ended}
    return EndsRead(tuple(ended_by(agents, ended)), ended, stalled, quiet)


def quiet_read(agents: Sequence[Agent], listing: list[Listed], now: float) -> dict[str, float]:
    """`TranscriptsRead.quiet` of `agents`. An agent the usage limit stopped
    is left out, since `limit_resume` covers it, and so is an agent whose
    transcript is not found."""
    out: dict[str, float] = {}
    for a in agents:
        if a.agent_id is None or a.waits in (None, Waits.LIMITED):
            continue
        path = launched_find(a.agent_id)
        if path is None:
            continue
        q = quiet_since(a.agent_id, path, listing, now)
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
