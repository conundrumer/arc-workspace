"""The profile of where an agent run's wall time goes, from its Claude
Code transcripts, and its print, as the HELP of `profile_runs` gives them."""

import math
import time
from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from agent_launches import run_launches
from agent_turns import idle_after, turns
from command_labels import AGENT_TOOLS, POLL, call_command, command_label
from controlled_markdown import mctx
from run_reads import (agent_type, blocks, context_size, in_background,
                       is_prompt, message_text, notified, parent_id,
                       results_by_call, run_entries, run_type, session_agents,
                       session_of)
from senders import Sender, sender
from ticket_log import MINUTE_FORM
from transcripts import Entry, agent_id, epoch, is_subagent


class Part(Enum):
    MODEL = "model"
    TOOLS = "tools"
    WAITS = "waits"
    IDLE = "idle"


type Key = tuple[Part, str]


WAIT_TOOLS = ("Monitor", "TaskOutput")
# Ways a Bash result says the harness, not the call, moved it to the
# background after it had run in the foreground.
MOVED = ("timedOutAfterMs", "assistantAutoBackgrounded", "backgroundedByUser")
# The characters of a call's command or of an agent's text output that
# `--running` prints.
COMMAND_WIDTH = 160


@dataclass
class Group:
    time: float = 0.0
    calls: int = 0
    ran: float = 0.0


@dataclass
class Span:
    """A call's span: its label, its command, the time of the call, its
    tool-use id and the time of its result."""
    label: str
    command: str
    start: float
    call: str
    end: float | None = None


@dataclass
class Message:
    """A message to a run: the index of its entry, its time, its text, and
    the run's `idle` time before it."""
    index: int
    time: float
    text: str
    idle: float


@dataclass
class Run:
    label: str
    agent_type: str
    description: str
    start: float | None
    wall: float
    parts: dict[Part, float]
    groups: dict[Key, Group]
    spans: list[Span]
    in_flight: list[Span]
    backgrounded: list[Span]
    context: int | None
    said: str | None
    # The messages from the run's parent, the brief first, the messages
    # from other agents, and the text of each later message whose sender is
    # unknown.
    messages: list[Message]
    others: list[Message]
    unknown: list[str]
    cwd: str | None
    path: Path

    @property
    def active(self) -> float:
        return self.wall - self.parts[Part.IDLE]

    def period_end(self, i: int) -> Message | None:
        """The message that ends the period of the `i`-th message from the
        run's parent, or None where the period runs to the run's last entry."""
        m = self.messages[i]
        later = [n for n in (*self.messages[i + 1:i + 2], *self.others)
                 if n.index > m.index]
        return min(later, key=lambda n: n.index, default=None)

    def active_from(self, i: int) -> float | None:
        """The active time over the period of the `i`-th message from the
        run's parent. None where its start or a message is unknown."""
        if self.start is None or self.unknown:
            return None
        m = self.messages[i]
        nxt = self.period_end(i)
        if nxt is not None:
            return (nxt.time - m.time) - (nxt.idle - m.idle)
        end = self.start + self.wall
        return (end - m.time) - (self.parts[Part.IDLE] - m.idle)

    def active_at(self, now: float) -> float | None:
        """The active time of a run whose turn has not ended, over the period
        of the latest message from its parent, to `now` where that period has
        not ended: the time since its last entry goes to a pending call or
        to the model, so it is active. None where its start or that message
        is unknown."""
        if self.start is None or not self.messages:
            return None
        last = len(self.messages) - 1
        active = self.active_from(last)
        if active is None or self.period_end(last) is not None:
            return active
        return active + max(0.0, now - (self.start + self.wall))


@dataclass
class Call:
    """Where a tool call's time goes: `pending` while it is pending, and
    `background` once its result says it runs in the background."""
    pending: Key
    background: Key | None
    task_ids: list[str] = field(default_factory=list)


# Profiles.

def launched_type(inp: dict[str, Any], result: dict[str, Any] | None,
                  session: Path) -> str | None:
    """The type of the agent an Agent call launched: the type the call gives,
    or else the type of the agent its result names."""
    if inp.get("subagent_type"):
        return inp["subagent_type"]
    aid = (result or {}).get("agentId")
    path = session_agents(session).get(aid) if aid else None
    return agent_type(path) if path else None


