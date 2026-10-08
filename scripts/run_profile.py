"""The profile of where an agent run's wall time goes, from its Claude
Code transcripts, and its print, as the HELP of `profile_runs` gives them."""

import math
import subprocess
import time
from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from agent_launches import run_launches
from agent_turns import idle_after, turns
from command_labels import AGENT_TOOLS, POLL, call_command, command_label
from controlled_markdown import mctx
from filed_texts import unfiled
from run_reads import (BACKGROUND_TASK, blocks, context_size,
                       in_background, is_prompt, message_text, notified,
                       output_file, parent_id, results_by_call, run_entries,
                       run_sessions, run_type, session_of,
                       type_in)
from senders import Sender, sender
from ticketing.times import MINUTE_FORM
from token_prices import run_cost
from transcripts import Entry, Refused, agent_id, epoch, is_subagent, state_cache


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
# The keys of a call's result that give an id a notification of the call
# gives.
TASK_KEYS = (BACKGROUND_TASK, "taskId", "agentId")


@dataclass
class Group:
    time: float = 0.0
    calls: int = 0
    ran: float = 0.0


@dataclass
class Span:
    """`call` is the call's tool-use id, and `end` the time of its
    result."""
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
    cost: float | None
    said: str | None
    # The messages from the run's parent, the brief first, the messages
    # from other agents than the monitor, and the text of each later message whose sender is
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


@dataclass(frozen=True)
class Background:
    """A call whose result says it runs in the background: the ids a
    notification of it gives, its tool-use id among them, and for a Bash
    call, the output file its result names, or None where it names none."""
    ids: frozenset[str]
    output: Path | None


# Backgrounded calls.

def agent_calls(entries: Iterable[Entry]) -> set[str]:
    return {str(b.get("id")) for e in entries if e.get("type") == "assistant"
            for b in blocks(e, "tool_use") if b.get("name") in AGENT_TOOLS}


def backgrounds(entries: Iterable[Entry], agent_calls: set[str],
                undecided: list[str]) -> dict[str, Background]:
    """Each call among `entries` that runs in the background, by its
    tool-use id, where `agent_calls` are the tool-use ids of Agent calls."""
    out: dict[str, Background] = {}
    for e in entries:
        r = e.get("toolUseResult")
        if e.get("type") != "user" or not isinstance(r, dict):
            continue
        bash = bool(r.get(BACKGROUND_TASK))
        for b in blocks(e, "tool_result"):
            if not b.get("tool_use_id"):
                continue
            call = str(b["tool_use_id"])
            if bash or (call in agent_calls and in_background(r, undecided, call)):
                out[call] = Background(
                    frozenset({call, *(str(r[k]) for k in TASK_KEYS if r.get(k))}),
                    output_file(b) if bash else None)
    return out


def background_ends(found: dict[str, Background],
                    entries: Iterable[Entry]) -> dict[str, float | None]:
    """When each call of `found` ended, as the HELP of `profile_runs` gives
    it, from the notifications among `entries`, or None where it still runs
    or whether it runs is unknown."""
    told: dict[str, float] = {}
    for e in entries:
        if e.get("type") != "assistant" and e.get("timestamp"):
            t = epoch(e["timestamp"])
            for ident in notified(e):
                told[ident] = min(t, told.get(ident, t))
    ends: dict[str, float | None] = {
        call: min((told[i] for i in b.ids if i in told), default=None)
        for call, b in found.items()}
    files = {call: b.output for call, b in found.items()
             if ends[call] is None and b.output is not None and b.output.is_file()}
    for call, f in files.items():
        if str(f.resolve()) not in held_in(f.resolve().parent):
            try:
                ends[call] = f.stat().st_mtime
            except FileNotFoundError:
                pass
    return ends


@state_cache(None)
def held_in(directory: Path) -> frozenset[str]:
    """The paths of the files in `directory` that a process holds open, as
    `lsof` gives them, read once for each state, so each reader of a run
    sees one state, and one `lsof` call serves the runs of a session."""
    # lsof exits 1 where it finds no open file as well as on a fault, so
    # only its stderr tells a fault.
    out = subprocess.run(["lsof", "-F", "n", "+d", str(directory)],
                         capture_output=True, text=True)
    if out.stderr.strip():
        raise Refused(mctx("which files in {dir} a process holds open is unknown: "
                           "lsof says {err}").format(dir=directory,
                                                     err=out.stderr.strip()))
    return frozenset(line[1:] for line in out.stdout.splitlines() if line.startswith("n"))


# Profiles.

def launched_type(inp: dict[str, Any], result: dict[str, Any] | None,
                  session: Path) -> str | None:
    """The type of the agent an Agent call launched: the type the call gives,
    or else the type of the agent its result names."""
    if inp.get("subagent_type"):
        return inp["subagent_type"]
    aid = (result or {}).get("agentId")
    return type_in([session], aid) if aid else None


def classify(block: dict[str, Any], result: dict[str, Any] | None, launched: bool,
             session: Path, undecided: list[str], run: str) -> Call:
    """Where the time of the call `block` goes, where `launched` is whether
    it runs in the background."""
    name, inp = block.get("name"), block.get("input") or {}
    r = result or {}
    if name in AGENT_TOOLS:
        kind = launched_type(inp, result, session)
        if kind is None:
            kind = "?"
            undecided.append(mctx("{run}: the agent type of call {call} is "
                                  "unknown").format(run=run, call=block.get("id")))
        key = (Part.WAITS, f"agent {kind}")
        return Call(key, key if launched else None)
    if name in WAIT_TOOLS:
        return Call((Part.WAITS, name), None)
    if name != "Bash":
        return Call((Part.TOOLS, str(name)), None)
    label = command_label(inp.get("command", ""))
    background = (Part.WAITS, f"bg {label}")
    moved = launched and any(k in r for k in MOVED)
    if launched and not moved:
        return Call(background, background)
    if inp.get("run_in_background"):
        return Call(background, None)
    pending = (Part.WAITS, POLL) if label == POLL else (Part.TOOLS, label)
    return Call(pending, background if launched else None)


