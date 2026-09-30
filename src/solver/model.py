"""The model of a solver as the handbook defines it: its case type, its
branches and cases, its parameters, the lib as the model reads it, and the
aggregate `Solver` with its one entry, `load`; and the functions that build
each part from a parsed program, which the checks read as well."""

import re
import threading
from collections import OrderedDict
from enum import Enum, auto
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field, replace
from itertools import product
from pathlib import Path

from arc import task as arc_task
from arc.task import Task
from engine import checkout
from engine import (
    AdtValue,
    DeclId,
    Engine,
    GridForm,
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
    AdtType,
    Aggregate,
    AliasType,
    Atom,
    AtomLiteral,
    BinaryOperator,
    Component,
    BinaryTerm,
    BodyLiteral,
    Column,
    Comparison,
    ComparisonOperator,
    ConstructorTerm,
    DefinedName,
    Disjunction,
    FunctorCall,
    GridCall,
    Instance,
    IntrinsicCall,
    RigidCall,
    NumberTerm,
    RecordTerm,
    RecordType,
    RelationDecl,
    StringTerm,
    SubtypeType,
    Term,
    TypeDecl,
    TypeField,
    UnaryOperator,
    UnaryTerm,
    Unit,
    Variable,
    Wildcard,
)
from solver import annotations as annotations_reader
from solver import witness as witness_reader
from solver.annotations import (
    Annotations,
    CaseMarker,
    DeriveLine,
    IgnoreForm,
    IgnoreLine,
    NamedVerdict,
    StoreLine,
)
from solver.problems import (
    InSolver,
    InWitnessFile,
    Named,
    ProblemKind,
    Fault,
    Undecided,
    UndecidedForm,
)
from solver.vocabulary import (
    BOX,
    CHOICE,
    DETERMINE,
    ELEM_SUFFIX,
    ENUMERATOR,
    IDENT,
    INPUT,
    LIB_FILE,
    OUTPUT,
    PARAMS,
    PROPOSE,
    PROPOSERS_FILE,
)
from solver.witness import AssignArg, AssignRows, Groups, WitnessFile

# Choice


@dataclass(frozen=True)
class ConstructorBranch:
    """A constructor of a choice ADT, one branch of its choice point, with
    the lines of its branch comment (solver-file.md:99-102, "Cases")."""

    name: str
    fields: tuple[TypeField, ...]
    comment: tuple[int, ...]
    line: int
    """The solver line the constructor starts on."""
    own_line: bool
    """Whether the constructor opens its line."""


@dataclass(frozen=True)
class ChoicePoint:
    """An ADT that stands in `Choice` (solver-file.md:125-129, "Types"):
    where it stands, as the path of record fields and constructors from
    the `Choice` root, its type, and its constructors, the concept branch
    first. (The old `models.Site`.)"""

    path: tuple[str, ...]
    type: str
    declaration: DeclId
    """The ADT's declaration, as the model resolves `type`."""
    constructors: tuple[ConstructorBranch, ...]


def concept_branch(point: ChoicePoint) -> ConstructorBranch:
    """The concept branch at `point`: its first constructor, since the
    concept branch is declared first in `Choice` and in each field's type
    of a record `Choice` (style.md:51)."""
    return point.constructors[0]


def other_branches(point: ChoicePoint) -> tuple[ConstructorBranch, ...]:
    """The branches at `point` other than its concept branch
    (`concept_branch`)."""
    concept = concept_branch(point)
    return tuple(c for c in point.constructors if c != concept)


@dataclass(frozen=True)
class Choice:
    """The case type, an ADT or a record of ADTs, with the constructor at
    each choice point (solver-file.md:97-110 "Cases", :124-131 "Choice
    types")."""

    declaration: DeclId
    record: tuple[TypeField, ...] | None
    """The fields of a record `Choice`; None for an ADT `Choice`."""
    points: tuple[ChoicePoint, ...]


type Base = AdtValue | RecordValue
"""A `Choice` value: a case without the `@derive` and `@store` branches it
takes (history 1159)."""


# Branches and cases


@dataclass(frozen=True)
class DeriveBranch:
    """`<param>=<Proposer>`: a branch of the choice point on a parameter
    (solver-file.md:120)."""

    parameter: str
    proposer: str
    line: DeriveLine | None
    """The `@derive` line; None for a derivation the survey proposes, which
    no line holds yet."""


@dataclass(frozen=True)
class StoreBranch:
    """`<rel>=stored`: a branch of the choice point on a relation
    (solver-file.md:137)."""

    relation: RelationName
    """The relation as a top-level clause reads it, which the run fixes."""
    spelled: str
    """The relation as the line spells it, the name the witness file writes
    before `=stored` (solver-file.md:199): the `.decl`'s name, or
    `<instance>.<relation>` for a line above an `.init`. Two lines that
    spell it the same are homonyms."""
    line: StoreLine | None
    """The `@store` line; None for a value the survey judges with a line
    on its relation, which no line holds yet."""


@dataclass(frozen=True)
class StoredAtDerive:
    """`<param>=stored`: the stored value at a `@derive` point (history
    1103)."""

    parameter: str


type Branch = DeriveBranch | StoreBranch | StoredAtDerive


@dataclass(frozen=True)
class Case:
    """A base with the branch taken at each `@derive` and `@store` point
    (plan §D4 `Case`; history 1159). `base` is None for a solver with no
    `Choice` (solver-file.md:103). `branches` holds each branch taken other
    than its point's first, in file order."""

    base: Base | None
    branches: tuple[Branch, ...]


# Params


@dataclass(frozen=True)
class UnderMarker:
    marker: CaseMarker


@dataclass(frozen=True)
class Unmarked:
    """Above the first marker that lists a case: a parameter every case
    reads (style.md:57)."""


type Section = UnderMarker | Unmarked
"""solver-file.md:104-107 ("Case markers"); style.md:56-58 ("Shared
parameters"). A marker that lists no case, such as `// --- Shared ---`,
is a marker like any other."""


@dataclass(frozen=True)
class StoredGridCall:
    """One GRID call of a parameter as the engine types it (patterns.md,
    "`GRID_HxW` for grid data"): its keys, its form, whether it is a stamp,
    and its cells, None for an empty cell `_` of a stamp or a mask or
    sparse form, with a stamp's anchor cell as (row, column)."""

    keys: Row
    form: GridForm
    stamp: bool
    cells: tuple[tuple[int | None, ...], ...]
    anchor: tuple[int, int] | None


@dataclass(frozen=True)
class StoredGrid:
    """A parameter stored by GRID macro calls, one grid per call."""

    grids: tuple[StoredGridCall, ...]


@dataclass(frozen=True)
class Parameter:
    """A relation of `Params` (solver-file.md:112-117, "Params")."""

    name: str
    declaration: DeclId
    columns: tuple[Column, ...]
    stored: Rows | StoredGrid
    determined: bool
    """A `Determine` relation mirrors it (solver-file.md:158)."""
    section: Section


@dataclass(frozen=True)
class DerivedRelation:
    """A relation of `Params` that clauses feed: data derived from the
    parameters, which is no parameter (solver-file.md:113, :160)."""

    name: str
    declaration: DeclId
    columns: tuple[Column, ...]
    mirrored: bool
    """A `Determine` relation of its name mirrors it, which
    solver-file.md:160 rules out."""
    section: Section
    """The section it stands in, as a parameter's (`Parameter.section`):
    what cases share is the marker rule's concern, whatever feeds the
    relation (style.md:57)."""


@dataclass(frozen=True)
class Params:
    """solver-file.md:112-117 ("Params")."""

    parameters: tuple[Parameter, ...]
    derived: tuple[DerivedRelation, ...] = ()
    """The relations of `Params` that clauses feed, which no parameter
    list holds."""


# Lib


@dataclass(frozen=True)
class Lib:
    """The lib's types and constants as the model reads them, parsed
    through the engine from `programs/lib/` (plan §D4 `Lib`)."""

    box_types: frozenset[str]
    orientation_types: Mapping[str, tuple[str, ...]]
    """Each orientation type and its members."""
    constants: Mapping[str, Value]
    """The constants a witness `assign` may name (solver-file.md:191)."""


# Solver


