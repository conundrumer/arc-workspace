"""The aggregate `Solver` and its load: the functions that read each part
of the model (`solver.model`) from a parsed program, which `solver.load`
and the checks read as well, the checks of the solver's form that `load`
runs, and what the model reads of the solver's cases (`solver.cases`)."""

from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Annotated

from arc.task import Task
from engine import checkout
from engine.memo import ByIdentity
from engine import (
    AdtValue,
    DeclId,
    Engine,
    Index,
    Limits,
    ParseFailure,
    Program,
    RecordValue,
    RelationName,
    Row,
    RunFailure,
    RunResult,
    Scope,
    Span,
    Tuples,
    Value,
)
from engine.program import (
    MemberCell,
    first_line,
    term_value,
    dotted,
    own,
    AdtType,
    AliasType,
    AtomLiteral,
    Component,
    DefinedName,
    GridCall,
    Instance,
    RigidCall,
    RecordType,
    RelationDecl,
    Term,
    TypeDecl,
)
from engine.quotes import quotes
from solver import witness as witness_reader
from solver.graph import (
    MAX_DEPTH,
    by_innermost,
    component_chain,
    followed,
)
from solver.annotations import (
    DirectiveWord,
    branch_band,
    Annotations,
    CaseMarker,
    IgnoreForm,
    IgnoreLine,
    NamedVerdict,
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
    IMPL,
    INPUT,
    LIB_FILE,
    PARAMS,
    PARAMS_SCOPE,
    PROPOSE,
    PROPOSERS_FILE,
)
from solver.witness import AssignRows, Groups, WitnessFile
from solver.model import (
    Base,
    Branch,
    Case,
    Choice,
    ChoicePoint,
    ConstructorBranch,
    DeriveBranch,
    DerivedRelation,
    Lib,
    Parameter,
    Params,
    Section,
    StoreBranch,
    StoredAtDerive,
    StoredGrid,
    StoredGridCall,
    UnderMarker,
    Unmarked,
    derived_parameters,
    non_concept_at,
)


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


def based_choice(solver: "Solver") -> Choice:
    """The solver's `Choice`, for a caller that holds a base of it. Raises
    `ValueError` for a solver with no `Choice`, which has no base."""
    if solver.choice is None:
        raise ValueError(f"{solver.stem}: no `Choice`, so no base")
    return solver.choice



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
    case (`solver.model.Unmarked`)."""
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
    keys and the strings of `assign` values (`solver.columns.arg_value`)."""
    from solver.columns import unknown_strings
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


def is_concept_case(solver: Solver, case: Case) -> bool:
    """Whether `case` is the concept case: the base case
    (`solver.model.base_case`) of the concept case's base (`is_concept`)
    (principles.md, under "The concept")."""
    return case.is_base_case and is_concept(solver, case.base)
