"""Name resolution: what a name of the witness file, a verdict, a marker or an
`@ignore` line denotes, in the forms solver-file.md gives under "Witness file",
a model where the place asks for one (`denote`, `name`) and a set of cases
where it asks for cases (`denoted_cases`, `lists`, `cover`). It lives here and
nowhere else."""

import re
from collections.abc import Collection, Sequence
from dataclasses import dataclass
from functools import cache
from itertools import combinations
from typing import Annotated

from engine import AdtValue, Engine, RecordValue, Value
from engine.quotes import quotes
from solver.annotations import (
    CaseMarker,
    DeriveLine,
    MarkerPart,
    NamedVerdict,
    StoreLine,
    Verdict,
    VerdictWord,
    WitnessLine,
    pieces,
)
from solver.model import (
    Base,
    Branch,
    Case,
    as_case,
    base_case,
    Choice,
    ChoicePoint,
    ConstructorBranch,
    DeriveBranch,
    DerivedAtStore,
    StoreBranch,
    StoredAtDerive,
    concept_branch,
    constructor_at,
    constructor_named,
    constructor_places,
    constructors_taken,
    is_concept_branch,
    non_concept_at,
    path_constructors,
    value_at,
)
from solver.aggregate import Solver, is_concept, store_branch, takes
from solver.problems import Named, NameFault, ProblemKind


@quotes("solver-file.md", "Witness file",
        "A `<name>` fixes the branch at some choice points, in one of these "
        "forms.")
@dataclass(frozen=True)
class Denoted:
    """The branches a name denotes: the points it fixes and the branch at
    each, the constructor branches and the `@derive` and `@store` branches.
    `model_of` and `cases_of` read them as a model or as cases, as the
    name's place asks."""

    constructors: tuple[ConstructorBranch, ...]
    branches: tuple[Branch, ...]
    concept: Annotated[bool,
        quotes("solver-file.md", "Witness file",
               "`concept`: the concept branch at every point the `Choice` "
               "encodes, the concept base")] = False
    """A part of the name is `concept`, the concept branch at every point:
    the name fixes each point it names no other branch of at its concept
    branch."""
    derived: Annotated[tuple[StoreBranch, ...],
        quotes("solver-file.md", "Witness file",
               "the branch of the point of the `@store` line on `<rel>` in "
               "which the solver's clauses derive its value")] = ()
    """The `@store` points the name fixes at `<rel>=derived`, the branch in
    which the solver's clauses derive the value."""



SEPARATOR: Annotated[str,
    quotes("solver-file.md", "Witness file",
           "`<name> & <name>`: what each fixes")] = " & "
"""What joins the parts of a name."""


def ctor_text(engine: Engine, ctor: str) -> str:
    """A constructor as a name writes it: `$Drawn`, the constructor's value
    with no fields as the engine writes it."""
    return engine.text(AdtValue(ctor, ()))


@dataclass(frozen=True)
class NameParts:
    """A name's parts, each in a listed form: whether it holds `concept`,
    its `<target>=<reading>` parts, and the constructors it names, without
    their prefix."""

    concept: bool
    readings: tuple[tuple[str, str], ...]
    constructors: tuple[str, ...]


def name_parts(engine: Engine, name: str | tuple[str, ...]) -> NameParts | None:
    """The parts of `name` in the forms solver-file.md lists under "Witness
    file", judged with no solver; None where a part is in no listed form: a
    bare constructor name, a slug, a constructor applied to a field or a
    value (`Derive(g=Iso)`, `Rank(Big)`), or `&` without its spaces. `name` is
    the name's parts as a reader gives them, or its string form, whose parts
    ` & ` joins."""
    parts = [p.strip() for p in (name.split(SEPARATOR) if isinstance(name, str)
                                 else name)]
    readings: list[tuple[str, str]] = []
    ctors: list[str] = []
    for part in parts:
        if part == VerdictWord.CONCEPT:
            continue
        if any(ch in part for ch in "()&"):
            return None
        if "=" in part:
            target, _eq, reading = (x.strip() for x in part.partition("="))
            readings.append((target, reading))
        elif (ctor := engine.prefixed(part)) is not None \
                and _CTOR_RE.fullmatch(ctor):
            ctors.append(ctor)
        else:
            return None
    return NameParts(VerdictWord.CONCEPT in parts, tuple(readings),
                     tuple(ctors))