@dataclass(frozen=True)
class Solver:
    """One solver: its program and the model read from it (plan §D4
    `Solver`). `problems` holds the faults: what `load` could not read."""

    stem: str
    task_id: str
    program: Program
    annotations: Annotations
    choice: Choice | None
    """None for a solver with one case (solver-file.md:103)."""
    branches: tuple[Branch, ...]
    params: Params
    witness_file: WitnessFile | None
    """None where the task has no witness file."""
    task: Task | None
    """None where the task has no task file."""
    lib: Lib
    problems: tuple[Fault, ...]


# Paths

def proposers_path() -> Path:
    """The proposers file under the checkout's `programs/`."""
    return checkout.programs() / PROPOSERS_FILE


LIB_INCLUDE = f'#include "../{LIB_FILE}"\n#line 1\n'
"""What `load` puts above a text that lacks the lib's include: the include,
and a `#line 1` directive, so that the text's own lines keep their
numbers."""
TOP = Scope(())
_STEM_RE = re.compile(r"^[0-9a-f]{8}")


def own(span: Span | None) -> bool:
    """Whether a part is the solver's own text: parsed from the text
    handed to `parse`, not from an include or an operation."""
    return span is not None and span.file is None


def parse_with_lib(engine: Engine, text: str) -> Program | ParseFailure:
    """`text` parsed against the solvers directory, with the lib's include
    added where the parse holds none (plan §D3 `parse`)."""
    parsed = engine.parse(text, checkout.solvers())
    if isinstance(parsed, Program) and any(
            Path(i.path).name == LIB_FILE for i in parsed.includes):
        return parsed
    return engine.parse(LIB_INCLUDE + text, checkout.solvers())


# Reading values


def term_value(term: Term, constants: Mapping[str, Value]) -> Value | None:
    """The value a term states with no variable in it: a number, a symbol,
    a constructor or record of such, or a defined constant; None for any
    other term."""
    match term:
        case NumberTerm(value=v):
            return v
        case StringTerm(value=v):
            return v
        case DefinedName(name=name):
            return constants.get(name)
        case ConstructorTerm(name=name, args=args):
            vals = [term_value(a, constants) for a in args]
            if any(v is None for v in vals):
                return None
            return AdtValue(name, tuple(v for v in vals if v is not None))
        case RecordTerm(args=args):
            vals = [term_value(a, constants) for a in args]
            if any(v is None for v in vals):
                return None
            return RecordValue(tuple(v for v in vals if v is not None))
        case UnaryTerm(op=UnaryOperator.NEGATE, arg=arg):
            v = term_value(arg, constants)
            return -v if isinstance(v, (int, float)) else None
        case BinaryTerm(op=op, lhs=lhs, rhs=rhs) if op in (
                BinaryOperator.ADD, BinaryOperator.SUB, BinaryOperator.MUL):
            a, b = term_value(lhs, constants), term_value(rhs, constants)
            if not isinstance(a, (int, float)) or not isinstance(b, (int, float)):
                return None
            return a + b if op == BinaryOperator.ADD else (
                a - b if op == BinaryOperator.SUB else a * b)
        case _:
            return None


