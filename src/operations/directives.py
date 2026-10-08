"""The fixed form of the lines the coordinator gives the loop, by
`operate.py tell`, that the command reads. Each line opens with the
word of its kind and a colon, past a list marker:

- `Solve: <task id> [<task id> ...]`, with `from create` or `from refine`
  after a task id to start its pipeline at that pass;
- `Solve from the queue: <count>`;
- `Drafts to review: <number>, ...`;
- `Tickets named: <number>, ...`;
- `Merged: <number>, ...`, the changes the coordinator gives as merged;
- `Merge: <number>`, a change under `tickets/blocked/` the user decided on;
- `Tickets are open.`;
- the rulings, which the command applies: `Decision: <decision key>
  <choice>`, which gives a held step one of the choices that step gives
  (`decided`); `Override: pass over <step key>`, which passes over the
  step whose key it gives (`passed_over`); and `Override: <task id>
  <pass> <override>`, which gives the override in the brief of the next
  launch of that pass on that task (`overrides`).

A line of the coordinator's in no such form, a ruling among them, goes
back to the coordinator as undecided, since only its writer knows what it
meant.

The reply of a ticket analyst on a held step (`decisions`) gives its
rulings in the same forms.

A ruling holds whether the coordinator gave it or a ticket analyst on a
held step replied with it."""

import re
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

from arc.task import TASK_ID
from controlled_markdown import mctx
from operations.reports import LIST_MARKER
from operations.roles import PASSES, Purpose, Role
from operations.state import Agent, Message, Report, State
from operations.steps import STEP_KEY, Undecided, decision_key, held


class Decision(StrEnum):
    """The choices a `Decision:` line gives a held step (`decided`): go on as though the step were passed, the
    merge, the move to `tickets/open/`, or another agent on it."""
    PASSES = "passes"
    MERGE = "merge"
    OPEN = "open"
    AGAIN = "again"


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


RULINGS = frozenset({Directive.OVERRIDE, Directive.DECISION})

PASS_OVER = re.compile(rf"pass over (?P<key>{STEP_KEY.pattern})")
OVERRIDE = re.compile(rf"(?P<task>{TASK_ID})\s+(?P<role>{'|'.join(PASSES)})\s+(?P<text>\S.*)")
DECISION = re.compile(rf"(?P<key>{STEP_KEY.pattern})\s+(?P<choice>[a-z]+)")

LINE = re.compile(rf"^\s*(?:{LIST_MARKER}\s+)?(?P<kind>[A-Z][a-z ]+?)(?::\s*(?P<rest>.*?)|\.)\s*$")
NUMBER = re.compile(r"\b(?:\d+-)?\d+\b")
TASK = re.compile(rf"\b(?P<task>{TASK_ID})(?:\s+from\s+(?P<start>create|refine))?\b")


@dataclass(frozen=True)
class Line:
    message: Message
    kind: Directive | None
    text: str
    rest: str


def lines(state: State) -> list[Line]:
    """Each non-blank line the coordinator gave the loop `me`, in the order
    the lines arrived."""
    return parsed(state.received)


def session_lines(state: State) -> list[Line]:
    """Each non-blank line the coordinator gave, in the order the lines
    arrived."""
    return parsed(state.arrived)


def parsed(messages: Iterable[Message]) -> list[Line]:
    return [ln for m in messages if m.sender is None for ln in message_lines(m)]


def message_lines(m: Message) -> list[Line]:
    """Each non-blank line of `m`, with its kind where it is in a form the
    command reads."""
    out: list[Line] = []
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


def step_decisions(state: State) -> list[Line]:
    """The `Override:` and `Decision:` lines of the replies of the ticket
    analysts on held steps, each read as a message of its analyst to the
    loop, in the order the replies came."""
    out = [ln for a, purpose, _ in state.analysts() if purpose is Purpose.STEP
           for r in a.reports for ln in reply_decisions(a, r)]
    return sorted(out, key=lambda ln: ln.message.time)


def reply_decisions(a: Agent, r: Report) -> list[Line]:
    """The `Override:` and `Decision:` lines of the reply `r` of `a`."""
    return [ln for ln in message_lines(Message(a.loop, r.time, a.agent_id, r.text))
            if ln.kind in RULINGS and ruling_form(ln) is not None]