def denote(solver: Solver, name: str | tuple[str, ...]
           ) -> Denoted | NameFault:
    """The branches `name` fixes, a partial choice (solver-file.md, under
    "Witness file"): `concept` the concept branch at every point the `Choice`
    encodes; `<param>=<Proposer>`, `<rel>=stored`, `<param>=stored` and
    `<rel>=derived` the branch of that point; a constructor's name with
    Souffle's prefix, `$Drawn`, that branch at each point where the constructor
    stands (solver-file.md, under "Witness file"). A name `name_parts` finds
    off the listed forms is the problem `NAME_FORM`. Two constructors that are
    branches of the same points denote no case. The problem's place is left
    for the caller, which knows where the name stands (`NameFault.at`)."""
    text = name if isinstance(name, str) else SEPARATOR.join(name)
    parts = name_parts(solver.engine, name)
    if parts is None:
        return name_fault(ProblemKind.NAME_FORM, text)
    branches: list[Branch] = []
    derived: list[StoreBranch] = []
    for target, reading in parts.readings:
        if reading == VerdictWord.DERIVED:
            store = store_branch(solver, target)
            if store is None:
                return name_fault(ProblemKind.NAME_DENOTES_NO_CASE, text)
            derived.append(store)
            continue
        branch = _branch(solver, target, reading)
        if branch is None:
            return name_fault(ProblemKind.NAME_DENOTES_NO_CASE, text)
        branches.append(branch)
    ctors = constructors_fixed(solver, parts.constructors)
    if ctors is None:
        return name_fault(ProblemKind.NAME_DENOTES_NO_CASE, text)
    return Denoted(ctors, tuple(branches), parts.concept, tuple(derived))


def constructors_fixed(solver: Solver, ctors: Sequence[str]
                       ) -> tuple[ConstructorBranch, ...] | None:
    """The branches the constructors `ctors` fix together (`denote`): each
    constructor's branch at each point where it stands. None where they
    denote no case: one stands at no point, or two are branches of the
    same points."""
    choice = solver.choice
    found: list[ConstructorBranch] = []
    points: list[frozenset[tuple[str, ...]]] = []
    for ctor in ctors:
        if choice is None:
            return None
        places = [(p.path, c) for p, c in constructor_places(choice, ctor)]
        if not places:
            return None
        at = frozenset(path for path, _c in places)
        if at in points:
            return None
        points.append(at)
        found += [c for _path, c in places if c not in found]
    return tuple(found)


def camel_words(name: str) -> list[str]:
    """The words of a PascalCase name, split before each capital but the
    first, in lower case: `MarkerHue` gives `marker`, `hue`."""
    return [w.lower() for w in re.split(r"(?<!^)(?=[A-Z])", name)]


def names_a_constructor(solver: Solver, text: str) -> bool:
    """Whether a name in no listed form (`denote`) writes a constructor of
    the solver without its prefix: some piece between its `&`s starts with
    a constructor's name or its slug (`Count`, `rarest-color`,
    `Tile(Size)`), with or without the prefix. The old form is matched,
    not read: what the name would denote is not asked."""
    choice = solver.choice
    if choice is None:
        return False
    words = {c.name for p in choice.points for c in p.constructors}
    words |= {"-".join(camel_words(w)) for w in words}

    def bare(piece: str) -> str:
        return solver.engine.prefixed(piece) or piece

    return any(
        (m := re.match(r"[\w-]+", bare(piece.strip()))) is not None
        and m[0] in words
        for piece in pieces(text))