def row_value(terms: tuple[Term, ...],
              constants: Mapping[str, Value]) -> Row | None:
    """The row the terms state (`term_value`), None where a term states no
    constant."""
    vals = [term_value(t, constants) for t in terms]
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
    lib_types = [t for t in program.types if t.span.file is not None]
    box = {BOX} if any(t.name == BOX for t in lib_types) else set[str]()
    aliases = {t.name: t.target for t in lib_types if isinstance(t, AliasType)}
    grown = bool(box)
    while grown:
        more = {n for n, of in aliases.items() if of in box} - box
        box |= more
        grown = bool(more)
    constants: dict[str, Value] = {}
    pending = [d for d in program.defines if d.file is not None
               and d.params is None and d.value is not None]
    while pending:
        left = []
        for d in pending:
            assert d.value is not None
            v = term_value(d.value, constants)
            if v is None:
                left.append(d)
            else:
                constants[d.name] = v
        if len(left) == len(pending):
            break
        pending = left
    elems = {r.name: r.columns[0].type for r in program.relations
             if r.span.file is not None and r.scope == TOP
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
                    rel = getattr(getattr(lit, "atom", None), "relation", None)
                    if isinstance(rel, RelationName) and not rel.instances \
                            and rel.name in elems and rel.name not in seen:
                        got += members(rel.name, seen | {rel.name})
            out += [m for m in got if m not in out]
        return out

    orientation = {t: tuple(members(n, frozenset({n})))
                   for n, t in elems.items()}
    return Lib(frozenset(box), orientation, constants)


# Reading the case type


def _own_types(program: Program) -> dict[str, TypeDecl]:
    """The top-level types of the solver's own text, by name."""
    return {t.name: t for t in program.types
            if t.span.file is None and t.scope == TOP}


def _branch_comment(program: Program, adt: AdtType,
                    index: int) -> tuple[int, ...]:
    """The lines of the own-line comments above constructor `index`, below
    the constructor before it or the type's first line."""
    start = adt.span.first if index == 0 \
        else adt.constructors[index - 1].span.last
    end = adt.constructors[index].span.first
    return tuple(sorted(c.line for c in program.comments
                        if c.file is None and c.own_line
                        and start < c.line < end))


def _points(program: Program, adt: AdtType, path: tuple[str, ...],
            types: Mapping[str, TypeDecl], seen: frozenset[str]
            ) -> list[ChoicePoint]:
    ctors = tuple(ConstructorBranch(c.name, c.fields,
                                    _branch_comment(program, adt, i),
                                    c.span.first, c.own_line)
                  for i, c in enumerate(adt.constructors))
    out = [ChoicePoint(path, adt.name, adt.id, ctors)]
    for c in adt.constructors:
        for f in c.fields:
            t = types.get(f.type)
            if isinstance(t, AdtType) and t.name not in seen:
                out += _points(program, t, (*path, c.name, f.name), types,
                               seen | {t.name})
    return out


def read_choice(program: Program, problems: list[Fault]
                ) -> Choice | None:
    """The `Choice` type (solver-file.md:97-110, :124-131): an ADT, or a
    record whose fields are ADTs, each ADT a choice point, and each ADT a
    field of a constructor stands in takes a point of its own."""
    types = _own_types(program)
    root = types.get(CHOICE)
    if root is None:
        return None
    if isinstance(root, AdtType):
        return Choice(root.id, None,
                      tuple(_points(program, root, (), types,
                                    frozenset({root.name}))))
    if isinstance(root, RecordType):
        points: list[ChoicePoint] = []
        for f in root.fields:
            t = types.get(f.type)
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


def value_at(choice: Choice, base: Base, path: tuple[str, ...]
             ) -> Value | None:
    """The value at a point's path in `base`, None where the base does not
    reach the point (a constructor on the path is another)."""
    value: Value = base
    steps = list(path)
    if choice.record is not None and steps:
        names = [f.name for f in choice.record]
        field = steps.pop(0)
        if not isinstance(value, RecordValue) or field not in names:
            return None
        value = value.fields[names.index(field)]
    while steps:
        ctor, field = steps.pop(0), steps.pop(0)
        if not isinstance(value, AdtValue) or value.constructor != ctor:
            return None
        point = next((p for p in choice.points
                      if any(c.name == ctor for c in p.constructors)), None)
        if point is None:
            return None
        decl = next(c for c in point.constructors if c.name == ctor)
        names = [f.name for f in decl.fields]
        if field not in names:
            return None
        value = value.args[names.index(field)]
    return value


def with_value_at(choice: Choice, base: Base, path: tuple[str, ...],
                  value: Value) -> Base | None:
    """`base` with `value` at a point's path; None where the base does not
    reach the point (`value_at`)."""
    if not path:
        return value if isinstance(value, AdtValue | RecordValue) else None
    if choice.record is not None:
        names = [f.name for f in choice.record]
        if not isinstance(base, RecordValue) or path[0] not in names:
            return None
        i = names.index(path[0])
        inner = _with_in_adt(choice, base.fields[i], path[1:], value)
        if inner is None:
            return None
        return RecordValue((*base.fields[:i], inner, *base.fields[i + 1:]))
    got = _with_in_adt(choice, base, path, value)
    return got if isinstance(got, AdtValue | RecordValue) else None


def _with_in_adt(choice: Choice, at: Value, path: tuple[str, ...],
                 value: Value) -> Value | None:
    """`with_value_at` below a record field: `path` alternates a
    constructor and one of its fields."""
    if not path:
        return value
    ctor, field = path[0], path[1]
    if not isinstance(at, AdtValue) or at.constructor != ctor:
        return None
    point = next((p for p in choice.points
                  if any(c.name == ctor for c in p.constructors)), None)
    if point is None:
        return None
    decl = next(c for c in point.constructors if c.name == ctor)
    names = [f.name for f in decl.fields]
    if field not in names:
        return None
    i = names.index(field)
    inner = _with_in_adt(choice, at.args[i], path[2:], value)
    if inner is None:
        return None
    return AdtValue(ctor, (*at.args[:i], inner, *at.args[i + 1:]))


def takes_constructor(choice: Choice, base: Base | None,
                      ctor: ConstructorBranch) -> bool:
    """Whether `base` has `ctor` at its point."""
    if base is None:
        return False
    at = value_at(choice, base, point_at(choice, ctor).path)
    return isinstance(at, AdtValue) and at.constructor == ctor.name


def every_base(choice: Choice) -> tuple[Base, ...] | None:
    """Every `Choice` value, for a solver that has no `impl_choice`
    (solver-file.md:110: the cases are every combination of the fields);
    None where a field is of a type with no ADT to enumerate."""
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
    return next((c for c in program.components
                 if c.name == name and own(c.span) and c.scope == TOP), None)


def instance_of(program: Program, component: str) -> Instance | None:
    """The top-level instance of `component` the solver's own text makes."""
    return next((i for i in program.instances
                 if i.component == component and i.scope == TOP
                 and own(i.span)), None)


def read_params(program: Program, annotations: Annotations,
                constants: Mapping[str, Value],
                lists_case: Callable[[CaseMarker], bool],
                problems: list[Fault]) -> Params:
    """The relations of `Params` (solver-file.md:112-117). A relation that
    a clause of `Params` feeds, other than a RIGID block's relations, which
    its closure places, is derived data (solver-file.md:113), listed
    apart with whether a `Determine` relation of its name mirrors it
    (solver-file.md:160). Every other relation is a parameter, with its
    stored facts or GRID calls, whether a `Determine` relation of its name
    mirrors it (solver-file.md:158); each with the section it stands in
    (`section_at`)."""
    comp = _component(program, PARAMS)
    if comp is None or comp.span is None:
        return Params(())
    scope = Scope((PARAMS,))
    determined = {r.name for r in program.relations
                  if r.scope == Scope((DETERMINE,)) and r.span.file is None}
    markers = [m for m in annotations.markers
               if comp.span.first <= m.line <= comp.span.last]
    rigid = {n for m in program.macros if isinstance(m, RigidCall)
             and m.scope == scope for n in m.names} | {
        r.name for r in program.relations
        if r.scope == scope and r.chart_of is not None}
    fed = {u.head.relation.name for u in program.units
           if u.scope == scope and u.body is not None and own(u.span)
           and not u.head.relation.instances} - rigid
    out: list[Parameter] = []
    derived: list[DerivedRelation] = []
    for rel in program.relations:
        if rel.scope != scope or rel.span.file is not None:
            continue
        if rel.name in fed:
            derived.append(DerivedRelation(
                rel.name, rel.id, rel.columns, rel.name in determined,
                _section(markers, rel.span.first, lists_case)))
            continue
        name = RelationName((), rel.name)
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
    anchor: tuple[int, int] | None = None
    for i, row in enumerate(call.cells):
        cells: list[int | None] = []
        for j, cell in enumerate(row):
            if cell.anchor:
                anchor = (i, j)
            if isinstance(cell.term, Wildcard) \
                    and (call.stamp or call.form is not GridForm.DENSE):
                cells.append(None)
                continue
            value = term_value(cell.term, constants)
            if type(value) is not int:
                return None
            cells.append(value)
        rows.append(tuple(cells))
    return StoredGridCall(keys, call.form, call.stamp, tuple(rows), anchor)


def _section(markers: Sequence[CaseMarker], line: int,
             lists_case: Callable[[CaseMarker], bool]) -> Section:
    """The section a line stands in among the markers of its part of the
    file: unmarked above the first marker that lists a case (style.md:57),
    else under the nearest marker above it, whatever it lists."""
    above = [m for m in markers if m.line < line]
    if any(lists_case(m) for m in above):
        return UnderMarker(above[-1])
    return Unmarked()


def section_at(solver: Solver, scope: Scope, line: int) -> Section:
    """The section a line of the solver's own text stands in
    (solver-file.md:104-107): among the markers inside the top-level
    component the line's scope stands in, or for a top-level line, among
    the markers outside every component (`_section`)."""
    return _sections(solver)(scope, line)


def _sections(solver: Solver) -> Callable[[Scope, int], Section]:
    """`section_at` for one solver, with each marker's listing read
    once."""
    spans = {c.name: c.span for c in solver.program.components
             if c.scope == TOP and own(c.span) and c.span is not None}
    markers = solver.annotations.markers
    listing = {m.line: lists_case(solver, m) for m in markers}
    outside = [m for m in markers
               if not any(s.first <= m.line <= s.last for s in spans.values())]

    def at(scope: Scope, line: int) -> Section:
        if scope.components:
            span = spans.get(scope.components[0])
            region = [] if span is None else [
                m for m in markers if span.first <= m.line <= span.last]
        else:
            region = outside
        return _section(region, line, lambda m: listing[m.line])
    return at


# Reading the branches


def _decl(program: Program, id: DeclId) -> RelationDecl | Instance | None:
    """The relation or instance `id` names, None for any other
    declaration."""
    for r in program.relations:
        if r.id == id:
            return r
    for i in program.instances:
        if i.id == id:
            return i
    return None


def _relations_of(program: Program, component: str) -> set[str]:
    """The relations a component declares, its bases' included."""
    out: set[str] = set()
    for name in _chain(program, component):
        out |= {r.name for r in program.relations
                if r.scope.components[-1:] == (name,)}
    return out


def _chain(program: Program, component: str) -> list[str]:
    """The component and the components it extends, in order."""
    out: list[str] = []
    name: str | None = component
    while name is not None and name not in out:
        out.append(name)
        comp = next((c for c in program.components if c.name == name), None)
        name = None if comp is None else comp.base
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
    for name in chain:
        out += [RelationName((), r.name) for r in program.relations
                if r.scope.components[-1:] == (name,)]
        for i in program.instances:
            if i.scope.components[-1:] == (name,):
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
    """The branches of the `@derive` and `@store` lines (solver-file.md:120,
    :137), and `<param>=stored` at each `@derive` point (history 1103), in
    file order: a point's stored branch before its `@derive` branches. A
    second line of one branch's name holds no branch of its own."""

    def unplaced(line: int, word: str) -> None:
        problems.append(Fault(ProblemKind.DIRECTIVE_UNPLACED,
                                       InSolver(line), Named(word)))

    found: list[tuple[int, Branch]] = []
    stored_at: set[str] = set()
    names: set[tuple[str, ...]] = set()
    for d in annotations.derives:
        decl = None if d.above is None else _decl(program, d.above)
        if not isinstance(decl, RelationDecl) or decl.scope != Scope((PARAMS,)):
            unplaced(d.line, "derive")
            continue
        if proposers is not None and d.proposer not in proposers:
            problems.append(Fault(ProblemKind.UNKNOWN_PROPOSER,
                                           InSolver(d.line),
                                           Named(d.proposer)))
        if decl.name not in stored_at:
            stored_at.add(decl.name)
            found.append((d.line, StoredAtDerive(decl.name)))
        key = ("derive", decl.name, d.proposer)
        if key not in names:
            names.add(key)
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
                    Named(RelationName((decl.name,), s.relation).text)))
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
            unplaced(s.line, "store")
            continue
        key = ("store", *rel.instances, rel.name)
        if key not in names:
            names.add(key)
            found.append((s.line, StoreBranch(rel, spelled, s)))
    for i in annotations.ignores:
        if i.form is IgnoreForm.LINT or i.name is not None:
            continue
        if not ignore_targets(program, i):
            unplaced(i.line, "ignore")
    return tuple(b for _l, b in sorted(found, key=lambda f: f[0]))


