"""The agents a run launched, the calls that resumed them, the agents
pending to it and running under it, and the reports of an agent that reached
its parent."""

from dataclasses import dataclass
from enum import Enum
from functools import cache
from pathlib import Path
from typing import Any

from command_labels import AGENT_TOOLS
from controlled_markdown import mctx
from quota import epoch
from run_reads import (MAIN, LaunchStatus, Status, agent_messages, blocks, is_prompt,
                       in_background, launch_status, notifications, notified, parent_id,
                       parent_label, read_meta, results_by_call, run_entries,
                       session_agents, session_of, session_transcripts, text_of)
from senders import INTERRUPTED
from transcripts import Entry, agent_id, chain, entries_back, main_transcript, read_entries

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
    and the time of the run's last sign that it reported, or None where the
    run holds none."""
    agent: str | None
    path: Path | None
    since: float
    done: float | None

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
    """The entries of the run at `path` that give a time."""
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
            out.append(Launch(aid, child, epoch(e["timestamp"]), done))
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


# The types of a transcript's message entries, the entries of a turn: the
# message that opens it and its work.
MESSAGE_TYPES = ("user", "assistant")


def turns(entries: list[Entry]) -> tuple[set[int], set[int]]:
    """The indices of the entries that start a turn and of those that end
    one. A prompt starts a turn when the next message entry is the model's;
    a local command, such as /compact, gives the model none. An assistant
    entry with no tool call ends a turn when it says so, or when the next
    message entry is a prompt, and the result of a call that ends the turn,
    such as SubagentHandback, ends one."""
    starts: set[int] = set()
    ends: set[int] = set()
    nxt: Entry | None = None
    for i in range(len(entries) - 1, -1, -1):
        e = entries[i]
        if is_prompt(e) and nxt is not None and nxt.get("type") == "assistant":
            starts.add(i)
        if e.get("type") == "assistant" and not blocks(e, "tool_use"):
            stop = (e.get("message") or {}).get("stop_reason")
            if stop in ("end_turn", "stop_sequence") or (
                    nxt is not None and is_prompt(nxt)):
                ends.add(i)
        if e.get("toolEndsTurn"):
            ends.add(i)
        if e.get("type") in MESSAGE_TYPES or is_prompt(e):
            nxt = e
    return starts, ends


def idle_after(idle: bool, i: int, entry: Entry, starts: set[int],
               ends: set[int]) -> bool:
    """Whether a run is idle after its `i`-th entry, from whether it was
    before it: an entry that ends a turn makes it idle, and otherwise an
    entry of the model or one that starts a turn makes it not."""
    if i in ends:
        return True
    return idle and entry.get("type") != "assistant" and i not in starts


def turn_ended(entries: list[Entry]) -> bool:
    """Whether the run whose entries are `entries`, or those from one of its
    timestamped assistant entries on, has ended its turn, or its last
    message entry is the harness's note that the user interrupted it. An
    entry with no timestamp moves no turn."""
    starts, ends = turns(entries)
    idle = False
    for i, e in enumerate(entries):
        if e.get("timestamp"):
            idle = idle_after(idle, i, e, starts, ends)
    last = [e for e in entries if e.get("type") in MESSAGE_TYPES][-1:]
    return idle or any(e.get("type") == "user" and text_of(
        (e.get("message") or {}).get("content")).startswith(INTERRUPTED)
        for e in last)


@cache
def has_ended(path: Path) -> bool:
    """`turn_ended` over the run at `path`, read from its last entry back to
    its last timestamped assistant entry, which settles it."""
    tail: list[Entry] = []
    for p in reversed(chain(path)):
        for e in entries_back(p):
            tail.append(e)
            if e.get("type") == "assistant" and e.get("timestamp"):
                return turn_ended(tail[::-1])
    return turn_ended(tail[::-1])


@cache
def live(path: Path) -> bool:
    """Whether the run at `path`, or a run under it, as the `.meta.json`
    files of its sessions give them, has not ended."""
    if not has_ended(path):
        return True
    under = run_launches(path)[1].get(agent_id(path), frozenset())
    agents = {aid: p for s in dict.fromkeys(session_of(p) for p in chain(path))
              for aid, p in session_agents(s).items()}
    return any(live(chain(agents[aid])[-1]) for aid in sorted(under) if aid in agents)


def turn_after(path: Path, t: float, undecided: list[str]) -> bool:
    """Whether the transcript at `path` holds an entry of a turn timestamped
    after `t`. An entry of a turn with no timestamp counts as not, and an
    `undecided` line names the run."""
    out = False
    for e in read_entries(path):
        if e.get("type") not in MESSAGE_TYPES:
            continue
        if not e.get("timestamp"):
            undecided.append(mctx("{run}: a `{type}` entry of its transcript has no "
                                  "timestamp, so it counts as before its parent's "
                                  "last sign that it reported").format(
                run=agent_id(path), type=e.get("type")))
        elif epoch(e["timestamp"]) > t:
            out = True
    return out


def running_agents(path: Path, undecided: list[str]) -> list[tuple[str, Path]]:
    """The agents under the run at `path` whose turn has not ended, and whose
    parent holds no sign that they reported, or whose transcript holds a
    `user` or `assistant` entry timestamped after the latest sign, each with
    its parent, each parent's agents after it. An entry of either type is
    the message that opens a turn or the work of one, so an attachment the
    harness writes after a turn has ended is none. An agent is passed over
    unread, with the agents under it, where it and each of them has ended."""
    parents = run_launches(path)[1]
    out: list[tuple[str, Path]] = []
    for a in launches(path, undecided):
        child = a.path
        if child is None or not live(child):
            continue
        if not has_ended(child) and (
                a.done is None or (child.stat().st_mtime > a.done
                                   and turn_after(child, a.done, undecided))):
            out.append((parent_label(path), child))
        if agent_id(child) in parents:
            out.extend(running_agents(child, undecided))
    return out


# Reports.

# The opening of the note of a notification that the agent stopped with work
# of its own still running.
STILL_RUNNING = "This agent stopped with background work of its own still running"


class ReportKind(Enum):
    """The entries of a parent's transcript that give a report of an agent,
    as HELP gives them."""
    NOTIFICATION = "notification"
    RESULT = "result"
    MESSAGE = "message"


@dataclass
class Report:
    kind: ReportKind
    time: float
    text: str


def parent_transcripts(path: Path) -> list[Path]:
    """The transcripts of the parent of the subagent at `path`, under the
    sessions of that subagent's run: the main transcript of each, or the
    transcripts of the parent's run."""
    parent = parent_id(path)
    sessions = dict.fromkeys(session_of(p) for p in chain(path))
    if parent == MAIN:
        return [m for s in sessions if (m := main_transcript(s)).is_file()]
    runs = [chain(a) for s in sessions if (a := session_agents(s).get(parent))]
    return list(dict.fromkeys(p for run in runs for p in run))


