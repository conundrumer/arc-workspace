"""The model of a solver as the handbook defines it: its case type, its
branches and cases, its parameters, the lib as the model reads it, and the
aggregate `Solver`; and the functions that build each part from a parsed
program, which `solver.load` and the checks read as well."""

from enum import Enum, auto
from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field, fields, is_dataclass, replace
from itertools import product
from pathlib import Path
from typing import Annotated

from arc.task import Task
from engine import checkout
from engine.engine import unresolved
from engine.memo import ByIdentity, Once, Recent
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
    UnitId,
    Value,
)
from engine.program import (
    Aggregate,
    BinaryTerm,
    BodyLiteral,
    Cast,
    Disjunction,
    FunctorCall,
    IntrinsicCall,
    UnaryTerm,
    MemberCell,
    Primitive,
    first_line,
    term_value,
    typed_value,
    TypeReading,
    ValueReading,
    dotted,
    body_atoms,
    enclosing,
    own,
    AdtType,
    AliasType,
    Atom,
    AtomLiteral,
    Component,
    Column,
    Comparison,
    ComparisonOperator,
    ConstructorTerm,
    DefinedName,
    GridCall,
    Instance,
    RigidCall,
    RecordTerm,
    RecordType,
    RelationDecl,
    SubtypeType,
    Term,
    TypeDecl,
    TypeField,
    Unit,
    Variable,
    Wildcard,
    term_of,
    with_literal_terms,
    with_subterms,
)
from engine.quotes import quotes
from engine.text import prefixed
from solver import witness as witness_reader
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
    CaseColumnOffForm,
    OffFormType,
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
    OUTPUT,
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


def followed(links: Mapping[str, str], name: str) -> list[str]:
    """`name`, then the type each link names in turn, each once: a type
    name followed through aliases (or subtypes) to the end of its chain,
    or to the first name met again."""
    out = [name]
    while name in links and links[name] not in out:
        name = links[name]
        out.append(name)
    return out


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


def _listing(solver: Solver) -> dict[int, bool]:
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
    listing = _listing(solver)
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


def component_chain(components: Mapping[str, Component], name: str | None
                    ) -> list[str | None]:
    """A component and each component it extends, in turn, a base that
    `components` lacks last; `[None]` for the top level."""
    out: list[str | None] = [name]
    while name is not None:
        c = components.get(name)
        name = None if c is None or c.base in out else c.base
        if name is not None:
            out.append(name)
    return out


def _chain(program: Program, component: str) -> list[str]:
    """The component and the components it extends, in order."""
    return [n for n in component_chain(
        {c.name: c for c in program.components}, component) if n is not None]


def by_innermost[D: (Instance, RelationDecl)](decls: Sequence[D]
                                              ) -> dict[str | None, dict[str, D]]:
    """Declarations by the innermost component that declares them, None
    for the top level, then by name."""
    out: dict[str | None, dict[str, D]] = {}
    for d in decls:
        out.setdefault(d.scope.components[-1] if d.scope.components
                       else None, {})[d.name] = d
    return out


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


MAX_DEPTH = 8
"""How many instances deep an instance path the model follows goes."""


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


# Dependence


@dataclass(frozen=True)
class Dependence:
    """Which of a list of bases have a derivation of `out` that depends on
    each part of the solver's own text, each in the list's order
    (`dependence`). The units stand in the program's order, the relations
    of `Params` in the order `Params` declares them, and the other
    relations in the order of their names' text."""

    units: Mapping[UnitId, tuple[Base | None, ...]]
    """Each unit a base's derivation of `out` depends on."""
    parameters: Mapping[str, tuple[Base | None, ...]]
    """Each relation of `Params` by name: a parameter, or a relation that
    clauses feed."""
    relations: Mapping[RelationName, tuple[Base | None, ...]]
    """Each relation that a unit the derivation depends on reads or
    feeds, by the name a top-level clause reads it by: `in`,
    `params.<p>`, `<instance>.<relation>`."""
    stranded: Mapping[tuple[UnitId, "Node"], tuple[Base | None, ...]] = field(
        default_factory=dict[tuple[UnitId, "Node"], tuple[Base | None, ...]])
    """Each unit a base's walk reads that stands under a marker that does
    not list the base, with the relation the unit feeds: as a top-level
    clause names it, or the instance of a lib component by its path.
    `checker` gives the marker of each a hint of the case-section
    category, which fails no command."""

    def reads_parameter(self, base: Base | None, name: str) -> bool:
        """Whether `base` has a derivation of `out` that depends on the
        relation of `Params` `name` (`parameters`); a name absent there is
        one no base reads."""
        return base in self.parameters.get(name, ())


def dependent_bases(rd: Dependence, units: Iterable[UnitId]
                    ) -> frozenset[Base | None]:
    """The bases whose derivation of `out` depends on any of `units`
    (`Dependence.units`)."""
    return frozenset(b for u in units for b in rd.units.get(u, ()))


DEPENDENCE_HELD = 32
"""The most results of `dependence` one process holds."""

_DEPENDENCE: Recent[tuple[tuple[int, ...], tuple[Base | None, ...]],
                    tuple[tuple[object, ...], Dependence]] \
    = Recent(DEPENDENCE_HELD)
"""`dependence`'s results by the identities of the parts it reads, each
with those parts, which it keeps alive while it holds the result."""
_DEPENDENCE_ONCE: Once[tuple[tuple[int, ...], tuple[Base | None, ...]],
                      tuple[tuple[object, ...], Dependence]] \
    = Once(_DEPENDENCE)


def dependence(engine: Engine, solver: Solver, bases: Sequence[Base | None]
               ) -> Dependence:
    """Which of `bases` have a derivation of `out` that depends on each
    unit, parameter and relation of the solver's own text
    (solver-file.md, under "Cases", "Params" and "Program").

    The result is a function of the solver's model, its case markers
    among its annotations, the program's declarations, its GRID and RIGID
    calls and the units of the solver's own text, whose rows are the rows
    the walk reads; a unit an operation wrote (`own`) is none of them. So
    it is computed once for each distinct such input, by the identity of
    those parts: a variation that fixes a parameter's value removes the
    same own units whatever the value, and a deletion removes its own.

    The walk reads the program as it runs, its GRID and RIGID calls
    expanded (`Engine.expand`), so that a unit in a RIGID block is read
    through the rules that place its chart; the units, parameters and
    stranded units it reports are those of the solver's program.

    A unit of a component runs at each instance of the component, and a
    relation of a component is one relation per instance (`Graph`). A base's
    model reads its grids from `out` at its case, so its derivation depends on
    each unit that heads `out` and admits it, and, from each unit it depends
    on, on each unit that heads a relation that unit reads and admits it. A
    unit whose head has a case column, a column of `Choice` (the case column
    `ch`, solver-file.md, under "Cases"), of a type that stands in `Choice`, or
    of a record type with a field of such a type, admits a base when the base's
    value can stand in each term the head holds there, whatever carries the
    value there (`_Cases`). A unit whose head has none admits every base,
    whatever section it stands in, since the program runs it for every case.
    Either unit admits only the bases whose value can stand in the term of an
    `impl_choice` atom of its body. A read asks for the rows its terms fix:
    where a read holds a constant constructor in a column of a type that stands
    at one choice point, or a constant `Choice` value, it asks for the rows
    that hold that value there, whatever the base holds, and the units it
    reaches are read for the base with that value at that point
    (`_Cases.demand`); so `near_arm($Clear(), P, D) :- near_arm($Any(), P, D)`
    reads the `$Any()` clauses for a base that takes `$Clear`. A read is at
    every value at each case-typed place where it holds a wildcard, or a
    variable that no case variable of the unit's head fills: there, a unit
    that heads its relation admits the base whatever term it holds. At the
    read's other case-typed places, the base's value still bounds which units
    the read reaches (`_Cases.bounded`), so `crowded(A, Id, Ch)` in a clause
    whose head fills `Ch` and not `A` reaches only the clauses whose head can
    hold the base's value in the column of `Ch`. A read of a
    relation of an instance of a lib component reads every unit that feeds the
    instance. A base's derivation depends on a parameter where it depends on a
    unit that reads it, and on a relation where it depends on a unit that reads
    it or a unit that feeds it. A unit the walk reads for a base that stands
    under a marker that does not list the base (`section_at`, solver-file.md,
    under "Cases") is reported with the base (`Dependence.stranded`)."""
    program = solver.program
    held: tuple[object, ...] = (
        solver.stem, solver.task_id, solver.annotations.markers, solver.choice,
        solver.branches, solver.params, solver.witness_file, solver.task,
        solver.lib, solver.problems, program.types, program.relations,
        program.components, program.instances, program.functors,
        program.comments, program.includes, program.defines,
        program.macros, *(u for u in program.units if own(u.span)))
    key = (tuple(map(id, held)), tuple(bases))

    def make() -> tuple[tuple[object, ...], Dependence]:
        got = (held, _dependence(engine, engine.expand(program), solver,
                                 bases))
        _DEPENDENCE.put(key, got)
        return got

    return _DEPENDENCE_ONCE.get(key, make)[1]