def ignore_targets(program: Program, line: IgnoreLine
                   ) -> tuple[RelationName, ...]:
    """The parameters or relations a bare `@ignore: derive` or `@ignore:
    store` line stands on (solver-file.md:122, :138), which are those a
    directive in its place stands on: a parameter's `.decl` for the derive
    form; for the store form, a relation's `.decl`, and above a `.init`
    the relation the line states, or with none stated every relation of
    the instance (solver-file.md:135). Empty where it stands on nothing its
    form takes."""
    decl = None if line.above is None else _decl(program, line.above)
    if line.form is IgnoreForm.DERIVE:
        if isinstance(decl, RelationDecl) and decl.scope == Scope((PARAMS,)) \
                and line.relation is None:
            return (RelationName((), decl.name),)
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
    runs it."""
    return parse_with_lib(engine, proposers_path().read_text())


def proposer_names(program: Program) -> tuple[str, ...]:
    """The proposers: the components of the proposers program, which is
    `proposers.dl` alone, that declare `propose` (proposers.dl's
    header)."""
    return tuple(c.name for c in program.components
                 if any(r.name == PROPOSE and r.scope.components[-1:]
                         == (c.name,) for r in program.relations))


# Load


def _empty_program() -> Program:
    """A program with no part, for a solver whose text does not parse."""
    return Program((), (), (), (), (), (), (), (), (), ())


def task_id_of(stem: str) -> str:
    """The task a solver's stem names: its leading eight hex digits."""
    m = _STEM_RE.match(stem)
    return m[0] if m else stem


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
    by_scope: dict[str | None, dict[str, Instance]] = {}
    for i in program.instances:
        by_scope.setdefault(i.scope.components[-1] if i.scope.components
                            else None, {})[i.name] = i
    out: list[Fault] = []

    def fault(kind: ProblemKind, span: Span | None, start: int,
              name: str) -> None:
        got = Fault(kind, InSolver(span.first if own(span) and span
                                   is not None else start), Named(name))
        if got not in out:
            out.append(got)

    def chain(comp: str | None, start: int) -> list[str | None]:
        seen: list[str | None] = [comp]
        while comp is not None:
            c = comps.get(comp)
            if c is None or c.base is None or c.base in seen:
                break
            if c.base not in comps:
                fault(ProblemKind.BASE_OF_NOTHING, c.span, start, c.base)
                break
            if len(c.base_type_args) != len(comps[c.base].type_params):
                fault(ProblemKind.TYPE_ARGUMENTS, c.span, start, c.base)
            comp = c.base
            seen.append(comp)
        return seen

    front: list[tuple[tuple[str, ...], str | None, int]] = [((), None, 0)]
    while front:
        at, here, start = front.pop(0)
        for scope in chain(here, start):
            for name, inst in by_scope.get(scope, {}).items():
                line = start if at else (
                    inst.span.first if inst.span is not None else 0)
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
                              ".".join(path))
                    continue
                front.append((path, comp.name, line))
    params = Scope((PARAMS,))
    for m in program.macros:
        if isinstance(m, RigidCall) and m.scope == params and len(
                [r for r in program.relations if r.scope == params
                 and r.chart_of == m.block]) != len(m.names):
            fault(ProblemKind.RIGID_CHARTS, m.span, 0, m.block)
    return out


def load(stem: str, engine: Engine) -> Solver:
    """The solver of `stem`, the one entry every command uses. Every solver
    reads the lib: `load` adds the lib's `#include` to the text when the
    text lacks it, and parses it against the solvers directory.

    The include goes above the text with a `#line 1` directive after it,
    so every line of the solver keeps its number in the parse."""
    task_id = task_id_of(stem)
    problems: list[Fault] = []
    parsed = parse_with_lib(engine,
                            (checkout.solvers() / f"{stem}.dl").read_text())
    if isinstance(parsed, ParseFailure):
        problems.append(Fault(ProblemKind.PARSE_FAILURE,
                                       InSolver(parsed.line), parsed))
        program = _empty_program()
        lib_parse = engine.parse(LIB_INCLUDE, checkout.solvers())
        lib = read_lib(lib_parse if isinstance(lib_parse, Program)
                       else _empty_program())
    else:
        program = parsed
        lib = read_lib(program)
    annotations, read_problems = annotations_reader.read(program)
    problems += read_problems
    declared = {c.name for c in program.components}
    problems += [Fault(ProblemKind.INSTANCE_OF_NOTHING,
                                InSolver(i.span.first), Named(i.component))
                 for i in program.instances
                 if own(i.span) and i.span is not None
                 and i.component not in declared]
    problems += instance_faults(program)
    choice = read_choice(program, problems)
    if choice is not None and not enumerates(program) \
            and every_base(choice) is None:
        problems.append(Fault(
            ProblemKind.UNDECIDED,
            InSolver(next(t.span.first for t in program.types
                          if t.id == choice.declaration)),
            Undecided(UndecidedForm.CHOICE_NOT_ENUMERABLE, None)))
    proposers: frozenset[str] | None = None
    if annotations.derives:
        probe_program = proposers_program(engine)
        if isinstance(probe_program, Program):
            proposers = frozenset(proposer_names(probe_program))
    branches = read_branches(program, annotations, proposers, problems)
    unread = Solver(stem, task_id, program, annotations, choice, branches,
                    Params(()), None, None, lib, ())
    params = read_params(program, annotations, lib.constants,
                         lambda m: lists_case(unread, m), problems)
    try:
        task: Task | None = arc_task.load(task_id)
    except FileNotFoundError:
        task = None
    witness_file = None
    wpath = witness_reader.path(task_id)
    if wpath.exists():
        witness_file, file_problems = witness_reader.read(wpath.read_text())
        problems += file_problems
        if witness_file is not None:
            grid_names = frozenset(p.name for p in params.parameters
                                   if isinstance(p.stored, StoredGrid))
            witness_file, grid_problems = witness_reader.with_grids(
                witness_file, grid_names)
            problems += grid_problems
    if annotations.representative is not None and not (
            checkout.solvers()
            / f"{annotations.representative.task_id}.dl").exists():
        problems.append(Fault(
            ProblemKind.REPRESENTATIVE_MISSING,
            InSolver(annotations.representative.line),
            Named(annotations.representative.task_id)))
    solver = Solver(stem, task_id, program, annotations, choice, branches,
                    params, witness_file, task, lib, tuple(problems))
    named = tuple(_name_problems(solver))
    if named:
        solver = Solver(stem, task_id, program, annotations, choice,
                        branches, params, witness_file, task, lib,
                        tuple(problems) + named)
    return solver


def lists_case(solver: Solver, marker: CaseMarker) -> bool:
    """Whether a marker lists a case: a part of it denotes one."""
    from solver.names import Denoted, denote
    return any(isinstance(denote(solver, p.name), Denoted)
               for p in marker.parts)


def _name_problems(solver: Solver) -> Iterator[Fault]:
    """The names the solver and its witness file hold that denote nothing:
    verdicts, markers, named `@ignore` lines, group names, and `assign`
    keys and constants."""
    from solver.names import denote, names_a_constructor

    def check(name: str | tuple[str, ...], line: int
              ) -> Iterator[Fault]:
        got = denote(solver, name)
        if isinstance(got, Fault):
            yield Fault(got.kind, InSolver(line), got.detail)

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
            if not isinstance(got, Fault):
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
    params = {p.name for p in solver.params.parameters}
    stored = {b.spelled for b in solver.branches
              if isinstance(b, StoreBranch)}
    for e in solver.witness_file.entries:
        if isinstance(e.output, Groups):
            for g in e.output.groups:
                for name in g.cases:
                    got = denote(solver, name)
                    if isinstance(got, Fault):
                        yield Fault(got.kind, InWitnessFile(e.id),
                                             got.detail)
        for key, value in e.assign:
            if key not in params and key not in stored:
                yield Fault(ProblemKind.ASSIGN_NAMES_NOTHING,
                                     InWitnessFile(e.id), Named(key))
            if isinstance(value, AssignRows):
                for s in _strings(value.rows):
                    if s not in solver.lib.constants:
                        yield Fault(ProblemKind.ASSIGN_NAMES_NOTHING,
                                             InWitnessFile(e.id), Named(s))


