"""The model of a solver as the handbook defines it: its values, its case
type and the values of a base at each choice point, its branches and cases,
its parameters, and the lib as the model reads it."""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from itertools import product
from typing import Annotated

from engine import (
    AdtValue,
    DeclId,
    GridLayout,
    RecordValue,
    RelationName,
    Row,
    Rows,
    Value,
)
from engine.program import (
    Column,
    TypeField,
)
from engine.quotes import quotes
from solver.annotations import (
    CaseMarker,
    DeriveLine,
    StoreLine,
)


# Choice


@quotes("solver-file.md", "Cases",
        "A constructor stands for its branch alone, not for what another "
        "branch shares with it")
@dataclass(frozen=True)
class ConstructorBranch:
    """A constructor of a choice ADT, one branch of its choice point, with
    the lines of its branch comment."""

    name: str
    fields: tuple[TypeField, ...]
    comment: tuple[int, ...]
    line: int
    """The solver line the constructor starts on."""
    own_line: bool
    """Whether the constructor opens its line."""


@quotes("solver-file.md", "Types",
        "an ADT in `Choice`, in one of these places:")
@dataclass(frozen=True)
class ChoicePoint:
    """An ADT that stands in `Choice`: where it stands, as the path of
    record fields and constructors from the `Choice` root, its type, and its
    constructors, the concept branch first."""

    path: tuple[str, ...]
    type: str
    declaration: DeclId
    """The ADT's declaration, as the model resolves `type`."""
    constructors: tuple[ConstructorBranch, ...]


def concept_branch(point: ChoicePoint) -> ConstructorBranch:
    """The concept branch at `point`: its first constructor, since the
    concept branch is declared first in `Choice` and in each field's type
    of a record `Choice` (style.md, under "Cases")."""
    return point.constructors[0]


def is_concept_branch(point: ChoicePoint, ctor: str) -> bool:
    """Whether the constructor named `ctor` is `point`'s concept branch
    (`concept_branch`)."""
    return concept_branch(point).name == ctor


def other_branches(point: ChoicePoint) -> tuple[ConstructorBranch, ...]:
    """The branches at `point` other than its concept branch
    (`concept_branch`)."""
    concept = concept_branch(point)
    return tuple(c for c in point.constructors if c != concept)


@quotes("solver-file.md", "Cases",
        "A case's base is its `Choice` value, its branch at each point the "
        "`Choice` encodes")
@quotes("solver-file.md", "Types",
        "an ADT in `Choice`, in one of these places:")
@dataclass(frozen=True)
class Choice:
    """The case type, an ADT or a record of ADTs, with the constructor at
    each choice point."""

    declaration: DeclId
    record: tuple[TypeField, ...] | None
    """The fields of a record `Choice`; None for an ADT `Choice`."""
    points: tuple[ChoicePoint, ...]


type Base = AdtValue | RecordValue
"""A `Choice` value: a case without the `@derive` and `@store` branches it
takes (history 1159)."""


# Branches and cases


@quotes("solver-file.md", "Params",
        "**`@derive` directive.** The line is a branch of a choice point on "
        "the parameter")
@dataclass(frozen=True)
class DeriveBranch:
    """`<param>=<Proposer>`: a branch of the choice point on a parameter."""

    parameter: str
    proposer: str
    line: DeriveLine | None
    """The `@derive` line; None for a derivation the survey proposes, which
    no line holds yet."""


@quotes("solver-file.md", "Program",
        "**`@store` directive.** The relation, or the instance's relation the "
        "line gives, has one value on every input, and the line is a branch "
        "of a choice point on it")
@dataclass(frozen=True)
class StoreBranch:
    """`<rel>=stored`: a branch of the choice point on a relation."""

    relation: RelationName
    """The relation as a top-level clause reads it, which the run fixes."""
    spelled: Annotated[str,
        quotes("solver-file.md", "Witness file",
               "`<param>=<Proposer>`, `<rel>=stored`, `<rel>=derived` and "
               "`<param>=stored`, each read as a constructor's name")]
    """The relation as the line spells it, the name the witness file writes
    before `=stored`: the `.decl`'s name, or `<instance>.<relation>` for a
    line above an `.init`. Two lines that spell it the same are homonyms."""
    line: StoreLine | None
    """The `@store` line; None for a value the survey judges with a line
    on its relation, which no line holds yet."""