type _Wanted = tuple[Base | None, tuple[CasePlace, ...] | None]
"""What a read asks for in `dependence`'s walk: the base whose value the
reached units hold, and the case-typed places of the read at which that
value bounds them, where the read is at every value at some other place
(`_Cases.bounded`); None where it is at every value at none."""


def _dependence(engine: Engine, expanded: Program, solver: Solver,
                bases: Sequence[Base | None]) -> Dependence:
    """`dependence`, computed over `expanded`, the solver's program with
    its GRID and RIGID calls expanded."""
    from solver.names import marker_lists

    graph = Graph(expanded, engine)
    cases = _Cases(graph, solver.choice)
    section_at = _sections(solver)
    listing = _listing(solver)
    marker_of: dict[UnitId, CaseMarker | None] = {}
    columns_of: dict[Placed, dict[int, tuple[str, Term]]] = {}
    impl_of: dict[Placed, list[Term]] = {}
    for u in graph.units:
        assert u.span is not None, "a unit of the solver's own text"
        section = section_at(u.scope, u.span.first)
        for at in graph.paths_of(u):
            columns_of[(u, at)], impl_of[(u, at)] = cases.checks(u, at)
        marker_of[u.id] = section.marker if isinstance(
            section, UnderMarker) and listing[section.marker.line] else None
    markers = sorted({m.line: m for m in marker_of.values()
                      if m is not None}.values(), key=lambda m: m.line)
    by_unit: dict[UnitId, list[Base | None]] = {}
    by_param: dict[str, list[Base | None]] = {}
    by_relation: dict[RelationName, list[Base | None]] = {}
    by_stranded: dict[tuple[UnitId, Node], list[Base | None]] = {}
    held: dict[tuple[int, tuple[CasePlace, ...] | None], _Wanted] = {}

    def wanted(base: Base | None, bounded: tuple[CasePlace, ...] | None
               ) -> _Wanted:
        """What a read asks for, one object per base and bounded places,
        as `Graph.read` keys a request by its identity."""
        got = held.get((id(base), bounded))
        if got is None or got[0] is not base:
            got = held[(id(base), bounded)] = (base, bounded)
        return got

    def demand(placed: Placed, atom: Atom, asked: _Wanted) -> _Wanted:
        return wanted(cases.demand(placed, atom, asked[0]),
                      cases.bounded(placed, atom))

    for base in bases:
        listed = {m.line: marker_lists(solver, m, base) for m in markers}

        def admits(placed: Placed, wanted: _Wanted) -> bool:
            base, bounded = wanted
            columns = columns_of[placed]
            return all(cases.admits(placed, CHOICE, term, (), base)
                       for term in impl_of[placed]) and (
                all(cases.admits(placed, t, term, (), base)
                    for t, term in columns.values())
                if bounded is None else
                all(cases.admits(placed, t, columns[i][1], path, base)
                    for i, path, t in bounded))

        def unlisted(placed: Placed,
                     listed: Mapping[int, bool] = listed) -> bool:
            m = marker_of[placed[0].id]
            return m is not None and not listed[m.line]

        units, nodes, names, stranded = graph.read(
            admits, wanted(base, None), demand, unlisted)
        for key in stranded:
            by_stranded.setdefault(key, []).append(base)
        for uid in units:
            by_unit.setdefault(uid, []).append(base)
        for n in nodes:
            if n.kind is NodeKind.RELATION \
                    and graph.component_at(n.path) == PARAMS:
                by_param.setdefault(n.name, []).append(base)
        for rel in names:
            by_relation.setdefault(rel, []).append(base)
    params = [r.name for r in solver.program.relations
              if r.scope == PARAMS_SCOPE]
    written = frozenset(u.id for u in solver.program.units)
    return Dependence(
        {u.id: tuple(by_unit[u.id]) for u in graph.units
         if u.id in by_unit and u.id in written},
        {p: tuple(by_param[p]) for p in params if p in by_param},
        {r: tuple(by_relation[r])
         for r in sorted(by_relation, key=lambda r: (r.instances, r.name))},
        {k: tuple(by_stranded[k]) for k in sorted(
            by_stranded, key=lambda k: (k[0].index, k[1].path, k[1].name))
         if k[0] in written})


class NodeKind(Enum):
    """What a node of `dependence`' reads stands for."""

    RELATION = auto()
    """A relation of the solver's own text or the lib's top level, at the
    instance path it stands at."""
    INSTANCE = auto()
    """An instance of a lib component, by its instance path, which stands
    for every relation of the instance."""


type InstancePath = tuple[str, ...]
"""The instances a top-level clause names a relation through, outermost
first: `()` for the top level, `("parse", "box")` for `parse.box`."""


@dataclass(frozen=True)
class Node:
    """A relation as the reads of `dependence` follow it (`NodeKind`): its
    instance path, and its name, empty for an instance of a lib
    component."""

    kind: NodeKind
    path: InstancePath
    name: str

    @property
    def text(self) -> str:
        """The relation as a top-level clause names it, or the instance of
        a lib component by its path."""
        return dotted(self.path) if self.kind is NodeKind.INSTANCE \
            else RelationName(self.path, self.name).text

    def __hash__(self) -> int:
        # Held after the first call: the walks of `dependence` key their
        # tables by node.
        h = self.__dict__.get("_hash")
        if h is None:
            h = hash((self.kind, self.path, self.name))
            object.__setattr__(self, "_hash", h)
        return h


type Placed = tuple[Unit, InstancePath]
"""A unit of the solver's own text at an instance path it runs at."""


type CasePlace = tuple[int, tuple[int, ...], str]
"""A case-typed place of an atom's terms (`_Cases`): its column, the
record fields that lead to it in that column, and its type."""


@dataclass(frozen=True)
class CaseTypes:
    """The types whose values carry a case (`_Cases`): `Choice`, each
    type that stands in it, and each record type of the solver's own text
    with a field of such a type; with each record type's field types, and
    the type of each choice point as the model resolves it, by its path."""

    types: frozenset[str]
    records: Mapping[str, tuple[str, ...]]
    points: Mapping[tuple[str, ...], str]

    def at(self, choice: Choice, type: str) -> list[ChoicePoint]:
        """The points of `choice` of `type`, as the model resolves it."""
        return [p for p in choice.points if self.points[p.path] == type]

    def fields(self, type: str) -> tuple[str, ...] | None:
        """The types of the fields a value of `type` opens into: those of
        `term_fields`, but none for `Choice`, which a value is compared
        with whole, as the base."""
        return None if type == CHOICE else self.term_fields(type)

    def term_fields(self, type: str) -> tuple[str, ...] | None:
        """The types of the fields a term of `type` in the program opens
        into; None where it is no record. A record `Choice` opens, since a
        term builds the base field by field."""
        return self.records.get(type)

    def leaves(self, type: str, value: Value) -> list[tuple[str, Value]]:
        """The values at the case-typed places of a value of `type`, each
        with its type: a record of a case type opened by its fields'
        types (`fields`)."""
        if type not in self.types:
            return []
        fields = self.fields(type)
        if fields is None \
                or not isinstance(value, RecordValue) \
                or len(fields) != len(value.fields):
            return [(type, value)]
        return [x for f, v in zip(fields, value.fields, strict=True)
                for x in self.leaves(f, v)]

    def whole(self, type: str) -> bool:
        """Whether every place of a value of `type` carries the case:
        `Choice`, a type that stands in it, or a record type whose fields
        are each of such a type."""
        if type not in self.types:
            return False
        fields = self.fields(type)
        return fields is None or all(self.whole(f) for f in fields)

    def kept(self, type: str) -> tuple[int, ...] | None:
        """For a record type with a field of a case type and a field of
        another (`whole`), the places of the fields that are not wholly of
        the case, in order; None for any other type."""
        fields = self.fields(type)
        if type not in self.types or fields is None or self.whole(type):
            return None
        return tuple(i for i, f in enumerate(fields) if not self.whole(f))


def case_types(solver: Solver) -> CaseTypes:
    """The solver's case types, as `dependence` reads them, the types
    named as `column_types` resolves them; computed once per program and
    `Choice` while the program lives."""
    program, choice = solver.program, solver.choice

    def make() -> CaseTypes:
        return _Cases(Graph(program, solver.engine), choice).types

    return _CASE_TYPES.guarded(program, choice, make)


_CASE_TYPES: ByIdentity[Program, tuple[Choice | None, CaseTypes]] \
    = ByIdentity()


