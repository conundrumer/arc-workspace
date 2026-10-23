"""The agents a run launched and the runs under it, as
`profile_runs.py --help running` and `profile_runs.py --help under` give
them: the launches of a session's agents by the Agent call of each, the
launches of a run with the time each was last resumed, and the agents a
run launched or resumed."""

from collections.abc import Callable, Collection
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from agent_reports import ENDED, AgentEntry, Report, last_sign, received_entries, reports_after
from command_labels import AGENT_TOOLS
from controlled_markdown import mctx
from run_reads import (blocks, in_background, meta_parent, parent_label, read_meta,
                       results_by_call, run_sessions, session_agents)
from state_reads import DERIVED, Kept, state_cache
from transcripts import agent_id, chain, held_find, launched_find
from entry_reads import line_entries
from transcript_entries import epoch
from transcript_folds import Makes, fold
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
    gives none, and otherwise as `transcripts.launched_find` gives it."""
    return held_find(aid) if held else launched_find(aid)


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


@dataclass(slots=True)
class Launch:
    """An agent a run launched: its agent id, where the run's transcript
    gives it, its transcript, where one gives the call as its launch, the
    time of the run's call that launched it, or in `launched` of the last
    call that resumed it, by the run or by any agent of the run's sessions,
    the time of the last sign in those sessions that it reported, or None
    where they hold none, the id of the call that launched it, and the
    matched report and end entries across the launcher and child's sessions,
    and whether the run's transcripts hold a result of that call."""
    agent: str | None
    path: Path | None
    since: float
    done: float | None
    call: str
    entries: tuple[AgentEntry, ...]
    answered: bool = True

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
    error. Result entries are kept as line references."""
    calls: list[tuple[str, dict[str, Any]]] = field(default_factory=list)
    results: dict[str, tuple[Path, int]] = field(default_factory=dict)
    answered: dict[str | None, float] = field(default_factory=dict)
    failed: set[str] = field(default_factory=set)

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


_made: Makes[Launch | None] = Makes()
"""The launches `launches` last made for each run, by the id of their
call."""


type Received = Callable[[Path, Path | None, str | None, str], tuple[AgentEntry, ...]]
"""The report and end entries of the agent a call launched, given the
launching run's transcript, the agent's transcript where one gives the call
as its launch, the agent id and the call's id."""


def session_entries(path: Path, child: Path | None, aid: str | None,
                    call: str) -> tuple[AgentEntry, ...]:
    """`received_entries` over the sessions of the launcher at `path` and of
    its child at `child`."""
    sessions = tuple(dict.fromkeys(s for p in (path, child) if p for s in run_sessions(p)))
    return received_entries(sessions, aid, call)


@state_cache(DERIVED, notes="undecided", kept=Kept.DISK)
def launches(path: Path, undecided: list[str],
             received: Received = session_entries) -> list[Launch]:
    """The agents the run at `path` launched, in the order of their launch.
    Report and end signs are read from the entries `received` gives, by
    default across the launcher and child sessions.
    Launch results remain tied to the launcher's call. An Agent call whose
    result is an error launched no agent,
    unless a transcript gives it as its launch or its result gives an
    `agentId`. A launch is made anew only where a value it is made from
    changed since the last read on the same fold. An Agent call that the
    transcripts give more than once is one launch, from its first entry."""
    read = fold(LaunchLines.step, LaunchLines, path, chain(path))
    making = _made.read(path, read)
    out: list[Launch] = []
    taken: set[str] = set()
    for at, b in read.calls:
        tid = b.get("id", "")
        if tid in taken:
            continue
        taken.add(tid)
        child = launched_by(path, tid)
        launch = making.item(
            tid, lambda _: (read.results.get(tid), child, tid in read.failed,
                            read.answered.get(tid)),
            lambda lines: make_launch(path, read, at, tid, child, lines), undecided)
        if launch is not None:
            entries = received(path, child, launch.agent, tid)
            sign = last_sign(entries, launch.since, {v for v in (launch.agent, tid) if v})
            done = (sign[1] if sign[0] in ENDED else None) if sign else launch.done
            if child is None and launch.agent is None and done is None and launch.answered:
                undecided.append(mctx("{run}: no transcript gives call {call} as "
                                      "its launch").format(run=path.stem, call=tid))
            out.append(replace(launch, entries=entries, done=done))
    return out


def make_launch(path: Path, read: LaunchLines, at: str, tid: str, child: Path | None,
                lines: list[str]) -> Launch | None:
    """The launch the Agent call `tid` at `at` of the run at `path` made, as
    `launches` gives it, where `child` is the transcript that gives the call
    as its launch, with the `undecided` lines its making gives added to
    `lines`."""
    given = (results_by_call(line_entries(*read.results[tid])).get(tid)
             if tid in read.results else None)
    background = given is not None and in_background(given, lines, tid)
    result = given or {}
    aid = agent_id(child) if child else result.get("agentId")
    if tid in read.failed and child is None and "agentId" not in result:
        return None
    done = None if background else read.answered.get(tid)
    launch = Launch(aid, child, epoch(at), done, tid, (), answered=tid in read.answered)
    return launch


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


def launched_or_resumed(path: Path, undecided: list[str], before: float | None = None) -> set[str]:
    """Agents this run launched or resumed, optionally before a time.
    Another run's later resume does not remove an agent from this set."""
    return ({a.agent for a in launches(path, undecided)
             if a.agent and (before is None or a.since < before)}
            | set(resumes(path, undecided, before)))
