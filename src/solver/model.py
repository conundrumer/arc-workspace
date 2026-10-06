"""The model of a solver as the handbook defines it: its case type, its
branches and cases, its parameters, the lib as the model reads it, and the
aggregate `Solver`; and the functions that build each part from a parsed
program, which `solver.load` and the checks read as well, but the solver's
cases (`solver.cases`)."""

from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from itertools import product
from pathlib import Path
from typing import Annotated

from arc.task import Task
from engine import checkout
from engine.engine import unresolved
from engine.memo import ByIdentity
from engine import (
    AdtValue,
    DeclId,
    Engine,
    GridLayout,
    Index,
    Limits,
    ParseFailure,
    Program,
    RecordValue,
    RelationName,
    Row,
    Rows,
    RunFailure,
    RunResult,
    Scope,
    Span,
    Tuples,
    Value,
)
from engine.program import (
    MemberCell,
    Primitive,
    first_line,
    term_value,
    typed_value,
    TypeReading,
    ValueReading,
    dotted,
    own,
    AdtType,
    AliasType,
    AtomLiteral,
    Component,
    Column,
    DefinedName,
    GridCall,
    Instance,
    RigidCall,
    RecordType,
    RelationDecl,
    SubtypeType,
    Term,
    TypeDecl,
    TypeField,
)
from engine.quotes import quotes
from engine.text import prefixed
from solver import witness as witness_reader
from solver.graph import (
    MAX_DEPTH,
    Graph,
    by_innermost,
    component_chain,
    followed,
)
from solver.annotations import (
    DirectiveWord,
    branch_band,
    Annotations,
    CaseMarker,
    DeriveLine,
    IgnoreForm,
    IgnoreLine,
    NamedVerdict,
    StoreLine,
    WitnessLine,
)
from solver.problems import (
    InSolver,
    InWitnessFile,
    Named,
    NameFault,
    ProblemKind,
    Fault,
    Undecided,
    UndecidedForm,
    WitnessFileRole,
)
from solver.vocabulary import (
    BOX,
    CHOICE,
    DETERMINE,
    DETERMINE_SCOPE,
    ELEM_SUFFIX,
    ENUMERATOR,
    IDENT,
    IMPL,
    INPUT,
    LIB_FILE,
    PARAMS,
    PARAMS_SCOPE,
    PROPOSE,
    PROPOSERS_FILE,
)
from solver.witness import AssignArg, AssignRows, Groups, WitnessFile

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
    constructors, the concept branch first. (The old `models.Site`.)"""

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
        "line names, has one value on every input, and the line is a branch "
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
           "the branch of `<rel>`'s point in which the solver's clauses "
           "derive its value; and the branch of `<param>`'s choice point in "
           "which its value is stored per case")]


def derived_parameters(branches: Iterable[Branch]) -> frozenset[str]:
    """The parameters a `@derive` branch among `branches` derives: a case
    that takes those branches reads each of them as derived, and every
    other parameter at its stored value."""
    return frozenset(b.parameter for b in branches
                     if isinstance(b, DeriveBranch))


@quotes("solver-file.md", "Witness file",
        "the branch of `<rel>`'s point in which the solver's clauses derive "
        "its value")
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


@quotes("lib-protocol.md", "Lib addition protocol",
        "the lib, `programs/lib.dl` and the modules under `programs/lib/`")
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


# Solver


@quotes("solver-file.md", "File structure",
        "A solver is one file, `<task_id>.dl`.")
@dataclass(frozen=True)
class Solver:
    """One solver: its program and the model read from it. `problems`
    holds the faults: what `load` could not read."""

    stem: str
    task_id: str
    program: Program
    annotations: Annotations
    choice: Annotated[Choice | None,
        quotes("solver-file.md", "Cases",
               "A solver with one case has no `Choice`, case markers, or case "
               "column on `out`.")]
    """None for a solver with one case."""
    branches: tuple[Branch, ...]
    params: Params
    witness_file: WitnessFile | None
    """None where the task has no witness file, or where its shape gives
    no file (`solver.witness.read`), which `problems` then reports."""
    task: Task | None
    """None where the task has no task file."""
    lib: Lib
    problems: tuple[Fault, ...]
    engine: Engine = field(compare=False, repr=False)
    """The engine `load` read the solver through, whose index of the
    program resolves the types the model reads (`Graph`)."""

    def fault(self, kind: ProblemKind) -> Fault | None:
        """The first of `problems` of `kind`; None where none is."""
        return next((p for p in self.problems if p.kind == kind), None)

    @property
    def given_task(self) -> Task:
        """The task, for a part that reads its pairs, which a command
        reaches only after it refuses a solver whose task has no task
        file. Raises `ValueError` where it has none."""
        if self.task is None:
            raise ValueError(f"{self.stem} has no task")
        return self.task


# Paths

def solver_file(stem: str) -> Path:
    """The file of the solver `stem` under `checkout.solvers()`."""
    return checkout.solvers() / f"{stem}.dl"


def proposers_path() -> Path:
    """The proposers file under the checkout's `programs/`."""
    return checkout.programs() / PROPOSERS_FILE


TOP = Scope(())


def parse_with_lib(engine: Engine, text: str) -> Program | ParseFailure:
    """`text` parsed against `programs/`, where the lib stands, with the
    lib's include added where the parse holds none."""
    parsed = engine.parse(text, checkout.programs())
    if isinstance(parsed, Program) and any(
            Path(i.path).name == LIB_FILE for i in parsed.includes):
        return parsed
    return engine.parse_including(text, LIB_FILE, checkout.programs())


# Reading values