@cache
def _prose_name_re(prefix: str) -> re.Pattern[str]:
    """The pattern of a name in prose (`names_in`), a constructor written
    with `prefix`."""
    word = rf"[\w.]+=\w+|(?:{re.escape(prefix)})?[A-Za-z]\w*"
    return re.compile(rf"(?:{word})(?:\s*&\s*(?:{word}))*")


def names_in(engine: Engine, text: str) -> list[str]:
    """The names in the one form (solver-file.md, under "Witness file") that
    prose, an entry's `separates` text among it, holds, each once, in text
    order: the runs of words joined by ` & `, a word with `=`, a constructor
    with its `$`, or `concept`. A bare word is prose. No other reader
    finds a name in prose."""
    out: list[str] = []
    for m in _prose_name_re(engine.constructor_prefix()).finditer(text):
        n = m.group(0)
        if ("&" in n or "=" in n or engine.prefixed(n) is not None
                or n == VerdictWord.CONCEPT) \
                and n not in out:
            out.append(n)
    return out


def marker_lists(solver: Solver, marker: CaseMarker, base: Base | None
                 ) -> bool:
    """Whether some part of a case marker lists `base` (`lists`)."""
    return any(lists(solver, p, base) for p in marker.parts)


def lists(solver: Solver, part: MarkerPart, base: Base | None) -> bool:
    """Whether a case marker's part lists a base (solver-file.md, under
    "Cases"): the base of a case `cases_of` gives for the part's name, its
    `@derive` and `@store` branches aside. A part that denotes nothing, prose
    among them (`MarkerPart.prose`), lists no base."""
    if part.prose:
        return False
    denoted = denote(solver, part.name)
    return isinstance(denoted, Denoted) and bool(cases_of(
        solver, Denoted(denoted.constructors, (), denoted.concept),
        [base_case(base)]))


_CTOR_RE = re.compile(r"[A-Z]\w*")


def name_fault(kind: ProblemKind, name: str) -> NameFault:
    """The problem `kind` at the name `name`, before its place is known."""
    return NameFault(kind, Named(name))


def _branch(solver: Solver, target: str, reading: str) -> Branch | None:
    for b in solver.branches:
        match b:
            case DeriveBranch(parameter=p, proposer=q) if (
                    p == target and q == reading):
                return b
            case StoredAtDerive(parameter=p) if (
                    p == target and reading == VerdictWord.STORED):
                return b
            case StoreBranch(spelled=r) if r == target and reading == VerdictWord.STORED:
                return b
            case _:
                pass
    return None


def derived_text(store: StoreBranch) -> str:
    """The derived branch of a `@store` point as a name's part,
    `<rel>=derived` (solver-file.md, under "Witness file")."""
    return f"{store.spelled}={VerdictWord.DERIVED}"


def branch_text(branch: Branch) -> str:
    """A `@derive` or `@store` branch as a name's part (solver-file.md, under
    "Witness file"): `<param>=<Proposer>`, `<rel>=stored`, or
    `<param>=stored`."""
    match branch:
        case DeriveBranch(parameter=p, proposer=q):
            return f"{p}={q}"
        case StoreBranch(spelled=r):
            return f"{r}={VerdictWord.STORED}"
        case StoredAtDerive(parameter=p):
            return f"{p}={VerdictWord.STORED}"


type VerdictLine = WitnessLine | DeriveLine | StoreLine


def verdict_lines(solver: Solver, id: str) -> tuple[VerdictLine, ...]:
    """The lines that record the verdict of the witness file's entry `id`,
    in file order: each `@witness` line whose id is `id`, and each `@derive`
    or `@store` line whose branch `id` names (`branch_text`)."""
    lines: list[VerdictLine] = [w for w in solver.annotations.witnesses
                                if w.id == id]
    lines += [b.line for b in solver.branches
              if isinstance(b, DeriveBranch | StoreBranch)
              and b.line is not None and branch_text(b) == id]
    return tuple(sorted(lines, key=lambda line: line.line))


@dataclass(frozen=True)
class LinesDiffer:
    """The `@witness` lines of one id that give another plausibility or
    verdict than its first line, in file order."""

    first: WitnessLine
    differing: tuple[WitnessLine, ...]


