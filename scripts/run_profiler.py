"""The profile of where an agent run's wall time goes, from its Claude
Code transcripts, as `profile_runs.py --help runs` gives it.

A profile is a fold over the run's entries (`transcript_entries.fold`), so
a later read in the process parses only the entries added since. The fold
holds only what the entries give, and what turns on a value no entry has
given yet, a call's result or the end of a call in the background, is held
by that call's id until a step gives it, or shared at each read where none
does. A profile also reads files past those transcripts, and the state of
running processes, at each read: `noted_reads` states those reads."""

import copy
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from agent_launches import children_of
from agent_turns import is_message, marks
from command_labels import AGENT_TOOLS, POLL, call_command, command_label
from controlled_markdown import mctx
from filed_texts import unfiled
from run_backgrounds import Background, backgrounds, ends_from, note_told, told_end
from run_reads import (blocks, entry_input, is_prompt, message_text, parent_id, refused_at,
                       results_by_call, run_sessions, run_type, session_of, tool_calls, type_in)
from run_records import Call, Group, Key, Message, Part, Run, Span
from senders import Sender, sender
from token_prices import grouped, groups_cost, request_cost, request_input
from transcripts import agent_id, chain, is_subagent
from transcript_entries import epoch, fold
from transcript_snapshots import Entry

WAIT_TOOLS = ("Monitor", "TaskOutput")
# Ways a Bash result says the harness, not the call, moved it to the
# background after it had run in the foreground.
MOVED = ("timedOutAfterMs", "assistantAutoBackgrounded", "backgroundedByUser")


def launched_type(inp: dict[str, Any], result: dict[str, Any] | None,
                  session: Path) -> str | None:
    """The type of the agent an Agent call launched: the type the call gives,
    or else the type of the agent its result names."""
    if inp.get("subagent_type"):
        return inp["subagent_type"]
    aid = (result or {}).get("agentId")
    return type_in([session], aid) if aid else None


def classify(block: dict[str, Any], result: dict[str, Any] | None, launched: bool,
             kind: str) -> Call:
    """Where the time of the call `block` goes, where `launched` is whether
    it runs in the background, and `kind` the type of the agent an Agent
    call launched (`launched_type`)."""
    name, inp = block.get("name"), block.get("input") or {}
    r = result or {}
    if name in AGENT_TOOLS:
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


def result_sure(block: dict[str, Any]) -> bool:
    """Whether the part `classify` gives a pending call `block` turns on
    nothing its result gives: the part of a Bash call that names no
    background run and is no poll turns on whether its result says it runs
    there."""
    inp = block.get("input") or {}
    return (block.get("name") != "Bash" or bool(inp.get("run_in_background"))
            or command_label(inp.get("command", "")) == POLL)


@dataclass
class CallTime:
    """A tool call of a run, as the loop of `profile` reads it: its
    `tool_use` block, the time of the call, its command (`call_command`),
    whether its part turns on nothing its result gives (`result_sure`), the
    keys of its result that `classify` reads, whether a result came and
    says it runs in the background, the time of its result, the latest
    time of the run when that result came, its `Call` once nothing more an
    entry gives can change it, and the count of its `tool_use` blocks, as a
    transcript may hold one twice."""
    block: dict[str, Any]
    start: float
    command: str
    sure: bool
    result: dict[str, Any] | None = None
    answered: bool = False
    launched: bool = False
    end: float | None = None
    reach: float = 0.0
    call: Call | None = None
    uses: int = 1

    def part(self) -> Part | None:
        """The part of the call while pending, or None where it turns on
        its result, which has not come."""
        return self.read_part() if self.sure or self.answered else None

    def read_part(self) -> Part:
        """The part of the call while pending, as what has come of it gives
        it."""
        if self.call is not None:
            return self.call.pending[0]
        return classify(self.block, self.result, self.launched, "").pending[0]


def waiting(agents: set[str], pending: Sequence[str], running: Sequence[str], idle: bool,
            part_of: Callable[[str], Part | None]) -> bool:
    """Whether the run waits on agents, as `profile_runs.py --help runs`
    gives it, where `agents` are its Agent calls, `pending` its pending
    calls, `running` its calls in the background, and `part_of` gives the
    part of a pending call."""
    return (bool(agents & {*pending, *running})
            and all(part_of(c) is Part.WAITS for c in pending)
            and (bool(pending) or idle))