def row_value(terms: tuple[Term, ...],
              constants: Mapping[str, Value]) -> Row | None:
    """The row the terms state (`term_value`), None where a term states no
    constant."""
    vals = [term_value(t, constants.get) for t in terms]
    if any(v is None for v in vals):
        return None
    return tuple(v for v in vals if v is not None)


# Reading the lib


def read_lib(program: Program) -> Lib:
    """The lib's types and constants as the model reads them, from a
    program that includes the lib: the parts whose `file` is set.

    The Box types are `Box` and each alias of one (style.md, "Box
    readings"); an orientation type is the type of an `*_elem` relation,
    and its members are the constants its facts state and the members of
    the `*_elem` relations its clauses read (principles.md, "Orientation");
    the constants are the lib's `#define` names whose value is a
    constant."""
    lib_types = [t for t in program.types if not own(t.span)]
    links = {t.name: t.target for t in lib_types if isinstance(t, AliasType)}
    box = {BOX} | {n for n in links if followed(links, n)[-1] == BOX} \
        if any(t.name == BOX for t in lib_types) else set[str]()
    constants: dict[str, Value] = {}
    pending = [d for d in program.defines if not own(d)
               and d.params is None and d.value is not None]
    while pending:
        left = []
        for d in pending:
            assert d.value is not None
            v = term_value(d.value, constants.get)
            if v is None:
                left.append(d)
            else:
                constants[d.name] = v
        if len(left) == len(pending):
            break
        pending = left
    elems = {r.name: r.columns[0].type for r in program.relations
             if not own(r.span) and r.scope == TOP
             and r.name.endswith(ELEM_SUFFIX) and len(r.columns) == 1}

    def members(name: str, seen: frozenset[str]) -> list[str]:
        out: list[str] = []
        for u in program.units:
            if u.scope != TOP or u.head.relation != RelationName((), name):
                continue
            got: list[str] = []
            if u.body is None and len(u.head.args) == 1 \
                    and isinstance(u.head.args[0], DefinedName):
                got = [u.head.args[0].name]
            elif u.body is not None:
                for lit in u.body:
                    if not isinstance(lit, AtomLiteral):
                        continue
                    rel = lit.atom.relation
                    if not rel.instances \
                            and rel.name in elems and rel.name not in seen:
                        got += members(rel.name, seen | {rel.name})
            out += [m for m in got if m not in out]
        return out

    orientation = {t: tuple(members(n, frozenset({n})))
                   for n, t in elems.items()}
    return Lib(frozenset(box), orientation, constants, elems)


# Reading the case type


type _OwnType = Callable[[str, Scope], TypeDecl | None]
"""The type of the solver's own text a name denotes when read in a scope
(`Index.type_decl`); None where it denotes none or a lib type."""


def _own_type(index: Index) -> _OwnType:
    """`_OwnType` through `index`."""
    def read(name: str, scope: Scope) -> TypeDecl | None:
        t = index.type_decl(name, scope)
        return t if t is not None and own(t.span) else None
    return read


def _branch_comment(program: Program, adt: AdtType,
                    index: int) -> tuple[int, ...]:
    """The lines of the own-line comments above constructor `index`, below
    the constructor before it or the type's first line."""
    start, end = branch_band(adt, index)
    return tuple(sorted(c.line for c in program.comments
                        if own(c) and c.own_line
                        and start < c.line < end))


def _points(program: Program, adt: AdtType, path: tuple[str, ...],
            types: _OwnType, seen: frozenset[str]) -> list[ChoicePoint]:
    ctors = tuple(ConstructorBranch(c.name, c.fields,
                                    _branch_comment(program, adt, i),
                                    c.span.first, c.own_line)
                  for i, c in enumerate(adt.constructors))
    out = [ChoicePoint(path, adt.name, adt.id, ctors)]
    for c in adt.constructors:
        for f in c.fields:
            t = types(f.type, adt.scope)
            if isinstance(t, AdtType) and t.name not in seen:
                out += _points(program, t, (*path, c.name, f.name), types,
                               seen | {t.name})
    return out


def read_choice(program: Program, index: Index, problems: list[Fault]
                ) -> Choice | None:
    """The `Choice` type (solver-file.md, under "Cases" and "Types"): an ADT,
    or a record whose fields are ADTs, each ADT a choice point, and each ADT a
    field of a constructor stands in takes a point of its own."""
    types = _own_type(index)
    root = types(CHOICE, TOP)
    if root is None:
        return None
    if isinstance(root, AdtType):
        return Choice(root.id, None,
                      tuple(_points(program, root, (), types,
                                    frozenset({root.name}))))
    if isinstance(root, RecordType):
        points: list[ChoicePoint] = []
        for f in root.fields:
            t = types(f.type, root.scope)
            if isinstance(t, AdtType):
                points += _points(program, t, (f.name,), types,
                                  frozenset({t.name}))
            else:
                problems.append(Fault(
                    ProblemKind.UNDECIDED, InSolver(root.span.first),
                    Undecided(UndecidedForm.CHOICE_FIELD_NOT_ADT, f.name)))
        return Choice(root.id, root.fields, tuple(points))
    problems.append(Fault(
        ProblemKind.UNDECIDED, InSolver(root.span.first),
        Undecided(UndecidedForm.CHOICE_NOT_ADT_OR_RECORD, None)))
    return None


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


def based_choice(solver: "Solver") -> Choice:
    """The solver's `Choice`, for a caller that holds a base of it. Raises
    `ValueError` for a solver with no `Choice`, which has no base."""
    if solver.choice is None:
        raise ValueError(f"{solver.stem}: no `Choice`, so no base")
    return solver.choice


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


# Reading the parameters


def _component(program: Program, name: str):
    """The top-level component `name` of the solver's own text."""
    return own_top(program.components, name)


def instance_of(program: Program, component: str) -> Instance | None:
    """The top-level instance of `component` the solver's own text makes."""
    return next((i for i in program.instances
                 if i.component == component and i.scope == TOP
                 and own(i.span)), None)


