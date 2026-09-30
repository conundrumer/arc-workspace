"""Name resolution: what a name of the witness file, a verdict, a marker
or an `@ignore` line denotes, in the forms of solver-file.md:193-199, a
model where the place asks for one (`denote`, `name`) and a set of cases
where it asks for cases (`denoted_cases`, `lists`, `cover`). It lives
here and nowhere else."""

import re
from collections.abc import Collection, Sequence
from dataclasses import dataclass
from itertools import combinations

from engine import AdtValue, RecordValue, Value
from solver.annotations import MarkerPart
from solver.model import (
    Base,
    Branch,
    Case,
    Choice,
    ChoicePoint,
    ConstructorBranch,
    DeriveBranch,
    Solver,
    StoreBranch,
    StoredAtDerive,
    concept_branch,
    is_concept,
    takes,
    value_at,
)
from solver.problems import InSolver, Named, ProblemKind, Fault
from solver.vocabulary import CONCEPT, STORED


@dataclass(frozen=True)
class Denoted:
    """The branches a name denotes (solver-file.md:193): the points it
    fixes and the branch at each, the constructor branches and the
    `@derive` and `@store` branches. `model_of` and `cases_of` read them
    as a model or as cases, as the name's place asks."""

    constructors: tuple[ConstructorBranch, ...]
    branches: tuple[Branch, ...]
    concept: bool = False
    """A part of the name is `concept`, the concept branch at every point:
    the name fixes each point it names no other branch of at its concept
    branch (solver-file.md:194)."""
    derived: tuple[StoreBranch, ...] = ()
    """The `@store` points the name fixes at `<rel>=derived`, the branch
    in which the solver's clauses derive the value (solver-file.md:199)."""


DERIVED = "derived"
"""The reading of the derived branch of a `@store` point, `<rel>=derived`
(solver-file.md:199)."""


SEPARATOR = " & "
"""What joins the parts of a name (solver-file.md:197)."""
PREFIX = "$"
"""What a constructor's name carries in a name, as Souffle writes a
constructor."""


def ctor_text(ctor: str) -> str:
    """A constructor as a name writes it: `$Drawn`."""
    return PREFIX + ctor


def denote(solver: Solver, name: str | tuple[str, ...]
           ) -> Denoted | Fault:
    """The branches `name` fixes, a partial choice (solver-file.md:193):
    `concept` the concept branch at every point the `Choice` encodes;
    `<param>=<Proposer>`, `<rel>=stored`, `<param>=stored` and
    `<rel>=derived` the branch of that point; a constructor's name with
    Souffle's prefix, `$Drawn`, that branch at each point where the
    constructor stands (solver-file.md:195-196). `name` is the name's
    parts as a reader gives them, or its string form, whose parts ` & `
    joins. A part in no listed form is the problem `NAME_FORM`: a bare
    constructor name, a slug, a constructor applied to a field or a value
    (`Derive(g=Iso)`, `Rank(Big)`), or `&` without its spaces. Two constructors that are branches of the same points denote
    no case. The problem's place is left for the caller, which knows
    where the name stands."""
    text = name if isinstance(name, str) else SEPARATOR.join(name)
    parts = [p.strip() for p in (text.split(SEPARATOR) if isinstance(name, str)
                                 else name)]
    ctor_parts: list[str] = []
    branches: list[Branch] = []
    derived: list[StoreBranch] = []
    for part in parts:
        if part == CONCEPT:
            continue
        if any(ch in part for ch in "()&"):
            return _problem(ProblemKind.NAME_FORM, text)
        if "=" in part:
            target, _eq, reading = (x.strip() for x in part.partition("="))
            if reading == DERIVED:
                store = next((b for b in solver.branches
                              if isinstance(b, StoreBranch)
                              and b.spelled == target), None)
                if store is None:
                    return _problem(ProblemKind.NAME_DENOTES_NO_CASE, text)
                derived.append(store)
                continue
            branch = _branch(solver, target, reading)
            if branch is None:
                return _problem(ProblemKind.NAME_DENOTES_NO_CASE, text)
            branches.append(branch)
        elif part.startswith(PREFIX) \
                and _CTOR_RE.fullmatch(part.removeprefix(PREFIX)):
            ctor_parts.append(part.removeprefix(PREFIX))
        else:
            return _problem(ProblemKind.NAME_FORM, text)
    choice = solver.choice
    ctors: list[ConstructorBranch] = []
    points: list[frozenset[tuple[str, ...]]] = []
    for part in ctor_parts:
        if choice is None:
            return _problem(ProblemKind.NAME_DENOTES_NO_CASE, text)
        places = [(p.path, c) for p in choice.points
                  for c in p.constructors if c.name == part]
        if not places:
            return _problem(ProblemKind.NAME_DENOTES_NO_CASE, text)
        at = frozenset(path for path, _c in places)
        if at in points:
            return _problem(ProblemKind.NAME_DENOTES_NO_CASE, text)
        points.append(at)
        ctors += [c for _path, c in places if c not in ctors]
    return Denoted(tuple(ctors), tuple(branches), CONCEPT in parts,
                   tuple(derived))


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
    words |= {re.sub(r"(?<!^)(?=[A-Z])", "-", w).lower() for w in words}
    return any(
        (m := re.match(r"\$?([\w-]+)", piece.strip())) is not None
        and m[1] in words
        for piece in text.split("&"))