def profile(path: Path, undecided: list[str]) -> Run:
    agent_type, description = run_type(path)
    label = agent_id(path) if is_subagent(path) else path.stem
    session = session_of(path)
    entries = run_entries(path)
    results = results_by_call(entries)
    found = backgrounds(entries, agent_calls(entries), undecided)
    bg_ends = background_ends(found, entries)
    starts, ends = turns(entries)
    # The index of the prompt the model first answers: the brief is the
    # prompts up to it.
    briefed = min(starts, default=len(entries))
    parent = parent_id(path) if is_subagent(path) else None
    children = run_launches(path)[1].get(label, frozenset())
    sessions = run_sessions(path)
    messages: list[Message] = []
    others: list[Message] = []
    unknown: list[str] = []

    parts = dict.fromkeys(Part, 0.0)
    groups: dict[Key, Group] = {}
    calls: dict[str, Call] = {}
    pending: dict[str, Key] = {}
    running: dict[str, tuple[Key, float]] = {}   # tool-use id -> key, start
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

    def spend(d: float) -> None:
        if pending:
            share(pending.values(), d)
        elif not idle:
            parts[Part.MODEL] += d
        elif running:
            share([k for k, _ in running.values()], d)
        else:
            parts[Part.IDLE] += d

    def close(tid: str, at: float) -> None:
        k, start = running.pop(tid)
        group(k).ran += max(at, start) - start

    for i, e in enumerate(entries):
        if not e.get("timestamp"):
            continue
        t = epoch(e["timestamp"])
        if prev is not None and t > prev:
            for at, tid in sorted((x, tid) for tid in running
                                  if (x := bg_ends[tid]) is not None and x < t):
                at = max(at, prev)
                spend(at - prev)
                prev = at
                close(tid, at)
            spend(t - prev)
        prev = t if prev is None else max(t, prev)
        first = t if first is None else first
        etype = e.get("type")
        if parent is not None and i > briefed and is_prompt(e):
            who = sender(e, parent, children, sessions)
            if who is Sender.PARENT:
                messages.append(Message(i, t, unfiled(message_text(e), label, undecided),
                                        parts[Part.IDLE]))
            elif who is Sender.AGENT:
                others.append(Message(i, t, message_text(e), parts[Part.IDLE]))
            elif who is Sender.UNKNOWN:
                unknown.append(message_text(e))
        if etype == "assistant":
            text = "\n".join(b.get("text", "") for b in blocks(e, "text")).strip()
            said = text or said
            for b in blocks(e, "tool_use"):
                tid = b.get("id", "")
                c = calls[tid] = classify(b, results.get(tid), tid in found,
                                          session, undecided, label)
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
        idle = idle_after(idle, i, e, starts, ends)
        if i in ends:
            pending.clear()
    end = prev or 0.0
    brief = [unfiled(message_text(e), label, undecided)
             for e in entries[:briefed + 1] if is_prompt(e)]
    if brief and first is not None:
        messages.insert(0, Message(briefed, first, "\n".join(brief), 0.0))
    cwd = next((e["cwd"] for e in entries if e.get("cwd")), None)
    context = context_size(reversed(entries))
    unpriced: list[str] = []
    cost = run_cost(entries, unpriced)
    undecided.extend(f"{label}: {line}" for line in dict.fromkeys(unpriced))
    in_flight = [spans[tid] for tid in pending if tid in spans]
    backgrounded = [spans[tid] for tid in running
                    if bg_ends[tid] is None and tid in spans]
    for tid in list(running):
        close(tid, end if (at := bg_ends[tid]) is None else at)
    wall = end - first if first is not None else 0.0
    if first is None:
        undecided.append(mctx("{run}: no entry gives a time, so its start "
                              "is unknown").format(run=label))
    return Run(label, agent_type, description, first, wall, parts,
               {k: g for k, g in groups.items() if g.time or g.calls},
               list(spans.values()), in_flight, backgrounded, context, cost, said,
               messages, others, unknown, cwd, path)


def minutes(s: float) -> str:
    return f"{s / 60:.1f}m"


def clock(t: float | None) -> str:
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


def dollars(cost: float | None) -> str:
    return f"${cost:.2f}" if cost is not None else "?"


def print_costs(by_type: dict[str, list[Run]], order: list[str]) -> None:
    """Per agent type, the total token cost of its priced runs, its share of
    the total over all priced runs, the median cost of a priced run, and the
    number of runs whose cost is unknown."""
    priced = {k: [r.cost for r in by_type[k] if r.cost is not None] for k in order}
    whole = sum(sum(c) for c in priced.values())
    print(f"\n{'type':<18} {'cost':>9} {'share':>6} {'p50':>8} {'unpriced':>8}")
    for kind in order:
        costs = priced[kind]
        total = sum(costs)
        share = f"{100 * total / whole:5.0f}%" if whole else "     -"
        median = dollars(percentile(costs, 50)) if costs else "?"
        print(f"{kind:<18} {dollars(total):>9} {share} {median:>8} "
              f"{len(by_type[kind]) - len(costs):>8}")


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
    print_costs(by_type, order)
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