def choice_line(program: Program, choice: Choice) -> int:
    """The line `Choice`'s declaration starts on, a declaration of the
    solver's own text. Raises `ValueError` where it has no span."""
    decl = program.declared(choice.declaration)
    if decl.span is None:
        raise ValueError("`Choice` has a declaration an operation wrote")
    return decl.span.first


def declaration_of(program: Program, p: Parameter | DerivedRelation
                   ) -> RelationDecl:
    """The declaration of a relation of `Params`."""
    return program.declared_relation(p.declaration)


def read_params(program: Program, annotations: Annotations,
                constants: Mapping[str, Value],
                lists_case: Callable[[CaseMarker], bool],
                problems: list[Fault]) -> Params:
    """The relations of `Params` (solver-file.md, under "Params"). A relation
    that a clause of `Params` feeds, other than a RIGID block's relations,
    which its closure places, is derived data (solver-file.md, under "Params"),
    listed apart with whether a `Determine` relation of its name mirrors it
    (solver-file.md, under "Determination"). Every other relation is a
    parameter, with its stored facts or GRID calls, whether a `Determine`
    relation of its name mirrors it (solver-file.md, under "Determination");
    each with the section it stands in (`section_at`)."""
    comp = _component(program, PARAMS)
    if comp is None or comp.span is None:
        return Params(())
    scope = PARAMS_SCOPE
    determined = {r.name for r in program.relations
                  if r.scope == DETERMINE_SCOPE and own(r.span)}
    markers = _markers_in(annotations.markers, comp.span)
    rigid = {n for m in program.macros if isinstance(m, RigidCall)
             and m.scope == scope
             for n in program.bound_names(m)}
    fed = {u.head.relation.name for u in program.units
           if u.scope == scope and u.body is not None and own(u.span)
           and not u.head.relation.instances} - rigid
    out: list[Parameter] = []
    derived: list[DerivedRelation] = []
    for rel in program.relations:
        if rel.scope != scope or not own(rel.span):
            continue
        if rel.name in fed:
            derived.append(DerivedRelation(
                rel.name, rel.id, rel.columns, rel.name in determined,
                _section(markers, rel.span.first, lists_case)))
            continue
        name = rel.scoped_name
        grids = [m for m in program.macros if isinstance(m, GridCall)
                 and m.scope == scope and m.relation == name]
        stored: tuple[Row, ...] | StoredGrid
        if grids:
            values: list[StoredGridCall] = []
            for g in grids:
                call = _grid_call(g, constants)
                if call is None:
                    problems.append(Fault(
                        ProblemKind.UNDECIDED,
                        InSolver(g.span.first if g.span else rel.span.first),
                        Undecided(UndecidedForm.GRID_CALL_NOT_CONSTANT,
                                  rel.name)))
                    continue
                values.append(call)
            stored = StoredGrid(tuple(values))
        else:
            rows: list[Row] = []
            for u in program.units:
                if u.scope != scope or u.body is not None \
                        or u.head.relation != name:
                    continue
                row = row_value(u.head.args, constants)
                if row is None:
                    problems.append(Fault(
                        ProblemKind.UNDECIDED, InSolver(u.head.line),
                        Undecided(UndecidedForm.FACT_NOT_CONSTANT,
                                  rel.name)))
                    continue
                rows.append(row)
            stored = tuple(rows)
        out.append(Parameter(rel.name, rel.id, rel.columns, stored,
                             rel.name in determined,
                             _section(markers, rel.span.first, lists_case)))
    return Params(tuple(out), tuple(derived))


def _grid_call(call: GridCall, constants: Mapping[str, Value]
               ) -> StoredGridCall | None:
    """The call's keys and cells as values; None where a key states no
    constant, or a cell holds neither a number nor, in a stamp or a mask
    or sparse form, the empty cell `_`."""
    keys = row_value(call.keys, constants)
    if keys is None:
        return None
    rows: list[tuple[int | None, ...]] = []
    for row in call.cells:
        cells: list[int | None] = []
        for cell in row:
            member = None if call.layout.full \
                else MemberCell.of_term(cell.term)
            if member is not None:
                cells.append(None if member is MemberCell.EMPTY
                             else member.grid_value)
                continue
            value = term_value(cell.term, constants.get)
            if type(value) is not int:
                return None
            cells.append(value)
        rows.append(tuple(cells))
    return StoredGridCall(keys, call.layout, tuple(rows), call.anchor)


def _section(markers: Sequence[CaseMarker], line: int,
             lists_case: Callable[[CaseMarker], bool]) -> Section:
    """The section a line stands in among the markers of its part of the file:
    unmarked above the first marker that lists a case (style.md, under
    "Params"), else under the nearest marker above it, whatever it lists."""
    above = [m for m in markers if m.line < line]
    if any(lists_case(m) for m in above):
        return UnderMarker(above[-1])
    return Unmarked()


def section_at(solver: Solver, scope: Scope, line: int) -> Section:
    """The section a line of the solver's own text stands in
    (solver-file.md, under "Cases"): among the markers inside the top-level
    component the line's scope stands in, or for a top-level line, among
    the markers outside every component (`_section`)."""
    return _SECTIONS.compute(solver, lambda: _sections(solver))(scope, line)


def marker_at(solver: Solver, scope: Scope, line: int) -> CaseMarker | None:
    """The case marker a line of the solver's own text stands under
    (`section_at`); None for a line above the first marker that lists a
    case (`Unmarked`)."""
    section = section_at(solver, scope, line)
    return section.marker if isinstance(section, UnderMarker) else None


_SECTIONS: ByIdentity[Solver, Callable[[Scope, int], Section]] \
    = ByIdentity()