class Graph:
    """The relations of the solver as its units read them at each instance
    (`dependence`, and the store check's relations between `in` and `out`
    and its stored-already test): the units of the solver's own text at the
    instance paths they run
    at, by the relation each heads, and the resolution of a relation a
    unit reads (`dependence`). A unit of the top level runs at `()`; a unit
    of a component, at each instance path of the component or of a
    component that extends it. A name resolves at the unit's path, then
    at each path around it, outermost last, as Souffle resolves a name
    inside an instance. An instance of a component that no included file
    declares resolves to nothing, a path deeper than `MAX_DEPTH` is not
    followed, a base no file declares ends a component's chain, and type
    arguments pair with type parameters as far as both go: each is a
    fault of `load` (`instance_faults`)."""

    def __init__(self, program: Program, engine: Engine) -> None:
        self.program = program
        self.index = engine.index(program)
        self.components = {c.name: c for c in program.components}
        self.relations = by_innermost(program.relations)
        self.instances = by_innermost(program.instances)
        self.args: dict[InstancePath, dict[str, str]] = {(): {}}
        self.comp: dict[InstancePath, str] = {}
        self.inst_scope: dict[InstancePath, tuple[str, ...]] = {}
        """The scope whose text declares the instance at each path."""
        self.type_decls: dict[str, TypeDecl] = {}
        """Each type the program declares by its key (`key_of`). Souffle
        takes one declaration of a name in a scope, so a key has one
        declaration."""
        for t in program.types:
            self.type_decls.setdefault(self.key_of(t), t)
        self.aliases: dict[str, str] = {
            k: self.link(t) for k, t in self.type_decls.items()
            if isinstance(t, AliasType)}
        """Each alias by its type key, with the type key its target names
        (`link`)."""
        for at, path, inst, comp in self._instance_tree(False):
            self.comp[path] = comp.name
            self.inst_scope[path] = inst.scope.components
            self.args[path] = self._chain_args(
                comp, {p: self.args[at].get(a, a) for p, a in zip(
                    comp.type_params, inst.type_args, strict=False)})
        self.units = [u for u in program.units if own(u.span)]
        self._full: dict[InstancePath, str] | None = None
        self._reach: frozenset[RelationName] | None = None
        self._feeds: dict[RelationName, list[tuple[Unit, InstancePath]]] \
            | None = None
        self.heads: dict[Node, list[Placed]] = {}
        for u in self.units:
            for at in self.paths_of(u):
                node = self.resolve(at, u.head.relation)
                if node is not None:
                    self.heads.setdefault(node, []).append((u, at))

    def component_at(self, path: InstancePath) -> str | None:
        """The component of the instance at `path`, a path of the instance
        tree; None for the top level."""
        return self.comp[path] if path else None

    def _chain(self, comp: str | None) -> list[str | None]:
        """A component and each component it extends, in turn
        (`component_chain`)."""
        return component_chain(self.components, comp)

    def _instance_tree(self, lib: bool
                       ) -> Iterator[tuple[InstancePath, InstancePath,
                                           Instance, Component]]:
        """Each instance path, breadth first from the top level, with the
        path it stands in, its instance and the instance's component: the
        instances the solver's own components hold, and where `lib` holds,
        those the lib's components hold too. A path deeper than
        `MAX_DEPTH` is not followed, and an instance of a component no
        file declares is left out."""
        comps: dict[InstancePath, str] = {}
        front: list[InstancePath] = [()]
        while front:
            at = front.pop(0)
            if len(at) > MAX_DEPTH:
                continue
            here = comps.get(at) if at else None
            for name in self._instance_names(here):
                inst = self._instance(here, name)
                comp = None if inst is None \
                    else self.components.get(inst.component)
                if inst is None or comp is None:
                    continue
                path = (*at, name)
                comps[path] = comp.name
                yield at, path, inst, comp
                if lib or own(comp.span):
                    front.append(path)

    def _paths_in(self, comps: Mapping[InstancePath, str], unit: Unit
                  ) -> list[InstancePath]:
        """The paths of `comps`, an instance tree, a unit runs at: the top
        level for a unit of the top level, else each path whose component
        is the unit's or extends it."""
        if not unit.scope.components:
            return [()]
        comp = unit.scope.components[-1]
        return [p for p, c in comps.items() if comp in self._chain(c)]

    def _locate(self, comps: Mapping[InstancePath, str], at: InstancePath,
                rel: RelationName, stop_at_lib: bool
                ) -> tuple[InstancePath, Instance | None] | None:
        """The instance path `rel`'s qualifiers lead to from `at` in
        `comps`, an instance tree, each qualifier resolving at the path
        around it, innermost first; where `stop_at_lib` holds, they stop
        at the first instance of a lib component, which is given. None
        where a qualifier names no instance."""
        for name in rel.instances:
            found = next((q for q in enclosing(at)
                          if self._instance(comps.get(q) if q else None, name)
                          is not None), None)
            if found is None:
                return None
            at = (*found, name)
            if at not in comps:
                return None
            if stop_at_lib and not own(self.components[comps[at]].span):
                return at, self._instance(comps.get(found) if found else None,
                                          name)
        return at, None

    def _declaring(self, comps: Mapping[InstancePath, str],
                   path: InstancePath, name: str) -> InstancePath | None:
        """The innermost path at or around `path` in `comps` whose
        component declares the relation `name`."""
        return next((q for q in enclosing(path)
                     if self._relation(comps.get(q) if q else None, name)
                     is not None), None)

    def _chain_args(self, comp: Component, args: dict[str, str]
                    ) -> dict[str, str]:
        """The type arguments of an instance of `comp` by type parameter,
        those of each component it extends included."""
        out = dict(args)
        seen = {comp.name}
        while comp.base is not None and comp.base not in seen:
            base = self.components.get(comp.base)
            if base is None:
                break
            out |= {p: out.get(a, a) for p, a in zip(
                base.type_params, comp.base_type_args, strict=False)}
            comp = base
            seen.add(comp.name)
        return out

    def _instance_names(self, comp: str | None) -> list[str]:
        return [n for c in self._chain(comp)
                for n in self.instances.get(c, {})]

    def _instance(self, comp: str | None, name: str) -> Instance | None:
        return next((self.instances[c][name] for c in self._chain(comp)
                     if name in self.instances.get(c, {})), None)

    def _relation(self, comp: str | None, name: str) -> RelationDecl | None:
        return next((self.relations[c][name] for c in self._chain(comp)
                     if name in self.relations.get(c, {})), None)

    def paths_of(self, unit: Unit) -> list[InstancePath]:
        """The instance paths a unit runs at, in the order of the
        instances."""
        if not unit.scope.components:
            return [()]
        return [p for p in self._paths_in(self.comp, unit)
                if own(self.components[self.comp[p]].span)]

    def resolve(self, at: InstancePath, rel: RelationName) -> Node | None:
        """The node a unit at `at` reads or heads by the name `rel`; None
        where no declaration gives it."""
        got = self._locate(self.comp, at, rel, True)
        if got is None:
            return None
        path, lib = got
        if lib is not None:
            return Node(NodeKind.INSTANCE, path, "")
        q = self._declaring(self.comp, path, rel.name)
        return None if q is None else Node(NodeKind.RELATION, q, rel.name)

    def decl(self, at: InstancePath, rel: RelationName
             ) -> tuple[RelationDecl, Mapping[str, str]] | None:
        """The declaration of the relation a unit at `at` names by `rel`,
        with the type arguments in force there by type parameter; None
        where it is no declaration the solver can read."""
        node = self.resolve(at, rel)
        if node is None:
            return None
        if node.kind is NodeKind.RELATION:
            d = self._relation(self.component_at(node.path), rel.name)
            return None if d is None else (d, self.args[node.path])
        d = self._relation(self.comp[node.path], rel.name)
        return None if d is None else (d, self.args[node.path])

    def column_types(self, at: InstancePath, rel: RelationName
                     ) -> list[str] | None:
        """The type of each column of the relation a unit at `at` names by
        `rel`, as `key_of` names it: a column's own type resolved in the
        scope that declares the relation, a type parameter's argument in
        the scope that declares the instance; None where it is no
        declaration the solver can read."""
        node = self.resolve(at, rel)
        got = self.decl(at, rel)
        if node is None or got is None:
            return None
        decl, args = got
        held = self.inst_scope[node.path] if node.path else ()
        return [self.resolve_type(args[c.type], held) if c.type in args
                else self.resolve_type(c.type, decl.scope.components)
                for c in decl.columns]

    def key_of(self, t: TypeDecl) -> str:
        """A type declaration's key: for a type of the solver's own text,
        the components of the scope that declares it and its name joined
        by dots, so that two components that declare one name name two
        types; for a lib type, its name."""
        return dotted((*t.scope.components, t.name)) if own(t.span) \
            else t.name

    def resolve_type(self, name: str, scope: tuple[str, ...]) -> str:
        """The type `name` denotes when read in `scope` (`scoped_key`), then
        each alias followed to the type it names (`aliases`). The one
        reading of a type that a comparison of types reads. Every type the
        model reads, a component's record among them, resolves through
        the engine's index of the program in the scope that reads it
        (`Index.type_decl`), never by its bare name."""
        return followed(self.aliases, self.scoped_key(name, scope))[-1]

    def link(self, t: AliasType | SubtypeType) -> str:
        """The type key an alias's target or a subtype's base names, read
        in the scope that declares the alias or subtype (`scoped_key`)."""
        target = t.target if isinstance(t, AliasType) else t.base
        return self.scoped_key(target, t.scope.components)

    def scoped_key(self, name: str, scope: tuple[str, ...]) -> str:
        """The key (`key_of`) of the type declaration `name` denotes when
        read in the text of `scope` (`Index.type_decl`); the name itself
        where it denotes none, as for a primitive type or a component's
        type parameter."""
        t = self.index.type_decl(name, Scope(scope))
        return name if t is None else self.key_of(t)

    def read[D](self, admits: Callable[[Placed, D], bool], start: D,
                demand: Callable[[Placed, Atom, D], D],
                unlisted: Callable[[Placed], bool] | None = None
                ) -> tuple[list[UnitId], list[Node], set[RelationName],
                           list[tuple[UnitId, Node]]]:
        """What one base's derivation depends on (`dependence`): the
        units, the nodes, and the relations by the names a top-level clause
        reads them by. A read asks for rows of what it demands, `start` at
        `out`: `demand` gives what a unit's read of an atom asks for,
        from what the unit was reached for, and `admits` tells the placed
        units whose head can hold such a row. Last, each admitted unit
        that `unlisted` names, with the node it feeds: the relation as a
        top-level clause names it, or an instance of a lib component by
        its path."""
        units: dict[UnitId, None] = {}
        placed: set[tuple[UnitId, InstancePath, int]] = set()
        nodes: dict[Node, None] = {}
        names: set[RelationName] = set()
        front: list[tuple[Unit, InstancePath, D]] = []
        asked: set[tuple[Node, int]] = set()
        stranded: dict[tuple[UnitId, Node], None] = {}
        # What a read asks for is keyed by identity: `demand` gives one
        # object per distinct result of a read, and the values are
        # records whose hash walks every field.

        def reach(node: Node, wanted: D) -> None:
            if (node, id(wanted)) in asked:
                return
            asked.add((node, id(wanted)))
            nodes[node] = None
            for u, at in self.heads.get(node, ()):
                if (u.id, at, id(wanted)) not in placed:
                    if not admits((u, at), wanted):
                        continue
                    placed.add((u.id, at, id(wanted)))
                    units[u.id] = None
                    front.append((u, at, wanted))
                    names.add(self.top_name(node, u.head.relation.name))
                if unlisted is not None and unlisted((u, at)):
                    stranded[(u.id, node)] = None

        reach(Node(NodeKind.RELATION, (), OUTPUT.name), start)
        while front:
            u, at, wanted = front.pop()
            for atom, _negated in body_atoms(u.body or ()):
                node = self.resolve(at, atom.relation)
                if node is not None:
                    reach(node, demand((u, at), atom, wanted))
                    names.add(self.top_name(node, atom.relation.name))
        return list(units), list(nodes), names, list(stranded)

    def placed(self) -> list[Placed]:
        """Every unit of the solver's own text at each instance path it
        runs at."""
        return [(u, at) for u in self.units for at in self.paths_of(u)]

    def reading_input(self) -> frozenset[RelationName]:
        """The relations whose rows depend on `in` by dataflow, each by
        its instance path and its name: a relation read by a unit that
        reads `in`, or that reads such a relation, at the instance path
        the unit runs at. The units of the lib's components count as the
        solver's own do, so each relation of a lib instance stands on its
        own: a relation of it that its units feed from constants or from
        stored parameters alone does not read `in` although another
        relation of the instance does. A relation stands at the innermost
        path around the reading unit's whose component declares it."""
        if self._reach is None:
            tree = self._tree()
            readers: dict[RelationName, list[tuple[Unit, InstancePath]]] = {}
            for u in self.program.units:
                for at in self._paths_in(tree, u):
                    for atom, _negated in body_atoms(u.body or ()):
                        got = self._place(tree, at, atom.relation)
                        if got is not None:
                            readers.setdefault(got, []).append((u, at))
            start = RelationName((), INPUT.name)
            seen = {start}
            work = [start]
            while work:
                for u, at in readers.get(work.pop(), ()):
                    head = self._place(tree, at, u.head.relation)
                    if head is not None and head not in seen:
                        seen.add(head)
                        work.append(head)
            self._reach = frozenset(seen)
        return self._reach

    def reads_input(self, rel: RelationName) -> bool:
        """Whether the relation a top-level clause names by `rel` depends
        on `in` (`reading_input`)."""
        got = self._place(self._tree(), (), rel)
        return got is not None and got in self.reading_input()

    def component_path(self, path: InstancePath) -> str | None:
        """The component of the instance at `path`, the instances inside
        the lib's components included; None for the top level."""
        return self._tree().get(path) if path else None

    def extends(self, comp: str, base: str) -> bool:
        """Whether `comp` is `base` or extends it."""
        return base in self._chain(comp)

    def _tree(self) -> dict[InstancePath, str]:
        """Every instance path to its component, the instances inside the
        lib's components included."""
        if self._full is None:
            self._full = {path: comp.name
                          for _at, path, _inst, comp in self._instance_tree(True)}
        return self._full

    def _place(self, tree: Mapping[InstancePath, str], at: InstancePath,
               rel: RelationName) -> RelationName | None:
        """The relation a unit at `at` names by `rel`, by the instance path
        it stands at and its name; None where no declaration gives it."""
        got = self._locate(tree, at, rel, False)
        if got is None:
            return None
        q = self._declaring(tree, got[0], rel.name)
        return None if q is None else RelationName(q, rel.name)

    def relation_decl(self, node: Node) -> RelationDecl | None:
        """The declaration of a relation node; None for an instance of a
        lib component, whose relations the node stands for together."""
        if node.kind is not NodeKind.RELATION:
            return None
        return self._relation(self.component_at(node.path), node.name)

    def place(self, at: InstancePath, rel: RelationName
              ) -> RelationName | None:
        """The relation a unit at `at` names by `rel`, by the instance
        path that declares it in the instance tree with the lib's
        instances, and its name; None where no declaration gives it."""
        return self._place(self._tree(), at, rel)

    def feeding(self, place: RelationName
                ) -> list[tuple[Unit, InstancePath]]:
        """The clauses that put rows into the relation at `place`
        (`place`), each at the instance path it runs at: the units of the
        solver's own text and of the lib alike, a subsumptive clause left
        out, as it puts no row in."""
        if self._feeds is None:
            tree = self._tree()
            feeds: dict[RelationName, list[tuple[Unit, InstancePath]]] = {}
            for u in self.program.units:
                if u.subsumptive:
                    continue
                for at in self._paths_in(tree, u):
                    q = self._place(tree, at, u.head.relation)
                    if q is not None:
                        feeds.setdefault(q, []).append((u, at))
            self._feeds = feeds
        return self._feeds.get(place, [])

    def top_name(self, node: Node, name: str) -> RelationName:
        """The name a top-level clause reads a node's relation by, where
        a unit read it by `name`."""
        return RelationName(node.path, node.name
                            if node.kind is NodeKind.RELATION else name)