def _places(solver: Solver, ctor: str) -> int:
    """How many choice points the constructor `ctor` stands at."""
    choice = solver.choice
    return 0 if choice is None else sum(
        1 for p in choice.points if any(c.name == ctor
                                        for c in p.constructors))


def lists(solver: Solver, part: MarkerPart, base: Base | None) -> bool:
    """Whether a case marker's part lists a base (solver-file.md:105-106):
    the base of a case `cases_of` gives for the part's name, its
    `@derive` and `@store` branches aside. A part that denotes nothing,
    prose among them (`MarkerPart.prose`), lists no base."""
    if part.prose:
        return False
    denoted = denote(solver, part.name)
    return isinstance(denoted, Denoted) and bool(cases_of(
        solver, Denoted(denoted.constructors, (), denoted.concept),
        [Case(base, ())]))


_CTOR_RE = re.compile(r"[A-Z]\w*")


def _problem(kind: ProblemKind, name: str) -> Fault:
    return Fault(kind, InSolver(0), Named(name))


def _branch(solver: Solver, target: str, reading: str) -> Branch | None:
    for b in solver.branches:
        match b:
            case DeriveBranch(parameter=p, proposer=q) if (
                    p == target and q == reading):
                return b
            case StoredAtDerive(parameter=p) if (
                    p == target and reading == STORED):
                return b
            case StoreBranch(spelled=r) if r == target and reading == STORED:
                return b
            case _:
                pass
    return None


def branch_text(branch: Branch) -> str:
    """A `@derive` or `@store` branch as a name's part
    (solver-file.md:199): `<param>=<Proposer>`, `<rel>=stored`, or
    `<param>=stored`."""
    match branch:
        case DeriveBranch(parameter=p, proposer=q):
            return f"{p}={q}"
        case StoreBranch(spelled=r):
            return f"{r}={STORED}"
        case StoredAtDerive(parameter=p):
            return f"{p}={STORED}"


def name(solver: Solver, case: Case) -> str:
    """The name of `case` for a place that asks for a model
    (solver-file.md:193-199), the inverse of `denote` read by `model_of`:
    the points at which the case differs from the concept case. `concept`
    for the concept case; else each constructor that is not first at its
    choice point, with its `$`, once, in the order of the points, and then each
    `@derive` and `@store` branch the case takes, in file order, and each
    it takes that no line of the file holds, a branch a survey proposes,
    in the case's order. A point
    at its concept branch is left out: a first constructor,
    `<param>=stored` at a `@derive` point, and `<rel>=derived` at a
    `@store` point (solver-file.md:120, :137)."""
    choice = solver.choice
    parts: list[str] = []
    if choice is not None and case.base is not None:
        for point in choice.points:
            at = value_at(choice, case.base, point.path)
            if isinstance(at, AdtValue) \
                    and at.constructor != concept_branch(point).name \
                    and ctor_text(at.constructor) not in parts:
                parts.append(ctor_text(at.constructor))
    parts += [branch_text(b) for b in solver.branches if b in case.branches]
    parts += [branch_text(b) for b in case.branches
              if b not in solver.branches and not isinstance(b, StoredAtDerive)]
    return SEPARATOR.join(parts) or CONCEPT


# The two readings of the branches a name denotes


def model_of(solver: Solver, denoted: Denoted, among: Sequence[Case] = ()
             ) -> Case | None:
    """The model of the branches `denoted` fixes, for a place that asks
    for a model (a `@witness` verdict, `grid --case`): the case that takes
    the fixed branches and the concept branch at every other point it
    takes (solver-file.md:194; principles.md:116, "A branch's model is the
    model of a case with that branch, with every other choice point fixed
    to its concept branch"). The concept branch is "the branch taken by
    the claims the point stands under" (principles.md:110), a point's
    first constructor, `<param>=stored` at a `@derive` point and
    `<rel>=derived` at a `@store` point (solver-file.md:120, :137). A
    constructor that stands at more than one point is taken at the one the
    other branches reach, under the concept parent where they fix none;
    one that no point they reach holds is reached through its first
    point's parents. The case of `among` that is that model where one
    is, else the case built, a case of the solver or not: a constructor
    denotes its branch "whether or not `impl_choice` contains its model"
    (solver-file.md:195). None where no case of `among` is the model and
    a point it reaches has no values to build (a field of a type that is
    no choice point)."""
    wanted = _reaching(solver, denoted)
    found = next((c for c in among if _is_model(solver, wanted, c)), None)
    if found is not None:
        return found
    choice = solver.choice
    order = {b: i for i, b in enumerate(solver.branches)}
    branches = tuple(sorted(_taken(denoted), key=lambda b: order.get(b, 0)))
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
        steps = paths[0][1:] if choice.record is not None else paths[0]
        for step in steps[0::2]:
            parent = next(k for p in choice.points for k in p.constructors
                          if k.name == step)
            if parent not in ctors:
                ctors.append(parent)
    return Denoted(tuple(ctors), denoted.branches, denoted.concept,
                   denoted.derived)