def _strings(args: tuple[AssignArg, ...] | tuple[tuple[AssignArg, ...], ...]
             ) -> Iterator[str]:
    """Every string among `assign` arguments, records opened."""
    for a in args:
        if isinstance(a, str):
            yield a
        elif isinstance(a, tuple):
            yield from _strings(a)


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
    stranded: Mapping[tuple[UnitId, str], tuple[Base | None, ...]] = field(
        default_factory=dict[tuple[UnitId, str], tuple[Base | None, ...]])
    """Each unit that feeds a relation a base's walk reads, where the
    unit's marker section does not list the base and no unit the walk
    reads under a section that lists the base, or under no marker, feeds
    that relation; with the relation as a top-level clause names it, or
    the instance of a lib component by its path."""


DEPENDENCE_HELD = 32
"""The most results of `dependence` one process holds."""

_DEPENDENCE: OrderedDict[tuple[tuple[int, ...], tuple[Base | None, ...]],
                         tuple[tuple[object, ...], Dependence]] = OrderedDict()
_DEPENDENCE_LOCK = threading.Lock()
_DEPENDENCE_BUSY: dict[tuple[tuple[int, ...], tuple[Base | None, ...]],
                       threading.Lock] = {}


def dependence(solver: Solver, bases: Sequence[Base | None]) -> Dependence:
    """Which of `bases` have a derivation of `out` that depends on each
    unit, parameter and relation of the solver's own text
    (solver-file.md:98, :104-110, :120, :137).

    The result is a function of the solver's model, the program's
    declarations and the units of the solver's own text, whose rows are
    the rows the walk reads; a unit an operation wrote (`own`) is none of
    them. So it is computed once for each distinct such input, by the
    identity of those parts: a variation that fixes a parameter's value
    removes the same own units whatever the value, and a deletion removes
    its own.

    A unit of a component runs at each instance of the component, and a
    relation of a component is one relation per instance (`Graph`). A
    base's model reads its grids from `out` at its case, so its derivation
    depends on each unit that heads `out` and admits it, and, from each
    unit it depends on, on each unit that heads a relation that unit reads
    and admits it. A unit whose head has a case column, a column of
    `Choice` (the case column `ch`, solver-file.md:108), of a type that
    stands in `Choice`, or of a record type with a field of such a type,
    admits a base when the base's value can stand in each term the head
    holds there, whatever carries the value there (`_Cases`). A unit whose
    head has none admits every base, whatever section it stands in, since
    the program runs it for every case. Either unit admits only the bases
    whose value can stand in the term of
    an `impl_choice` atom of its body. A read asks for the rows its terms
    fix: where a read holds a constant constructor in a column of a type
    that stands at one choice point, or a constant `Choice` value, it asks
    for the rows that hold that value there, whatever the base holds, and
    the units it reaches are read for the base with that value at that
    point (`_Cases.demand`); so `near_arm($Clear(), P, D) :-
    near_arm($Any(), P, D)` reads the `$Any()` clauses for a base that
    takes `$Clear`. A read of a relation of an instance
    of a lib component reads every unit that feeds the instance. A base's
    derivation depends on a parameter where it depends on a unit that
    reads it, and on a relation where it depends on a unit that reads it
    or a unit that feeds it. Where every unit that feeds a relation a
    base's walk reaches, for the rows the walk asks for there, stands
    under a marker that does not list the base
    (`section_at`, solver-file.md:104), those units are reported with the
    base (`Dependence.stranded`)."""
    program = solver.program
    held: tuple[object, ...] = (
        solver.stem, solver.task_id, solver.annotations, solver.choice,
        solver.branches, solver.params, solver.witness_file, solver.task,
        solver.lib, solver.problems, program.types, program.relations,
        program.components, program.instances, program.functors,
        program.comments, program.includes, program.defines,
        *(u for u in program.units if own(u.span)))
    key = (tuple(map(id, held)), tuple(bases))
    with _DEPENDENCE_LOCK:
        busy = _DEPENDENCE_BUSY.setdefault(key, threading.Lock())
    with busy:
        with _DEPENDENCE_LOCK:
            got = _DEPENDENCE.get(key)
            if got is not None:
                _DEPENDENCE.move_to_end(key)
                return got[1]
        result = _dependence(solver, bases)
        with _DEPENDENCE_LOCK:
            _DEPENDENCE[key] = (held, result)
            while len(_DEPENDENCE) > DEPENDENCE_HELD:
                _DEPENDENCE.popitem(last=False)
            _DEPENDENCE_BUSY.pop(key, None)
    return result