def substituted(t: Term, terms: dict[str, Term]) -> Term:
    """`t` with each variable of `terms` replaced by its term."""
    match t:
        case Variable(name=name):
            return terms.get(name, t)
        case Aggregate(expr=expr, body=body):
            return replace(t, expr=None if expr is None
                           else substituted(expr, terms),
                           body=tuple(substituted_literal(x, terms)
                                      for x in body))
    return with_subterms(t, lambda x: substituted(x, terms))


def substituted_atom(a: Atom, terms: dict[str, Term]) -> Atom:
    """`a` with each variable of `terms` replaced by its term."""
    return replace(a, args=tuple(substituted(x, terms) for x in a.args))


def substituted_literal(lit: BodyLiteral, terms: dict[str, Term]
                        ) -> BodyLiteral:
    """`lit` with each variable of `terms` replaced by its term."""
    if isinstance(lit, Disjunction):
        return replace(lit, branches=tuple(
            tuple(substituted_literal(x, terms) for x in b)
            for b in lit.branches))
    return with_literal_terms(lit, lambda x: substituted(x, terms))


def _wild(x: object) -> bool:
    """Whether a term, or a tuple of terms, holds a wildcard."""
    if isinstance(x, Wildcard):
        return True
    if isinstance(x, tuple):
        return any(_wild(y) for y in x)
    if is_dataclass(x) and not isinstance(x, type):
        return any(_wild(getattr(x, f.name)) for f in fields(x))
    return False


def _variables(x: object) -> set[str]:
    """The names of the variables a term, or a tuple of terms, holds."""
    if isinstance(x, Variable):
        return {x.name}
    if isinstance(x, tuple):
        return set().union(*(_variables(y) for y in x))
    if is_dataclass(x) and not isinstance(x, type):
        return set().union(*(_variables(getattr(x, f.name))
                             for f in fields(x)))
    return set()


def _holds_case(term: Term) -> bool:
    """Whether a term holds a constructor or a record, which a case value
    it is compared with must match."""
    return isinstance(term, (ConstructorTerm, RecordTerm))