def witness_verdict(solver: Solver, id: str) -> WitnessLine | LinesDiffer | None:
    """The plausibility and verdict of the `@witness` lines of the id `id`
    (`verdict_lines`), as the first of them, where every line gives them;
    the lines that differ where some do not; None where no `@witness` line
    has the id. Two verdicts agree where they are one verdict word, or names
    that denote the same branches (`denote`), in any order of their parts. A
    name `denote` gives a fault for agrees only with a name of the same
    text."""
    lines = [w for w in verdict_lines(solver, id) if isinstance(w, WitnessLine)]
    if not lines:
        return None
    first, *rest = lines
    differing = tuple(
        w for w in rest
        if w.plausibility != first.plausibility
        or _verdict_key(solver, w.verdict) != _verdict_key(solver, first.verdict))
    return LinesDiffer(first, differing) if differing else first


type _VerdictKey = (Verdict
                    | tuple[bool, frozenset[ConstructorBranch],
                            frozenset[Branch], frozenset[StoreBranch]])


def _verdict_key(solver: Solver, verdict: Verdict) -> _VerdictKey:
    """What two verdicts that agree (`witness_verdict`) share: the word, the
    branches a name denotes as sets, or the verdict itself where it is a
    word or a name that denotes none."""
    if not isinstance(verdict, NamedVerdict):
        return verdict
    d = denote(solver, verdict.text)
    if isinstance(d, NameFault):
        return verdict
    return (d.concept, frozenset(d.constructors), frozenset(d.branches),
            frozenset(d.derived))


def name(solver: Solver, case: Case | Base) -> str:
    """The name of `case` for a place that asks for a model (solver-file.md,
    under "Witness file"), the inverse of `denote` read by `model_of`: the
    points at which the case differs from the concept case. `concept` for the
    concept case; else each constructor that is not first at its choice point,
    with its `$`, once, in the order of the points, and then each `@derive` and
    `@store` branch the case takes, in file order, and each it takes that no
    line of the file holds, a branch a survey proposes, in the case's order. A
    point at its concept branch is left out: a first constructor,
    `<param>=stored` at a `@derive` point, and `<rel>=derived` at a `@store`
    point (solver-file.md, under "Params" and "Program"). A base is named
    as its base case (`solver.model.as_case`)."""
    case = as_case(case)
    choice = solver.choice
    parts: list[str] = []
    if choice is not None and case.base is not None:
        for point, ctor in constructors_taken(choice, case.base):
            if not is_concept_branch(point, ctor) \
                    and ctor_text(solver.engine, ctor) not in parts:
                parts.append(ctor_text(solver.engine, ctor))
    parts += [branch_text(b) for b in solver.branches if b in case.branches]
    parts += [branch_text(b) for b in case.branches
              if b not in solver.branches and not isinstance(b, StoredAtDerive)]
    return SEPARATOR.join(parts) or VerdictWord.CONCEPT.value


# The two readings of the branches a name denotes


