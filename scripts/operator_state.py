"""The reads the assembly of the operator's state (`state_assembly`) takes
beside the reads of the tracker, git and the transcripts: the ends of the
operators' agents, with the quiet and the stuck ones, and the holders of
assigned tickets."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path

from filed_texts import gone_line
from git_session_reads import given_lines
from monitor_reads import watched
from open_agents import Listed, quiet_since, work_open
from operator_reads import (
    ended_by,
    ended_elsewhere,
    stalled_reports,
)
from transcripts import find, is_subagent
from transcript_entries import Refused
from tree_reads import (
    fragments,
    gate_outputs,
)

from operations.changes import holds
from operations.monitor import Watched
from operations.plan import elsewhere, unknown_line
from operations.state import (
    Agent,
    Call,
    GitRead,
    HeldRead,
    ReadOnUse,
    Report,
    Waits,
    State,
    Stuck,
    Ticket,
)
from operations.worktrees import worktree_in
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
    `TranscriptsRead.quiet`."""
    agents: tuple[Agent, ...]
    ended: Mapping[str, Report | None]
    stalled: Mapping[str, Report]
    quiet: Mapping[str, float]


def ends_read(agents: Sequence[Agent], me: str, listing: list[Listed],
              now_watched: Sequence[Watched], now: float, undecided: list[str]) -> EndsRead:
    """`agents`, each pending one ended where a stall alert fired on it, where
    it is of another operator whose work is no longer open
    (`ended_elsewhere`), or where it stopped with work of its own still
    running and is quiet. A watched agent that no operator launched, and
    that the coordinator launched, has its stall read too."""
    launched = {a.agent_id for a in agents if a.agent_id}
    watched_ids = {w.agent_id for w in now_watched}
    coordinators = {aid: x.launch.since for x in listing
                    if (aid := x.launch.agent) in watched_ids and aid not in launched}
    stalled = stalled_reports(list(agents), coordinators,
                              [w.agent_id for w in now_watched if w.stalled is not None])
    ended: dict[str, Report | None] = {**ended_elsewhere(list(agents), me, undecided), **stalled}
    quiet = quiet_read([a for a in agents if a.agent_id not in ended], listing, now)
    ended.update(dict.fromkeys(aid for a in agents if a.waits is Waits.STILL_RUNNING
                               and (aid := a.agent_id) is not None and aid in quiet))
    return EndsRead(tuple(ended_by(agents, ended)), ended, stalled, quiet)


def quiet_read(agents: Sequence[Agent], listing: list[Listed], now: float) -> dict[str, float]:
    """`TranscriptsRead.quiet` of `agents`. An agent the usage limit stopped
    is left out, since `limit_resume` covers it, and so is an agent whose
    transcript is not found."""
    out: dict[str, float] = {}
    for a in agents:
        if a.agent_id is None or a.waits in (None, Waits.LIMITED):
            continue
        try:
            path = find(a.agent_id)
        except Refused:
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


def undecided_lines(me: str, runs: list[tuple[str, Path]], calls: Sequence[Call],
                    agents: Sequence[Agent], others: Sequence[Agent], took_up: frozenset[str],
                    ended: Mapping[str, Report | None], undecided: list[str]) -> list[str]:
    """The lines of `undecided` that `MonitorState.undecided` gives: each
    on a run or an agent the read knows, that no final reply of an
    earlier operator gave (`given_lines`), and whose text a step of `me`
    still reads (`text_readers`) or is not gone."""
    known = {a.agent_id for a in (*agents, *others) if a.agent_id} | {aid for aid, _ in runs}
    given = given_lines(runs, me, list(calls))
    readers = text_readers(me, took_up, ended, agents)
    return [line for line in dict.fromkeys(undecided)
            if (where := line.split(":", 1)[0]) in known and unknown_line(line) not in given
            and (where in readers or not gone_line(line))]


@dataclass(frozen=True)
class HoldersRead:
    """The transcript of each holder of an assigned ticket (`found`), those
    of them whose work is open (`State.open_holders`), and
    `State.session_holders`."""
    found: Mapping[str, Path]
    open: frozenset[str]
    session: frozenset[str]


def holders_read(tickets: Mapping[str, Ticket], session: str, main_path: Path,
                 sessions_running: frozenset[str] | None) -> HoldersRead:
    """`HoldersRead` of `tickets`, where `main_path` is the transcript of
    `session`. A holder that is a session is open where
    `sessions_running` gives it, and any other where its work is open."""
    holders = {t.holder for t in tickets.values() if t.status is Status.ASSIGNED and t.holder}
    found = {h: find(h) for h in sorted(holders)}
    open_paths = {h: p for h, p in found.items()
                  if (h in sessions_running if sessions_running is not None
                      and not is_subagent(p) else work_open(p, []))}
    return HoldersRead(found, frozenset(open_paths), frozenset(
        h for h, p in open_paths.items()
        if p == main_path or p.is_relative_to(main_path.parent / session)))


def with_quiet_holders(state: State, found: Mapping[str, Path], listing: list[Listed],
                       running_work: Mapping[str, tuple[str, ...]]) -> State:
    """`state` with each live holder of a ticket of `plan.elsewhere` that is
    quiet in `TranscriptsRead.stuck`, where `found` gives each holder's
    transcript."""
    stuck = state.transcripts.stuck
    holders = dict.fromkeys(h for n in elsewhere(state)
                            if (h := state.tracker.tickets[n].holder) is not None
                            and h not in stuck)
    quiet = {h: q for h in holders
             if (q := quiet_since(h, found[h], listing, state.now)) is not None}
    added = stuck_read(state.session, quiet, (), running_work)
    return replace(state, transcripts=replace(state.transcripts, stuck={**stuck, **added}))


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


def read_held(tickets: Mapping[str, Ticket], me: str, tree: GitRead) -> HeldRead:
    """The read of the worktrees of the tickets of `tickets` that `me`
    holds."""
    trees = {w for t in tickets.values() if holds(t, me)
             and (w := worktree_in(t, tree.worktrees)) is not None}
    return HeldRead(gate_outputs=ReadOnUse(sorted(trees), gate_outputs),
                    fragments=ReadOnUse(sorted(trees), fragments))