def _dependence(solver: Solver, bases: Sequence[Base | None]) -> Dependence:
    """`dependence`, computed."""
    from solver.names import lists

    graph = Graph(solver.program)
    cases = _Cases(graph, solver.choice)
    section_at = _sections(solver)
    listing = {m.line: lists_case(solver, m)
               for m in solver.annotations.markers}
    marker_of: dict[UnitId, CaseMarker | None] = {}
    terms_of: dict[Placed, list[tuple[str, Term]]] = {}
    for u in graph.units:
        section = section_at(u.scope, 0 if u.span is None else u.span.first)
        for at in graph.paths_of(u):
            _column, terms_of[(u, at)] = cases.checks(u, at)
        marker_of[u.id] = section.marker if isinstance(
            section, UnderMarker) and listing[section.marker.line] else None
    markers = sorted({m.line: m for m in marker_of.values()
                      if m is not None}.values(), key=lambda m: m.line)
    by_unit: dict[UnitId, list[Base | None]] = {}
    by_param: dict[str, list[Base | None]] = {}
    by_relation: dict[RelationName, list[Base | None]] = {}
    by_stranded: dict[tuple[UnitId, str], list[Base | None]] = {}
    for base in bases:
        listed = {m.line: any(lists(solver, p, base) for p in m.parts)
                  for m in markers}

        def admits(placed: Placed, wanted: Base | None) -> bool:
            return all(cases.admits(placed, t, term, wanted)
                       for t, term in terms_of[placed])

        def unlisted(placed: Placed,
                     listed: Mapping[int, bool] = listed) -> bool:
            m = marker_of[placed[0].id]
            return m is not None and not listed[m.line]

        units, nodes, names, stranded = graph.read(
            admits, base, cases.demand, unlisted)
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
              if r.scope == Scope((PARAMS,))]
    return Dependence(
        {u.id: tuple(by_unit[u.id]) for u in graph.units if u.id in by_unit},
        {p: tuple(by_param[p]) for p in params if p in by_param},
        {r: tuple(by_relation[r])
         for r in sorted(by_relation, key=lambda r: r.text)},
        {k: tuple(by_stranded[k]) for k in sorted(
            by_stranded, key=lambda k: (k[0].index, k[1]))})


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

    def __init__(self, program: Program) -> None:
        self.program = program
        self.components = {c.name: c for c in program.components}
        self.relations: dict[str | None, dict[str, RelationDecl]] = {}
        for r in program.relations:
            self.relations.setdefault(
                r.scope.components[-1] if r.scope.components else None,
                {})[r.name] = r
        self.instances: dict[str | None, dict[str, Instance]] = {}
        for i in program.instances:
            self.instances.setdefault(
                i.scope.components[-1] if i.scope.components else None,
                {})[i.name] = i
        self.args: dict[InstancePath, dict[str, str]] = {(): {}}
        self.comp: dict[InstancePath, str] = {}
        self.inst_scope: dict[InstancePath, tuple[str, ...]] = {}
        """The scope whose text declares the instance at each path."""
        self.own_types = {(t.scope.components, t.name)
                          for t in program.types if own(t.span)}
        front: list[InstancePath] = [()]
        while front:
            at = front.pop(0)
            if len(at) > MAX_DEPTH:
                continue
            for name in self._instance_names(self.component_at(at)):
                inst = self._instance(self.component_at(at), name)
                comp = None if inst is None \
                    else self.components.get(inst.component)
                if inst is None or comp is None:
                    continue
                path = (*at, name)
                self.comp[path] = comp.name
                self.inst_scope[path] = inst.scope.components
                self.args[path] = self._chain_args(
                    comp, {p: self.args[at].get(a, a) for p, a in zip(
                        comp.type_params, inst.type_args, strict=False)})
                if own(comp.span):
                    front.append(path)
        self.units = [u for u in program.units if own(u.span)]
        self._full: dict[InstancePath, str] | None = None
        self._reach: frozenset[RelationName] | None = None
        self.heads: dict[Node, list[Placed]] = {}
        for u in self.units:
            for at in self.paths_of(u):
                node = self.resolve(at, u.head.relation)
                if node is not None:
                    self.heads.setdefault(node, []).append((u, at))

    def component_at(self, path: InstancePath) -> str | None:
        """The component of the instance at `path`; None for the top
        level."""
        return self.comp.get(path) if path else None

    def _chain(self, comp: str | None) -> list[str | None]:
        """A component and each component it extends, in turn."""
        out: list[str | None] = [comp]
        while comp is not None:
            c = self.components.get(comp)
            comp = None if c is None or c.base in out else c.base
            if comp is not None:
                out.append(comp)
        return out

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
        comp = unit.scope.components[-1]
        return [p for p, c in self.comp.items()
                if comp in self._chain(c) and own(
                    self.components[c].span)]

    def _walk(self, at: InstancePath, rel: RelationName
              ) -> tuple[InstancePath, Instance | None] | None:
        """The instance path `rel`'s qualifiers lead to from `at`, and the
        lib instance they stop at, where they stop at one."""
        for name in rel.instances:
            found = next((q for q in (at[:n] for n in range(len(at), -1, -1))
                          if self._instance(self.component_at(q), name)
                          is not None), None)
            if found is None:
                return None
            at = (*found, name)
            if at not in self.comp:
                return None
            if not own(self.components[self.comp[at]].span):
                inst = self._instance(self.component_at(found), name)
                return at, inst
        return at, None

    def resolve(self, at: InstancePath, rel: RelationName) -> Node | None:
        """The node a unit at `at` reads or heads by the name `rel`; None
        where no declaration gives it."""
        got = self._walk(at, rel)
        if got is None:
            return None
        path, lib = got
        if lib is not None:
            return Node(NodeKind.INSTANCE, path, "")
        for q in (path[:n] for n in range(len(path), -1, -1)):
            if self._relation(self.component_at(q), rel.name) is not None:
                return Node(NodeKind.RELATION, q, rel.name)
        return None

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
            return None if d is None else (d, self.args.get(node.path, {}))
        d = self._relation(self.comp[node.path], rel.name)
        return None if d is None else (d, self.args[node.path])

    def column_types(self, at: InstancePath, rel: RelationName
                     ) -> list[str] | None:
        """The type of each column of the relation a unit at `at` names by
        `rel`, as `type_key` names it: a column's own type resolved in the
        scope that declares the relation, a type parameter's argument in
        the scope that declares the instance; None where it is no
        declaration the solver can read."""
        node = self.resolve(at, rel)
        got = self.decl(at, rel)
        if node is None or got is None:
            return None
        decl, args = got
        held = self.inst_scope.get(node.path, ())
        return [self.resolve_type(args[c.type], held) if c.type in args
                else self.resolve_type(c.type, decl.scope.components)
                for c in decl.columns]

    def type_key(self, scope: tuple[str, ...], name: str) -> str:
        """A type of the solver's own text by the scope that declares it
        and its name: the name for a top-level type, else the scope's
        components and the name joined by dots, so that two components
        that declare one name name two types."""
        return ".".join((*scope, name))

    def resolve_type(self, name: str, scope: tuple[str, ...]) -> str:
        """The type `name` denotes when read in `scope`: the nearest scope
        around it, itself first, whose own text declares the name, as
        `type_key` names it; the name itself where no own text declares
        it, as for a lib or built-in type."""
        for k in range(len(scope), -1, -1):
            if (scope[:k], name) in self.own_types:
                return self.type_key(scope[:k], name)
        return name

    def read[D](self, admits: Callable[[Placed, D], bool], start: D,
                demand: Callable[[Placed, Atom, D], D],
                unlisted: Callable[[Placed], bool] | None = None
                ) -> tuple[list[UnitId], list[Node], set[RelationName],
                           list[tuple[UnitId, str]]]:
        """What one base's derivation depends on (`dependence`): the
        units, the nodes, and the relations by the names a top-level clause
        reads them by. A read asks for rows of what it demands, `start` at
        `out`: `demand` gives what a unit's read of an atom asks for,
        from what the unit was reached for, and `admits` tells the placed
        units whose head can hold such a row. Last, at each node where
        every admitted unit that feeds it is one `unlisted` names, those
        units, each with the node: the relation as a top-level clause
        names it, or an instance of a lib component by its path."""
        units: dict[UnitId, None] = {}
        placed: set[tuple[UnitId, InstancePath, int]] = set()
        nodes: dict[Node, None] = {}
        names: set[RelationName] = set()
        front: list[tuple[Unit, InstancePath, D]] = []
        asked: set[tuple[Node, int]] = set()
        stranded: dict[tuple[UnitId, str], None] = {}
        # What a read asks for is keyed by identity: `demand` gives one
        # object per distinct result of a read, and the values are
        # records whose hash walks every field.

        def reach(node: Node, wanted: D) -> None:
            if (node, id(wanted)) in asked:
                return
            asked.add((node, id(wanted)))
            nodes[node] = None
            fed = False
            held: list[UnitId] = []
            for u, at in self.heads.get(node, ()):
                if (u.id, at, id(wanted)) not in placed:
                    if not admits((u, at), wanted):
                        continue
                    placed.add((u.id, at, id(wanted)))
                    units[u.id] = None
                    front.append((u, at, wanted))
                    names.add(self.top_name(node, u.head.relation.name))
                if unlisted is not None and unlisted((u, at)):
                    held.append(u.id)
                else:
                    fed = True
            if not fed:
                text = ".".join(node.path) if node.kind is NodeKind.INSTANCE \
                    else RelationName(node.path, node.name).text
                for uid in held:
                    stranded[(uid, text)] = None

        reach(Node(NodeKind.RELATION, (), OUTPUT.name), start)
        while front:
            u, at, wanted = front.pop()
            for atom in (a for lit in u.body or () for a in atoms_of(lit)):
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
                if not u.scope.components:
                    paths: list[InstancePath] = [()]
                else:
                    comp = u.scope.components[-1]
                    paths = [p for p, c in tree.items()
                             if comp in self._chain(c)]
                for at in paths:
                    for atom in (a for lit in u.body or ()
                                 for a in atoms_of(lit)):
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
            full: dict[InstancePath, str] = {}
            front: list[InstancePath] = [()]
            while front:
                at = front.pop(0)
                if len(at) > MAX_DEPTH:
                    continue
                here = full.get(at) if at else None
                for name in self._instance_names(here):
                    inst = self._instance(here, name)
                    if inst is None or inst.component not in self.components:
                        continue
                    path = (*at, name)
                    full[path] = inst.component
                    front.append(path)
            self._full = full
        return self._full

    def _place(self, tree: Mapping[InstancePath, str], at: InstancePath,
               rel: RelationName) -> RelationName | None:
        """The relation a unit at `at` names by `rel`, by the instance path
        it stands at and its name; None where no declaration gives it."""
        for name in rel.instances:
            found = next((q for q in (at[:n] for n in range(len(at), -1, -1))
                          if self._instance(tree.get(q) if q else None, name)
                          is not None), None)
            if found is None:
                return None
            at = (*found, name)
            if at not in tree:
                return None
        for q in (at[:n] for n in range(len(at), -1, -1)):
            if self._relation(tree.get(q) if q else None,
                              rel.name) is not None:
                return RelationName(q, rel.name)
        return None

    def relation_decl(self, node: Node) -> RelationDecl | None:
        """The declaration of a relation node; None for an instance of a
        lib component, whose relations the node stands for together."""
        if node.kind is not NodeKind.RELATION:
            return None
        return self._relation(self.component_at(node.path), node.name)

    def top_name(self, node: Node, name: str) -> RelationName:
        """The name a top-level clause reads a node's relation by, where
        a unit read it by `name`."""
        return RelationName(node.path, node.name
                            if node.kind is NodeKind.RELATION else name)


def atoms_of(lit: BodyLiteral) -> Iterator[Atom]:
    """Every atom a body literal reads, negated ones, those of its
    aggregates and those of its disjunctions included."""
    match lit:
        case AtomLiteral(atom=atom):
            yield atom
            for a in atom.args:
                yield from _term_atoms(a)
        case Comparison(lhs=lhs, rhs=rhs):
            yield from _term_atoms(lhs)
            yield from _term_atoms(rhs)
        case Disjunction(branches=branches):
            for branch in branches:
                for sub in branch:
                    yield from atoms_of(sub)
        case _:
            pass