def reports(path: Path, since: float, undecided: list[str]) -> list[Report] | None:
    """The entries after `since` of the transcripts of the parent of the
    subagent at `path` that give a report of it, as HELP gives them, in the
    order of their time, or None where no transcript of its parent is
    found."""
    aid = agent_id(path)
    found = parent_transcripts(path)
    if not found:
        undecided.append(mctx("{run}: no transcript of its parent is found, so "
                              "whether a report reached it is unknown").format(run=aid))
        return None
    call = (read_meta(path) or {}).get("toolUseId")
    if not call:
        undecided.append(mctx("{run}: no `.meta.json` of its run gives a `toolUseId`, "
                              "so the result of its launch cannot be matched").format(run=aid))
    out: list[Report] = []
    for e in (e for p in found for e in read_entries(p)):
        if not e.get("timestamp") or e.get("type") == "assistant":
            continue
        t = epoch(e["timestamp"])
        if t <= since:
            continue
        for n in notifications(e):
            if aid not in n.ids and call not in n.ids:
                continue
            if n.status is None:
                undecided.append(mctx("{run}: a notification of it at {time} gives "
                                      "the status `{status}`, of no known form").format(
                    run=aid, time=e["timestamp"], status=n.status_text))
            elif (n.status is Status.COMPLETED and n.result is not None
                    and not (n.note or "").startswith(STILL_RUNNING)):
                out.append(Report(ReportKind.NOTIFICATION, t, n.result.strip()))
        if is_prompt(e):
            out.extend(Report(ReportKind.MESSAGE, t, text)
                       for who, text in agent_messages(e) if who == aid)
        result = e.get("toolUseResult")
        if call and isinstance(result, dict) and any(
                b.get("tool_use_id") == call for b in blocks(e, "tool_result")):
            if launch_status(result, undecided, call) is LaunchStatus.COMPLETED:
                out.append(Report(ReportKind.RESULT, t,
                                  text_of(result.get("content")).strip()))
    return sorted(out, key=lambda r: r.time)