_LISTING: ByIdentity[Solver, dict[int, bool]] = ByIdentity()


def marker_listing(solver: Solver) -> dict[int, bool]:
    """Whether each case marker, by its line, lists a case (`lists_case`),
    read once per solver while it lives."""
    return _LISTING.compute(solver, lambda: {
        m.line: lists_case(solver, m) for m in solver.annotations.markers})


def _markers_in(markers: Sequence[CaseMarker], span: Span
                ) -> list[CaseMarker]:
    """The case markers whose lines `span` holds."""
    return [m for m in markers if span.first <= m.line <= span.last]


def _sections(solver: Solver) -> Callable[[Scope, int], Section]:
    """`section_at` for one solver, with each marker's listing read
    once."""
    spans = {c.name: c.span for c in solver.program.components
             if c.scope == TOP and own(c.span) and c.span is not None}
    markers = solver.annotations.markers
    listing = marker_listing(solver)
    outside = [m for m in markers
               if not any(s.first <= m.line <= s.last for s in spans.values())]

    def at(scope: Scope, line: int) -> Section:
        if scope.components:
            span = spans.get(scope.components[0])
            region = [] if span is None else _markers_in(markers, span)
        else:
            region = outside
        return _section(region, line, lambda m: listing[m.line])
    return at


# Reading the branches


def _decl(program: Program, id: DeclId) -> RelationDecl | Instance | None:
    """The relation or instance `id` names, None for any other
    declaration."""
    got = program.declaration(id)
    return got if isinstance(got, RelationDecl | Instance) else None


def _relations_of(program: Program, component: str) -> set[str]:
    """The relations a component declares, its bases' included."""
    by_scope = by_innermost(program.relations)
    return {r for name in _chain(program, component)
            for r in by_scope.get(name, {})}


def _chain(program: Program, component: str) -> list[str]:
    """The component and the components it extends, in order."""
    return [n for n in component_chain(
        {c.name: c for c in program.components}, component) if n is not None]


def _relations_under(program: Program, component: str,
                     outer: frozenset[str] = frozenset()
                     ) -> list[RelationName]:
    """Every relation an instance of `component` holds, as a name from the
    instance: the relations the component and its bases declare, and those
    of each instance they make, in turn."""
    out: list[RelationName] = []
    chain = _chain(program, component)
    if outer & set(chain):
        return out
    relations = by_innermost(program.relations)
    instances = by_innermost(program.instances)
    for name in chain:
        out += [RelationName((), r) for r in relations.get(name, {})]
        for i in instances.get(name, {}).values():
            out += [RelationName((i.name, *r.instances), r.name)
                    for r in _relations_under(program, i.component,
                                              outer | set(chain))]
    return out


def _scope_path(program: Program, scope: Scope) -> tuple[str, ...] | None:
    """The instances a top-level statement reads a declaration of `scope`
    through: none at the top level, and the one top-level instance of a
    top-level component; None for any other scope."""
    if scope == TOP:
        return ()
    instances = [i for i in program.instances
                 if i.scope == TOP and i.component == scope.components[-1]]
    if len(scope.components) == 1 and len(instances) == 1:
        return (instances[0].name,)
    return None


def _decl_relation(program: Program, decl: RelationDecl
                   ) -> RelationName | None:
    """The name a top-level statement reads a relation by (`_scope_path`)."""
    path = _scope_path(program, decl.scope)
    return None if path is None else RelationName(path, decl.name)


def _instance_path(program: Program, decl: Instance
                   ) -> tuple[str, ...] | None:
    """The instances a top-level statement reads the relations of the
    instance `decl` through, `decl` last (`_scope_path`)."""
    path = _scope_path(program, decl.scope)
    return None if path is None else (*path, decl.name)


def read_branches(program: Program, annotations: Annotations,
                  proposers: frozenset[str] | None,
                  problems: list[Fault]) -> tuple[Branch, ...]:
    """The branches of the `@derive` and `@store` lines (solver-file.md, under
    "Params" and "Program"), and `<param>=stored` at each `@derive` point
    (history 1103), in file order: a point's stored branch before its `@derive`
    branches. A second line of one branch's name holds no branch of its own."""
    def unplaced(line: int, word: DirectiveWord) -> None:
        problems.append(Fault(ProblemKind.DIRECTIVE_UNPLACED,
                              InSolver(line), Named(word)))

    found: list[tuple[int, Branch]] = []
    stored_at: set[str] = set()
    derivations: set[tuple[str, str]] = set()
    stores: set[RelationName] = set()
    for d in annotations.derives:
        decl = None if d.above is None else _decl(program, d.above)
        if not isinstance(decl, RelationDecl) or decl.scope != PARAMS_SCOPE:
            unplaced(d.line, DirectiveWord.DERIVE)
            continue
        if proposers is not None and d.proposer not in proposers:
            problems.append(Fault(ProblemKind.UNKNOWN_PROPOSER,
                                           InSolver(d.line),
                                           Named(d.proposer)))
        if decl.name not in stored_at:
            stored_at.add(decl.name)
            found.append((d.line, StoredAtDerive(decl.name)))
        if (decl.name, d.proposer) not in derivations:
            derivations.add((decl.name, d.proposer))
            found.append((d.line, DeriveBranch(decl.name, d.proposer, d)))
    for s in annotations.stores:
        decl = None if s.above is None else _decl(program, s.above)
        rel: RelationName | None = None
        spelled = ""
        if isinstance(decl, RelationDecl) and s.relation is None:
            spelled = decl.name
            rel = _decl_relation(program, decl)
            if rel is None:
                problems.append(Fault(
                    ProblemKind.UNDECIDED, InSolver(s.line),
                    Undecided(UndecidedForm.READ_THROUGH_NO_INSTANCE,
                              decl.name)))
                continue
        elif isinstance(decl, Instance) and s.relation is not None:
            if s.relation not in _relations_of(program, decl.component):
                problems.append(Fault(
                    ProblemKind.STORE_NAMES_NOTHING, InSolver(s.line),
                    Named(RelationName((decl.name,), s.relation))))
                continue
            path = _instance_path(program, decl)
            if path is None:
                problems.append(Fault(
                    ProblemKind.UNDECIDED, InSolver(s.line),
                    Undecided(UndecidedForm.READ_THROUGH_NO_INSTANCE,
                              decl.name)))
                continue
            rel = RelationName(path, s.relation)
            spelled = RelationName((decl.name,), s.relation).text
        if rel is None:
            unplaced(s.line, DirectiveWord.STORE)
            continue
        if rel not in stores:
            stores.add(rel)
            found.append((s.line, StoreBranch(rel, spelled, s)))
    lined = {(b.parameter, b.proposer) for _l, b in found
             if isinstance(b, DeriveBranch)}
    for i in annotations.ignores:
        if i.form is IgnoreForm.LINT or i.name is not None:
            continue
        targets = ignore_targets(program, i)
        if not targets:
            unplaced(i.line, DirectiveWord.IGNORE)
        if i.proposer is None:
            continue
        if proposers is not None and i.proposer not in proposers:
            problems.append(Fault(ProblemKind.UNKNOWN_PROPOSER,
                                  InSolver(i.line), Named(i.proposer)))
        for t in targets:
            if (t.name, i.proposer) in lined:
                problems.append(Fault(
                    ProblemKind.TWO_LINES_ON_DERIVATION, InSolver(i.line),
                    Named(DeriveBranch(t.name, i.proposer, None))))
    return tuple(b for _l, b in sorted(found, key=lambda f: f[0]))


