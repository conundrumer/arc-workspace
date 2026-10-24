"""The SendMessage calls that resumed agents: the agent each call resumed,
as its result gives it, the latest call that resumed each agent among
the calls of a run or of the other runs of its sessions, and the agents a
run's calls went to."""

from collections.abc import Collection, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from controlled_markdown import mctx
from run_reads import (blocks, parent_label, results_by_call, run_entries,
                       run_sessions)
from state_reads import DERIVED, Kept, state_cache
from transcripts import chain
from transcript_entries import epoch
from transcript_folds import fold
from transcript_snapshots import Entry
from agent_deliveries import Delivery, delivery
from session_changes import agents_facts, transcript_stamp


def pin_id(result: dict[str, Any]) -> str | None:
    """The agent id of the `pin` of `result`, a SendMessage result."""
    return (result.get("pin") or {}).get("id")


def resumed(result: dict[str, Any], run: str, call: str,
            undecided: list[str]) -> str | None:
    """The agent id of the agent a SendMessage call resumed, as its result
    gives it, or None where the call resumed none or its result is of an
    unknown form."""
    if result.get("resumedAgentId"):
        return str(result["resumedAgentId"])
    done = delivery(result)
    if done is Delivery.RESUMED:
        return pin_id(result)
    if result.get("pin") and done is None:
        undecided.append(mctx("{run}: the result of SendMessage call {call} "
                              "says neither that it resumed an agent nor "
                              "that it queued the message").format(
            run=run, call=call))
    return None


def note_latest(times: dict[str, float], agent: str, t: float) -> None:
    """Keep in `times` the later of the time it gives `agent` and `t`."""
    times[agent] = max(times.get(agent, t), t)


@dataclass(frozen=True, slots=True)
class Send:
    """A SendMessage call: its time, the agent id `resumed` gives for its
    result, and, where `resumed` gives a note for it, the `pin` id of its
    result and that note."""
    time: float
    agent: str | None
    pin: str | None
    note: str | None


@dataclass
class SendPairs:
    """SendMessage call times and the last result of each tool-use id."""
    results: dict[str, dict[str, Any]]
    calls: list[tuple[float, str]]

    def step(self, _path: Path, _line: int, e: Entry) -> None:
        self.add(e)

    def add(self, e: Entry) -> None:
        self.results.update(results_by_call((e,)))
        if e.get("type") == "assistant" and e.get("timestamp"):
            self.calls.extend((epoch(e["timestamp"]), b.get("id", ""))
                              for b in blocks(e, "tool_use") if b.get("name") == "SendMessage")

    def sends(self, run: str) -> list[Send]:
        out: list[Send] = []
        for t, call in self.calls:
            result = self.results.get(call) or {}
            notes: list[str] = []
            aid = resumed(result, run, call, notes)
            out.append(Send(t, aid, pin_id(result) if notes else None,
                            notes[0] if notes else None))
        return out


def sends(entries: Iterable[Entry], run: str) -> list[Send]:
    """The SendMessage calls among `entries` that have a time, in their
    order, read in one pass."""
    pairs = SendPairs({}, [])
    for e in entries:
        pairs.add(e)
    return pairs.sends(run)


def picked(calls: Iterable[Send], agents: Collection[str] | None, undecided: list[str],
           before: float | None) -> dict[str, float]:
    """The time of the last of `calls` that resumed each agent, or with
    `agents` each of those agents, and with `before` only of the calls
    earlier than it. The note of each call it takes goes to `undecided`,
    with `agents` only where its `pin` id is one of them."""
    out: dict[str, float] = {}
    for c in calls:
        if before is not None and c.time >= before:
            continue
        if c.note and (agents is None or c.pin in agents):
            undecided.append(c.note)
        if c.agent and (agents is None or c.agent in agents):
            note_latest(out, c.agent, c.time)
    return out


SEND_WORDS = frozenset({"SendMessage", "resumedAgentId", '"pin":'})
"""The words of the lines `sends` reads: `SendMessage`, which the line of
each call holds, and each word of a result that `resumed` gives an agent id
or a note for."""


def resumes(path: Path, undecided: list[str], before: float | None = None) -> dict[str, float]:
    """`picked` of the SendMessage calls of the run at `path`."""
    return picked(run_sends(path), None, undecided, before)


@state_cache(DERIVED, kept=Kept.DISK)
def run_sends(path: Path) -> tuple[Send, ...]:
    """`sends` of the run at `path`, from the lines that hold a word of
    `SEND_WORDS`, held so that each caller reads none of the run's other
    entries."""
    return tuple(sends(run_entries(path, naming=set(SEND_WORDS)), path.stem))


@dataclass
class ResumeResults:
    """The call ids of results that refer to requested agents."""
    agents: frozenset[str]
    calls: set[str]

    def step(self, _path: Path, _line: int, entry: Entry) -> None:
        self.calls.update(call for call, result in results_by_call((entry,)).items()
                          if result.get("resumedAgentId") in self.agents
                          or pin_id(result) in self.agents)


@state_cache(lambda path, agents: transcript_stamp(path) if agents else (), kept=Kept.DISK)
def transcript_resumes(path: Path, agents: frozenset[str]) -> tuple[Send, ...]:
    """Selected resume results paired with their calls, including earlier
    calls and later replacement results. Both queries fold appended candidate
    lines. Unknown delivery notes remain attached to the pin. Sources are
    those of `transcript_stamp`."""
    if not agents:
        return ()
    calls = frozenset(fold(ResumeResults.step, lambda: ResumeResults(agents, set()),
                           (path, agents), [path], agents, selective=True).calls)
    if not calls:
        return ()
    pairs = fold(SendPairs.step, lambda: SendPairs({}, []), (path, agents), [path],
                 calls, selective=True)
    return tuple(c for c in pairs.sends(parent_label(path)) if agents.intersection(send_agents(c)))


def session_resumes(path: Path, agents: set[str], since: float,
                    undecided: list[str], before: float | None = None) -> dict[str, float]:
    """The time of the last SendMessage call that resumed each of `agents`,
    among the calls of each agent of the sessions of the run at `path`, main
    among them, other than that run, whose transcript changed at or after
    `since`, and with `before` only of the calls earlier than it."""
    return resumes_since(path, frozenset(agents), since, undecided, before)


@state_cache(DERIVED, notes="undecided", kept=Kept.VALUE)
def resumes_since(path: Path, agents: frozenset[str], since: float,
                  undecided: list[str], before: float | None) -> dict[str, float]:
    """`session_resumes`, held so that a read derived from it sees a new
    transcript of the sessions only where it resumed one of `agents`."""
    own = set(chain(path))
    return picked([at.fact for at in agents_facts(run_sessions(path), since,
                                                  transcript_resumes, agents) if at.path not in own],
                  agents, undecided, before)


def send_agents(send: Send) -> tuple[str, ...]:
    """The agent id `send` resumed and the `pin` id of its result, those it
    gives."""
    return tuple(v for v in (send.agent, send.pin) if v)


def sent_to(path: Path) -> frozenset[str]:
    """The agent ids the SendMessage calls of the run at `path` went to."""
    return frozenset(fold(add_sent, set[str], path, chain(path), frozenset({"SendMessage"})))


def add_sent(to: set[str], _path: Path, _line: int, e: Entry) -> None:
    """Add to `to` the agent ids the SendMessage calls of the entry `e`
    went to."""
    if e.get("type") == "assistant":
        to.update(str(b["input"]["to"]) for b in blocks(e, "tool_use")
                  if b.get("name") == "SendMessage" and (b.get("input") or {}).get("to"))