@dataclass(frozen=True)
class StoredAtDerive:
    """`<param>=stored`: the stored value at a `@derive` point (history
    1103)."""

    parameter: str


type Branch = Annotated[
    DeriveBranch | StoreBranch | StoredAtDerive,
    quotes("solver-file.md", "Witness file",
           "the branch that the `@derive` line on `<param>` with that "
           "`<Proposer>` is; the branch that the `@store` line on `<rel>` is; "
           "the branch of the point of the `@store` line on `<rel>` in which "
           "the solver's clauses derive its value; and the branch of "
           "`<param>`'s choice point in which its value is stored per case")]


def derived_parameters(branches: Iterable[Branch]) -> frozenset[str]:
    """The parameters a `@derive` branch among `branches` derives: a case
    that takes those branches reads each of them as derived, and every
    other parameter at its stored value."""
    return frozenset(b.parameter for b in branches
                     if isinstance(b, DeriveBranch))


@quotes("solver-file.md", "Witness file",
        "the branch of the point of the `@store` line on `<rel>` in which "
        "the solver's clauses derive its value")
@dataclass(frozen=True)
class DerivedAtStore:
    """`<rel>=derived`: the derived branch of a `@store` point, the branch a
    case takes there where it takes no `@store` branch."""

    store: StoreBranch


@quotes("solver-file.md", "Cases",
        "a case is a base with a branch at each `@derive` and `@store` point "
        "its base reads.")
@quotes("solver-file.md", "Cases",
        "A solver with one case has no `Choice`, case markers, or case column "
        "on `out`.")
@dataclass(frozen=True)
class Case:
    """A base with the branch taken at each `@derive` and `@store` point.
    `base` is None for a solver with no `Choice`. `branches` holds each
    branch taken other than its point's first, in file order."""

    base: Base | None
    branches: tuple[Branch, ...]

    @property
    def is_base_case(self) -> bool:
        """Whether the case is its base's case (`base_case`)."""
        return not self.branches


@quotes("solver-file.md", "Params",
        "A case stores its base's values of each open parameter it stores, "
        "and those are that parameter's open values under the case "
        "of that base that takes the concept branch at every `@derive` and "
        "`@store` point.")
def base_case(base: Base | None) -> Case:
    """The case of `base` that takes the concept branch at every `@derive`
    and `@store` point: its base's case, under which the base's stored
    values are read."""
    return Case(base, ())


def as_case(c: Case | Base) -> Case:
    """`c` as a case: a case as it is, a base as its base case
    (`base_case`)."""
    return c if isinstance(c, Case) else base_case(c)


def bases_of(cases: Iterable[Case]) -> list[Base | None]:
    """The bases of `cases`, each once, in their order; None where the
    solver has no `Choice` (`Case.base`)."""
    return list(dict.fromkeys(c.base for c in cases))


def choice_values(bases: Iterable[Base | None]) -> list[Base]:
    """The `Choice` values among `bases`, None left out, in their
    order."""
    return [b for b in bases if b is not None]


def choice_bases(cases: Iterable[Case]) -> list[Base]:
    """The `Choice` values among the bases of `cases` (`bases_of`,
    `choice_values`), each once, in their order."""
    return choice_values(bases_of(cases))


# Params


@dataclass(frozen=True)
class UnderMarker:
    marker: CaseMarker


@quotes("style.md", "Params",
        "A parameter that every case reads is declared above the case "
        "markers, and so are its facts when it has no case column.")
@dataclass(frozen=True)
class Unmarked:
    """Above the first marker that lists a case: a parameter every case
    reads."""


type Section = Annotated[UnderMarker | Unmarked,
    quotes("solver-file.md", "Cases",
           "**Case markers.** Cases do not interleave: each case's Params and "
           "clauses are under its marker.")]
"""Case markers, and the shared parameters (`Unmarked`). A marker that lists no case, such as
`// --- Shared ---`, is a marker like any other."""


@quotes("patterns.md", "`GRID_HxW` for grid data",
        "A GRID call stores a grid as a literal layout, one fact per cell in "
        "row-major order")
@quotes("patterns.md", "`GRID_HxW` for grid data",
        "A cell that holds nothing is an empty cell, and `_` is its token.")