def numbers(state: State, kind: Directive) -> list[tuple[str, float]]:
    """Each ticket number lines of `kind` give, with the time of the
    message that gave it."""
    return [(n, ln.message.time) for ln in lines(state) if ln.kind is kind
            for n in NUMBER.findall(ln.rest)]


def decided(state: State, what: str, choices: dict[Decision, str]) -> Decision | Undecided:
    """The choice among `choices` that the last `Decision:` line giving the
    decision key of the held step `what` gives, of the coordinator or of
    the reply of a ticket analyst on a held
    step: the first of its words after that key that is a choice. Where no
    such line came, the step held on `what` with its choices, and where
    the last such line gives none of them, the undecided step on that
    line."""
    k = decision_key(what)
    for ln in reversed(rulings(state)):
        m = DECISION.fullmatch(ln.rest)
        if ln.kind is not Directive.DECISION or m is None or m["key"] != k:
            continue
        found = Decision(m["choice"]) if m["choice"] in choices else None
        if found is None:
            listed = ", ".join(choices)
            return Undecided(mctx("the line `{line}` gives step {k} none of the choices "
                                  "{listed}").format(line=ln.text, k=k, listed=listed))
        return found
    return held_on(what, choices)


def rulings(state: State) -> list[Line]:
    """The rulings of the coordinator and of the replies of the ticket analysts on held steps, in the order they
    came."""
    return sorted([ln for ln in session_lines(state) if ln.kind in RULINGS]
                  + step_decisions(state), key=lambda ln: ln.message.time)


def ruling_form(ln: Line) -> re.Match[str] | None:
    """The fixed form `ln`, a ruling, is in, or None."""
    if ln.kind is Directive.DECISION:
        return DECISION.fullmatch(ln.rest)
    return PASS_OVER.fullmatch(ln.rest) or OVERRIDE.fullmatch(ln.rest)


def passed_over(state: State) -> dict[str, str]:
    """The step keys the `Override: pass over` rulings give, each with the
    line that gives it."""
    return {m["key"]: ln.text for ln in rulings(state)
            if ln.kind is Directive.OVERRIDE and (m := PASS_OVER.fullmatch(ln.rest))}


def overrides(state: State, task: str, role: Role, since: float) -> list[str]:
    """The overrides the rulings since `since` give the pass `role` on
    `task`, in the order they came."""
    return [m["text"] for ln in rulings(state) if ln.message.time >= since
            and ln.kind is Directive.OVERRIDE and (m := OVERRIDE.fullmatch(ln.rest))
            and m["task"] == task and m["role"] == role]


def held_on(what: str, choices: dict[Decision, str]) -> Undecided:
    """The step held on `what` until a `Decision:` line gives it one of
    `choices`."""
    return held(what, {c.value: meaning for c, meaning in choices.items()})


def named(state: State) -> set[str]:
    """The tickets the coordinator names to the loop."""
    return {n for k in (Directive.NAMED, Directive.DRAFTS, Directive.MERGE, Directive.MERGED)
            for n, _ in numbers(state, k)}


@dataclass(frozen=True)
class Pipeline:
    """A solver pipeline the coordinator gives: its task, the pass it
    starts at, the time of the line that gives it, the loop that line
    reached, and whether a `Solve from the queue` line gives it."""
    task: str
    start: Role
    since: float
    loop: str
    queued: bool = False


def pipelines(given: list[Line]) -> list[Pipeline]:
    """The pipelines the `Solve` lines of `given` give."""
    out: list[Pipeline] = []
    for ln in given:
        if ln.kind is Directive.SOLVE:
            for m in TASK.finditer(ln.rest):
                start = Role(m["start"]) if m["start"] else PASSES[0]
                out.append(Pipeline(m["task"], start, ln.message.time, ln.message.loop))
    return out


def queue_counts(given: list[Line]) -> list[tuple[int, Message]]:
    """The count each `Solve from the queue` line of `given` gives, with
    its message."""
    return [(int(ln.rest), ln.message) for ln in given
            if ln.kind is Directive.QUEUE and ln.rest.isdigit()]


def unread(state: State) -> list[Line]:
    """The coordinator's lines in no form the command reads, rulings in no
    fixed form among them."""
    return [ln for ln in lines(state)
            if ln.kind is None or ln.kind in RULINGS and ruling_form(ln) is None]