def _term_atoms(term: Term) -> Iterator[Atom]:
    """Every atom the aggregates inside a term read."""
    match term:
        case Aggregate(expr=expr, body=body):
            if expr is not None:
                yield from _term_atoms(expr)
            for lit in body:
                yield from atoms_of(lit)
        case ConstructorTerm(args=args) | RecordTerm(args=args) \
                | IntrinsicCall(args=args) | FunctorCall(args=args):
            for a in args:
                yield from _term_atoms(a)
        case UnaryTerm(arg=arg):
            yield from _term_atoms(arg)
        case BinaryTerm(lhs=lhs, rhs=rhs):
            yield from _term_atoms(lhs)
            yield from _term_atoms(rhs)
        case _:
            pass


def _holds_case(term: Term) -> bool:
    """Whether a term holds a constructor or a record, which a case value
    it is compared with must match."""
    return isinstance(term, (ConstructorTerm, RecordTerm))


class _Cases:
    """Where a unit's rows hold a case value, and whether a base's value
    can stand there (`dependence`).

    A case value stands in a column of a case type: `Choice`, a type that
    stands in `Choice`, or a record type of the solver's own text with a
    field of a case type, the value then standing in that field. A term
    there admits a base where the base's value can stand in it. A variable
    takes the term an equality of the body sets it to. Else, for each
    positive atom of the body that reads it in a column, or in a field of
    a record there, the variable holds one of the terms the rows of that
    column can hold there, read in the unit that heads them: the terms
    each clause of the relation heads in that column, or, for a relation
    of an instance of a lib component, the terms each clause that feeds
    the instance heads in a column of the same type, since a lib
    component builds no value of a type its instance passes it. So
    `cut_choice(S)` with facts `cut_choice($Separator())` and
    `cut_choice($Mirror())` admits only the bases whose value there is
    one of the two, and so does a read of `cut.tile_of(S, _, _)` where
    `cut.cell(S, P) :- cut_choice(S)` feeds the instance. An atom where
    some such clause holds no term there sets no bound."""

    def __init__(self, graph: Graph, choice: Choice | None) -> None:
        self.graph = graph
        self.choice = choice
        self.points = set() if choice is None else {
            p.type for p in choice.points}
        self.records: dict[str, tuple[str, ...]] = {
            graph.type_key(t.scope.components, t.name): tuple(
                graph.resolve_type(f.type, t.scope.components)
                for f in t.fields)
            for t in graph.program.types
            if isinstance(t, RecordType) and own(t.span)}
        self.case_types = {CHOICE, *self.points}
        grown = True
        while grown:
            more = {n for n, fields in self.records.items()
                    if n not in self.case_types
                    and any(f in self.case_types for f in fields)}
            self.case_types |= more
            grown = bool(more)
        self._eq: dict[UnitId, dict[str, Term]] = {}
        self.declared = {graph.type_key(t.scope.components, t.name)
                         if own(t.span) else t.name
                         for t in graph.program.types}
        self._cycles = 0
        """How many reads of a place being read already have been met; a
        result that met none, or holds, is final."""
        self._alts: dict[tuple[UnitId, InstancePath, str], list[list[
            tuple[Placed, Term, tuple[int, ...], str]]]] = {}
        self._admits: dict[tuple[UnitId, InstancePath, str, tuple[int, ...],
                                 str, Base], bool] = {}
        self._fixed: dict[tuple[UnitId, InstancePath, int], tuple[
            tuple[tuple[str, ...] | None, Base], ...]] = {}
        self._demanded: dict[tuple[tuple[UnitId, InstancePath, int], int],
                             tuple[Base, Base]] = {}
        """`demand`'s result by read and by the identity of the base,
        which the entry holds alive, so that equal requests give one
        object."""

    def checks(self, unit: Unit, at: InstancePath
               ) -> tuple[bool, list[tuple[str, Term]]]:
        """Whether the unit's head has a case column, and each term where
        the unit holds a case value, with its type: each term of its head
        in a column of a case type, and each term of an `impl_choice` atom
        of its body."""
        out: list[tuple[str, Term]] = []
        column = False
        for t, term in self._typed(at, unit.head):
            if t in self.case_types:
                column = True
                out.append((t, term))
        for lit in unit.body or ():
            if isinstance(lit, AtomLiteral) and not lit.negated \
                    and lit.atom.relation == RelationName((), ENUMERATOR) \
                    and len(lit.atom.args) == 1:
                out.append((CHOICE, lit.atom.args[0]))
        return column, out

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
            value = term_value(term, {})
            if not isinstance(value, AdtValue | RecordValue):
                continue
            if t == CHOICE:
                out.append((None, value))
                continue
            points = [p for p in choice.points if p.type == t]
            if len(points) == 1 and isinstance(value, AdtValue):
                out.append((points[0].path, value))
        return tuple(out)

    def admits(self, placed: Placed, type: str, term: Term,
               base: Base | None) -> bool:
        """Whether `base`'s value can stand in `term` of type `type`, the
        variables of `term` read in the placed unit."""
        return self._admits_in(placed, type, term, (), base, frozenset())

    def _admits_in(self, placed: Placed, type: str, term: Term,
                   path: tuple[int, ...], base: Base | None,
                   open_: frozenset[tuple[UnitId, InstancePath, str,
                                          tuple[int, ...]]]
                   ) -> bool:
        """`admits` for the part of `term` at `path`, the record fields to
        it, where the places of `open_` are being read already. A value
        reaches such a place again only through another route, so a read
        of it on this path admits nothing, as a recursive clause adds no
        value its other clauses do not give."""
        choice = self.choice
        if choice is None or base is None or type not in self.case_types:
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
            key = (unit.id, at, term.name, path)
            if key in open_:
                self._cycles += 1
                return False
            memo = (unit.id, at, term.name, path, type, base)
            if memo not in self._admits:
                inner = open_ | {key}
                cycles = self._cycles
                got = all(
                    any(self._admits_in(h, type, alt, (*to, *path), base,
                                        inner)
                        for h, alt, to, column in alts
                        if self._may_hold(column, (*to, *path), type))
                    for alts in self._alternatives(placed, term.name))
                if got or cycles == self._cycles:
                    self._admits[memo] = got
                return got
            return self._admits[memo]
        if path:
            return True
        if type in self.records and not (type == CHOICE
                                         and choice.record is None):
            fields = self.records[type]
            if isinstance(term, RecordTerm) and len(term.args) == len(fields):
                return all(self._admits_in(placed, f, a, (), base, open_)
                           for f, a in zip(fields, term.args, strict=True))
            return True
        if type == CHOICE:
            return _matches(term, base)
        return any(v is not None and _matches(term, v)
                   for v in (value_at(choice, base, p.path)
                             for p in choice.points if p.type == type))

    def _equalities(self, unit: Unit) -> dict[str, Term]:
        """The terms the equalities of a unit's body set its variables
        to, where the term holds a constructor or a record."""
        if unit.id not in self._eq:
            eq: dict[str, Term] = {}
            for lit in unit.body or ():
                if isinstance(lit, Comparison) \
                        and lit.op is ComparisonOperator.EQ:
                    if isinstance(lit.lhs, Variable) and _holds_case(lit.rhs):
                        eq[lit.lhs.name] = lit.rhs
                    elif isinstance(lit.rhs, Variable) \
                            and _holds_case(lit.lhs):
                        eq[lit.rhs.name] = lit.lhs
            self._eq[unit.id] = eq
        return self._eq[unit.id]

    def _may_hold(self, column: str, path: tuple[int, ...],
                  type: str) -> bool:
        """Whether a column of type `column`, as the unit that heads it
        types it, can hold a value of `type` at `path`: not where both
        types are declared and differ, since then the clause feeds another
        instance of the component that reads it."""
        for j in path:
            fields = self.records.get(column)
            if fields is None or j >= len(fields):
                return True
            column = fields[j]
        return column == type or column not in self.declared \
            or type not in self.declared

    def _alternatives(self, placed: Placed, var: str
                      ) -> list[list[tuple[Placed, Term, tuple[int, ...],
                                           str]]]:
        """For each place a positive atom of a unit's body reads `var`,
        the terms the rows can hold in that column, each with the unit
        that heads it, the place of `var` in the column, and the column's
        type as that unit types it (`_Cases`)."""
        unit, at = placed
        key = (unit.id, at, var)
        if key not in self._alts:
            out: list[list[tuple[Placed, Term, tuple[int, ...], str]]] = []
            for lit in unit.body or ():
                if not isinstance(lit, AtomLiteral) or lit.negated:
                    continue
                node = self.graph.resolve(at, lit.atom.relation)
                if node is None:
                    continue
                heads = self.graph.heads.get(node, [])
                if not heads:
                    continue
                read = self._typed(at, lit.atom)
                for i, arg in enumerate(lit.atom.args):
                    for path in _paths(arg, var):
                        got = self._held_at(node, heads, i, read)
                        if got:
                            out.append([(h, t, path, c) for h, t, c in got])
            self._alts[key] = out
        return self._alts[key]

    def _held_at(self, node: Node, heads: Sequence[Placed], column: int,
                 read: Sequence[tuple[str, Term]]
                 ) -> list[tuple[Placed, Term, str]] | None:
        """The terms the clauses `heads` of `node` hold in a column a read
        names, each with the column's type as its clause types it
        (`_alternatives`); None where one holds none."""
        out: list[tuple[Placed, Term, str]] = []
        if node.kind is NodeKind.RELATION:
            for h in heads:
                typed = self._typed(h[1], h[0].head)
                if column >= len(typed):
                    return None
                out.append((h, typed[column][1], typed[column][0]))
            return out
        if column >= len(read):
            return None
        type = read[column][0]
        for h in heads:
            out += [(h, term, t) for t, term in self._typed(h[1], h[0].head)
                    if t == type]
        return out or None


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