@dataclass
class Shares:
    """The time the loop of `profile` shared: to the model, to idle time,
    to the run's waits on agents, and to each call while it was pending and
    while it ran in the background, by its id."""
    model: float = 0.0
    idle: float = 0.0
    waits: float = 0.0
    pending: dict[str, float] = field(default_factory=dict)
    background: dict[str, float] = field(default_factory=dict)

    def spend(self, d: float, pending: Sequence[str], running: Sequence[str], idle: bool,
              waiting: bool) -> None:
        """Share `d` seconds of a gap where `pending` are the pending calls,
        `running` the calls in the background, and `idle` whether the run is
        idle, as `profile_runs.py --help runs` gives it."""
        if waiting:
            self.waits += d
        if pending:
            add(self.pending, pending, d)
        elif not idle:
            self.model += d
        elif running:
            add(self.background, running, d)
        else:
            self.idle += d

    def merge(self, other: "Shares") -> None:
        """Add the time `other` shared."""
        self.model += other.model
        self.idle += other.idle
        self.waits += other.waits
        for into, given in ((self.pending, other.pending), (self.background, other.background)):
            for c, d in given.items():
                into[c] = into.get(c, 0.0) + d


def add(into: dict[str, float], calls: Sequence[str], d: float) -> None:
    for c in calls:
        into[c] = into.get(c, 0.0) + d / len(calls)


@dataclass
class Gap:
    """The time between two entries of a run: its start and end, the calls
    pending and those in the background at its start, whether the run is
    idle, and, once shared, its `Shares`."""
    start: float
    end: float
    pending: tuple[str, ...]
    running: tuple[str, ...]
    idle: bool
    shares: Shares | None = None

    def share(self, into: Shares, end_of: Callable[[str], float | None],
              part_of: Callable[[str], Part | None], agents: set[str]) -> list[str]:
        """Share the gap into `into`, where `end_of` gives when a call in the
        background ended, and `part_of` the part of a pending call, closing
        each call that ends within it, in the order of their ends; the
        calls it closed."""
        running = list(self.running)
        closed: list[str] = []
        prev = self.start

        def spend(d: float) -> None:
            into.spend(d, self.pending, running, self.idle,
                       waiting(agents, self.pending, running, self.idle, part_of))

        for at, call in sorted((x, c) for c in self.running
                               if (x := end_of(c)) is not None and x < self.end):
            at = max(at, prev)
            spend(at - prev)
            prev = at
            running.remove(call)
            closed.append(call)
        spend(self.end - prev)
        return closed


@dataclass
class Prompt:
    """A prompt after a run's brief: the index of its entry, its time, the
    entry, and the idle time and waits shared before it, with the gaps held
    then, whose shares it adds."""
    index: int
    time: float
    entry: Entry
    idle: float
    waits: float
    held: tuple["Gap", ...]


type Line = str | CallTime | Prompt
"""An `undecided` line of the loop of `profile`, or the call or the prompt
whose read at each read of the profile gives one: the agent type of an
Agent call, and the files a prompt gives."""