def ignore_targets(program: Program, line: IgnoreLine
                   ) -> tuple[RelationName, ...]:
    """The parameters or relations a bare `@ignore: derive` or `@ignore: store`
    line stands on (solver-file.md, under "Params" and "Program"), which are
    those a directive in its place stands on: a parameter's `.decl` for the
    derive form; for the store form, a relation's `.decl`, and above a `.init`
    the relation the line states, or with none stated every relation of the
    instance (solver-file.md, under "Program"). Empty where it stands on
    nothing its form takes."""
    decl = None if line.above is None else _decl(program, line.above)
    if line.form is IgnoreForm.DERIVE:
        if isinstance(decl, RelationDecl) and decl.scope == PARAMS_SCOPE \
                and line.relation is None:
            return (decl.scoped_name,)
        return ()
    if isinstance(decl, RelationDecl) and line.relation is None:
        rel = _decl_relation(program, decl)
        return () if rel is None else (rel,)
    if isinstance(decl, Instance):
        path = _instance_path(program, decl)
        if path is None:
            return ()
        if line.relation is not None:
            return (RelationName(path, line.relation),)
        return tuple(RelationName((*path, *r.instances), r.name)
                     for r in _relations_under(program, decl.component))
    return ()


def ignore_target(program: Program, line: IgnoreLine) -> RelationName | None:
    """The one parameter or relation a bare `@ignore: derive` or `@ignore:
    store` line stands on (`ignore_targets`); None where it stands on
    none, or on every relation of an instance."""
    targets = ignore_targets(program, line)
    if len(targets) != 1 or (line.relation is None and isinstance(
            None if line.above is None else _decl(program, line.above),
            Instance)):
        return None
    return targets[0]


# Reading the proposers


def proposers_program(engine: Engine) -> Program | ParseFailure:
    """`programs/proposers.dl` parsed with the lib, as the proposer probe
    runs it; parsed once per engine and text of the file."""
    text = proposers_path().read_text()
    return _PROPOSERS.guarded(engine, text,
                              lambda: parse_with_lib(engine, text))


_PROPOSERS: ByIdentity[Engine, tuple[str, Program | ParseFailure]] \
    = ByIdentity()
"""`proposers_program`'s parse for each engine while it lives, with the
text it parsed."""


def proposer_names(program: Program) -> tuple[str, ...]:
    """The proposers: the components of the proposers program, which is
    `proposers.dl` alone, that declare `propose` (proposers.dl's
    header)."""
    return tuple(c.name for c in program.components
                 if any(r.name == PROPOSE and r.scope.components[-1:]
                         == (c.name,) for r in program.relations))


# Load