def compared(unit: Unit, op: ComparisonOperator
             ) -> Iterator[tuple[str, Term]]:
    """Each variable a comparison `op` of a unit's body compares with a
    term, from either side, with that term, in body order."""
    for lit in unit.body or ():
        if isinstance(lit, Comparison) and lit.op is op:
            for var, term in ((lit.lhs, lit.rhs), (lit.rhs, lit.lhs)):
                if isinstance(var, Variable):
                    yield var.name, term


class _Cases:
    """Where a unit's rows hold a case value, and whether a base's value
    can stand there (`dependence`).

    A case value stands in a column of a case type: `Choice`, a type that
    stands in `Choice`, or a record type of the solver's own text with a
    field of a case type, the value then standing in that field. A term
    there admits a base where the base's value can stand in it. A variable
    takes the term an equality of the body sets it to. A variable that a
    `!=` of the body holds apart from a constant admits no base whose value
    there is that constant, as `An != $AnchorMinority()` shuts out the
    bases that take `$AnchorMinority`. Else, for each
    positive atom of the body that reads it in a column, or in a field of
    a record there, the variable holds one of the terms the rows of that
    column can hold there, read in the unit that heads them. For a
    relation, these are the terms one clause of the relation heads at
    every place the atom reads the variable, together. For a relation of
    an instance of a lib component, they are the terms each clause that
    feeds the instance heads in a column of the same type, each place on
    its own, since a lib component builds no value of a type its instance
    passes it. So `cut_choice(S)` with facts `cut_choice($Separator())`
    and `cut_choice($Mirror())` admits only the bases whose value there
    is one of the two, and so does a read of `cut.tile_of(S, _, _)` where
    `cut.cell(S, P) :- cut_choice(S)` feeds the instance. An atom where
    some such clause holds no term there sets no bound.

    One clause also ties the places of an atom to one another: where the
    atom holds a variable filled by the base's value (`bounded`) at some
    places, and each clause of the relation that the atom joins heads, at
    another case-typed place, only variables that its head's terms at the
    filled places hold, or that an equality of its body sets from those,
    the atom's variable at that other place is filled too. So, where each clause of `crowded` heads
    `crowded(A, Id, [A, Kind, U, $Threshold()])`, a read
    `crowded(A, Id, Ch)` in a unit whose head fills `Ch` fills `A`, and
    a read `parse.object($U(), A, Id, P)` beside it reaches only the
    clauses of `parse.object` whose head can hold the base's value in the
    column of `A`."""

    def __init__(self, graph: Graph, choice: Choice | None) -> None:
        self.graph = graph
        self.choice = choice
        points = {} if choice is None else {
            p.path: graph.resolve_type(p.type, ()) for p in choice.points}
        records: dict[str, tuple[str, ...]] = {
            graph.key_of(t): tuple(
                graph.resolve_type(f.type, t.scope.components)
                for f in t.fields)
            for t in graph.program.types
            if isinstance(t, RecordType) and own(t.span)}
        carrying = {CHOICE, *points.values()}
        grown = True
        while grown:
            more = {n for n, fields in records.items()
                    if n not in carrying
                    and any(f in carrying for f in fields)}
            carrying |= more
            grown = bool(more)
        self.types = CaseTypes(frozenset(carrying), records, points)
        self._eq: dict[UnitId, dict[str, Term]] = {}
        self._ne: dict[UnitId, dict[str, list[Term]]] = {}
        self.declared = set(graph.type_decls)
        self._cycles = 0
        """How many reads of a place being read already have been met; a
        result that met none, or holds, is final."""
        self._alts: dict[tuple[UnitId, InstancePath, str], list[list[list[
            tuple[Placed, Term, tuple[int, ...], str]]]]] = {}
        self._filled: dict[tuple[UnitId, InstancePath], frozenset[str]] = {}
        self._admits: dict[tuple[UnitId, InstancePath, str, tuple[int, ...],
                                 str, Base], bool] = {}
        self._fixed: dict[tuple[UnitId, InstancePath, int], tuple[
            tuple[tuple[str, ...] | None, Base], ...]] = {}
        self._bounded: dict[tuple[UnitId, InstancePath, int],
                            tuple[CasePlace, ...] | None] = {}
        self._demanded: dict[tuple[tuple[UnitId, InstancePath, int], int],
                             tuple[Base, Base]] = {}
        """`demand`'s result by read and by the identity of the base,
        which the entry holds alive, so that equal requests give one
        object."""

    def checks(self, unit: Unit, at: InstancePath
               ) -> tuple[dict[int, tuple[str, Term]], list[Term]]:
        """Each term where the unit holds a case value: each term of its
        head in a column of a case type, by the column, with its type, and
        each term of an `impl_choice` atom of its body, of type `Choice`."""
        columns = {i: (t, term)
                   for i, (t, term) in enumerate(self._typed(at, unit.head))
                   if t in self.types.types}
        impl = [lit.atom.args[0] for lit in unit.body or ()
                if isinstance(lit, AtomLiteral) and not lit.negated
                and lit.atom.relation == IMPL and len(lit.atom.args) == 1]
        return columns, impl

    def bounded(self, placed: Placed, atom: Atom
                ) -> tuple[CasePlace, ...] | None:
        """The case-typed places at which the base's value bounds the units
        a body atom of the placed unit reads, where the atom reads its
        relation at every value at some other place; None where it reads
        it at every value at none (`dependence`). The atom reads at every
        value at a case-typed place of its terms that holds a wildcard, or
        a variable that no case variable of the unit's head fills, a
        variable an equality sets to a term with a filled variable, and a
        variable a body atom ties to filled ones (`_Cases`), being filled
        too. A read of a relation of an instance of a lib component
        that is at every value at some place is bounded at none, since the
        units that feed the instance head other relations than the one it
        reads."""
        key = (placed[0].id, placed[1], id(atom))
        if key in self._bounded:
            return self._bounded[key]
        at = placed[1]
        filled = self._fills(placed)
        places = [((i, path, t), isinstance(leaf, ConstructorTerm) or (
                      isinstance(leaf, Variable) and leaf.name in filled))
                  for i, (column, term) in enumerate(self._typed(at, atom))
                  for path, t, leaf in self._case_leaves(term, column, ())]
        got: tuple[CasePlace, ...] | None = None
        if not all(bounds for _place, bounds in places):
            node = self.graph.resolve(at, atom.relation)
            got = () if node is None or node.kind is not NodeKind.RELATION \
                else tuple(place for place, bounds in places if bounds)
        self._bounded[key] = got
        return got

    def _fills(self, placed: Placed) -> frozenset[str]:
        """The variables of the placed unit that a case variable of its
        head fills (`bounded`): those of its head's case-typed terms, and
        those the equalities of its body (`_through_equalities`) and its
        positive atoms (`_tied`) give from filled ones."""
        unit, at = placed
        key = (unit.id, at)
        if key in self._filled:
            return self._filled[key]
        filled: set[str] = set()
        for _t, term in self.checks(unit, at)[0].values():
            filled |= _variables(term)
        atoms = [lit.atom for lit in unit.body or ()
                 if isinstance(lit, AtomLiteral) and not lit.negated]
        grown = True
        while grown:
            size = len(filled)
            filled = self._through_equalities(unit, filled)
            for atom in atoms:
                filled |= self._tied(at, atom, filled)
            grown = len(filled) > size
        self._filled[key] = frozenset(filled)
        return self._filled[key]

    def _through_equalities(self, unit: Unit, filled: set[str]
                            ) -> set[str]:
        """`filled` with each variable of the unit that an equality of its
        body sets to a term with no wildcard whose variables all stand in
        it, and each variable of a term an equality sets a variable of it
        to, to a fixpoint."""
        filled = set(filled)
        eq = self._equalities(unit)
        grown = True
        while grown:
            grown = False
            for v, term in eq.items():
                if v in filled:
                    more = _variables(term) - filled
                elif _variables(term) <= filled and not _wild(term):
                    more = {v}
                else:
                    more = set()
                if more:
                    filled |= more
                    grown = True
        return filled

    def _tied(self, at: InstancePath, atom: Atom, filled: set[str]
              ) -> set[str]:
        """The variables at the case-typed places of a positive body atom,
        read at `at`, that the atom ties to the variables of `filled` it
        holds (`_Cases`): those where each clause of its relation that the
        atom joins (`_joined_heads`) heads a term whose case-typed places
        hold only variables of the head's terms at the atom's places of
        `filled`, or variables an equality of the clause's body sets from
        them (`_through_equalities`). A relation that no clause heads, and
        a relation of a lib instance, tie none."""
        node = self.graph.resolve(at, atom.relation)
        heads = [] if node is None or node.kind is not NodeKind.RELATION \
            else self.graph.heads.get(node, [])
        if not heads:
            return set()
        leaves = [(i, path, t, leaf)
                  for i, (column, term) in enumerate(self._typed(at, atom))
                  for path, t, leaf in self._case_leaves(term, column, ())
                  if isinstance(leaf, Variable)]
        given = [(i, path) for i, path, _t, leaf in leaves
                 if leaf.name in filled]
        open_ = {leaf.name for _i, _path, _t, leaf in leaves
                 if leaf.name not in filled}
        if not given or not open_:
            return set()
        for h, typed in self._joined_heads(heads, atom):
            fixes: set[str] = set()
            for i, path in given:
                got = self._head_at(typed, i, path)
                if got is not None and not got[2]:
                    fixes |= {x.name for _p, _t, x in self._case_leaves(
                        got[1], got[0], ()) if isinstance(x, Variable)}
            fixes = self._through_equalities(h[0], fixes)
            open_ = {v for v in open_
                     if any(self._fixed_at(typed, i, path, fixes)
                            for i, path, _t, leaf in leaves
                            if leaf.name == v)}
        return open_

    def _head_at(self, typed: Sequence[tuple[str, Term]], column: int,
                 path: tuple[int, ...]
                 ) -> tuple[str, Term, tuple[int, ...]] | None:
        """The term a clause's head, `typed` as `_joined_heads` gives it,
        holds at the record fields `path` of a column, with its type and
        the part of `path` that leads on into it where it holds no record
        there; None where the head holds no term of that column."""
        if column >= len(typed):
            return None
        type, term = typed[column]
        while path and isinstance(term, RecordTerm):
            fields = self.types.term_fields(type)
            if fields is None or len(fields) != len(term.args) \
                    or path[0] >= len(fields):
                return None
            type, term, path = fields[path[0]], term.args[path[0]], path[1:]
        return type, term, path

    def _fixed_at(self, typed: Sequence[tuple[str, Term]], column: int,
                  path: tuple[int, ...], fixes: set[str]) -> bool:
        """Whether a clause's head, `typed` as `_joined_heads` gives it,
        holds at the record fields `path` of a column a term each of whose
        case-typed places holds a variable of `fixes`."""
        got = self._head_at(typed, column, path)
        if got is None:
            return False
        type, term, rest = got
        if rest:
            return isinstance(term, Variable) and term.name in fixes
        leaves = self._case_leaves(term, type, ())
        return bool(leaves) and all(
            isinstance(x, Variable) and x.name in fixes
            for _p, _t, x in leaves)

    def _case_leaves(self, term: Term, type: str, path: tuple[int, ...]
                     ) -> list[tuple[tuple[int, ...], str, Term]]:
        """The terms at the case-typed places of a term of `type` that
        stands at `path`, each with its own path and type, records opened
        by their fields' types (`CaseTypes.term_fields`)."""
        if type not in self.types.types:
            return []
        fields = self.types.term_fields(type)
        if isinstance(term, RecordTerm) and fields is not None \
                and len(fields) == len(term.args):
            return [x for j, (a, f) in enumerate(
                        zip(term.args, fields, strict=True))
                    for x in self._case_leaves(a, f, (*path, j))]
        return [(path, type, term)]

    def _typed(self, at: InstancePath, atom: Atom
               ) -> list[tuple[str, Term]]:
        """Each term of an atom a unit at `at` holds, with its column's
        type, read through the type arguments in force there; none where
        no declaration gives the relation."""
        types = self.graph.column_types(at, atom.relation)
        if types is None:
            return []
        return list(zip(types, atom.args, strict=False))

    def demand(self, placed: Placed, atom: Atom, base: Base | None
               ) -> Base | None:
        """What a read asks for, for a unit reached for `base`: `base` with
        the value of each constant term of the atom that stands in a
        column of a point's type, where one point has that type, set at
        that point, and a constant `Choice` value in place of the base."""
        choice = self.choice
        if choice is None or base is None:
            return base
        key = (placed[0].id, placed[1], id(atom))
        fixed = self._fixed.get(key)
        if fixed is None:
            fixed = self._fixed[key] = self._fixes(placed[1], atom, choice)
        if not fixed:
            return base
        memo = (key, id(base))
        if memo in self._demanded:
            return self._demanded[memo][1]
        out = base
        for path, value in fixed:
            if path is None:
                out = value
                continue
            got = with_value_at(choice, out, path, value)
            if got is not None:
                out = got
        if out == base:
            out = base
        self._demanded[memo] = (base, out)
        return out

    def _fixes(self, at: InstancePath, atom: Atom, choice: Choice
               ) -> tuple[tuple[tuple[str, ...] | None, Base], ...]:
        """The values a read fixes (`demand`): each constant term of the
        atom in a column of a point's type, where one point has that type,
        with the point's path, and a constant `Choice` value with None."""
        out: list[tuple[tuple[str, ...] | None, Base]] = []
        for t, term in self._typed(at, atom):
            if not isinstance(term, ConstructorTerm | RecordTerm):
                continue
            value = _constant(term)
            if not isinstance(value, AdtValue | RecordValue):
                continue
            if t == CHOICE:
                out.append((None, value))
                continue
            points = points_of_type(choice, t)
            if len(points) == 1 and isinstance(value, AdtValue):
                out.append((points[0].path, value))
        return tuple(out)

    def admits(self, placed: Placed, type: str, term: Term,
               path: tuple[int, ...], base: Base | None) -> bool:
        """Whether `base`'s value can stand at the place of type `type`
        that the record fields `path` lead to in `term`, the variables of
        `term` read in the placed unit."""
        return self._admits_in(placed, type, term, path, base, frozenset())

    def _admits_in(self, placed: Placed, type: str, term: Term,
                   path: tuple[int, ...], base: Base | None,
                   open_: frozenset[tuple[UnitId, InstancePath, str,
                                          tuple[int, ...]]]
                   ) -> bool:
        """`admits` for the part of `term` at `path`, the record fields to
        it, where the places of `open_` are being read already. A value
        reaches such a place again only through another route, so a read
        of it on this path admits nothing, as a recursive clause adds no
        value its other clauses do not give. A term of a point's type is
        admitted where the base's value at some point of that type matches
        it, or where the base has no value at some point of that type: a
        unit can give a constructor a fixed value at a point under another
        branch, as `markers_of($OnePiece(), $SingleDots())` does where
        `markers` stands under `LargestPiece`."""
        choice = self.choice
        if choice is None or base is None or type not in self.types.types:
            return True
        while path and isinstance(term, RecordTerm):
            if path[0] >= len(term.args):
                return True
            term, path = term.args[path[0]], path[1:]
        unit, at = placed
        if isinstance(term, Variable):
            term = self._equalities(unit).get(term.name, term)
            if not isinstance(term, Variable):
                return self._admits_in(placed, type, term, path, base, open_)
            if not path and any(self._is_value(type, c, base)
                                for c in self._exclusions(unit, term.name)):
                return False
            key = (unit.id, at, term.name, path)
            if key in open_:
                self._cycles += 1
                return False
            memo = (unit.id, at, term.name, path, type, base)
            if memo not in self._admits:
                inner = open_ | {key}
                cycles = self._cycles
                got = all(
                    any(all(self._admits_in(h, type, alt, (*to, *path), base,
                                            inner)
                            for h, alt, to, _column in clause)
                        for clause in alts
                        if all(self._may_hold(column, (*to, *path), type)
                               for _h, _alt, to, column in clause))
                    for alts in self._alternatives(placed, term.name))
                if got or cycles == self._cycles:
                    self._admits[memo] = got
                return got
            return self._admits[memo]
        if path:
            return True
        fields = self.types.term_fields(type)
        if fields is not None:
            if isinstance(term, RecordTerm) and len(term.args) == len(fields):
                return all(self._admits_in(placed, f, a, (), base, open_)
                           for f, a in zip(fields, term.args, strict=True))
            return True
        return any(v is None or _matches(term, v)
                   for v in self._leaf_values(type, base))

    def _leaf_values(self, type: str, base: Base) -> list[Value | None]:
        """The values `base` can hold at a case-typed place of `type` that
        is no record: the base itself in a `Choice` column, else its value
        at each point of that type, None where it does not reach it."""
        choice = self.choice
        assert choice is not None, "a case-typed place has a choice"
        if type == CHOICE:
            return [base]
        points = points_of_type(choice, type)
        if not points:
            raise ValueError(f"no choice point has the type `{type}`")
        return [value_at(choice, base, p.path) for p in points]

    def _is_value(self, type: str, term: Term, base: Base) -> bool:
        """Whether `term`, a constant that a `!=` of the unit's body
        compares a variable with, is the value `base` holds at a
        case-typed place of `type` that is no record: at each point of
        that type, where several have it, so that the comparison shuts the
        base out there."""
        if self.types.term_fields(type) is not None:
            return False
        value = _constant(term)
        if not isinstance(value, AdtValue | RecordValue):
            return False
        return all(v == value for v in self._leaf_values(type, base))

    def _equalities(self, unit: Unit) -> dict[str, Term]:
        """The terms the equalities of a unit's body set its variables
        to, where the term holds a constructor or a record."""
        if unit.id not in self._eq:
            self._eq[unit.id] = {
                v: t for v, t in compared(unit, ComparisonOperator.EQ)
                if _holds_case(t)}
        return self._eq[unit.id]

    def _exclusions(self, unit: Unit, var: str) -> list[Term]:
        """The terms the `!=` comparisons of a unit's body hold a variable
        apart from, where the term holds a constructor or a record."""
        if unit.id not in self._ne:
            ne: dict[str, list[Term]] = {}
            for v, term in compared(unit, ComparisonOperator.NE):
                if _holds_case(term):
                    ne.setdefault(v, []).append(term)
            self._ne[unit.id] = ne
        return self._ne[unit.id].get(var, [])

    def _may_hold(self, column: str, path: tuple[int, ...],
                  type: str) -> bool:
        """Whether a column of type `column`, as the unit that heads it
        types it, can hold a value of `type` at `path`: not where both
        types are declared and differ, since then the clause feeds another
        instance of the component that reads it."""
        for j in path:
            fields = self.types.term_fields(column)
            if fields is None or j >= len(fields):
                return True
            column = fields[j]
        return column == type or column not in self.declared \
            or type not in self.declared

    def _alternatives(self, placed: Placed, var: str
                      ) -> list[list[list[tuple[Placed, Term, tuple[int, ...],
                                                str]]]]:
        """For each positive atom of a unit's body that reads `var`, the
        alternatives its rows give `var` (`_Cases`): for a relation, one
        per clause, with the term the clause heads at each place the atom
        reads `var`; for a relation of a lib instance, one per term and
        place. Each term stands with the unit that heads it, the place of
        `var` in its column, and the column's type as that unit types
        it."""
        unit, at = placed
        key = (unit.id, at, var)
        if key not in self._alts:
            out: list[list[list[tuple[Placed, Term, tuple[int, ...],
                                      str]]]] = []
            for lit in unit.body or ():
                if not isinstance(lit, AtomLiteral) or lit.negated:
                    continue
                node = self.graph.resolve(at, lit.atom.relation)
                if node is None:
                    continue
                heads = self.graph.heads.get(node, [])
                if not heads:
                    continue
                places = [(i, path) for i, arg in enumerate(lit.atom.args)
                          for path in _paths(arg, var)]
                if not places:
                    continue
                if node.kind is NodeKind.RELATION:
                    clauses = self._joined_heads(heads, lit.atom)
                    if all(i < len(typed) for _h, typed in clauses
                           for i, _path in places):
                        out.append([[(h, typed[i][1], path, typed[i][0])
                                     for i, path in places]
                                    for h, typed in clauses])
                    continue
                for i, path in places:
                    got = self._fed_terms(heads, i, at, lit.atom)
                    if got is not None:
                        out.append([[(h, t, path, c)] for h, t, c in got])
            self._alts[key] = out
        return self._alts[key]

    def _joined_heads(self, heads: Sequence[Placed], read: Atom
                      ) -> list[tuple[Placed, list[tuple[str, Term]]]]:
        """The clauses `heads` of a relation that a read joins
        (`joined`), each with the terms of its head and their columns'
        types as it types them: a value the read fixes wholly in a column
        sets the variable the clause's head holds there, and a clause
        whose head holds another value there gives the read no row."""
        row = _row(read)
        out: list[tuple[Placed, list[tuple[str, Term]]]] = []
        for h in heads:
            held = joined(h[0].head.args, row, _no_name)
            if held is None:
                continue
            terms = {v: term_of(x) for v, x in held.items() if fixed(x)}
            out.append((h, [(t, substituted(term, terms))
                            for t, term in self._typed(h[1], h[0].head)]))
        return out

    def _fed_terms(self, heads: Sequence[Placed], column: int,
                   at: InstancePath, read: Atom
                   ) -> list[tuple[Placed, Term, str]] | None:
        """The terms the clauses `heads` that feed a lib instance hold in
        a column of the type of a read's column, the read's unit running
        at `at`, each with its type (`_alternatives`); none where no
        clause that feeds the relation the read reads (`Graph.feeding`)
        meets it, and None where the read's column has no type or no
        clause holds a term of its type."""
        typed_read = self._typed(at, read)
        if column >= len(typed_read):
            return None
        place = self.graph.place(at, read.relation)
        if place is None:
            raise ValueError(f"`{read.relation.text}` has column types and "
                             "no place")
        row = _row(read)
        feeding = self.graph.feeding(place)
        if feeding and all(joined(u.head.args, row, _no_name) is None
                           for u, _at in feeding):
            return []
        type = typed_read[column][0]
        out: list[tuple[Placed, Term, str]] = []
        for h in heads:
            out += [(h, term, t) for t, term in self._typed(h[1], h[0].head)
                    if t == type]
        return out or None