def model_of(solver: Solver, denoted: Denoted, among: Sequence[Case] = ()
             ) -> Case | None:
    """The model of the branches `denoted` fixes, for a place that asks for a
    model (a `@witness` verdict, `grid --case`): the case that takes the fixed
    branches and the concept branch at every other point it takes
    (solver-file.md, under "Witness file"; principles.md, under "Choice points
    and open parameters"). The concept branch is "the branch taken by the
    claims the point stands under" (principles.md, under "Choice points and
    open parameters"), a point's first
    constructor, `<param>=stored` at a `@derive` point and `<rel>=derived` at a
    `@store` point (solver-file.md, under "Params" and "Program"). A
    constructor that stands at more than one point is taken at the one the
    other branches reach, under the concept parent where they fix none; one
    that no point they reach holds is reached through its first point's
    parents. The case of `among` that is that model where one is, else the case
    built, a case of the solver or not: a constructor denotes its branch
    "whether or not `impl_choice` contains its model" (solver-file.md, under
    "Witness file"). None where no case of `among` is the model and a point it
    reaches has no values to build (a field of a type that is no choice
    point)."""
    wanted = _reaching(solver, denoted)
    found = next((c for c in among if _is_model(solver, wanted, c)), None)
    if found is not None:
        return found
    choice = solver.choice
    order = {b: i for i, b in enumerate(solver.branches)}
    branches = tuple(sorted(_taken(denoted), key=lambda b: (
        order.get(b, len(order)), branch_text(b))))
    if choice is None:
        return None if denoted.constructors else Case(None, branches)
    by_path = {p.path: p for p in choice.points}

    def value(path: tuple[str, ...]) -> AdtValue | None:
        point = by_path.get(path)
        if point is None:
            return None
        ctor = _at_point(point, wanted)
        args: list[Value] = []
        for f in ctor.fields:
            sub = value((*path, ctor.name, f.name))
            if sub is None:
                return None
            args.append(sub)
        return AdtValue(ctor.name, tuple(args))

    if choice.record is None:
        base = value(())
        return None if base is None else Case(base, branches)
    fields: list[Value] = []
    for f in choice.record:
        sub = value((f.name,))
        if sub is None:
            return None
        fields.append(sub)
    return Case(RecordValue(tuple(fields)), branches)


def _reaching(solver: Solver, denoted: Denoted) -> Denoted:
    """`denoted` with the constructors on the path to the first point of
    each constructor it fixes that no point reached by the others and the
    concept branches holds (`model_of`)."""
    choice = solver.choice
    if choice is None:
        return denoted
    ctors = list(denoted.constructors)
    for c in denoted.constructors:
        paths = [p.path for p in choice.points if c in p.constructors]
        if any(_reached(choice, path, ctors) for path in paths):
            continue
        for step in path_constructors(choice, paths[0]):
            parent = constructor_named(choice, step)
            assert parent is not None, "a point's path names its constructors"
            if parent not in ctors:
                ctors.append(parent)
    return Denoted(tuple(ctors), denoted.branches, denoted.concept,
                   denoted.derived)


def _reached(choice: Choice, path: tuple[str, ...],
             ctors: Sequence[ConstructorBranch]) -> bool:
    """Whether the point at `path` is reached where each point takes the
    constructor of `ctors` it holds, else its concept branch."""
    head = 1 if choice.record is not None else 0
    for i, name in enumerate(path_constructors(choice, path)):
        prefix = path[:head + 2 * i]
        point = next((p for p in choice.points if p.path == prefix), None)
        if point is None:
            return False
        want = next((c for c in point.constructors if c in ctors),
                    concept_branch(point))
        if want.name != name:
            return False
    return True


def _taken(denoted: Denoted) -> frozenset[Branch]:
    """The `@derive` and `@store` branches a model of `denoted` lists: the
    first branch of a `@derive` point, `<param>=stored`, is the one it
    takes where it lists none of the point."""
    return frozenset(b for b in denoted.branches
                     if not isinstance(b, StoredAtDerive))


def _at_point(point: ChoicePoint, denoted: Denoted) -> ConstructorBranch:
    """The constructor a model of `denoted` takes at `point`: the one it
    holds there, else the point's concept branch."""
    return next((c for c in point.constructors
                 if c in denoted.constructors), concept_branch(point))


def _is_model(solver: Solver, denoted: Denoted, case: Case) -> bool:
    """Whether `case` is the model of `denoted` with its path constructors
    (`model_of`): it takes the constructor `model_of` builds at each
    choice point it reaches, and exactly the `@derive` and `@store`
    branches `denoted` lists."""
    if frozenset(case.branches) != _taken(denoted):
        return False
    choice = solver.choice
    if choice is None or case.base is None:
        return not denoted.constructors
    for p in choice.points:
        at = value_at(choice, case.base, p.path)
        if isinstance(at, AdtValue) \
                and at.constructor != _at_point(p, denoted).name:
            return False
    return _takes_each(choice, case.base, denoted)


