"""The readers of each part of the model (`solver.model`) from a parsed
program: its values, the lib, the case type, the parameters with the
case sections and markers, the branches and the proposers. `solver.load`
and the checks read them."""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

from engine.memo import ByIdentity
from engine import (
    DeclId,
    Engine,
    Index,
    ParseFailure,
    Program,
    RelationName,
    Row,
    Scope,
    Span,
    Value,
)
from engine.program import (
    MemberCell,
    term_value,
    own,
    AdtType,
    AliasType,
    AtomLiteral,
    DefinedName,
    GridCall,
    Instance,
    RigidCall,
    RecordType,
    RelationDecl,
    Term,
    TypeDecl,
    TypeName,
)
from solver.graph import (
    Graph,
    by_innermost,
    chain_relation,
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
)
from solver.problems import (
    InSolver,
    Named,
    ProblemKind,
    Fault,
    Undecided,
    UndecidedForm,
)
from solver.vocabulary import (
    BOX,
    CHOICE,
    DETERMINE_SCOPE,
    ELEM_SUFFIX,
    PARAMS,
    PARAMS_SCOPE,
    PROPOSE,
)
from solver.model import (
    Branch,
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
)

from solver.aggregate import (
    TOP,
    Solver,
    lists_case,
    own_top,
    parse_with_lib,
    proposers_path,
)


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

    The Box types are `Box` and each alias of one
    (docs/handbook/style.md#box-roles); an orientation type is the type of an
    `*_elem` relation, and its members are the constants its facts state and
    the members of the `*_elem` relations its clauses read
    (docs/handbook/principles.md#orientation); the constants are the lib's
    `#define` names whose value is a constant."""
    lib_types = [t for t in program.types if not own(t.span)]
    links = {t.name: t.target.text for t in lib_types
             if isinstance(t, AliasType)}
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
    elems = {r.name: r.columns[0].type.text for r in program.relations
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


type _OwnType = Callable[[TypeName, Scope], TypeDecl | None]
"""The type of the solver's own text a name denotes when read in a scope
(`Index.type_decl`); None where it denotes none or a lib type."""


def _own_type(index: Index) -> _OwnType:
    """`_OwnType` through `index`."""
    def read(name: TypeName, scope: Scope) -> TypeDecl | None:
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
    """The `Choice` type (docs/handbook/solver-file.md#cases,
    docs/handbook/solver-file.md#types): an ADT, or a record whose fields are
    ADTs, each ADT a choice point, and each ADT a field of a constructor stands
    in takes a point of its own."""
    types = _own_type(index)
    root = types(TypeName((), CHOICE), TOP)
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


def parameter(solver: Solver, name: str) -> RelationName:
    """A parameter as the program reads it, `params.<rel>`
    (docs/handbook/solver-file.md#params)."""
    inst = instance_of(solver.program, PARAMS)
    if inst is None:
        raise ValueError(f"{solver.stem}: no instance of `Params`")
    return RelationName((inst.name,), name)


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
    """The relations of `Params` (docs/handbook/solver-file.md#params). A
    relation that a clause of `Params` feeds, other than a RIGID block's
    relations, which its closure places, is derived data
    (docs/handbook/solver-file.md#params), listed apart with whether a
    `Determine` relation of its name mirrors it
    (docs/handbook/solver-file.md#determination). Every other relation is a
    parameter, with its stored facts or GRID calls, whether a `Determine`
    relation of its name mirrors it
    (docs/handbook/solver-file.md#determination); each with the section it
    stands in (`section_at`) and whether an `@open` line stands above it. An
    `@open` line above no parameter is unplaced."""
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
    marked = {o.above for o in annotations.opens}
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
                             rel.name in determined, rel.id in marked,
                             _section(markers, rel.span.first, lists_case)))
    params = {p.declaration for p in out}
    for o in annotations.opens:
        if o.above not in params:
            _unplaced(problems, o.line, DirectiveWord.OPEN)
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
    unmarked above the first marker that lists a case
    (docs/handbook/style.md#params), else under the nearest marker above it,
    whatever it lists."""
    above = [m for m in markers if m.line < line]
    if any(lists_case(m) for m in above):
        return UnderMarker(above[-1])
    return Unmarked()


def section_at(solver: Solver, scope: Scope, line: int) -> Section:
    """The section a line of the solver's own text stands in
    (docs/handbook/solver-file.md#cases): among the markers inside the
    top-level component the line's scope stands in, or for a top-level line,
    among the markers outside every component (`_section`)."""
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


def _unplaced(problems: list[Fault], line: int, word: DirectiveWord) -> None:
    problems.append(Fault(ProblemKind.DIRECTIVE_UNPLACED, InSolver(line),
                          Named(word)))


def read_branches(program: Program, annotations: Annotations,
                  proposers: frozenset[str] | None,
                  problems: list[Fault]) -> tuple[Branch, ...]:
    """The branches of the `@derive` and `@store` lines
    (docs/handbook/solver-file.md#params,
    docs/handbook/solver-file.md#program), and `<param>=stored` at each
    `@derive` point (history 1103), in file order: a point's stored branch
    before its `@derive` branches. A second line of one branch's name holds no
    branch of its own."""
    found: list[tuple[int, Branch]] = []
    stored_at: set[str] = set()
    derivations: set[tuple[str, str]] = set()
    stores: set[RelationName] = set()
    for d in annotations.derives:
        decl = None if d.above is None else _decl(program, d.above)
        if not isinstance(decl, RelationDecl) or decl.scope != PARAMS_SCOPE:
            _unplaced(problems, d.line, DirectiveWord.DERIVE)
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
            if chain_relation(program, decl.component, s.relation) is None:
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
            _unplaced(problems, s.line, DirectiveWord.STORE)
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
            _unplaced(problems, i.line, DirectiveWord.IGNORE)
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
    line stands on (docs/handbook/solver-file.md#params,
    docs/handbook/solver-file.md#program), which are those a directive in its
    place stands on: a parameter's `.decl` for the derive form; for the store
    form, a relation's `.decl`, and above a `.init` the relation the line
    states, or with none stated every relation of the instance
    (docs/handbook/solver-file.md#program). Empty where it stands on nothing
    its form takes."""
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
    """The proposers: the comps of the proposers program, which is
    `proposers.dl` alone, that declare `propose` (proposers.dl's
    header)."""
    return tuple(c.name for c in program.components
                 if any(r.name == PROPOSE and r.scope.components[-1:]
                         == (c.name,) for r in program.relations))


@dataclass(frozen=True)
class Proposer:
    """A proposer of `programs/proposers.dl`: the column types of its
    `propose` relation with every alias resolved, and the text of the
    comment above its component with no comment marker, as the `derive`
    report states it."""

    name: str
    types: tuple[str, ...]
    comment: str


def proposers(engine: Engine, program: Program) -> dict[str, Proposer]:
    """Each proposer of the proposers program by name
    (`proposer_names`)."""
    out: dict[str, Proposer] = {}
    graph = Graph(program, engine)
    for name in proposer_names(program):
        comp = next(c for c in program.components if c.name == name)
        decl = next(r for r in program.relations
                    if r.name == PROPOSE and r.scope.components[-1:] == (name,))
        lines = sorted((c.line, c.text.removeprefix("/").strip())
                       for c in program.comments
                       if c.above == comp.id and not c.block)
        text = " ".join(t for _l, t in lines if t).rstrip(".")
        out[name] = Proposer(
            name, tuple(graph.resolve_type(c.type, decl.scope.components)
                        for c in decl.columns),
            text[:1].lower() + text[1:])
    return out
