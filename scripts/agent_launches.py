"""The agents a run launched and the runs under it, as
`profile_runs.py --help running` and `profile_runs.py --help under` give
them: the launches of a session's agents by the Agent call of each, the
launches of a run with the time each was last resumed, and the agents a
run launched or resumed."""

from collections.abc import Collection
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from agent_reports import AgentEntry, Report, agent_entries, report_ids, reports_after
from command_labels import AGENT_TOOLS
from controlled_markdown import mctx
from run_reads import (blocks, in_background, meta_parent, notified, parent_label, read_meta,
                       results_by_call, run_sessions, session_agents)
from state_reads import DERIVED, Kept, state_cache
from transcripts import agent_id, chain, find, held_find
from entry_reads import line_entries
from transcript_entries import epoch, fold
from transcript_snapshots import Entry
from agent_resumes import note_latest, resumes, session_resumes


@state_cache(DERIVED)
def session_launches(session: Path) -> tuple[dict[str, Path], dict[str, frozenset[str]]]:
    """The transcripts of a session's agents by the Agent call that launched
    each, and the agent ids of the agents each run launched, by its agent
    id, or `MAIN` for the session's main transcript, as their `.meta.json`
    files give them (`agent_launch`)."""
    by_call: dict[str, Path] = {}
    children: dict[str, set[str]] = {}
    for aid, p in session_agents(session).items():
        found = agent_launch(p)
        if found is None:
            continue
        call, last, parent = found
        if call:
            by_call[call] = last
        children.setdefault(parent, set()).add(aid)
    return by_call, {k: frozenset(v) for k, v in children.items()}


@state_cache(DERIVED, kept=Kept.DISK)
def agent_launch(path: Path) -> tuple[str | None, Path, str] | None:
    """The Agent call that launched the run of the subagent whose
    transcript is at `path`, the last transcript of that run, and its
    parent (`meta_parent`), as its `.meta.json` files give them, or None
    where it has none."""
    meta = read_meta(path)
    if meta is None:
        return None
    return meta.get("toolUseId") or None, chain(path)[-1], meta_parent(meta)


def run_launches(path: Path) -> tuple[dict[str, Path], dict[str, frozenset[str]]]:
    """`session_launches` over the sessions of the transcripts of the run
    at `path`."""
    return sessions_launches(tuple(run_sessions(path)))


@state_cache(DERIVED)
def sessions_launches(sessions: tuple[Path, ...]
                      ) -> tuple[dict[str, Path], dict[str, frozenset[str]]]:
    """`session_launches` merged over `sessions`, held once for each set of
    sessions that runs span."""
    if len(sessions) == 1:
        return session_launches(sessions[0])
    by_call: dict[str, Path] = {}
    children: dict[str, frozenset[str]] = {}
    for session in sessions:
        calls, kids = session_launches(session)
        by_call.update(calls)
        for k, v in kids.items():
            children[k] = children.get(k, frozenset()) | v
    return by_call, children


@state_cache(DERIVED, kept=Kept.VALUE)
def launched_by(path: Path, call: str) -> Path | None:
    """The transcript `run_launches` gives the Agent call `call` of the run
    at `path` as its launch, held so that a read derived from it sees no
    launch of another call."""
    return run_launches(path)[0].get(call)


@state_cache(DERIVED, kept=Kept.VALUE)
def children_of(path: Path, label: str) -> frozenset[str]:
    """The agents `run_launches` gives the run `label` as launching, of the
    sessions of the run at `path`, held as `launched_by` is."""
    return run_launches(path)[1].get(label, frozenset())


def run_transcript(aid: str, held: bool) -> Path | None:
    """The transcript of the run `aid`: where `held`, from the agent index
    this state holds alone (`transcripts.held_find`), None where that index
    gives none, and otherwise as `find` gives it."""
    return held_find(aid) if held else find(aid)


def runs_under(path: Path, pending: Collection[str] = frozenset(),
               held: set[Path] | None = None) -> list[Path]:
    """The last transcript of each run under the run at `path`: the agents
    it launched, the agents those launched, and so on, by `run_launches`,
    each as `run_transcript` gives it, leaving out a run it gives none
    for, and the runs under it. A run is read held where its agent id is
    in `pending`, or where the transcript of the run that launched it is
    in `held`, the record of the transcripts read held, which a caller
    may share across walks, and to which each transcript read held is
    added."""
    held = set() if held is None else held
    out: dict[str, Path] = {}
    todo = [path]
    while todo:
        p = todo.pop()
        for aid in sorted(children_of(p, parent_label(p))):
            if aid in out:
                continue
            run_held = p in held or aid in pending
            if (q := run_transcript(aid, run_held)) is not None:
                if run_held:
                    held.add(q)
                out[aid] = q
                todo.append(q)
    return list(out.values())


