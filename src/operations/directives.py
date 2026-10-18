"""The fixed form of the lines the coordinator gives an operator, in its
brief or a later message, that the command reads. Each line opens with the
prefix `Op`, the word of its kind and a colon, past a list marker:

- `Op solve: <task id> [<task id> ...]`, with `from create` or `from refine`
  after a task id to start its pipeline at that pass;
- `Op run: <path>`, a run script, as `runs` gives it;
- `Op drafts to review: <number>, ...`;
- `Op expedite: <number>, ...`, for every operator of the session, and
  the tickets an `Op allow:` line with those numbers reaches
  (`taking.expedited`);
- `Op allow: <number>, ...`, the tickets that `Op scope: own.` and
  `Op pause.` admit for every operator of the session, and the changes a
  chain of links reaches from them, with each `change` whose Motivation
  gives a reached ticket that is not a `change` (`taking.allowed`);
- `Op merged: <number>, ...`, the changes the coordinator gives as merged;
- `Op merge: <number>`, a change under `tickets/blocked/` whose merge that line rules;
- `Op tickets are open.`, which leaves the scope as `own_scope` gives it;
- `Op scope: own.`, under which no operator of the session settles an open
  ticket or takes a change outside the work held, the tickets an
  `Op allow:` or an `Op expedite:` line gives and the session's line of
  work (`taking.own_work`), and `Op scope: all.`, which ends that limit,
  the last such line standing, and `Op scope: own.` where none came
  (`own_scope`);
- `Op pause.`, after which no operator of the session settles an open
  ticket or takes a change outside the work held and the tickets an
  `Op allow:` or an `Op expedite:` line gives, and `Op resume.`, which ends
  the pause, the last such line standing (`paused`);
- `Op pace: <preset> [<argument> ...]` or `Op pace: <path>`, the usage pace
  for every operator of the session (`pace`), as `pacing` gives it;
- the rulings, `Op decision:` and `Op override:` lines in the forms that
  `scripts/operate.py --help rulings` gives, which the command applies (`ruling`,
  `passed_over`, `given_again`, `overrides`).

A line of the coordinator's in no such form, a ruling among them, goes
back to the coordinator once as undecided, since only its writer knows
what it meant.

A line in a bare form, one of these forms with no prefix and the word of
its kind capitalized (`BARE`), takes its kind only in a message that
arrived before the session's first message of the coordinator with a line
in a prefixed form (`cutoff`), so that an operator that runs across the
change to the prefixed forms keeps what the lines it received before that
change gave it. The reply of a ticket analyst whose brief gives the bare
ruling form (`steps.bare`) is read in the bare forms as well.

The reply of a ticket analyst on a held step (`decisions`) gives its
rulings in the same forms.

Which operator a line gives steps to is as `plan` gives. A ruling holds
for every operator of the session, whether the coordinator gave it or a
ticket analyst on a held step replied with it, so an operator that takes
over a change from an earlier one continues it by the rulings the earlier
one received."""

import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from arc.task import TASK_ID
from controlled_markdown import mctx
from operations.reports import LIST_MARKER
from operations.pacing import Preset, line_pace
from operations.roles import PASSES, Purpose, Role
from operations.state import Agent, Message, Report, State
from operations.steps import (STEP_KEY, Step, Undecided, bare, decision_key, digest,
                              held, key)


class Decision(StrEnum):
    """The choices an `Op decision:` line gives a held step (`ruling`): go on as though the step were passed, the
    merge, the move to `tickets/open/`, or another agent on it."""
    PASSES = "passes"
    MERGE = "merge"
    OPEN = "open"
    AGAIN = "again"


OP = "Op "


class Scope(StrEnum):
    """The tickets an `Op scope:` line has the operators take: the
    session's line of work, as `taking.scope_admits` gives it, the scope
    where no such line came, or every open ticket."""
    OWN = "own"
    ALL = "all"