def _no_name(_name: str) -> Value | None:
    """The value `_Cases` reads a defined name as: none."""
    return None


def _row(read: Atom) -> "Pattern":
    """What a read's terms fix of the rows it reads (`_known`)."""
    return tuple(_known(t) for t in read.args)


def _known(term: Term) -> Value | None:
    """What a read's term fixes of its value (`known`), a defined name
    read as fixing none."""
    return known(term, {}, _no_name)


def _constant(term: Term) -> Value | None:
    """The value a term states with no variable, call or defined name in
    it (`term_value`); None for any other term."""
    return term_value(term, _no_name)


type Pattern = tuple[Value | None, ...]
"""What is known of a row of a relation, per column: the value that a
read's term, or a case, fixes there; None where nothing does."""


UNFIXED: Value = AdtValue("", ())
"""A part of a record or constructor value in a `Pattern` that nothing
fixes, where some other part of it is fixed."""


def compatible(a: Value, b: Value) -> bool:
    """Whether two values of a `Pattern` may be one value: equal where
    both fix a part (`UNFIXED`)."""
    if a == UNFIXED or b == UNFIXED:
        return True
    if isinstance(a, AdtValue) and isinstance(b, AdtValue):
        return a.constructor == b.constructor \
            and len(a.args) == len(b.args) \
            and all(compatible(x, y)
                    for x, y in zip(a.args, b.args, strict=True))
    if isinstance(a, RecordValue) and isinstance(b, RecordValue):
        return len(a.fields) == len(b.fields) \
            and all(compatible(x, y)
                    for x, y in zip(a.fields, b.fields, strict=True))
    return a == b