def instance_faults(program: Program) -> list[Fault]:
    """The faults of the instance tree the model walks (`Graph`), each at
    the solver's line it stands on, or, inside an included component, at
    the line of the solver's instance its path starts from: a path deeper
    than `MAX_DEPTH`; an instance of a component no file declares inside
    an included component (the solver's own are `load`'s); a component
    that extends one no file declares; and type arguments that are not
    one per type parameter, of an instance or of a component's base. A
    RIGID call in `Params` whose block's charts are not one per name it
    binds is a fault too (`solve._blocks`)."""
    comps = {c.name: c for c in program.components}
    by_scope = by_innermost(program.instances)
    out: list[Fault] = []

    def fault(kind: ProblemKind, span: Span | None, start: int,
              name: str) -> None:
        got = Fault(kind, InSolver(span.first if own(span) and span
                                   is not None else start), Named(name))
        if got not in out:
            out.append(got)

    def chain(comp: str | None, start: int) -> list[str | None]:
        seen = component_chain(comps, comp)
        for name, base in zip(seen, seen[1:], strict=False):
            if name is None or base is None:
                break
            c = comps[name]
            if base not in comps:
                fault(ProblemKind.BASE_OF_NOTHING, c.span, start, base)
                return seen[:-1]
            if len(c.base_type_args) != len(comps[base].type_params):
                fault(ProblemKind.TYPE_ARGUMENTS, c.span, start, base)
        return seen

    front: list[tuple[tuple[str, ...], str | None, int]] = [((), None, 0)]
    while front:
        at, here, start = front.pop(0)
        for scope in chain(here, start):
            for name, inst in by_scope.get(scope, {}).items():
                line = start if at else first_line(inst.span)
                path = (*at, name)
                comp = comps.get(inst.component)
                if comp is None:
                    if not own(inst.span):
                        fault(ProblemKind.INSTANCE_OF_NOTHING, inst.span,
                              line, inst.component)
                    continue
                if len(inst.type_args) != len(comp.type_params):
                    fault(ProblemKind.TYPE_ARGUMENTS, inst.span, line,
                          inst.component)
                if len(path) > MAX_DEPTH:
                    if not any(f.kind is ProblemKind.INSTANCE_UNFOLLOWED
                               and f.place == InSolver(line) for f in out):
                        fault(ProblemKind.INSTANCE_UNFOLLOWED, None, line,
                              dotted(path))
                    continue
                front.append((path, comp.name, line))
    params = PARAMS_SCOPE
    for m in program.macros:
        if isinstance(m, RigidCall) and m.scope == params \
                and program.bound_charts(m) is None:
            fault(ProblemKind.RIGID_CHARTS, m.span, 0, m.block)
    return out


def branch_witnesses(solver: Solver, ctor: str) -> list[WitnessLine]:
    """The `@witness` lines the branch comment of the constructor named
    `ctor` holds, in file order."""
    return [w for w in solver.annotations.witnesses if w.constructor == ctor]


def assignable(solver: Solver, key: str) -> bool:
    """Whether an `assign` key names something an entry may assign
    (solver-file.md, under "Witness file"): a parameter, or a `@store` relation
    as its line spells it."""
    return any(p.name == key for p in solver.params.parameters) \
        or store_branch(solver, key) is not None


def store_branch(solver: Solver, spelled: str) -> StoreBranch | None:
    """The `@store` branch whose line spells its relation `spelled`, the
    first in file order; None where no line does."""
    return next((b for b in solver.branches
                 if isinstance(b, StoreBranch) and b.spelled == spelled),
                None)


def read_witness(text: str, params: Params, role: WitnessFileRole
                 ) -> tuple[WitnessFile | None, tuple[Fault, ...]]:
    """The witness file `text` states (`solver.witness.read`), each
    `assign` value of a parameter `params` stores by a GRID call read as a
    grid (`solver.witness.with_grids`), and what could not be read, placed
    in the file `role`."""
    file, problems = witness_reader.read(text, role)
    if file is None:
        return None, problems
    return witness_reader.with_grids(file, grid_stored(params)), problems


def grid_stored(params: Params) -> frozenset[str]:
    """The parameters stored by GRID calls, whose `assign` values read as
    grids (solver-file.md, under "Witness file")."""
    return frozenset(p.name for p in params.parameters
                     if isinstance(p.stored, StoredGrid))


def lists_case(solver: Solver, marker: CaseMarker) -> bool:
    """Whether a marker lists a case: a part of it denotes one."""
    from solver.names import Denoted, denote
    return any(isinstance(denote(solver, p.name), Denoted)
               for p in marker.parts)


def name_problems(solver: Solver) -> Iterator[Fault]:
    """The names the solver and its witness file hold that denote nothing:
    verdicts, markers, named `@ignore` lines, group names, and `assign`
    keys and the strings of `assign` values (`arg_value`)."""
    from solver.names import denote, names_a_constructor

    def check(name: str | tuple[str, ...], line: int
              ) -> Iterator[Fault]:
        got = denote(solver, name)
        if isinstance(got, NameFault):
            yield got.at(InSolver(line))

    a = solver.annotations
    for v in (*a.witnesses, *a.derives, *a.stores):
        if isinstance(v.verdict, NamedVerdict):
            yield from check(v.verdict.text, v.line)
    for m in a.markers:
        listing = lists_case(solver, m)
        for part in m.parts:
            if part.prose:
                continue
            got = denote(solver, part.name)
            if not isinstance(got, NameFault):
                continue
            if got.kind == ProblemKind.NAME_FORM \
                    and names_a_constructor(solver, part.name):
                yield Fault(ProblemKind.NAME_FORM, InSolver(m.line),
                            Named(part.name))
            elif listing:
                yield Fault(ProblemKind.MARKER_NAMES_NOTHING,
                            InSolver(m.line), Named(part.name))
    for i in a.ignores:
        if i.name is not None:
            yield from check(i.name, i.line)
    if solver.witness_file is None:
        return
    for e in solver.witness_file.entries:
        if isinstance(e.output, Groups):
            for g in e.output.groups:
                for name in g.cases:
                    got = denote(solver, name)
                    if isinstance(got, NameFault):
                        yield got.at(InWitnessFile(e.id, WitnessFileRole.TASK))
        for key, value in e.assign:
            if not assignable(solver, key):
                yield Fault(ProblemKind.ASSIGN_NAMES_NOTHING,
                            InWitnessFile(e.id, WitnessFileRole.TASK),
                            Named(key))
            if isinstance(value, AssignRows):
                for s in unknown_strings(solver, value.rows):
                    yield Fault(ProblemKind.ASSIGN_VALUE_UNKNOWN,
                                InWitnessFile(e.id, WitnessFileRole.TASK),
                                Named(s))


# The solver's cases


def run_empty(engine: Engine, program: Program, outputs: list[RelationName],
              limits: Limits) -> RunResult:
    """`outputs` of a run of `program` on the empty input."""
    return engine.run(program, {INPUT: ()}, outputs, limits)