@dataclass
class ProfileLoop:
    """The state of the loop of `profile` over a run's entries, after the
    entry before the last message entry (`agent_turns.is_message`), with the
    entries from that one on (`tail`), whose turn marks the next message
    entry gives. `label` names the run in an `undecided` line, and
    `messaged` is whether the run has a parent whose messages it reads."""
    label: str
    messaged: bool
    count: int = 0
    tail: list[tuple[int, Entry]] = field(default_factory=list)
    first: float | None = None
    prev: float | None = None
    last: float = 0.0
    idle: bool = False
    briefed: int | None = None
    brief: list[str] = field(default_factory=list)
    prompts: list[Prompt] = field(default_factory=list)
    lines: list[Line] = field(default_factory=list)
    found_lines: list[str] = field(default_factory=list)
    calls: dict[str, CallTime] = field(default_factory=dict)
    pending: dict[str, None] = field(default_factory=dict)
    running: dict[str, None] = field(default_factory=dict)
    agents: set[str] = field(default_factory=set)
    agent_calls: set[str] = field(default_factory=set)
    found: dict[str, Background] = field(default_factory=dict)
    told: dict[str, float] = field(default_factory=dict)
    shares: Shares = field(default_factory=Shares)
    held: list[Gap] = field(default_factory=list)
    changed: bool = False
    said: str | None = None
    cwd: str | None = None
    context: int | None = None
    usage: dict[str | None, list[dict[str, Any]]] = field(default_factory=dict)
    priced: dict[tuple[int, str | None], tuple[int, float | None, tuple[str, ...]]] = field(
        default_factory=dict)
    bash: set[str] = field(default_factory=set)
    refused: list[float] = field(default_factory=list)

    def step(self, _path: Path, _line: int, e: Entry) -> None:
        """Add the entry `e`: its reads that no later entry changes, and the
        loop over the entries before it whose turn marks it gives."""
        i = self.count
        self.count += 1
        self.read(e)
        if not is_message(e):
            self.tail.append((i, e))
            return
        for j, x in self.tail:
            self.run(j, x, e)
        self.tail = [(i, e)]
        if self.changed:
            self.changed = False
            self.share_held()

    def read(self, e: Entry) -> None:
        """The reads of `e` that need no later entry."""
        self.agent_calls |= tool_calls([e], AGENT_TOOLS)
        self.bash |= tool_calls([e], ("Bash",))
        found = backgrounds([e], self.agent_calls, self.found_lines)
        self.found.update(found)
        before = len(self.told)
        note_told(self.told, e)
        self.changed = self.changed or len(self.told) != before
        if e.get("timestamp"):
            self.last = max(self.last, epoch(e["timestamp"]))
        self.cwd = self.cwd or e.get("cwd") or None
        if e.get("type") == "assistant" and (n := entry_input(e)) is not None:
            self.context = n
        for k, group in grouped([e]).items():
            message = group[0]["message"]
            self.usage.setdefault(k, []).append(
                {"message": {"model": message.get("model"), "usage": message["usage"]}})
        self.refused += refused_at([e])

    def end_of(self, call: str) -> float | None:
        """When the call `call` in the background ended, as the
        notifications read so far give it."""
        return told_end(self.found[call], self.told)

    def part_of(self, call: str) -> Part | None:
        return self.calls[call].part()

    def run(self, i: int, e: Entry, nxt: Entry | None) -> None:
        """The loop of `profile` over the entry `e` of index `i`, where
        `nxt` is the next message entry after it."""
        start, end = marks(e, nxt)
        if is_prompt(e) and self.briefed is None:
            self.brief.append(message_text(e))
        if start and self.briefed is None:
            self.briefed = i
        if not e.get("timestamp"):
            return
        t = epoch(e["timestamp"])
        if self.prev is not None and t > self.prev:
            self.gap(Gap(self.prev, t, tuple(self.pending), tuple(self.running), self.idle))
        self.prev = t if self.prev is None else max(t, self.prev)
        self.first = t if self.first is None else self.first
        etype = e.get("type")
        if (self.messaged and self.briefed is not None and i > self.briefed
                and is_prompt(e)):
            p = Prompt(i, t, e, self.shares.idle, self.shares.waits, tuple(self.held))
            self.prompts.append(p)
            self.lines.append(p)
        if etype == "assistant":
            text = "\n".join(b.get("text", "") for b in blocks(e, "text")).strip()
            self.said = text or self.said
            for b in blocks(e, "tool_use"):
                self.call(b, t)
        elif etype == "user":
            results = results_by_call([e])
            for b in blocks(e, "tool_result"):
                self.answer(b.get("tool_use_id", ""), results, t)
        if end:
            self.idle = True
            self.pending.clear()
        else:
            self.idle = self.idle and etype != "assistant" and not start

    def gap(self, g: Gap) -> None:
        """Share the gap `g`, or hold it where its share turns on a value no
        entry has given yet: the end of a call in the background, where the
        run is idle with no call pending or that call launched an agent, or
        the part of a pending call, where the run waits on an agent."""
        open_ = [c for c in g.running if self.end_of(c) is None]
        waits_turn = (bool(g.pending) or g.idle) and bool(
            self.agents & {*g.pending, *g.running}) and (
            any(self.part_of(c) is None for c in g.pending)
            or not self.agents & set(g.pending) and any(c in self.agents for c in open_))
        if (open_ and g.idle and not g.pending) or waits_turn:
            self.held.append(g)
            for c in g.running:
                if (x := self.end_of(c)) is not None and x < g.end:
                    del self.running[c]
            return
        for c in g.share(self.shares, self.end_of, self.part_of, self.agents):
            del self.running[c]

    def share_held(self) -> None:
        """Share each held gap whose values the entries read so far give,
        and hold it no longer."""
        for g in self.held:
            if all(self.end_of(c) is not None for c in g.running) and all(
                    self.part_of(c) is not None for c in g.pending):
                g.shares = Shares()
                g.share(g.shares, self.end_of, self.part_of, self.agents)
                self.shares.merge(g.shares)
        self.held = [g for g in self.held if g.shares is None]

    def call(self, b: dict[str, Any], t: float) -> None:
        tid = b.get("id", "")
        rec = CallTime(b, t, "", result_sure(b))
        if (old := self.calls.get(tid)) is not None:
            rec = replace(old, block=b, start=t, end=None, uses=old.uses + 1)
        if b.get("name") in AGENT_TOOLS:
            self.agents.add(tid)
            self.lines.append(rec)
        lines: list[str] = []
        rec.command = call_command(b, lines, self.label)
        self.lines += lines
        self.calls[tid] = rec
        self.pending[tid] = None

    def answer(self, tid: str, results: dict[str, dict[str, Any]], t: float) -> None:
        self.pending.pop(tid, None)
        rec = self.calls.get(tid)
        if rec is None:
            return
        r = results.get(tid)
        rec.result = None if r is None else {k: r[k] for k in ("agentId", *MOVED) if k in r}
        rec.answered = True
        rec.launched = tid in self.found
        rec.end = t
        self.changed = True
        if rec.block.get("name") not in AGENT_TOOLS or (rec.block.get("input") or {}).get(
                "subagent_type"):
            rec.call = classify(rec.block, rec.result, rec.launched,
                                str((rec.block.get("input") or {}).get("subagent_type")))
        if rec.launched:
            self.running.pop(tid, None)
            self.running[tid] = None
            rec.reach = t if self.prev is None else self.prev

    def copied(self) -> "ProfileLoop":
        """A copy that a read of the profile runs on, leaving this state as
        the fold keeps it."""
        out = copy.copy(self)
        out.tail, out.brief, out.prompts, out.lines = [], list(self.brief), list(
            self.prompts), list(self.lines)
        out.calls = {k: replace(v) for k, v in self.calls.items()}
        out.lines = [out.calls.get(x.block.get("id", ""), x) if isinstance(x, CallTime) else x
                     for x in self.lines]
        out.pending, out.running = dict(self.pending), dict(self.running)
        out.agents = set(self.agents)
        out.shares = replace(self.shares, pending=dict(self.shares.pending),
                             background=dict(self.shares.background))
        out.held = list(self.held)
        return out

    def price(self, group: list[dict[str, Any]], undecided: list[str],
              at: str | None) -> float | None:
        """`request_cost` of `group`, a group of `usage`, held while the
        group keeps its count of entries."""
        key = (id(group), at)
        held = self.priced.get(key)
        if held is None or held[0] != len(group):
            lines: list[str] = []
            held = len(group), request_cost(group, lines, at), tuple(lines)
            self.priced[key] = held
        undecided.extend(held[2])
        return held[1]


