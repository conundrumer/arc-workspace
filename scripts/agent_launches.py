"""The agents a run launched and the runs under it, as
`profile_runs.py --help running` and `profile_runs.py --help under` give
them: the launches of a session's agents by the Agent call of each, the
launches of a run with the time each was last resumed, and the agents a
run launched or resumed."""

from dataclasses import dataclass, replace
from pathlib import Path

from agent_reports import Report, report_ids, reports_after
from command_labels import AGENT_TOOLS
from controlled_markdown import mctx
from run_reads import (blocks, in_background, meta_parent, notified, parent_label, read_meta,
                       results_by_call, run_sessions, session_agents)
from state_reads import DERIVED, Kept, state_cache
from transcripts import agent_id, chain, find
from transcript_entries import Entry, epoch
from agent_resumes import note_latest, resumes, session_resumes
from session_changes import timed_entries


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


@state_cache(DERIVED)
def run_launches(path: Path) -> tuple[dict[str, Path], dict[str, frozenset[str]]]:
    """`session_launches` over the sessions of the transcripts of the run
    at `path`."""
    by_call: dict[str, Path] = {}
    children: dict[str, frozenset[str]] = {}
    for session in run_sessions(path):
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


def runs_under(path: Path) -> list[Path]:
    """The last transcript of each run under the run at `path`: the agents
    it launched, the agents those launched, and so on, by `run_launches`."""
    out: dict[str, Path] = {}
    todo = [path]
    while todo:
        p = todo.pop()
        for aid in sorted(children_of(p, parent_label(p))):
            if aid not in out:
                out[aid] = find(aid)
                todo.append(out[aid])
    return list(out.values())


@dataclass
class Launch:
    """An agent a run launched: its agent id, where the run's transcript
    gives it, its transcript, where one gives the call as its launch, the
    time of the run's call that launched it, or in `launched` of the last
    call that resumed it, by the run or by any agent of the run's sessions,
    the time of the run's last sign that it reported, or None where the
    run holds none, the id of the call that launched it, and the entries of
    the run's transcripts to which `report_ids` gives its agent id or the
    id of that call."""
    agent: str | None
    path: Path | None
    since: float
    done: float | None
    call: str
    entries: list[Entry]

    def reports(self, since: float, undecided: list[str]) -> list[Report]:
        return reports_after(self.entries, since, self.agent, self.call, undecided)

    @property
    def pending(self) -> bool:
        """Whether the agent is pending to the run: the run holds no sign
        that it reported since the call that launched or last resumed it."""
        return self.done is None or self.since > self.done


@state_cache(DERIVED, notes="undecided", kept=Kept.DISK)
def launches(path: Path, undecided: list[str]) -> list[Launch]:
    """The agents the run at `path` launched, in the order of their launch.
    A sign that an agent reported is the run's notification of it, or a
    result of its launch that does not say the agent runs in the
    background. An Agent call whose result is an error launched no agent,
    unless a transcript gives it as its launch or its result gives an
    `agentId`."""
    entries = timed_entries(path)
    results = results_by_call(entries)
    replies = [(e, b) for e in entries if e.get("type") == "user"
               for b in blocks(e, "tool_result")]
    answered = {b.get("tool_use_id"): epoch(e["timestamp"]) for e, b in replies}
    failed: set[str] = {b.get("tool_use_id", "") for _, b in replies
                        if b.get("is_error")}
    told = {v: epoch(e["timestamp"]) for e in entries
            if e.get("type") != "assistant" for v in notified(e)}
    naming: dict[str, list[Entry]] = {}
    for e in entries:
        for v in report_ids(e):
            naming.setdefault(v, []).append(e)
    out: list[Launch] = []
    for e in entries:
        if e.get("type") != "assistant":
            continue
        for b in blocks(e, "tool_use"):
            if b.get("name") not in AGENT_TOOLS:
                continue
            tid = b.get("id", "")
            given = results.get(tid)
            background = given is not None and in_background(given, undecided, tid)
            result = given or {}
            child = launched_by(path, tid)
            if tid in failed and child is None and "agentId" not in result:
                continue
            signs = [told.get(tid), told.get(result.get("agentId", "")),
                     None if background else answered.get(tid)]
            done = max((t for t in signs if t is not None), default=None)
            aid = agent_id(child) if child else result.get("agentId")
            if child is None and done is None and given is not None:
                undecided.append(mctx("{run}: no transcript gives call {call} as "
                                      "its launch").format(run=path.stem, call=tid))
            named = {id(n): n for v in (tid, *([aid] if aid else []))
                     for n in naming.get(v, [])}
            out.append(Launch(aid, child, epoch(e["timestamp"]), done, tid,
                              list(named.values())))
    return out


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
    own = resumes(timed_entries(path), path.stem, None, undecided, before)
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