def classify(block: dict[str, Any], result: dict[str, Any] | None,
             session: Path, undecided: list[str], run: str) -> Call:
    name, inp = block.get("name"), block.get("input") or {}
    r = result or {}
    task_ids = [str(r[k]) for k in ("backgroundTaskId", "taskId", "agentId") if r.get(k)]
    launched = bool(r.get("backgroundTaskId")) or (
        name in AGENT_TOOLS and result is not None
        and in_background(result, undecided, str(block.get("id"))))
    if name in AGENT_TOOLS:
        kind = launched_type(inp, result, session)
        if kind is None:
            kind = "?"
            undecided.append(mctx("{run}: the agent type of call {call} is "
                                  "unknown").format(run=run, call=block.get("id")))
        key = (Part.WAITS, f"agent {kind}")
        return Call(key, key if launched else None, task_ids)
    if name in WAIT_TOOLS:
        return Call((Part.WAITS, name), None, task_ids)
    if name != "Bash":
        return Call((Part.TOOLS, str(name)), None, task_ids)
    label = command_label(inp.get("command", ""))
    background = (Part.WAITS, f"bg {label}")
    moved = launched and any(k in r for k in MOVED)
    if launched and not moved:
        return Call(background, background, task_ids)
    if inp.get("run_in_background"):
        return Call(background, None, task_ids)
    pending = (Part.WAITS, POLL) if label == POLL else (Part.TOOLS, label)
    return Call(pending, background if launched else None, task_ids)


def profile(path: Path, undecided: list[str]) -> Run:
    agent_type, description = run_type(path)
    label = agent_id(path) if is_subagent(path) else path.stem
    session = session_of(path)
    entries = run_entries(path)
    results = results_by_call(entries)
    starts, ends = turns(entries)
    # The index of the prompt the model first answers: the brief is the
    # prompts up to it.
    briefed = min(starts, default=len(entries))
    parent = parent_id(path) if is_subagent(path) else None
    children = run_launches(path)[1].get(label, frozenset())
    messages: list[Message] = []
    others: list[Message] = []
    unknown: list[str] = []

    parts = dict.fromkeys(Part, 0.0)
    groups: dict[Key, Group] = {}
    calls: dict[str, Call] = {}
    pending: dict[str, Key] = {}
    running: dict[str, tuple[Key, float]] = {}   # tool-use id -> key, start
    by_task: dict[str, str] = {}                # task id -> tool-use id
    spans: dict[str, Span] = {}
    said: str | None = None
    idle = False
    prev: float | None = None
    first: float | None = None

    def group(key: Key) -> Group:
        return groups.setdefault(key, Group())

    def share(keys: Iterable[Key], d: float) -> None:
        keys = list(keys)
        for k in keys:
            group(k).time += d / len(keys)
            parts[k[0]] += d / len(keys)

    for i, e in enumerate(entries):
        if not e.get("timestamp"):
            continue
        t = epoch(e["timestamp"])
        if prev is not None and t > prev:
            d = t - prev
            if pending:
                share(pending.values(), d)
            elif not idle:
                parts[Part.MODEL] += d
            elif running:
                share([k for k, _ in running.values()], d)
            else:
                parts[Part.IDLE] += d
        prev = t if prev is None else max(t, prev)
        first = t if first is None else first
        etype = e.get("type")
        if parent is not None and i > briefed and is_prompt(e):
            who = sender(e, parent, children)
            if who is Sender.PARENT:
                messages.append(Message(i, t, message_text(e), parts[Part.IDLE]))
            elif who is Sender.AGENT:
                others.append(Message(i, t, message_text(e), parts[Part.IDLE]))
            elif who is Sender.UNKNOWN:
                unknown.append(message_text(e))
        if etype == "assistant":
            text = "\n".join(b.get("text", "") for b in blocks(e, "text")).strip()
            said = text or said
            for b in blocks(e, "tool_use"):
                tid = b.get("id", "")
                c = calls[tid] = classify(b, results.get(tid), session,
                                          undecided, label)
                pending[tid] = c.pending
                spans[tid] = Span(c.pending[1], call_command(b, undecided, label), t, tid)
                group(c.pending).calls += 1
        elif etype == "user":
            for b in blocks(e, "tool_result"):
                tid = b.get("tool_use_id", "")
                pending.pop(tid, None)
                if tid in spans:
                    spans[tid].end = t
                c = calls.get(tid)
                if c and c.background:
                    if c.background != c.pending:
                        group(c.background).calls += 1
                    running[tid] = (c.background, t)
                    for task in c.task_ids:
                        by_task[task] = tid
        idle = idle_after(idle, i, e, starts, ends)
        if i in ends:
            pending.clear()
        for ident in notified(e) if etype != "assistant" else []:
            tid = by_task.get(ident, ident)
            if tid in running:
                k, start = running.pop(tid)
                group(k).ran += t - start
    end = prev or 0.0
    brief = [message_text(e) for e in entries[:briefed + 1] if is_prompt(e)]
    if brief and first is not None:
        messages.insert(0, Message(briefed, first, "\n".join(brief), 0.0))
    cwd = next((e["cwd"] for e in entries if e.get("cwd")), None)
    context = context_size(reversed(entries))
    in_flight = [spans[tid] for tid in pending if tid in spans]
    backgrounded = [spans[tid] for tid in running if tid in spans]
    for k, start in running.values():
        group(k).ran += end - start
    wall = end - first if first is not None else 0.0
    if first is None:
        undecided.append(mctx("{run}: no entry gives a time, so its start "
                              "is unknown").format(run=label))
    return Run(label, agent_type, description, first, wall, parts,
               {k: g for k, g in groups.items() if g.time or g.calls},
               list(spans.values()), in_flight, backgrounded, context, said,
               messages, others, unknown, cwd, path)