def _meet(a: Value, b: Value) -> Value:
    """What two `compatible` values of a `Pattern` fix together."""
    if a == UNFIXED:
        return b
    if isinstance(a, AdtValue) and isinstance(b, AdtValue):
        return AdtValue(a.constructor, tuple(
            _meet(x, y) for x, y in zip(a.args, b.args, strict=True)))
    if isinstance(a, RecordValue) and isinstance(b, RecordValue):
        return RecordValue(tuple(
            _meet(x, y) for x, y in zip(a.fields, b.fields, strict=True)))
    return a


def fixed(v: Value) -> bool:
    """Whether a value of a `Pattern` fixes every part (`UNFIXED`)."""
    if v == UNFIXED:
        return False
    if isinstance(v, AdtValue):
        return all(fixed(x) for x in v.args)
    if isinstance(v, RecordValue):
        return all(fixed(x) for x in v.fields)
    return True


def known(term: Term, env: Mapping[str, Value],
          defined: Callable[[str], Value | None]) -> Value | None:
    """What a read's term fixes of the value it stands for, a variable's
    value read in `env` and a defined name's through `defined`: None where
    it fixes none of it, and a record or constructor value with `UNFIXED`
    at each part it does not fix."""
    match term:
        case Variable(name=name):
            return env.get(name)
        case ConstructorTerm(name=name, args=args):
            vals = [known(a, env, defined) for a in args]
            return AdtValue(name, tuple(UNFIXED if v is None else v
                                        for v in vals))
        case RecordTerm(args=args):
            vals = [known(a, env, defined) for a in args]
            return None if all(v is None for v in vals) else RecordValue(
                tuple(UNFIXED if v is None else v for v in vals))
    return term_value(term, defined)


def joined(head: Sequence[Term], row: Pattern,
           defined: Callable[[str], Value | None]
           ) -> dict[str, Value] | None:
    """The value a read fixes (`row`) of each variable of a clause's head,
    column by column, a variable met twice taking what both fix; None
    where the read and the head fix different values in one place, so
    that no row of the clause meets the read. A defined name of the head
    reads through `defined`. Raises `ValueError` where the head and the
    row differ in length."""
    if len(head) != len(row):
        raise ValueError(f"a head of {len(head)} terms read with "
                         f"{len(row)}")
    env: dict[str, Value] = {}

    def join(term: Term, value: Value | None) -> bool:
        if value is None or value == UNFIXED:
            return True
        match term:
            case Variable(name=name):
                if name in env:
                    if not compatible(env[name], value):
                        return False
                    value = _meet(env[name], value)
                env[name] = value
                return True
            case ConstructorTerm(name=name, args=args):
                return isinstance(value, AdtValue) \
                    and value.constructor == name \
                    and len(value.args) == len(args) and all(
                        join(t, v)
                        for t, v in zip(args, value.args, strict=True))
            case RecordTerm(args=args):
                return isinstance(value, RecordValue) \
                    and len(value.fields) == len(args) and all(
                        join(t, v)
                        for t, v in zip(args, value.fields, strict=True))
        mine = term_value(term, defined)
        return mine is None or compatible(mine, value)

    ok = all(join(t, v) for t, v in zip(head, row, strict=True))
    return env if ok else None