def enumerates(program: Program) -> bool:
    """Whether the solver's own text declares `impl_choice` at the top
    level (solver-file.md:108)."""
    return any(r.name == ENUMERATOR and r.scope == TOP and r.span.file is None
               for r in program.relations)


def takes(solver: Solver, case: Case, branch: Branch) -> bool:
    """Whether `case` takes `branch`: a `@derive` or `@store` branch it
    lists, or `<param>=stored` where it lists no `@derive` branch of the
    parameter."""
    if isinstance(branch, StoredAtDerive):
        return not any(isinstance(b, DeriveBranch)
                       and b.parameter == branch.parameter
                       for b in case.branches)
    return branch in case.branches


def branch_under(solver: Solver, line: IgnoreLine) -> Branch | None:
    """The branch of the `@derive` or `@store` line a named `@ignore:
    derive` or `@ignore: store` line stands under: the nearest line of its
    kind above it on the same declaration (solver-file.md:122, :138)."""
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
    """Whether the solver's own file declares the top-level `Determine`
    comp that holds its determination (solver-file.md:158)."""
    return any(c.name == DETERMINE and c.scope == TOP and own(c.span)
               for c in solver.program.components)


def is_concept(solver: Solver, base: Base | None) -> bool:
    """Whether `base` is the concept case's: the first constructor at each
    point it reaches (solver-file.md:194; principles.md, "concept
    branch")."""
    choice = solver.choice
    if choice is None or base is None:
        return base is None
    for p in choice.points:
        at = value_at(choice, base, p.path)
        if isinstance(at, AdtValue) \
                and at.constructor != concept_branch(p).name:
            return False
    return True


def column_types(program: Program, relation: RelationName
                 ) -> tuple[str, ...]:
    """The type of each column of `relation`, named from the top level, as
    the model resolves it (`Graph.column_types`), so that a type the
    solver's own text declares in a component is not a top-level type of
    the same name. Raises `ValueError` where the model resolves no
    declaration of the relation."""
    got = Graph(program).column_types((), relation)
    if got is None:
        raise ValueError(f"`{relation.text}` resolves to no declaration")
    return tuple(got)


def ident_keyed(program: Program, relation: RelationName) -> bool:
    """Whether the relation, named from the top level, has a column whose
    type, as the model resolves it (`Graph.column_types`), is `Ident`, or
    a type that is `Ident` by an alias or a subtype, each link resolved in
    the scope that declares it. The program assigns an `Ident` as an
    ordinal in each run, so a stored row of the relation names no object in
    another run (plan §D5 `FAILING`). A relation the model resolves to no
    declaration it reads, which `load` reports as a fault, has no column
    the model reads."""
    graph = Graph(program)
    types = graph.column_types((), relation)
    if types is None:
        return False
    links: dict[str, str] = {}
    for t in program.types:
        if not isinstance(t, AliasType | SubtypeType):
            continue
        target = t.target if isinstance(t, AliasType) else t.base
        scope = t.scope.components
        if own(t.span):
            links.setdefault(graph.type_key(scope, t.name),
                             graph.resolve_type(target, scope))
        else:
            links.setdefault(t.name, target)

    def ident(name: str) -> bool:
        seen: set[str] = set()
        while name not in seen:
            if name == IDENT:
                return True
            seen.add(name)
            if name not in links:
                return False
            name = links[name]
        return False

    return any(ident(t) for t in types)


def cases(solver: Solver, engine: Engine, limits: Limits
         ) -> tuple[Case, ...] | RunFailure:
    """The solver's cases, in enumeration order, or the failure of
    the run that enumerates them.

    The solver's cases are the bases that `impl_choice` enumerates, read from a
    run on the empty input since the enumeration is a clause, each combined
    with every choice of branch at the `@derive` and `@store` points whose
    parameter or relation the base's derivation of `out` depends on
    (`dependence`; the point "stands
    under the branches that read it", solver-file.md:120, :137), minus
    each case that an `@ignore: derive` or `@ignore: store` line excludes:
    the bare form excludes every case that takes the branch in its place,
    and a named form, under a `@derive` or `@store` line, every case that
    takes that line's branch and every branch its `<name>` contains
    (`solver.names.cases_of`; solver-file.md:120, :122, :137; history "The runner holds cases the
    solver does not write" and 1103), and minus each case that takes a
    `@store` branch on a relation with an `Ident` column (`ident_keyed`),
    since no stored value of it names an object on another input; the
    `@store` line on such a relation is a finding of the store check
    (plan §D5 `FAILING`). The handbook does not
    define the solver's cases in one place; this docstring is where the
    definition stands.

    A `Choice` with no `impl_choice` relation has every combination of
    its fields as a case (solver-file.md:110)."""
    from solver.names import Denoted, cases_of, denote

    choice = solver.choice
    bases: tuple[Base | None, ...]
    if choice is None:
        bases = (None,)
    elif enumerates(solver.program):
        got = run_empty(engine, solver.program,
                        [RelationName((), ENUMERATOR)], limits)
        if not isinstance(got, Tuples):
            return got
        rows = got.relations.get(RelationName((), ENUMERATOR), ())
        bases = tuple(r[0] for r in rows
                      if len(r) == 1 and isinstance(r[0], (AdtValue,
                                                           RecordValue)))
    else:
        every = every_base(choice)
        bases = () if every is None else every
    read = dependence(solver, bases) if solver.branches else Dependence({}, {}, {})
    params = {p: set(b) for p, b in read.parameters.items()}
    relations = {r: set(b) for r, b in read.relations.items()}
    order = {b: i for i, b in enumerate(solver.branches)}
    cases: list[Case] = []
    for base in bases:
        points: list[list[Branch | None]] = []
        at: dict[str, int] = {}
        for b in solver.branches:
            if isinstance(b, DeriveBranch) \
                    and base in params.get(b.parameter, ()):
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
    bare: list[tuple[IgnoreForm, RelationName]] = []
    for i in solver.annotations.ignores:
        if i.form is IgnoreForm.LINT:
            continue
        if i.name is None:
            bare += [(i.form, t) for t in ignore_targets(solver.program, i)]
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
             and ident_keyed(solver.program, b.relation)}

    def out(case: Case) -> bool:
        if any(isinstance(b, StoreBranch) and b.relation in keyed
               for b in case.branches):
            return True
        for form, target in bare:
            for b in case.branches:
                if form is IgnoreForm.DERIVE and isinstance(b, DeriveBranch) \
                        and RelationName((), b.parameter) == target:
                    return True
                if form is IgnoreForm.STORE and isinstance(b, StoreBranch) \
                        and b.relation == target:
                    return True
        return False

    named = {c for d in excluded for c in cases_of(solver, d, cases)}
    return tuple(c for c in cases if not out(c) and c not in named)
