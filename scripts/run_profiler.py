"""The profile of where an agent run's wall time goes, from its Claude
Code transcripts, as `profile_runs.py --help runs` gives it.

A profile also reads files past those transcripts, and the state of running
processes: `noted_reads` states those reads."""

from collections.abc import Iterable
from pathlib import Path
from typing import Any

from agent_launches import children_of
from agent_turns import idle_after, turns
from command_labels import AGENT_TOOLS, POLL, call_command, command_label
from controlled_markdown import mctx
from filed_texts import unfiled
from run_backgrounds import background_ends, backgrounds
from run_reads import (blocks, context_size, is_prompt, message_text, parent_id,
                       results_by_call, run_entries, run_sessions, run_type, session_of,
                       tool_calls, type_in)
from run_records import Call, Group, Key, Message, Part, Run, Span
from senders import Sender, sender
from token_prices import grouped, request_input, requests, run_cost
from transcripts import agent_id, epoch, is_subagent

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


def profile(path: Path, undecided: list[str], price_at: str | None = None) -> Run:
    """Its token cost is priced at the model `price_at` where one is given."""
    agent_type, description = run_type(path)
    label = agent_id(path) if is_subagent(path) else path.stem
    session = session_of(path)
    entries = run_entries(path)
    results = results_by_call(entries)
    found = backgrounds(entries, tool_calls(entries, AGENT_TOOLS), undecided)
    bg_ends = background_ends(found, entries)
    starts, ends = turns(entries)
    # The index of the prompt the model first answers: the brief is the
    # prompts up to it.
    briefed = min(starts, default=len(entries))
    parent = parent_id(path) if is_subagent(path) else None
    children = children_of(path, label)
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
    agents: set[str] = set()
    waits = 0.0
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

    def waiting() -> bool:
        return bool(agents & (pending.keys() | running.keys())
                    and all(k[0] is Part.WAITS for k in pending.values())
                    and (pending or idle))

    def spend(d: float) -> None:
        nonlocal waits
        if waiting():
            waits += d
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
                                        parts[Part.IDLE], waits))
            elif who is Sender.AGENT:
                others.append(Message(i, t, message_text(e), parts[Part.IDLE], waits))
            elif who is Sender.UNKNOWN:
                unknown.append(message_text(e))
        if etype == "assistant":
            text = "\n".join(b.get("text", "") for b in blocks(e, "text")).strip()
            said = text or said
            for b in blocks(e, "tool_use"):
                tid = b.get("id", "")
                c = calls[tid] = classify(b, results.get(tid), tid in found,
                                          session, undecided, label)
                if b.get("name") in AGENT_TOOLS:
                    agents.add(tid)
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
    waiting_at_end = waiting()
    brief = [unfiled(message_text(e), label, undecided)
             for e in entries[:briefed + 1] if is_prompt(e)]
    if brief and first is not None:
        messages.insert(0, Message(briefed, first, "\n".join(brief), 0.0, 0.0))
    cwd = next((e["cwd"] for e in entries if e.get("cwd")), None)
    context = context_size(reversed(entries))
    request_contexts = [int(request_input(e["message"]["usage"]))
                        for e in requests(grouped(entries))]
    unpriced: list[str] = []
    cost = run_cost(entries, unpriced, price_at)
    undecided.extend(f"{label}: {line}" for line in dict.fromkeys(unpriced))
    in_flight = [spans[tid] for tid in pending if tid in spans]
    backgrounded = [spans[tid] for tid in running
                    if bg_ends[tid] is None and tid in spans]
    ended = sorted(t for t in bg_ends.values() if t is not None)
    for tid in list(running):
        close(tid, end if (at := bg_ends[tid]) is None else at)
    wall = end - first if first is not None else 0.0
    if first is None:
        undecided.append(mctx("{run}: no entry gives a time, so its start "
                              "is unknown").format(run=label))
    return Run(label, agent_type, description, first, wall, parts,
               {k: g for k, g in groups.items() if g.time or g.calls},
               list(spans.values()), in_flight, backgrounded, ended, context, request_contexts,
               cost, said, waits, waiting_at_end,
               messages, others, unknown, cwd, path)