def profile(path: Path, undecided: list[str], price_at: str | None = None) -> Run:
    """Its token cost is priced at the model `price_at` where one is given."""
    agent_type, description = run_type(path)
    label = agent_id(path) if is_subagent(path) else path.stem
    parent = parent_id(path) if is_subagent(path) else None
    kept = fold(ProfileLoop.step, lambda: ProfileLoop(label, parent is not None), path,
                chain(path))
    loop = kept.copied()
    for i, e in kept.tail:
        loop.run(i, e, None)
    session = session_of(path)
    undecided.extend(loop.found_lines)
    ends = ends_from(loop.found, loop.told, loop.last)
    end = loop.prev or 0.0

    def part_of(call: str) -> Part:
        return loop.calls[call].read_part()

    held: dict[int, Shares] = {}
    for g in loop.held:
        held[id(g)] = Shares()
        g.share(held[id(g)], ends.__getitem__, part_of, loop.agents)

    def shared(g: Gap) -> Shares:
        return g.shares or held[id(g)]

    calls = {tid: c.call or classify(c.block, c.result, c.launched,
                                     launched_type(c.block.get("input") or {}, c.result, session)
                                     or "?")
             for tid, c in loop.calls.items()}
    children = children_of(path, label) if parent is not None else frozenset()
    sessions = run_sessions(path) if parent is not None else []
    messages: list[Message] = []
    others: list[Message] = []
    unknown: list[str] = []
    for line in loop.lines:
        if isinstance(line, str):
            undecided.append(line)
        elif isinstance(line, CallTime):
            if launched_type(line.block.get("input") or {}, line.result, session) is None:
                undecided.append(mctx("{run}: the agent type of call {call} is "
                                      "unknown").format(run=label, call=line.block.get("id")))
        else:
            assert parent is not None
            idle = line.idle + sum(shared(g).idle for g in line.held)
            waits = line.waits + sum(shared(g).waits for g in line.held)
            who = sender(line.entry, parent, children, sessions)
            text = message_text(line.entry)
            if who is Sender.PARENT:
                messages.append(Message(line.index, line.time, unfiled(text, label, undecided),
                                        idle, waits))
            elif who is Sender.AGENT:
                others.append(Message(line.index, line.time, text, idle, waits))
            elif who is Sender.UNKNOWN:
                unknown.append(text)
    shares = [loop.shares, *held.values()]
    parts = dict.fromkeys(Part, 0.0)
    parts[Part.MODEL] = sum(s.model for s in shares)
    parts[Part.IDLE] = sum(s.idle for s in shares)
    waits = sum(s.waits for s in shares)
    groups: dict[Key, Group] = {}

    def group(key: Key) -> Group:
        return groups.setdefault(key, Group())

    still: list[str] = []
    for tid, c in calls.items():
        rec = loop.calls[tid]
        spent = sum(s.pending.get(tid, 0.0) for s in shares)
        group(c.pending).calls += rec.uses
        group(c.pending).time += spent
        parts[c.pending[0]] += spent
        if not (rec.launched and c.background):
            continue
        if c.background != c.pending:
            group(c.background).calls += 1
        ran = sum(s.background.get(tid, 0.0) for s in shares)
        group(c.background).time += ran
        parts[c.background[0]] += ran
        x = ends[tid]
        if x is None or x >= end or end == rec.reach:
            still.append(tid)
        close = end if x is None else x if end == rec.reach else max(x, rec.reach)
        start = rec.end or 0.0
        group(c.background).ran += max(close, start) - start
    running = [tid for tid in loop.running if tid in still]
    pending = list(loop.pending)
    waiting_at_end = waiting(loop.agents, pending, running, loop.idle, part_of)
    spans = {tid: Span(calls[tid].pending[1], c.command, c.start, tid, c.end)
             for tid, c in loop.calls.items()}
    if loop.brief and loop.first is not None:
        messages.insert(0, Message(loop.briefed if loop.briefed is not None else loop.count,
                                   loop.first,
                                   "\n".join(unfiled(text, label, undecided)
                                             for text in loop.brief), 0.0, 0.0))
    unpriced: list[str] = []
    cost = groups_cost(loop.usage, unpriced, price_at, loop.price)
    undecided.extend(f"{label}: {line}" for line in dict.fromkeys(unpriced))
    if loop.first is None:
        undecided.append(mctx("{run}: no entry gives a time, so its start "
                              "is unknown").format(run=label))
    return Run(label, agent_type, description, loop.first,
               end - loop.first if loop.first is not None else 0.0, parts,
               {k: g for k, g in groups.items() if g.time or g.calls},
               list(spans.values()), [spans[tid] for tid in pending if tid in spans],
               [spans[tid] for tid in running if ends[tid] is None and tid in spans],
               sorted(t for t in ends.values() if t is not None), loop.context,
               [int(request_input(g[0]["message"]["usage"])) for g in loop.usage.values()],
               cost, loop.said, waits, waiting_at_end,
               messages, others, unknown, loop.cwd, path,
               [s.command for s in spans.values() if s.call in loop.bash], loop.refused)