def enumerated(engine: Engine, program: Program, limits: Limits
               ) -> tuple[Base, ...] | RunFailure:
    """The bases `impl_choice` holds on a run of `program` on the empty
    input, in the order the run gives them; the run's failure where it
    fails."""
    got = run_empty(engine, program, [IMPL], limits)
    if not isinstance(got, Tuples):
        return got
    return tuple(r[0] for r in got.relations[IMPL]
                 if len(r) == 1 and isinstance(r[0], AdtValue | RecordValue))


def own_top[D: RelationDecl | Component | TypeDecl](
        parts: tuple[D, ...], name: str) -> D | None:
    """The part of `parts` named `name` that the solver's own text
    declares at the top level; None where none is."""
    return next((x for x in parts
                 if x.name == name and x.scope == TOP and own(x.span)), None)


def enumerates(program: Program) -> bool:
    """Whether the solver's own text declares `impl_choice` at the top
    level (solver-file.md, under "Cases")."""
    return own_top(program.relations, ENUMERATOR) is not None


def takes(solver: Solver, case: Case, branch: Branch) -> bool:
    """Whether `case` takes `branch`: a `@derive` or `@store` branch it
    lists, or `<param>=stored` where it lists no `@derive` branch of the
    parameter."""
    if isinstance(branch, StoredAtDerive):
        return branch.parameter not in derived_parameters(case.branches)
    return branch in case.branches


def branch_under(solver: Solver, line: IgnoreLine) -> Branch | None:
    """The branch of the `@derive` or `@store` line a named `@ignore: derive`
    or `@ignore: store` line stands under: the nearest line of its kind above
    it on the same declaration (solver-file.md, under "Params" and
    "Program")."""
    found: tuple[int, DeriveBranch | StoreBranch] | None = None
    for b in solver.branches:
        if isinstance(b, StoredAtDerive) or b.line is None \
                or line.above is None or b.line.above != line.above \
                or b.line.line > line.line:
            continue
        if (line.form is IgnoreForm.DERIVE) != isinstance(b, DeriveBranch):
            continue
        if found is None or b.line.line > found[0]:
            found = (b.line.line, b)
    return None if found is None else found[1]


def has_determine(solver: Solver) -> bool:
    """Whether the solver's own file declares the top-level `Determine` comp
    that holds its determination (solver-file.md, under "Determination")."""
    return own_top(solver.program.components, DETERMINE) is not None


def is_concept(solver: Solver, base: Base | None) -> bool:
    """Whether `base` is the concept case's: the first constructor at each
    point it reaches (solver-file.md, under "Witness file"; principles.md,
    "concept branch")."""
    choice = solver.choice
    if choice is None or base is None:
        return base is None
    return all(non_concept_at(choice, base, p) is None for p in choice.points)


def parameter(solver: Solver, name: str) -> RelationName:
    """A parameter as the program reads it, `params.<rel>`
    (solver-file.md, under "Params")."""
    inst = instance_of(solver.program, PARAMS)
    if inst is None:
        raise ValueError(f"{solver.stem}: no instance of `Params`")
    return RelationName((inst.name,), name)


@quotes("solver-file.md", "Params",
        "**Case column.** Where the cases that read a relation in Params "
        "store different values of it, the relation takes a case column in "
        "the form of `out`'s, and each fact's case column is the `Choice` "
        "value of the case that stores the fact.")
def parameter_case_columns(types: Sequence[str]) -> tuple[int, ...]:
    """The case columns of a parameter of column types `types`, as the
    model resolves them (`column_types`): its columns of type `Choice`,
    each fact's `Choice` value there being the case that stores the
    fact."""
    # A case column is keyed by the whole `Choice` value; keying it by one
    # branch in its place is deferred.
    return tuple(i for i, t in enumerate(types) if t == CHOICE)


def parameter_columns(solver: Solver, name: str) -> "ColumnTypes":
    """The column types of the parameter `name` as the program reads it
    (`parameter`, `column_reading`)."""
    return column_reading(solver.engine, solver.program,
                          parameter(solver, name))


def is_concept_case(solver: Solver, case: Case) -> bool:
    """Whether `case` is the concept case: the base case (`base_case`) of
    the concept case's base (`is_concept`) (principles.md, under "The
    concept")."""
    return case.is_base_case and is_concept(solver, case.base)


@dataclass(frozen=True)
class ColumnTypes:
    """A relation's column types: `types`, each as the model resolves it
    (`Graph.resolve_type`), which every comparison of types reads; and
    `written`, each as the declaration writes it, which a report prints."""

    written: tuple[str, ...]
    types: tuple[str, ...]


_COLUMN_READINGS: ByIdentity[Program, dict[RelationName, ColumnTypes]] \
    = ByIdentity()
"""`column_reading`'s results, for each program while it lives: a
parameter's value is written into a group's program on every input."""


def column_reading(engine: Engine, program: Program, relation: RelationName
                   ) -> ColumnTypes:
    """The column types of `relation`, named from the top level
    (`ColumnTypes`), so that a type the solver's own text declares in a
    component is not a top-level type of the same name. Raises
    `ValueError` where the model resolves no declaration of the
    relation. Computed once per program and relation while the program
    lives."""
    return _COLUMN_READINGS.keyed(
        program, relation, lambda: _column_reading(engine, program, relation))


def _column_reading(engine: Engine, program: Program, relation: RelationName
                    ) -> ColumnTypes:
    """`column_reading`, computed."""
    graph = Graph(program, engine)
    got = graph.column_types((), relation)
    if got is None:
        raise unresolved(relation)
    decl = _declaration(graph, relation)
    return ColumnTypes(tuple(c.type for c in decl.columns), tuple(got))