def _takes_each(choice: Choice, base: Base, denoted: Denoted) -> bool:
    """Whether `base` takes each constructor `denoted` fixes at some point
    where it stands."""
    return all(any(constructor_at(choice, base, p) == name
                   for p, _c in constructor_places(choice, name))
               for name in {c.name for c in denoted.constructors})


def cases_of(solver: Solver, denoted: Denoted, among: Sequence[Case]
             ) -> tuple[Case, ...]:
    """The cases of `among` that take each branch `denoted` holds, for a place
    that asks for cases (a case marker, an `@ignore` line, a group): "A
    branch's cases are the cases that take it" (principles.md, under "Choice
    points and open parameters"), and of branches taken together, the cases
    that take each (solver-file.md, under "Witness file"). A point `denoted`
    does not fix is free; with `concept` among the name's parts, every point it
    does not fix is at its concept branch, so `concept` alone gives the concept
    case (solver-file.md, under "Witness file"). In the order of `among`."""
    return tuple(c for c in among if _in(solver, denoted, c))


def denoted_cases(solver: Solver, text: str | tuple[str, ...],
                  among: Sequence[Case]) -> frozenset[Case] | NameFault:
    """`cases_of` the branches a name denotes (`denote`), for a place
    that asks for cases; the problem where the name denotes nothing.
    `text` is the name, or its parts as a reader gives them."""
    d = denote(solver, text)
    if isinstance(d, NameFault):
        return d
    return frozenset(cases_of(solver, d, among))


def _in(solver: Solver, d: Denoted, case: Case) -> bool:
    """Whether `case` takes each branch `d` fixes (`cases_of`): each
    constructor at some point where it stands, and with `concept`, the
    concept branch at every other point the `Choice` encodes; its
    `@derive` and `@store` points are free unless `d` fixes them."""
    choice = solver.choice
    if d.constructors and (choice is None or case.base is None
                           or not _takes_each(choice, case.base, d)):
        return False
    if not all(takes(solver, case, b) for b in d.branches) \
            or any(b in case.branches for b in d.derived):
        return False
    if not d.concept or choice is None or case.base is None:
        return True
    named = {c.name for c in d.constructors}
    return all((ctor := non_concept_at(choice, case.base, p)) is None
               or ctor in named for p in choice.points)


@dataclass(frozen=True)
class _Ctor:
    """A constructor, taken at any point where it stands, as `cases_of`
    reads it."""

    name: str


type _Part = _Ctor | Branch | DerivedAtStore
"""A branch a case takes: a constructor, a `@derive` or `@store` branch,
`<param>=stored`, or `<rel>=derived`."""


def _parts(solver: Solver, case: Case, points: Collection[Branch]
           ) -> tuple[_Part, ...]:
    """Every branch `case` takes, its constructors first, once each, in
    point order, then the branches of `points` it takes in file order:
    the `@derive` and `@store` branches, `<param>=stored`, and
    `<rel>=derived` at a `@store` point of `points` whose branch it does
    not take."""
    out: list[_Part] = []
    choice = solver.choice
    if choice is not None and case.base is not None:
        for _p, ctor in constructors_taken(choice, case.base):
            if _Ctor(ctor) not in out:
                out.append(_Ctor(ctor))
    for b in solver.branches:
        if b not in points:
            continue
        if takes(solver, case, b):
            out.append(b)
        elif isinstance(b, StoreBranch):
            out.append(DerivedAtStore(b))
    return tuple(out)


def part_text(engine: Engine, part: _Part | ConstructorBranch) -> str:
    """One part of a name: a constructor with its `$`, a `@derive` or
    `@store` branch, `<param>=stored`, or `<rel>=derived`."""
    match part:
        case _Ctor(name=n) | ConstructorBranch(name=n):
            return ctor_text(engine, n)
        case DerivedAtStore(store=store):
            return derived_text(store)
        case _:
            return branch_text(part)


