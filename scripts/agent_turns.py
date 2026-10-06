"""The turns of an agent's run, read from its transcripts, as the HELP of
`profile_runs` gives them."""

from collections.abc import Callable
from functools import cache
from pathlib import Path

from controlled_markdown import mctx
from run_reads import blocks, is_prompt, text_of
from senders import INTERRUPTED
from transcripts import Entry, agent_id, chain, entries_back, epoch, read_entries

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
        if is_turn_entry(e) or is_prompt(e):
            nxt = e
    return starts, ends


def idle_after(idle: bool, i: int, entry: Entry, starts: set[int],
               ends: set[int]) -> bool:
    """Whether a run is idle after its `i`-th entry, from `idle`, whether it
    was before it."""
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
    last = [e for e in entries if is_turn_entry(e)][-1:]
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


def turn_after(path: Path, t: float, undecided: list[str]) -> bool:
    """Whether the transcript at `path` holds an entry of a turn timestamped
    after `t`. An entry of a turn with no timestamp counts as not, and an
    `undecided` line names the run."""
    out = False
    for e in read_entries(path):
        if not is_turn_entry(e):
            continue
        if not e.get("timestamp"):
            undecided.append(mctx("{run}: a `{type}` entry of its transcript has no "
                                  "timestamp, so it counts as before its parent's "
                                  "last sign that it reported").format(
                run=agent_id(path), type=e.get("type")))
        elif epoch(e["timestamp"]) > t:
            out = True
    return out


def last_time(path: Path, holds: Callable[[Entry], bool] | None = None) -> float | None:
    for p in reversed(chain(path)):
        for e in entries_back(p):
            if e.get("timestamp") and (holds is None or holds(e)):
                return epoch(e["timestamp"])
    return None


def is_turn_entry(entry: Entry) -> bool:
    return entry.get("type") in MESSAGE_TYPES