class Directive(StrEnum):
    SOLVE = "Op solve"
    RUN = "Op run"
    DRAFTS = "Op drafts to review"
    EXPEDITE = "Op expedite"
    ALLOW = "Op allow"
    MERGED = "Op merged"
    MERGE = "Op merge"
    OPEN = "Op tickets are open"
    PAUSE = "Op pause"
    RESUME = "Op resume"
    SCOPE = "Op scope"
    PACE = "Op pace"
    OVERRIDE = "Op override"
    DECISION = "Op decision"


BARE = {d.removeprefix(OP).capitalize(): d for d in Directive}


RULINGS = frozenset({Directive.OVERRIDE, Directive.DECISION})

PAUSE_LINES = frozenset({Directive.PAUSE, Directive.RESUME})

PASS_OVER = re.compile(rf"pass over (?P<key>{STEP_KEY.pattern})")
GIVE_AGAIN_WORDS = "give again"
GIVE_AGAIN = re.compile(rf"{GIVE_AGAIN_WORDS} (?P<key>{STEP_KEY.pattern})")
OVERRIDE = re.compile(rf"(?P<task>{TASK_ID})\s+(?P<role>{'|'.join(PASSES)})\s+(?P<text>\S.*)")
DECISION = re.compile(rf"(?P<key>{STEP_KEY.pattern})\s+(?P<choice>[a-z]+)")
SCOPE = re.compile(rf"(?P<scope>{'|'.join(Scope)})\.")

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
    """Each non-blank line the coordinator gave the operator `me`, in the
    order the messages arrived."""
    return parsed(state.received, cutoff(state.arrived))


def session_lines(state: State) -> list[Line]:
    """Each non-blank line the coordinator gave any operator of the
    session, in the order the messages arrived."""
    return parsed(state.arrived, cutoff(state.arrived))


def parsed(messages: Iterable[Message], before: float | None) -> list[Line]:
    """The lines of the coordinator's messages among `messages`, a bare
    line with its kind where its message arrived before `before`, or
    `before` is None."""
    return [ln for m in messages if m.sender is None
            for ln in message_lines(m, before is None or m.time < before)]


def cutoff(arrived: Iterable[Message]) -> float | None:
    """The time of the first message of the coordinator among `arrived`,
    the session's messages in the order they arrived, with a line in a
    prefixed form, or None where none came."""
    return next((m.time for m in arrived if m.sender is None
                 if any(ln.kind is not None for ln in message_lines(m, False))), None)


def message_lines(m: Message, bare: bool) -> list[Line]:
    """Each non-blank line of `m`, with its kind where it is in a form the
    command reads, a bare form among them where `bare`."""
    out: list[Line] = []
    for raw in m.text.splitlines():
        if not raw.strip():
            continue
        match = LINE.match(raw)
        kind = None if match is None else kind_of(match["kind"], bare)
        rest = "" if match is None or kind is None else match["rest"] or ""
        out.append(Line(m, kind, raw.strip(), rest))
    return out


def kind_of(word: str, bare: bool) -> Directive | None:
    if word in Directive:
        return Directive(word)
    return BARE.get(word) if bare else None


def step_decisions(state: State) -> list[Line]:
    """The `Op override:` and `Op decision:` lines of the replies of the ticket
    analysts on held steps, each read as a message of its analyst to the
    operator that launched it, in the order the replies came."""
    out = [ln for a, purpose, _ in state.analysts() if purpose is Purpose.STEP
           for r in a.reports for ln in reply_decisions(a, r)]
    return sorted(out, key=lambda ln: ln.message.time)


def reply_decisions(a: Agent, r: Report) -> list[Line]:
    """The `Op override:` and `Op decision:` lines of the reply `r` of `a`."""
    return [ln for ln in message_lines(Message(a.operator, r.time, a.agent_id, r.text),
                                       bare(a.brief))
            if ln.kind in RULINGS and ruling_form(ln) is not None]


def numbers(state: State, kind: Directive) -> list[tuple[str, float]]:
    """Each ticket number lines of `kind` to the operator give, with the
    time of the message that gave it."""
    return numbers_in(lines(state), kind)