def minutes(s: float) -> str:
    return f"{s / 60:.1f}m"


def clock(t: float | None) -> str:
    """The epoch time `t` as the tool prints a time, in UTC to the minute."""
    return time.strftime(MINUTE_FORM, time.gmtime(t)) if t is not None else "?"


def one_line(text: str, tail: bool = False) -> str:
    """`text` on one line, cut to its first COMMAND_WIDTH characters, or
    with `tail` to its last."""
    line = " ".join(text.split())
    if len(line) <= COMMAND_WIDTH:
        return line
    if tail:
        return "..." + line[3 - COMMAND_WIDTH:]
    return line[:COMMAND_WIDTH - 3] + "..."


def percentile(values: list[float], p: float) -> float:
    """The nearest-rank percentile of a list of numbers."""
    v = sorted(values)
    return v[max(0, min(len(v) - 1, math.ceil(len(v) * p / 100) - 1))]


def by_agent_type(runs: list[Run]) -> dict[str, list[Run]]:
    by_type: dict[str, list[Run]] = {}
    for r in runs:
        by_type.setdefault(r.agent_type, []).append(r)
    return by_type


def part_split(parts: dict[Part, float]) -> str:
    return "  ".join(f"{p.value} {minutes(parts[p])}" for p in Part)


def print_groups(groups: dict[Key, Group], top: int, wall: float,
                 present: dict[Key, int] | None = None) -> None:
    ranked = sorted(groups.items(), key=lambda kv: (-kv[1].time, kv[0][0].value, kv[0][1]))
    for (part, label), g in ranked[:top or None]:
        pct = f"{100 * g.time / wall:3.0f}%" if wall else "   -"
        ran = f"  ran {minutes(g.ran)}" if g.ran else ""
        runs = f"  in {present[(part, label)]} runs" if present else ""
        print(f"  {part.value:<5} {minutes(g.time):>8} {pct}  {g.calls:>4}x  {label}{ran}{runs}")


def print_types(runs: list[Run], pct: float, top: int) -> None:
    by_type = by_agent_type(runs)
    order = sorted(by_type, key=lambda k: (-sum(r.wall for r in by_type[k]), k))
    print(f"{'type':<18} {'runs':>4} {'min':>7} {'p50':>7} {f'p{pct:g}':>7} "
          f"{'max':>7} {'total':>8} {'act p50':>8} {f'act p{pct:g}':>8}  "
          + "  ".join(f"{p.value:>6}" for p in Part))
    for kind in order:
        rs = by_type[kind]
        walls = [r.wall for r in rs]
        active = [r.active for r in rs]
        total = sum(walls)
        shares = "  ".join(
            f"{(100 * sum(r.parts[p] for r in rs) / total if total else 0):5.0f}%"
            for p in Part)
        print(f"{kind:<18} {len(rs):>4} {minutes(min(walls)):>7} "
              f"{minutes(percentile(walls, 50)):>7} {minutes(percentile(walls, pct)):>7} "
              f"{minutes(max(walls)):>7} {minutes(total):>8} "
              f"{minutes(percentile(active, 50)):>8} {minutes(percentile(active, pct)):>8}  {shares}")
    if top == 0:
        return
    for kind in order:
        rs = by_type[kind]
        merged: dict[Key, Group] = {}
        present: dict[Key, int] = {}
        for r in rs:
            for k, g in r.groups.items():
                m = merged.setdefault(k, Group())
                m.time += g.time
                m.calls += g.calls
                m.ran += g.ran
                present[k] = present.get(k, 0) + 1
        total = sum(r.wall for r in rs)
        print(f"\n{kind}: {minutes(total)} over {len(rs)} runs")
        print_groups(merged, top, total, present)