def _paths(term: Term, var: str, at: tuple[int, ...] = ()
           ) -> Iterator[tuple[int, ...]]:
    """Each place `var` stands in a term, as the record fields to it."""
    if isinstance(term, Variable) and term.name == var:
        yield at
    elif isinstance(term, RecordTerm):
        for j, a in enumerate(term.args):
            yield from _paths(a, var, (*at, j))


def _matches(term: Term, value: Value) -> bool:
    """Whether a value can stand where a term stands: each constructor
    and record of the term matches the value's, and any other term matches
    any value."""
    match term:
        case ConstructorTerm(name=name, args=args):
            return isinstance(value, AdtValue) and value.constructor == name \
                and len(args) == len(value.args) \
                and all(_matches(a, v)
                        for a, v in zip(args, value.args, strict=True))
        case RecordTerm(args=args):
            return isinstance(value, RecordValue) \
                and len(args) == len(value.fields) \
                and all(_matches(a, v)
                        for a, v in zip(args, value.fields, strict=True))
        case _:
            return True


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


def holds_at(solver: Solver, base: Base | None, types: Sequence[str],
             case_cols: Sequence[int], values: tuple[Value, ...]) -> bool:
    """Whether the base holds the case values of a row: the base itself
    at a `Choice` column, and at a column of a point's type, the column's
    value at some point of that type, `types` being the column types as
    the model resolves them (`column_types`). Whether the base depends on
    the relation is the caller's to ask."""
    choice = solver.choice
    if choice is None or base is None:
        return False
    reading = case_types(solver)
    for i, v in zip(case_cols, values, strict=True):
        for t, leaf in reading.leaves(types[i], v):
            if leaf not in base_values(choice, reading, base, t):
                return False
    return True


def base_values(choice: Choice, reading: CaseTypes, base: Base, type: str
                ) -> list[Value]:
    """What `base` holds at a case column of `type`: the base itself at a
    `Choice` column, and at a column of a point's type the base's value at
    each point of that type it reaches (`value_at`). Raises `ValueError`
    where `type` is neither: a place of a record case type that holds no
    record of its fields, which no value of the column's type is."""
    if type == CHOICE:
        return [base]
    points = reading.at(choice, type)
    if not points:
        raise ValueError(f"`{type}` is neither `Choice` nor a point's type")
    return [v for p in points
            if (v := value_at(choice, base, p.path)) is not None]


def case_values(solver: Solver, choice: Choice, base: Base, type: str
                ) -> list[Value]:
    """What `base` holds at a case column or field of `type` wholly of the
    case (`CaseTypes.whole`): `base_values` at `Choice` and at a point's
    type, and at a record type each record of what the base holds at its
    fields. Raises `ValueError` where `type` is not wholly of the case."""
    reading = case_types(solver)
    if not reading.whole(type):
        raise ValueError(f"`{type}` is not wholly of the case")
    fields = reading.fields(type)
    if fields is None:
        return base_values(choice, reading, base, type)
    return [RecordValue(tuple(v)) for v in product(
        *(case_values(solver, choice, base, f) for f in fields))]


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


def off_form_case_columns(solver: Solver) -> Iterator[Fault]:
    """Each parameter's column that carries the case (`case_columns`) and
    is no case column of a parameter (`parameter_case_columns`). With no
    `Choice` no column carries the case, and with no instance of `Params`
    the program reads no parameter."""
    if solver.choice is None or instance_of(solver.program, PARAMS) is None:
        return
    records = case_types(solver).records
    for p in solver.params.parameters:
        decl = declaration_of(solver.program, p)
        types = parameter_columns(solver, p.name).types
        case = parameter_case_columns(types)
        for i in case_columns(solver, types):
            if i not in case:
                column = decl.columns[i]
                yield Fault(ProblemKind.CASE_COLUMN_OFF_FORM,
                            InSolver(decl.span.first),
                            CaseColumnOffForm(
                                p.name, column.name, column.type,
                                OffFormType.RECORD if types[i] in records
                                else OffFormType.ADT))


def case_columns(solver: Solver, of: RelationName | Sequence[str]
                 ) -> tuple[int, ...]:
    """The columns of the relation `of` of the solver's program, or of a
    relation of column types `of`, as the model resolves them
    (`column_types`), that carry the case: of type `Choice`, of an
    ADT that stands in `Choice` (solver-file.md, under "Types"), or of a record
    type with a field of such a type, a component's type parameter read through
    the instance, which carries the case in that field and is a key in its
    other fields (`case_types`, as `dependence` reads them). A
    case column is a key of a stored value, never one of its columns."""
    if solver.choice is None:
        return ()
    types = column_types(solver.engine, solver.program, of) \
        if isinstance(of, RelationName) else of
    case = case_types(solver).types
    return tuple(i for i, t in enumerate(types) if t in case)


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


def cases(solver: Solver, engine: Engine, limits: Limits
         ) -> tuple[Case, ...] | RunFailure:
    """The solver's cases, in enumeration order, or the failure of
    the run that enumerates them.

    The solver's cases are the bases that `impl_choice` enumerates, read from a
    run on the empty input since the enumeration is a clause, each combined
    with every choice of branch at the `@derive` and `@store` points whose
    parameter or relation the base's derivation of `out` depends on
    (`dependence`; solver-file.md, under "Params" and "Program"), minus each
    case that an `@ignore: derive` or `@ignore: store` line excludes: the bare
    form excludes every case that takes the branch in its place, every
    derivation of the parameter for the derive form; `@ignore: derive
    <Proposer>` every case that takes that one derivation; and a named form,
    under a `@derive` or `@store` line, every case that takes that line's
    branch and every branch its `<name>` contains (`solver.names.cases_of`;
    solver-file.md, under "Params" and "Program"; history "The runner holds
    cases the solver does not write" and 1103), and minus each case that takes
    a `@store` branch on a relation with an `Ident` column (`ident_keyed`);
    the `@store` line on such a relation is a finding of the store check that
    fails the command. The handbook does not define the solver's cases in one
    place; this docstring is where the definition stands.

    A `Choice` with no `impl_choice` relation has every combination of
    its fields as a case (solver-file.md, under "Cases")."""
    from solver.names import Denoted, cases_of, denote

    choice = solver.choice
    bases: tuple[Base | None, ...]
    if choice is None:
        bases = (None,)
    elif enumerates(solver.program):
        got = enumerated(engine, solver.program, limits)
        if not isinstance(got, tuple):
            return got
        bases = got
    else:
        every = every_base(choice)
        bases = () if every is None else every
    read = dependence(engine, solver, bases) if solver.branches \
        else Dependence({}, {}, {})
    relations = {r: set(b) for r, b in read.relations.items()}
    order = {b: i for i, b in enumerate(solver.branches)}
    cases: list[Case] = []
    for base in bases:
        points: list[list[Branch | None]] = []
        at: dict[str, int] = {}
        for b in solver.branches:
            if isinstance(b, DeriveBranch) \
                    and read.reads_parameter(base, b.parameter):
                if b.parameter not in at:
                    at[b.parameter] = len(points)
                    points.append([None])
                points[at[b.parameter]].append(b)
            elif isinstance(b, StoreBranch) \
                    and base in relations.get(b.relation, ()):
                points.append([None, b])
        cases += [Case(base, tuple(sorted((b for b in combo if b is not None),
                                          key=lambda b: order[b])))
                  for combo in product(*points)]
    excluded: list[Denoted] = []
    bare: list[tuple[IgnoreForm, RelationName, str | None]] = []
    for i in solver.annotations.ignores:
        if i.form is IgnoreForm.LINT:
            continue
        if i.name is None:
            bare += [(i.form, t, i.proposer)
                     for t in ignore_targets(solver.program, i)]
            continue
        denoted = denote(solver, i.name)
        if isinstance(denoted, Denoted):
            under = branch_under(solver, i)
            if under is not None and under not in denoted.branches:
                denoted = replace(denoted,
                                  branches=(*denoted.branches, under))
            excluded.append(denoted)

    keyed = {b.relation for b in solver.branches
             if isinstance(b, StoreBranch)
             and ident_keyed(engine, solver.program, b.relation)}

    def out(case: Case) -> bool:
        if any(isinstance(b, StoreBranch) and b.relation in keyed
               for b in case.branches):
            return True
        for form, target, proposer in bare:
            for b in case.branches:
                if form is IgnoreForm.DERIVE and isinstance(b, DeriveBranch) \
                        and RelationName((), b.parameter) == target \
                        and proposer in (None, b.proposer):
                    return True
                if form is IgnoreForm.STORE and isinstance(b, StoreBranch) \
                        and b.relation == target:
                    return True
        return False

    named = {c for d in excluded for c in cases_of(solver, d, cases)}
    return tuple(c for c in cases if not out(c) and c not in named)
