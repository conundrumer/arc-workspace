"""The fixed form of the lines the coordinator gives an operator, in its
brief or a later message, that the command reads. Each line opens with the
prefix `Op`, the word of its kind and a colon, past a list marker:

- `Op solve: <task id> [<task id> ...]`, with `from create` or `from refine`
  after a task id to start its pipeline at that pass;
- `Op run: <path>`, a run script, as `runs` gives it;
- `Op drafts to review: <number>, ...`;
- `Op expedite: <number>, ...`, for every operator of the session, and
  the tickets a chain of links reaches from those numbers
  (`taking.expedited`);
- `Op merged: <number>, ...`, the changes the coordinator gives as merged;
- `Op merge: <number>`, a change under `tickets/blocked/` whose merge that line rules;
- `Op tickets are open.`, which leaves the scope as `own_scope` gives it;
- `Op scope: own.`, under which no operator of the session settles an untaken
  ticket or takes a change outside the work held, the tickets an allow
  line of the session gives (`taking.allowed`) and the session's line of
  work (`taking.own_work`), other than the launch of a ticket analyst that
  judges whether that line needs a ticket whose title refers to a file
  the line changed (`admission.judging`), and `Op scope: all.`, which ends that limit,
  the last such line standing, and `Op scope: own.` where none came
  (`own_scope`);
- `Op pause.`, after which no operator of the session settles an untaken
  ticket or takes a change outside the work held and the tickets an
  allow line of the session gives, and `Op resume.`, which ends
  the pause, the last such line standing (`paused`);
- `Op pace: <preset> [<argument> ...]` or `Op pace: <path>`, the usage pace
  for every operator of the session (`pace`), as `pacing` gives it;
- the rulings, `Op decision:` and `Op override:` lines in the forms that
  `scripts/operate.py --help rulings` gives, which the command applies (`ruling`,
  `passed_over`, `given_again`, `overrides`).

The coordinator gives these lines by `operate.py send`, which records them
in the session's store (`state.stored_messages`) and refuses a line
`undecided` holds for. A line of the coordinator's in no such form, a
ruling among them, that reaches an operator goes back to the coordinator
once as undecided, since only its writer knows what it meant.

A line of a message of the coordinator's, not of the store, takes its
kind only where that message arrived before the session's first line of
the store (`sent_from`); after it, each such line other than
`constants.WAKE` is in no form. The command reads `constants.WAKE` as no
line in any message.

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
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from enum import Enum, StrEnum
from pathlib import Path

from arc.task import TASK_ID
from controlled_markdown import mctx
from operations.constants import WAKE
from operations.reports import LIST_MARKER
from operations.pacing import Preset, line_pace
from operations.roles import PASSES, Purpose, Role
from operations.state import Agent, Message, Report, State, memoized, memoized_by_transcripts
from operations.steps import (STEP_KEY, Step, Undecided, bare, decision_key, digest,
                              held, key)


class Decision(StrEnum):
    """The choices an `Op decision:` line gives a held step (`ruling`): go on as though the step were passed, the
    merge, the move to `tickets/approved/`, or another agent on it."""
    PASSES = "passes"
    MERGE = "merge"
    APPROVE = "approve"
    AGAIN = "again"


OP = "Op "


class Scope(StrEnum):
    """The tickets an `Op scope:` line has the operators take: the
    session's line of work, as `admission.scope_admits` gives it, the scope
    where no such line came, or every open ticket."""
    OWN = "own"
    ALL = "all"


class Directive(StrEnum):
    SOLVE = "Op solve"
    RUN = "Op run"
    DRAFTS = "Op drafts to review"
    EXPEDITE = "Op expedite"
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


class Forms(Enum):
    """The forms in which a line of a message takes its kind: the prefixed
    and the bare forms, the prefixed forms alone, or none."""
    BARE = "bare"
    PREFIXED = "prefixed"
    NONE = "none"


@memoized
def lines(state: State) -> tuple[Line, ...]:
    """Each non-blank line the coordinator gave the operator `me`, in the
    order the messages arrived."""
    return tuple(parsed(state.received, state.arrived))


@memoized_by_transcripts
def session_lines(state: State) -> tuple[Line, ...]:
    """Each non-blank line the coordinator gave any operator of the
    session, in the order the messages arrived."""
    return tuple(parsed(state.arrived, state.arrived))


def parsed(messages: Iterable[Message], arrived: Sequence[Message]) -> list[Line]:
    """The lines of the coordinator's messages among `messages`, each in
    the forms `forms_of` gives its message among `arrived`, the session's
    messages in the order they arrived."""
    before, sent = cutoff(arrived), sent_from(arrived)
    return [ln for m in messages if m.sender is None
            for ln in message_lines(m, forms_of(m, before, sent))]


def forms_of(m: Message, before: float | None, sent: float | None) -> Forms:
    """The forms a line of `m` takes its kind in: none where `m` is no line
    of the store and arrived at or after `sent`, the bare forms as well
    where it arrived before `before` or `before` is None, and the prefixed
    forms alone otherwise."""
    if not m.stored and sent is not None and m.time >= sent:
        return Forms.NONE
    return Forms.BARE if before is None or m.time < before else Forms.PREFIXED


def sent_from(arrived: Iterable[Message]) -> float | None:
    """The time of the first line of the store among `arrived`, or None
    where none came."""
    return next((m.time for m in arrived if m.stored), None)


def cutoff(arrived: Iterable[Message]) -> float | None:
    """The time of the first message of the coordinator among `arrived`,
    the session's messages in the order they arrived, with a line in a
    prefixed form, or None where none came."""
    return next((m.time for m in arrived if m.sender is None
                 if any(ln.kind is not None for ln in message_lines(m, Forms.PREFIXED))), None)


def message_lines(m: Message, forms: Forms) -> list[Line]:
    """Each non-blank line of `m` other than `constants.WAKE`, with its kind
    where it is in one of `forms`."""
    out: list[Line] = []
    for raw in m.text.splitlines():
        if not raw.strip() or raw.strip() == WAKE:
            continue
        match = LINE.match(raw)
        kind = None if match is None else kind_of(match["kind"], forms)
        rest = "" if match is None or kind is None else match["rest"] or ""
        out.append(Line(m, kind, raw.strip(), rest))
    return out


def kind_of(word: str, forms: Forms) -> Directive | None:
    if forms is Forms.NONE:
        return None
    if word in Directive:
        return Directive(word)
    return BARE.get(word) if forms is Forms.BARE else None


def step_decisions(state: State) -> list[Line]:
    """The `Op override:` and `Op decision:` lines of the replies of the ticket
    analysts on held steps, each read as a message of its analyst to the
    operator that launched it, in the order the replies came."""
    out = [ln for a, purpose, _ in state.analysts() if purpose is Purpose.STEP
           for r in a.reports for ln in reply_decisions(a, r)]
    return sorted(out, key=lambda ln: ln.message.time)


def reply_decisions(a: Agent, r: Report) -> list[Line]:
    """The `Op override:` and `Op decision:` lines of the reply `r` of `a`."""
    forms = Forms.BARE if bare(a.brief) else Forms.PREFIXED
    return [ln for ln in message_lines(Message(a.operator, r.time, a.agent_id, r.text), forms)
            if ln.kind in RULINGS and ruling_form(ln) is not None]


def numbers(state: State, kind: Directive) -> list[tuple[str, float]]:
    """Each ticket number lines of `kind` to the operator give, with the
    time of the message that gave it."""
    return numbers_in(lines(state), kind)


def numbers_in(given: Iterable[Line], kind: Directive) -> list[tuple[str, float]]:
    return [(n, ln.message.time) for ln in given if ln.kind is kind
            for n in NUMBER.findall(ln.rest)]


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
    """The tickets the coordinator gives the operator in a line."""
    return {n for k in (Directive.EXPEDITE, Directive.DRAFTS, Directive.MERGE, Directive.MERGED)
            for n, _ in numbers(state, k)}


@dataclass(frozen=True)
class Pipeline:
    """A solver pipeline: its task, its passes in their order, the time of
    the message that gives it or of the call that starts it (`runs`), and
    the operator that message reached or that made that call."""
    task: str
    passes: tuple[Role, ...]
    since: float
    operator: str


def pipelines(given: Iterable[Line]) -> list[Pipeline]:
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
    """The coordinator's lines to the operator that `undecided` holds for."""
    return [ln for ln in lines(state) if undecided(ln, state.main_tree)]


def undecided(ln: Line, main_tree: Path) -> bool:
    """Whether `ln` is in no form the command reads, or is a ruling, an
    `Op pace:` or an `Op scope:` line in no fixed form, or an `Op pause:` or
    `Op resume:` line with text after the colon."""
    return (ln.kind is None or ln.kind in RULINGS and ruling_form(ln) is None
            or ln.kind is Directive.PACE and line_pace(ln.rest, main_tree) is None
            or ln.kind is Directive.SCOPE and line_scope(ln.rest) is None
            or ln.kind in PAUSE_LINES and bool(ln.rest))


def refused(texts: Iterable[str], main_tree: Path) -> list[str]:
    """The lines among `texts` that `operate.py send` refuses: each that
    `undecided` holds for, read as a line of the store."""
    m = Message("", 0.0, None, "\n".join(texts), stored=True)
    return [ln.text for ln in message_lines(m, Forms.PREFIXED) if undecided(ln, main_tree)]