@dataclass(frozen=True)
class StoredGridCall:
    """One GRID call of a parameter as the engine types it: its keys, its
    layout, and its cells, None for an empty cell `_` of a stamp or a mask
    or sparse form, with a stamp's anchor cell as (row, column)."""

    keys: Row
    layout: GridLayout
    cells: tuple[tuple[int | None, ...], ...]
    anchor: tuple[int, int] | None


@dataclass(frozen=True)
class StoredGrid:
    """A parameter stored by GRID macro calls, one grid per call."""

    grids: tuple[StoredGridCall, ...]


@quotes("solver-file.md", "Params",
        "Params contains the parameterization and what derives from it.")
@dataclass(frozen=True)
class Parameter:
    """A relation of `Params`."""

    name: str
    declaration: DeclId
    columns: tuple[Column, ...]
    stored: Rows | StoredGrid
    determined: Annotated[bool,
        quotes("solver-file.md", "Determination",
               "`Determine` contains the determination as one relation per "
               "determined parameter, with the parameter's name and schema")]
    """A `Determine` relation mirrors it."""
    open: Annotated[bool,
        quotes("solver-file.md", "Params", "**`@open` directive.**")]
    """An `@open` line stands above its declaration."""
    section: Section


@quotes("solver-file.md", "Params",
        "Params contains the parameterization and what derives from it.")
@dataclass(frozen=True)
class DerivedRelation:
    """A relation of `Params` that clauses feed: data derived from the
    parameters, which is no parameter."""

    name: str
    declaration: DeclId
    columns: tuple[Column, ...]
    mirrored: Annotated[bool,
        quotes("solver-file.md", "Determination",
               "A derived relation has no determination relation.")]
    """A `Determine` relation of its name mirrors it."""
    section: Section
    """The section it stands in, as a parameter's (`Parameter.section`):
    what cases share is the marker rule's concern, whatever feeds the
    relation."""


@quotes("solver-file.md", "Params",
        "Params contains the parameterization and what derives from it.")
@dataclass(frozen=True)
class Params:
    """The parameters of `Params`, and the relations its clauses derive."""

    parameters: tuple[Parameter, ...]
    derived: tuple[DerivedRelation, ...] = ()
    """The relations of `Params` that clauses feed, which no parameter
    list holds."""

    def parameter(self, name: str) -> Parameter | None:
        """The parameter `name`; None where no parameter is of that
        name."""
        return next((p for p in self.parameters if p.name == name), None)


# Lib


@dataclass(frozen=True)
class Lib:
    """The lib's types and constants as the model reads them, parsed
    through the engine from `programs/lib/`."""

    box_types: frozenset[str]
    orientation_types: Mapping[str, tuple[str, ...]]
    """Each orientation type and its members."""
    constants: Annotated[Mapping[str, Value],
        quotes("solver-file.md", "Witness file",
               "Use a string for a lib constant and a list for a record.")]
    """The constants a witness `assign` may name."""
    elems: Mapping[str, str]
    """Each lib relation that enumerates an orientation type (its name
    ends in `vocabulary.ELEM_SUFFIX`), with the type it enumerates."""



# The case type's values


def point_at(choice: Choice, ctor: ConstructorBranch) -> ChoicePoint:
    """The choice point `ctor` is a branch of."""
    return next(p for p in choice.points if ctor in p.constructors)


def constructor_places(choice: Choice, name: str
                       ) -> tuple[tuple[ChoicePoint, ConstructorBranch], ...]:
    """Each choice point where a constructor named `name` stands, with
    that constructor, in point order."""
    return tuple((p, c) for p in choice.points for c in p.constructors
                 if c.name == name)


def points_of_type(choice: Choice, type: str) -> list[ChoicePoint]:
    """The choice points whose type is `type`, in point order."""
    return [p for p in choice.points if p.type == type]


def constructor_named(choice: Choice, name: str) -> ConstructorBranch | None:
    """The constructor of `Choice` named `name`, at the first point, in
    point order, where one stands; None where none does."""
    places = constructor_places(choice, name)
    return places[0][1] if places else None


def path_constructors(choice: Choice, path: tuple[str, ...]
                      ) -> tuple[str, ...]:
    """The names of the constructors a point's path passes through, top
    first: a path is a record `Choice`'s field, then a constructor and one
    of its fields at each step."""
    return (path[1:] if choice.record is not None else path)[0::2]


