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
the coordinator as undecided."""

import re
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
    """Each non-blank line the coordinator gave the session's operators, in
    the order the messages arrived."""
    out: list[Line] = []
    for m in sorted((m for m in state.messages if m.sender is None), key=lambda m: m.time):
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
    """The tickets the coordinator names to the operators."""
    return {n for k in (Directive.NAMED, Directive.DRAFTS, Directive.MERGE, Directive.MERGED)
            for n, _ in numbers(state, k)}


@dataclass(frozen=True)
class Pipeline:
    """A solver pipeline the coordinator gives: its task, the pass it
    starts at, and the time of the message that gives it."""
    task: str
    start: Role
    since: float


def pipelines(state: State) -> list[Pipeline]:
    out: list[Pipeline] = []
    for ln in lines(state):
        if ln.kind is Directive.SOLVE:
            for m in TASK.finditer(ln.rest):
                start = Role(m["start"]) if m["start"] else PASSES[0]
                out.append(Pipeline(m["task"], start, ln.message.time))
    return out


def queue_counts(state: State) -> list[tuple[int, float]]:
    return [(int(ln.rest), ln.message.time) for ln in lines(state)
            if ln.kind is Directive.QUEUE and ln.rest.isdigit()]


def unread(state: State) -> list[Line]:
    """The coordinator's lines in no form the command reads."""
    return [ln for ln in lines(state) if ln.kind is None]