def part_name(engine: Engine, parts: Sequence[_Part | ConstructorBranch]
              ) -> str:
    """A partial name's text: its parts joined in the order given, as
    `_parts` gives them."""
    return SEPARATOR.join(part_text(engine, p) for p in parts)


type _Key = tuple[int, bool, str]
"""How a name of a set of cases ranks among names of the same set: its
parts, whether it is other than `concept`, and its text."""


def cover(solver: Solver, chosen: Collection[Case] | Collection[Base],
          among: Sequence[Case] | Sequence[Base]) -> tuple[str, ...]:
    """The fewest names whose sets within `among` (`denoted_cases`) are
    together exactly `chosen` (solver-file.md, under "Witness file"), in the
    order of the first case each denotes. A set of cases is covered exactly by
    the largest partial names it contains, a case alone by every point it
    fixes, and the cases of the concept base are also named `concept`
    (solver-file.md, under "Witness file"). Of the covers by those names, the
    fewest names; of names of one set, the fewest parts, then `concept` before
    any other name, then name order. Bases are read as their base cases
    (`solver.model.base_case`), for naming a set of bases."""
    universe = [as_case(c) for c in among]
    wanted = {as_case(c) for c in chosen}
    bit = {c: 1 << i for i, c in enumerate(universe)}
    target = 0
    for c in wanted:
        target |= bit[c]
    taken = {b for c in universe for b in c.branches}
    points = taken | {b for b in solver.branches
                      if isinstance(b, StoredAtDerive) and any(
                          isinstance(t, DeriveBranch)
                          and t.parameter == b.parameter for t in taken)}
    masks: dict[_Part, int] = {}
    for c in universe:
        for part in _parts(solver, c, points):
            masks[part] = masks.get(part, 0) | bit[c]
    found: dict[int, _Key] = {}

    def offer(mask: int, parts: int, text: str) -> None:
        key = (parts, text != VerdictWord.CONCEPT, text)
        if mask not in found or key < found[mask]:
            found[mask] = key

    for c in universe:
        if not bit[c] & target:
            continue
        parts = _parts(solver, c, points)
        inside: list[frozenset[_Part]] = []
        for r in range(1, len(parts) + 1):
            for sub in combinations(parts, r):
                if any(s <= set(sub) for s in inside):
                    continue
                mask = -1
                for part in sub:
                    mask &= masks[part]
                if mask & ~target:
                    continue
                inside.append(frozenset(sub))
                offer(mask, r, part_name(solver.engine, sub))

    concept = 0
    for c in universe:
        if is_concept(solver, c.base):
            concept |= bit[c]
    if concept and not concept & ~target:
        offer(concept, 1, VerdictWord.CONCEPT.value)
    largest = sorted(
        ((m, k) for m, k in found.items()
         if not any(o != m and o & m == m for o in found)),
        key=lambda mk: mk[1])

    def first(mask: int) -> int:
        return (mask & -mask).bit_length()

    return tuple(k[2] for _m, k in sorted(_fewest(target, largest),
                                          key=lambda mk: first(mk[0])))


def _fewest(target: int, options: Sequence[tuple[int, _Key]]
            ) -> list[tuple[int, _Key]]:
    """The fewest of `options` whose masks together are `target`, each
    option's mask inside `target`; of covers of one size, the first in
    the order of `options`."""
    widest = max((m.bit_count() for m, _k in options), default=1)
    failed: set[tuple[int, int]] = set()

    def search(rem: int, slots: int, chosen: list[tuple[int, _Key]]
               ) -> bool:
        if not rem:
            return True
        if slots == 0 or rem.bit_count() > slots * widest \
                or (rem, slots) in failed:
            return False
        low = rem & -rem
        for m, key in options:
            if m & low:
                chosen.append((m, key))
                if search(rem & ~m, slots - 1, chosen):
                    return True
                chosen.pop()
        failed.add((rem, slots))
        return False

    for size in range(1, len(options) + 1):
        chosen: list[tuple[int, _Key]] = []
        if search(target, size, chosen):
            return chosen
    return []