@dataclass
class Launch:
    """An agent a run launched: its agent id, where the run's transcript
    gives it, its transcript, where one gives the call as its launch, the
    time of the run's call that launched it, or in `launched` of the last
    call that resumed it, by the run or by any agent of the run's sessions,
    the time of the run's last sign that it reported, or None where the
    run holds none, the id of the call that launched it, and the
    `AgentEntry` of each entry of the run's transcripts to which
    `report_ids` gives its agent id or the id of that call."""
    agent: str | None
    path: Path | None
    since: float
    done: float | None
    call: str
    entries: tuple[AgentEntry, ...]

    def reports(self, since: float, undecided: list[str]) -> list[Report]:
        return reports_after(self.entries, since, self.agent, self.call, undecided)

    @property
    def pending(self) -> bool:
        """Whether the agent is pending to the run: the run holds no sign
        that it reported since the call that launched or last resumed it."""
        return self.done is None or self.since > self.done


@dataclass
class LaunchLines:
    """What `launches` reads of a run's entries that have a time: each
    Agent call with its time, the line of each entry that gives a call's
    result, the time each call was answered, the calls whose result is an
    error, the time of each id a notification gives, and the lines of the
    entries to which `report_ids` gives each id. Of the entries that give
    a result or that `report_ids` names only their lines are kept, so that
    no call holds the entries of a long transcript parsed at once."""
    calls: list[tuple[str, dict[str, Any]]] = field(default_factory=list)
    results: dict[str, tuple[Path, int]] = field(default_factory=dict)
    answered: dict[str | None, float] = field(default_factory=dict)
    failed: set[str] = field(default_factory=set)
    told: dict[str, float] = field(default_factory=dict)
    naming: dict[str, list[tuple[Path, int]]] = field(default_factory=dict)

    def step(self, p: Path, i: int, e: Entry) -> None:
        """Add the entry `e` of line `i` of the transcript at `p`."""
        if not e.get("timestamp"):
            return
        kind = e.get("type")
        if kind == "assistant":
            for b in blocks(e, "tool_use"):
                if b.get("name") in AGENT_TOOLS:
                    self.calls.append((e["timestamp"], b))
            return
        if kind == "user":
            for b in blocks(e, "tool_result"):
                self.answered[b.get("tool_use_id")] = epoch(e["timestamp"])
                if b.get("is_error"):
                    self.failed.add(b.get("tool_use_id", ""))
            self.results.update(dict.fromkeys(results_by_call([e]), (p, i)))
        for v in notified(e):
            self.told[v] = epoch(e["timestamp"])
        for v in report_ids(e):
            self.naming.setdefault(v, []).append((p, i))


@dataclass(frozen=True)
class Made:
    """A launch as `launches` made it from an Agent call, with the values it
    was made from: the line of the call's result and the transcript that
    gives the call as its launch (`given`), the values of `LaunchLines`
    the launch reads (`signs`), the agent ids it reads them for, and the
    `undecided` lines its making gave. A launch of None is a call that
    launched no agent."""
    given: tuple[tuple[Path, int] | None, Path | None]
    signs: tuple[object, ...]
    agents: tuple[str, ...]
    launch: Launch | None
    lines: tuple[str, ...]


_made: dict[Path, tuple[LaunchLines, dict[str, Made]]] = {}
"""The launches `launches` last made for each run, by the id of their
call, with the state of the fold they were made from."""


@state_cache(DERIVED, notes="undecided", kept=Kept.DISK)
def launches(path: Path, undecided: list[str]) -> list[Launch]:
    """The agents the run at `path` launched, in the order of their launch.
    A sign that an agent reported is the run's notification of it, or a
    result of its launch that does not say the agent runs in the
    background. An Agent call whose result is an error launched no agent,
    unless a transcript gives it as its launch or its result gives an
    `agentId`. A launch is made anew only where a value it is made from
    changed since the last read on the same fold."""
    read = fold(LaunchLines.step, LaunchLines, path, chain(path))
    held = _made.get(path)
    before = held[1] if held is not None and held[0] is read else {}
    made: dict[str, Made] = {}
    out: list[Launch] = []
    for at, b in read.calls:
        tid = b.get("id", "")
        m = before.get(tid)
        given = (read.results.get(tid), launched_by(path, tid))
        if m is None or m.given != given or m.signs != launch_signs(read, tid, m.agents):
            m = make_launch(path, read, at, tid, given[1])
        made[tid] = m
        undecided.extend(m.lines)
        if m.launch is not None:
            out.append(m.launch)
    _made[path] = read, made
    return out