def numbers_in(given: list[Line], kind: Directive) -> list[tuple[str, float]]:
    return [(n, ln.message.time) for ln in given if ln.kind is kind
            for n in NUMBER.findall(ln.rest)]


def allow_named(state: State) -> set[str]:
    """The tickets an `Op allow:` line to any operator of the session gives."""
    return {n for n, _ in numbers_in(session_lines(state), Directive.ALLOW)}


@dataclass(frozen=True)
class Ruling:
    """The choice a ruling on a held step gives, and the time of that
    ruling. A launch on that ruling takes the time into its occasion, so a
    second launch on one held step has a key of its own."""
    choice: Decision
    time: float


def ruling(state: State, what: str, choices: dict[Decision, str]) -> Ruling | Undecided:
    """The choice among `choices` that the last `Op decision:` ruling giving
    the decision key of the held step `what` gives, of the coordinator to
    an operator of the session or of the reply of a ticket analyst on a
    held step, with its time. Where no such ruling came, the step held on
    `what` with its choices, and where the last such ruling gives none of
    them, the undecided step on that line."""
    found = last_decision(state, what)
    if found is None:
        return held_on(what, choices)
    ln, m = found
    if m["choice"] not in choices:
        listed = ", ".join(choices)
        return Undecided(mctx("the line `{line}` gives step {k} none of the choices "
                              "{listed}").format(line=ln.text, k=m["key"], listed=listed))
    return Ruling(Decision(m["choice"]), ln.message.time)


def last_decision(state: State, what: str) -> tuple[Line, re.Match[str]] | None:
    """The last `Op decision:` ruling that gives the decision key of the held
    step `what`, with its match of `DECISION`, or None."""
    k = decision_key(what)
    for ln in reversed(rulings(state)):
        m = DECISION.fullmatch(ln.rest)
        if ln.kind is Directive.DECISION and m is not None and m["key"] == k:
            return ln, m
    return None


def rulings(state: State) -> list[Line]:
    """The rulings in a fixed form of the coordinator to any operator of
    the session and of the replies of the ticket analysts on held steps, in
    the order they came."""
    return sorted([ln for ln in session_lines(state)
                   if ln.kind in RULINGS and ruling_form(ln) is not None]
                  + step_decisions(state), key=lambda ln: ln.message.time)


def line_scope(rest: str) -> Scope | None:
    """The scope an `Op scope:` line's text after the colon gives, or None
    where it is in no form `SCOPE` reads."""
    m = SCOPE.fullmatch(rest)
    return None if m is None else Scope(m["scope"])


def own_scope(state: State) -> bool:
    """Whether the last `Op scope:` line in a form `line_scope` reads, to any
    operator of the session, gives `own`, or no such line came. The result
    holds for every operator of the session, one that takes over from an
    ended operator included."""
    return last_given(state, frozenset({Directive.SCOPE}),
                      lambda ln: line_scope(ln.rest)) is not Scope.ALL


def paused(state: State) -> bool:
    """Whether the last `Op pause.` or `Op resume.` line, to any operator
    of the session, is `Op pause.`. The result holds for every operator of
    the session, one that takes over from an ended operator included."""
    return last_given(state, PAUSE_LINES, lambda ln: None if ln.rest else ln.kind) is Directive.PAUSE


def pace(state: State) -> Preset | Path | None:
    """The preset or the script path of the last `Op pace:` line in a form
    `pacing.line_pace` reads to any operator of the session, or None where
    none came."""
    return last_given(state, frozenset({Directive.PACE}),
                      lambda ln: line_pace(ln.rest, state.main_tree))


def last_given[T](state: State, kinds: frozenset[Directive],
                  read: Callable[[Line], T | None]) -> T | None:
    """What `read` gives for the last line of `kinds`, to any operator of
    the session, for which it gives anything, or None where no such line
    came."""
    given = [v for ln in session_lines(state) if ln.kind in kinds if (v := read(ln)) is not None]
    return given[-1] if given else None


