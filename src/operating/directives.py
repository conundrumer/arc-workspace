"""The fixed form of the lines the coordinator gives an operator, in its
brief or a later message, that the command reads. Each line opens with the
word of its kind and a colon, past a list marker:

- `Solve: <task id> [<task id> ...]`, with `from create` or `from refine`
  after a task id to start its pipeline at that pass;
- `Solve from the queue: <count>`;
- `Drafts to review: <number>, ...`;
- `Tickets named: <number>, ...`;
- `Merged: <number>, ...`, the changes the coordinator gives as merged;
- `Merge: <number>`, a change under `tickets/blocked/` the user ruled on;
- `Tickets are open.`;
- `Override:` and `Decision:` lines, which the operator agent applies to the
  step the command prints, and the command passes over.

A line of the coordinator's in no such form is a step the command gives to
the coordinator as undecided.

A line gives steps only to the operator it reached, in its brief or a later
message: a line to an earlier operator of the session reaches a later one
only where a line to the later one gives its pipeline again while that
pipeline runs (`passes.every`)."""

import re
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

from operating.roles import PASSES, Role
from operating.state import Message, State


class Directive(StrEnum):
    SOLVE = "Solve"
    QUEUE = "Solve from the queue"
    DRAFTS = "Drafts to review"
    NAMED = "Tickets named"
    MERGED = "Merged"
    MERGE = "Merge"
    OPEN = "Tickets are open"
    OVERRIDE = "Override"
    DECISION = "Decision"


APPLIED = frozenset({Directive.OVERRIDE, Directive.DECISION})
"""The kinds the operator agent applies itself."""

LINE = re.compile(r"^\s*(?:[-*]\s+)?(?P<kind>[A-Z][a-z ]+?)(?::\s*(?P<rest>.*?)|\.)\s*$")
NUMBER = re.compile(r"\b(?:\d+-)?\d+\b")
TASK = re.compile(r"\b(?P<task>[0-9a-f]{8})(?:\s+from\s+(?P<start>create|refine))?\b")


@dataclass(frozen=True)
class Line:
    message: Message
    kind: Directive | None
    text: str
    rest: str


def lines(state: State) -> list[Line]:
    """Each non-blank line the coordinator gave the operator `me`, in the
    order the messages arrived."""
    return parsed(state.received)


def session_lines(state: State) -> list[Line]:
    """Each non-blank line the coordinator gave any operator of the
    session, in the order the messages arrived."""
    return parsed(state.arrived)


def parsed(messages: Iterable[Message]) -> list[Line]:
    out: list[Line] = []
    for m in (m for m in messages if m.sender is None):
        for raw in m.text.splitlines():
            if not raw.strip():
                continue
            match = LINE.match(raw)
            kind = None
            rest = ""
            if match is not None:
                try:
                    kind = Directive(match["kind"])
                    rest = match["rest"] or ""
                except ValueError:
                    kind = None
            out.append(Line(m, kind, raw.strip(), rest))
    return out


def numbers(state: State, kind: Directive) -> list[tuple[str, float]]:
    """Each ticket number lines of `kind` give, with the time of the
    message that gave it."""
    return [(n, ln.message.time) for ln in lines(state) if ln.kind is kind
            for n in NUMBER.findall(ln.rest)]


def named(state: State) -> set[str]:
    """The tickets the coordinator names to the operator."""
    return {n for k in (Directive.NAMED, Directive.DRAFTS, Directive.MERGE, Directive.MERGED)
            for n, _ in numbers(state, k)}


@dataclass(frozen=True)
class Pipeline:
    """A solver pipeline the coordinator gives: its task, the pass it
    starts at, the time of the message that gives it, the operator that
    message reached, and whether a `Solve from the queue` line gives it."""
    task: str
    start: Role
    since: float
    operator: str
    queued: bool = False


def pipelines(given: list[Line]) -> list[Pipeline]:
    """The pipelines the `Solve` lines of `given` give."""
    out: list[Pipeline] = []
    for ln in given:
        if ln.kind is Directive.SOLVE:
            for m in TASK.finditer(ln.rest):
                start = Role(m["start"]) if m["start"] else PASSES[0]
                out.append(Pipeline(m["task"], start, ln.message.time, ln.message.operator))
    return out


def queue_counts(given: list[Line]) -> list[tuple[int, Message]]:
    """The count each `Solve from the queue` line of `given` gives, with
    its message."""
    return [(int(ln.rest), ln.message) for ln in given
            if ln.kind is Directive.QUEUE and ln.rest.isdigit()]


def unread(state: State) -> list[Line]:
    """The coordinator's lines in no form the command reads."""
    return [ln for ln in lines(state) if ln.kind is None]