def _descent(choice: Choice, base: Base, path: tuple[str, ...]
             ) -> tuple[list[tuple[AdtValue | RecordValue, int]], Value] | None:
    """The values a point's path enters in `base`, top first, each with
    the index of the field the path takes in it, and the value at the
    point; None where the base does not reach the point (a constructor on
    the path is another)."""
    entered: list[tuple[AdtValue | RecordValue, int]] = []
    value: Value = base
    steps = path
    if choice.record is not None and steps:
        names = [f.name for f in choice.record]
        if not isinstance(value, RecordValue) or steps[0] not in names:
            return None
        entered.append((value, names.index(steps[0])))
        value = value.fields[names.index(steps[0])]
        steps = steps[1:]
    for ctor, field in zip(steps[0::2], steps[1::2], strict=True):
        if not isinstance(value, AdtValue) or value.constructor != ctor:
            return None
        decl = constructor_named(choice, ctor)
        if decl is None:
            return None
        names = [f.name for f in decl.fields]
        if field not in names:
            return None
        entered.append((value, names.index(field)))
        value = value.args[names.index(field)]
    return entered, value


def value_at(choice: Choice, base: Base, path: tuple[str, ...]
             ) -> Value | None:
    """The value at a point's path in `base`, None where the base does not
    reach the point (a constructor on the path is another)."""
    got = _descent(choice, base, path)
    return None if got is None else got[1]


def with_value_at(choice: Choice, base: Base, path: tuple[str, ...],
                  value: Value) -> Base | None:
    """`base` with `value` at a point's path; None where the base does not
    reach the point (`value_at`)."""
    if not path:
        return value if isinstance(value, AdtValue | RecordValue) else None
    got = _descent(choice, base, path)
    if got is None:
        return None
    new: Value = value
    for at, i in reversed(got[0]):
        if isinstance(at, RecordValue):
            new = RecordValue((*at.fields[:i], new, *at.fields[i + 1:]))
        else:
            new = AdtValue(at.constructor, (*at.args[:i], new, *at.args[i + 1:]))
    return new if isinstance(new, AdtValue | RecordValue) else None


def constructor_at(choice: Choice, base: Base, point: ChoicePoint
                   ) -> str | None:
    """The constructor `base` takes at `point`; None where the base does
    not reach the point."""
    at = value_at(choice, base, point.path)
    return at.constructor if isinstance(at, AdtValue) else None


def constructors_taken(choice: Choice, base: Base
                       ) -> tuple[tuple[ChoicePoint, str], ...]:
    """Each choice point `base` reaches with the constructor it takes
    there, in point order."""
    return tuple((p, c) for p in choice.points
                 if (c := constructor_at(choice, base, p)) is not None)


def non_concept_at(choice: Choice, base: Base, point: ChoicePoint
                   ) -> str | None:
    """The constructor `base` takes at `point` where it is not the point's
    concept branch; None where the base takes the concept branch there or
    does not reach the point."""
    at = constructor_at(choice, base, point)
    return at if at is not None and not is_concept_branch(point, at) else None


def takes_constructor(choice: Choice, base: Base | None,
                      ctor: ConstructorBranch) -> bool:
    """Whether `base` has `ctor` at its point."""
    return base is not None \
        and constructor_at(choice, base, point_at(choice, ctor)) == ctor.name


def every_base(choice: Choice) -> tuple[Base, ...] | None:
    """Every `Choice` value, for a solver that has no `impl_choice`
    (solver-file.md, under "Cases": the cases are every combination of the
    fields); None where a field is of a type with no ADT to enumerate."""
    by_path = {p.path: p for p in choice.points}

    def values(path: tuple[str, ...]) -> list[Value] | None:
        point = by_path.get(path)
        if point is None:
            return None
        out: list[Value] = []
        for c in point.constructors:
            args: list[list[Value]] = []
            for f in c.fields:
                sub = values((*path, c.name, f.name))
                if sub is None:
                    return None
                args.append(sub)
            out += [AdtValue(c.name, tuple(a)) for a in product(*args)]
        return out

    if choice.record is None:
        got = values(())
        return None if got is None else tuple(
            v for v in got if isinstance(v, AdtValue))
    fields: list[list[Value]] = []
    for f in choice.record:
        sub = values((f.name,))
        if sub is None:
            return None
        fields.append(sub)
    return tuple(RecordValue(tuple(combo)) for combo in product(*fields))