def ruling_form(ln: Line) -> re.Match[str] | None:
    """The fixed form `ln`, a ruling, is in, or None."""
    if ln.kind is Directive.DECISION:
        return DECISION.fullmatch(ln.rest)
    return (PASS_OVER.fullmatch(ln.rest) or GIVE_AGAIN.fullmatch(ln.rest)
            or OVERRIDE.fullmatch(ln.rest))


def passed_over(state: State) -> dict[str, Line]:
    """The step keys the `Op override: pass over` rulings give, each with the
    last ruling that gives it, less each key a later `Op override: give again`
    ruling gives."""
    out: dict[str, Line] = {}
    for ln in rulings(state):
        if ln.kind is not Directive.OVERRIDE:
            continue
        if m := PASS_OVER.fullmatch(ln.rest):
            out[m["key"]] = ln
        elif m := GIVE_AGAIN.fullmatch(ln.rest):
            out.pop(m["key"], None)
    return out


def give_again_line(key: str) -> str:
    """The ruling that makes the step `key` due once more, in the form
    `given_again` reads."""
    return f"{Directive.OVERRIDE}: {GIVE_AGAIN_WORDS} {key}"


def given_again(state: State) -> dict[str, float]:
    """The step keys the `Op override: give again` rulings give, each with the
    message time of the last ruling that gives it."""
    return {m["key"]: ln.message.time for ln in rulings(state)
            if ln.kind is Directive.OVERRIDE and (m := GIVE_AGAIN.fullmatch(ln.rest))}


def passed(step: Step, state: State) -> Line | None:
    """The ruling that passes `step` over, by its key or by its digest
    (`steps.digest`), the key a ruling written before the journal gave,
    or None. Whether a ruling on a solver pass holds for a pipeline is
    `passes.run`'s to decide."""
    over = passed_over(state)
    return over.get(key(step)) or over.get(digest(step))


def overrides(state: State, task: str, role: Role, since: float) -> list[str]:
    """The overrides the rulings since `since` give the pass `role` on
    `task`, in the order they came."""
    return [m["text"] for ln in rulings(state) if ln.message.time >= since
            and ln.kind is Directive.OVERRIDE and (m := OVERRIDE.fullmatch(ln.rest))
            and m["task"] == task and m["role"] == role]


def held_on(what: str, choices: dict[Decision, str]) -> Undecided:
    """The step held on `what` until an `Op decision:` line gives it one of
    `choices`."""
    return held(what, {c.value: meaning for c, meaning in choices.items()})


def named(state: State) -> set[str]:
    """The tickets the coordinator gives the operator in a line, and those
    of `allow_named`."""
    return {n for k in (Directive.EXPEDITE, Directive.DRAFTS, Directive.MERGE, Directive.MERGED)
            for n, _ in numbers(state, k)} | allow_named(state)


@dataclass(frozen=True)
class Pipeline:
    """A solver pipeline: its task, its passes in their order, the time of
    the message that gives it or of the call that starts it (`runs`), and
    the operator that message reached or that made that call."""
    task: str
    passes: tuple[Role, ...]
    since: float
    operator: str


def pipelines(given: list[Line]) -> list[Pipeline]:
    """The pipelines the `Op solve` lines of `given` give."""
    out: list[Pipeline] = []
    for ln in given:
        if ln.kind is Directive.SOLVE:
            for m in TASK.finditer(ln.rest):
                start = Role(m["start"]) if m["start"] else PASSES[0]
                out.append(Pipeline(m["task"], PASSES[PASSES.index(start):], ln.message.time,
                                    ln.message.operator))
    return out


def unread(state: State) -> list[Line]:
    """The coordinator's lines in no form the command reads, rulings,
    `Op pace:` and `Op scope:` lines in no fixed form, and `Op pause:` and
    `Op resume:` lines with text after the colon, among them."""
    return [ln for ln in lines(state)
            if ln.kind is None or ln.kind in RULINGS and ruling_form(ln) is None
            or ln.kind is Directive.PACE and line_pace(ln.rest, state.main_tree) is None
            or ln.kind is Directive.SCOPE and line_scope(ln.rest) is None
            or ln.kind in PAUSE_LINES and bool(ln.rest)]
