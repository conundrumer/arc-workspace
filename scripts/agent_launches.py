"""The agents a run launched, the calls that resumed them, and the agents
pending to it, as the HELP of `profile_runs` gives them."""

from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

from agent_reports import Report, report_ids, reports_after
from command_labels import AGENT_TOOLS
from controlled_markdown import mctx
from quota import epoch
from run_reads import (blocks, in_background, notified, parent_label, read_meta,
                       results_by_call, run_entries, session_agents, session_of,
                       session_transcripts)
from transcripts import Entry, agent_id, chain, read_entries

# The openings of the message of a SendMessage result where the call resumed
# the agent it was sent to, and where it queued the message to a running one.
RESUMING = "Resuming agent"
QUEUED = "Message queued"


@cache
def session_launches(session: Path) -> tuple[dict[str, Path], dict[str, frozenset[str]]]:
    """The transcripts of a session's agents by the Agent call that launched
    each, and the agent ids of the agents each subagent launched, by its
    agent id, as their `.meta.json` files give them."""
    by_call: dict[str, Path] = {}
    children: dict[str, set[str]] = {}
    for aid, p in session_agents(session).items():
        meta = read_meta(p) or {}
        if meta.get("toolUseId"):
            by_call[meta["toolUseId"]] = chain(p)[-1]
        if meta.get("parentAgentId"):
            children.setdefault(meta["parentAgentId"], set()).add(aid)
    return by_call, {k: frozenset(v) for k, v in children.items()}


def run_launches(path: Path) -> tuple[dict[str, Path], dict[str, frozenset[str]]]:
    """`session_launches` over the sessions of the transcripts of the run
    at `path`."""
    by_call: dict[str, Path] = {}
    children: dict[str, frozenset[str]] = {}
    for p in chain(path):
        calls, kids = session_launches(session_of(p))
        by_call.update(calls)
        for k, v in kids.items():
            children[k] = children.get(k, frozenset()) | v
    return by_call, children


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


def resumed(result: dict[str, Any], run: str, call: str,
            undecided: list[str]) -> str | None:
    """The agent id of the agent a SendMessage call resumed, as its result
    gives it, or None where the call resumed none or its result is of an
    unknown form."""
    if result.get("resumedAgentId"):
        return str(result["resumedAgentId"])
    message = str(result.get("message", ""))
    if message.startswith(RESUMING):
        return (result.get("pin") or {}).get("id")
    if result.get("pin") and not message.startswith(QUEUED):
        undecided.append(mctx("{run}: the result of SendMessage call {call} "
                              "says neither that it resumed an agent nor "
                              "that it queued the message").format(
            run=run, call=call))
    return None


def note_latest(times: dict[str, float], agent: str, t: float) -> None:
    """Keep in `times` the later of the time it gives `agent` and `t`."""
    times[agent] = max(times.get(agent, t), t)


def resumes(entries: list[Entry], run: str, agents: set[str] | None,
            undecided: list[str]) -> dict[str, float]:
    """The time of the last SendMessage call among `entries` that resumed
    each agent, or with `agents` each of those agents."""
    results = results_by_call(entries)
    out: dict[str, float] = {}
    for e in entries:
        if e.get("type") != "assistant" or not e.get("timestamp"):
            continue
        for b in blocks(e, "tool_use"):
            if b.get("name") != "SendMessage":
                continue
            aid = resumed(results.get(b.get("id", "")) or {}, run,
                          b.get("id", ""), undecided)
            if aid and (agents is None or aid in agents):
                note_latest(out, aid, epoch(e["timestamp"]))
    return out


def session_resumes(path: Path, agents: set[str], since: float,
                    undecided: list[str]) -> dict[str, float]:
    """The time of the last SendMessage call that resumed each of `agents`,
    among the calls of each agent of the sessions of the run at `path`, main
    among them, other than that run, whose transcript changed at or after
    `since`."""
    own = chain(path)
    sessions = dict.fromkeys(session_of(p) for p in own)
    out: dict[str, float] = {}
    for session in sessions:
        for p in session_transcripts(session):
            if p in own or p.stat().st_mtime < since:
                continue
            entries = read_entries(p, naming=agents | {"SendMessage"})
            for aid, t in resumes(entries, parent_label(p), agents,
                                  undecided).items():
                note_latest(out, aid, t)
    return out


def timed_entries(path: Path) -> list[Entry]:
    return [e for e in run_entries(path) if e.get("timestamp")]


def launches(path: Path, undecided: list[str]) -> list[Launch]:
    """The agents the run at `path` launched, in the order of their launch.
    A sign that an agent reported is the run's notification of it, or a
    result of its launch that does not say the agent runs in the
    background."""
    entries = timed_entries(path)
    results = results_by_call(entries)
    answered = {b.get("tool_use_id"): epoch(e["timestamp"]) for e in entries
                if e.get("type") == "user" for b in blocks(e, "tool_result")}
    told = {v: epoch(e["timestamp"]) for e in entries
            if e.get("type") != "assistant" for v in notified(e)}
    naming: dict[str, list[Entry]] = {}
    for e in entries:
        for v in report_ids(e):
            naming.setdefault(v, []).append(e)
    by_call = run_launches(path)[0]
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
            signs = [told.get(tid), told.get(result.get("agentId", "")),
                     None if background else answered.get(tid)]
            done = max((t for t in signs if t is not None), default=None)
            child = by_call.get(tid)
            aid = agent_id(child) if child else result.get("agentId")
            if child is None and done is None:
                undecided.append(mctx("{run}: no transcript gives call {call} as "
                                      "its launch").format(run=path.stem, call=tid))
            named = {id(n): n for v in (tid, *([aid] if aid else []))
                     for n in naming.get(v, [])}
            out.append(Launch(aid, child, epoch(e["timestamp"]), done, tid,
                              list(named.values())))
    return out


def launched(path: Path, undecided: list[str]) -> list[Launch]:
    """`launches` of the run at `path`, each from the last call that resumed
    it where one did."""
    out = launches(path, undecided)
    own = resumes(timed_entries(path), path.stem, None, undecided)
    agents = {a.agent for a in out if a.agent}
    others = (session_resumes(path, agents, min(a.since for a in out), undecided)
              if agents else {})
    for a in out:
        a.since = max(a.since, own.get(a.agent or "", 0.0),
                      others.get(a.agent or "", 0.0))
    return out


def pending_agents(path: Path, undecided: list[str]) -> list[str]:
    """The agent ids of the agents pending to the run at `path`, in the
    order of their launch, as HELP gives them."""
    own = [a for a in launched(path, undecided) if a.pending and a.agent]
    if not own:
        return []
    told = session_notified(session_of(path), {a.agent for a in own if a.agent},
                            min(a.since for a in own))
    out: list[str] = []
    for a in own:
        last = told.get(a.agent or "")
        if a.agent and (last is None or last <= a.since):
            out.append(a.agent)
    return out


def session_notified(session: Path, agents: set[str],
                     since: float) -> dict[str, float]:
    """The time of the last notification of each of `agents` that a
    transcript of `session` changed at or after `since` holds."""
    out: dict[str, float] = {}
    for p in session_transcripts(session):
        if p.stat().st_mtime < since:
            continue
        for e in read_entries(p, naming=agents):
            if not e.get("timestamp") or e.get("type") == "assistant":
                continue
            for v in notified(e):
                if v in agents:
                    note_latest(out, v, epoch(e["timestamp"]))
    return out