def launch_signs(read: LaunchLines, call: str, agents: tuple[str, ...]) -> tuple[object, ...]:
    """The values of `read` that the launch of the Agent call `call` is made
    from, other than its result and its transcript, where `agents` are the
    agent ids it reads them for. The lines `naming` gives an id only grow
    along a fold, so their count stands for them."""
    return (call in read.failed, read.told.get(call), read.answered.get(call),
            len(read.naming.get(call, ())),
            *((read.told.get(a), len(read.naming.get(a, ()))) for a in agents))


def make_launch(path: Path, read: LaunchLines, at: str, tid: str, child: Path | None) -> Made:
    """The launch the Agent call `tid` at `at` of the run at `path` made, as
    `launches` gives it, where `child` is the transcript that gives the call
    as its launch."""
    lines: list[str] = []
    given = (results_by_call(line_entries(*read.results[tid])).get(tid)
             if tid in read.results else None)
    background = given is not None and in_background(given, lines, tid)
    result = given or {}
    aid = agent_id(child) if child else result.get("agentId")
    agents = tuple(a for a in (result.get("agentId", ""), aid) if a)
    signs = launch_signs(read, tid, agents)
    if tid in read.failed and child is None and "agentId" not in result:
        return Made((read.results.get(tid), child), signs, agents, None, tuple(lines))
    told = [read.told.get(tid), read.told.get(result.get("agentId", "")),
            None if background else read.answered.get(tid)]
    done = max((t for t in told if t is not None), default=None)
    if child is None and done is None and given is not None:
        lines.append(mctx("{run}: no transcript gives call {call} as "
                          "its launch").format(run=path.stem, call=tid))
    named = dict.fromkeys(line for v in (tid, *([aid] if aid else []))
                          for line in read.naming.get(v, []))
    launch = Launch(aid, child, epoch(at), done, tid,
                    agent_entries((n for p, i in named for n in line_entries(p, i)), aid, tid))
    return Made((read.results.get(tid), child), signs, agents, launch, tuple(lines))


@state_cache(DERIVED)
def launches_by_call(path: Path) -> dict[str, Launch]:
    """`launches` of the run at `path`, by the id of the call of each."""
    return {a.call: a for a in launches(path, [])}


@state_cache(DERIVED)
def launch_of(path: Path, call: str) -> Launch:
    """The launch of `launches` of the run at `path` by the Agent call
    `call`, held so that a read derived from it sees a change only where
    that launch changes."""
    return launches_by_call(path)[call]


def resume_times(path: Path, found: list[Launch], undecided: list[str],
                 before: float | None = None) -> tuple[dict[str, float], dict[str, float]]:
    """The time of the last SendMessage call that resumed each agent: the
    calls of the run at `path`, and the calls of the other runs of its
    sessions that resumed an agent of `found`, the run's launches, or an
    agent the run resumed, with `before` only of the calls earlier than
    it."""
    own = resumes(path, undecided, before)
    agents = {a.agent for a in found if a.agent} | set(own)
    if not agents:
        return own, {}
    since = min([a.since for a in found] + list(own.values()))
    return own, session_resumes(path, agents, since, undecided, before)


def launched(path: Path, undecided: list[str]) -> list[Launch]:
    """`launches` of the run at `path`, each from the last call that resumed
    it where one did."""
    found = launches(path, undecided)
    own, others = resume_times(path, found, undecided)
    return [replace(a, since=max(a.since, own.get(a.agent or "", 0.0),
                                 others.get(a.agent or "", 0.0))) for a in found]


def callees(path: Path, undecided: list[str], before: float | None = None) -> set[str]:
    """The agent ids of the agents whose last launch or resume was a call
    of the run at `path`, so that their reports go to that run, and with
    `before` the same among the calls earlier than it, so that their reports
    go to that run at that time."""
    found = [a for a in launches(path, undecided) if before is None or a.since < before]
    own, others = resume_times(path, found, undecided, before)
    mine = {a.agent: a.since for a in found if a.agent}
    for aid, t in own.items():
        note_latest(mine, aid, t)
    return {aid for aid, t in mine.items() if t >= others.get(aid, 0.0)}