def _reached(choice: Choice, path: tuple[str, ...],
             ctors: Sequence[ConstructorBranch]) -> bool:
    """Whether the point at `path` is reached where each point takes the
    constructor of `ctors` it holds, else its concept branch."""
    steps = path[1:] if choice.record is not None else path
    prefix = path[:1] if choice.record is not None else ()
    for i in range(0, len(steps), 2):
        point = next((p for p in choice.points if p.path == prefix), None)
        if point is None:
            return False
        want = next((c for c in point.constructors if c in ctors),
                    concept_branch(point))
        if want.name != steps[i]:
            return False
        prefix = (*prefix, steps[i], steps[i + 1])
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
    return all(any(isinstance(at := value_at(choice, base, p.path), AdtValue)
                   and at.constructor == name for p in choice.points
                   if any(c.name == name for c in p.constructors))
               for name in {c.name for c in denoted.constructors})


def cases_of(solver: Solver, denoted: Denoted, among: Sequence[Case]
             ) -> tuple[Case, ...]:
    """The cases of `among` that take each branch `denoted` holds, for a
    place that asks for cases (a case marker, an `@ignore` line, a
    group): "A branch's cases are the cases that take it"
    (principles.md:117), and of branches taken together, the cases that
    take each (solver-file.md:198). A point `denoted` does not fix is
    free; with `concept` among the name's parts, every point it does not
    fix is at its concept branch, so `concept` alone gives the concept
    case (solver-file.md:194). In the order of `among`."""
    return tuple(c for c in among if _in(solver, denoted, c))


def denoted_cases(solver: Solver, text: str | tuple[str, ...],
                  among: Sequence[Case]) -> frozenset[Case] | Fault:
    """`cases_of` the branches a name denotes (`denote`), for a place
    that asks for cases; the problem where the name denotes nothing.
    `text` is the name, or its parts as a reader gives them."""
    d = denote(solver, text)
    if isinstance(d, Fault):
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
    return all(not isinstance(at := value_at(choice, case.base, p.path),
                              AdtValue)
               or at.constructor == concept_branch(p).name
               or at.constructor in named
               for p in choice.points)


@dataclass(frozen=True)
class _Derived:
    """`<rel>=derived`: the derived branch of a `@store` point."""

    store: StoreBranch


@dataclass(frozen=True)
class _Ctor:
    """A constructor, taken at any point where it stands, as `cases_of`
    reads it."""

    name: str


type _Part = _Ctor | Branch | _Derived
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
        for p in choice.points:
            at = value_at(choice, case.base, p.path)
            if isinstance(at, AdtValue) and _Ctor(at.constructor) not in out:
                out.append(_Ctor(at.constructor))
    for b in solver.branches:
        if b not in points:
            continue
        if takes(solver, case, b):
            out.append(b)
        elif isinstance(b, StoreBranch):
            out.append(_Derived(b))
    return tuple(out)


def _part_name(parts: Sequence[_Part]) -> str:
    """A partial name's text: its parts in the order `_parts` gives
    them."""
    out: list[str] = []
    for part in parts:
        if isinstance(part, _Ctor):
            out.append(ctor_text(part.name))
        elif isinstance(part, _Derived):
            out.append(f"{part.store.spelled}={DERIVED}")
        else:
            out.append(branch_text(part))
    return SEPARATOR.join(out)


type _Key = tuple[int, bool, str]
"""How a name of a set of cases ranks among names of the same set: its
parts, whether it is other than `concept`, and its text."""


def cover(solver: Solver, chosen: Collection[Case] | Collection[Base],
          among: Sequence[Case] | Sequence[Base]) -> tuple[str, ...]:
    """The fewest names whose sets within `among` (`denoted_cases`) are
    together exactly `chosen` (solver-file.md:185), in the order of the
    first case each denotes. A set of cases is covered exactly by the
    largest partial names it contains, a case alone by every point it
    fixes, and the cases of the concept base are also named `concept`
    (solver-file.md:194). Of the
    covers by those names, the fewest names; of names of one set, the
    fewest parts, then `concept` before any other name, then name order. Bases are
    read as the cases that take no `@derive` or `@store` branch, for
    naming a set of bases."""
    universe = [c if isinstance(c, Case) else Case(c, ()) for c in among]
    wanted = {c if isinstance(c, Case) else Case(c, ()) for c in chosen}
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
        key = (parts, text != CONCEPT, text)
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
                offer(mask, r, _part_name(sub))

    concept = 0
    for c in universe:
        if is_concept(solver, c.base):
            concept |= bit[c]
    if concept and not concept & ~target:
        offer(concept, 1, CONCEPT)
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