def column_names(engine: Engine, program: Program, relation: RelationName
                 ) -> tuple[str, ...]:
    """The name of each column of `relation`, named from the top level, in
    its declaration. Raises `ValueError` where the model resolves no
    declaration of the relation."""
    return tuple(c.name for c in
                 _declaration(Graph(program, engine), relation).columns)


def _declaration(graph: Graph, relation: RelationName) -> RelationDecl:
    """The declaration of `relation`, named from the top level, that the
    model resolves. Raises `ValueError` where it resolves none."""
    got = graph.decl((), relation)
    if got is None:
        raise unresolved(relation)
    return got[0]


def column_types(engine: Engine, program: Program, relation: RelationName
                 ) -> tuple[str, ...]:
    """The type of each column of `relation` as the model resolves it
    (`column_reading`)."""
    return column_reading(engine, program, relation).types


def ident_keyed(engine: Engine, program: Program, relation: RelationName
                ) -> bool:
    """Whether the relation, named from the top level, has a column whose
    type, as the model resolves it (`Graph.column_types`), is `Ident`, or
    a type that is `Ident` by an alias or a subtype, each link resolved in
    the scope that declares it. The program assigns an `Ident` as an
    ordinal in each run, so a stored row of the relation names no object in
    another run. A relation the model resolves to no
    declaration it reads, which `load` reports as a fault, has no column
    the model reads."""
    graph = Graph(program, engine)
    types = graph.column_types((), relation)
    if types is None:
        return False
    links = {k: graph.link(t) for k, t in graph.type_decls.items()
             if isinstance(t, AliasType | SubtypeType)}
    return any(IDENT in followed(links, t) for t in types)


# Reading an `assign` argument


@dataclass(frozen=True)
class ArgUnknown:
    """An `assign` string that names no lib constant and, with its `$`
    prefix, no constructor with no arguments of a type the program
    declares."""

    text: str


@dataclass(frozen=True)
class ArgOffType:
    """An `assign` argument whose value is no value of `type`."""

    type: str


type ArgOff = ArgUnknown | ArgOffType


@quotes("solver-file.md", "Witness file",
        "Use a string for a lib constant and a list for a record. Write a "
        "constructor with no arguments as a string, such as "
        "`\"$Anchor\"`.")
def arg_value(solver: Solver, arg: AssignArg, type: str
              ) -> Value | ArgOff:
    """An `assign` argument as a value (`_arg_read`), which must be a value
    of `type`, a column type as `column_types` names it, a type parameter
    read as the type the instance gives it (`engine.program.typed_value`).
    Raises ValueError for a type name that resolves to no declaration
    (`_types`)."""
    value = _arg_read(solver, arg, _nullary_constructors(solver.program))
    if isinstance(value, ArgUnknown):
        return value
    fits = typed_value(value, type, _as_named,
                       _types(solver.engine, solver.program),
                       _VALUES) is not None
    return value if fits else ArgOffType(type)


def _arg_read(solver: Solver, arg: AssignArg, ctors: frozenset[str]
              ) -> Value | ArgUnknown:
    """An `assign` argument as a value: a number; a string with the
    constructor prefix as the constructor of `ctors` of that name, any
    other string as the lib constant it names; a list as a record of
    such."""
    if isinstance(arg, tuple):
        fields: list[Value] = []
        for f in arg:
            v = _arg_read(solver, f, ctors)
            if isinstance(v, ArgUnknown):
                return v
            fields.append(v)
        return RecordValue(tuple(fields))
    if isinstance(arg, int):
        return arg
    if (name := prefixed(arg)) is not None:
        return AdtValue(name, ()) if name in ctors else ArgUnknown(arg)
    got = solver.lib.constants.get(arg)
    return ArgUnknown(arg) if got is None else got


def unknown_strings(solver: Solver, args: Sequence[AssignArg]
                    ) -> Iterator[str]:
    """Each string among `assign` arguments, records opened, that names
    nothing (`_arg_read`), in order."""
    ctors = _nullary_constructors(solver.program)
    for a in args:
        if isinstance(a, tuple):
            yield from unknown_strings(solver, a)
        elif isinstance(a, str) \
                and isinstance(_arg_read(solver, a, ctors), ArgUnknown):
            yield a


def _nullary_constructors(program: Program) -> frozenset[str]:
    """The constructors with no arguments of the types the program
    declares, its lib's among them."""
    return frozenset(c.name for t in program.types if isinstance(t, AdtType)
                     for c in t.constructors if not c.fields)


type _Scope = Callable[[str], str]
"""The reading of a type name in the scope that declares the type it is
read in, as `column_types` names a type."""


def _types(engine: Engine, program: Program) -> TypeReading[_Scope]:
    """The reading of a type name, as `column_types` names a type: each
    type the program declares by its key (`Graph.type_decls`), with the
    reading of a name in the scope that declares it. Raises ValueError for
    a name that is neither a primitive nor such a key."""
    graph = Graph(program, engine)

    def read(name: str, scope: _Scope) -> tuple[TypeDecl | Primitive, _Scope]:
        key = scope(name)
        if (primitive := Primitive.named(key)) is not None:
            return primitive, scope
        t = graph.type_decls.get(key)
        if t is None:
            raise ValueError(f"type `{key}` resolves to no declaration")
        own_scope = t.scope.components
        return t, ((lambda n: graph.resolve_type(n, own_scope))
                   if own(t.span) else _as_named)

    return read


def _as_named(name: str) -> str:
    return name


_VALUES = ValueReading[Value](
    primitive=lambda v, kind: v if isinstance(v, kind.values)
    and not isinstance(v, bool) else None,
    record=lambda v: v.fields if isinstance(v, RecordValue) else None,
    constructor=lambda v: (v.constructor, v.args)
    if isinstance(v, AdtValue) else None)
"""A value as the value it is."""


