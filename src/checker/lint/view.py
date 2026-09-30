"""The views of a solver's parsed program the lint checks read: its own
parts, the scopes program style applies to, the case enumeration, the
units that feed and read each relation, and walks over terms and
literals."""

from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field, fields, is_dataclass, replace
from typing import Any, cast
from functools import cached_property
from weakref import WeakKeyDictionary

from checker.finding import AtLine, Finding, Kind, LintPayload
from checker.runs import Runs
from engine import Index, Resolved, Role
from engine.program import (
    Cast,
    AdtType,
    Aggregate,
    AliasType,
    Atom,
    AtomLiteral,
    BinaryTerm,
    BodyLiteral,
    Comparison,
    Component,
    ConstructorTerm,
    DeclId,
    Disjunction,
    FunctorCall,
    FunctorDecl,
    Instance,
    IntrinsicCall,
    RecordTerm,
    RecordType,
    RelationDecl,
    Scope,
    Span,
    SubtypeType,
    Term,
    TypeDecl,
    UnaryTerm,
    UnionType,
    Unit,
    UnitId,
    Variable,
)
from solver.vocabulary import (
    DETERMINE,
    ENUMERATOR,
    PARAMS,
    PARSE,
)
from solver.annotations import CaseMarker
from solver.category import HINTS
from solver.model import Solver


STOCK_COMPS = (PARAMS, DETERMINE, PARSE)
"""The comps a solver holds as its own (solver-file.md:152)."""

PROGRAM_COMPS = (DETERMINE, PARSE)
"""The comps whose clauses program style reads beside the top level."""

TOP = Scope(())


def lint(line: int, payload: LintPayload) -> Finding:
    """A lint finding on a solver line: a hint where its category is one
    (`solver.category.HINTS`)."""
    kind = Kind.HINT if payload.category in HINTS else Kind.LINT
    return Finding(kind, AtLine(line), payload)


# Terms and literals


def subterms(term: Term, into_aggregates: bool = False) -> Iterator[Term]:
    """`term` and every term inside it, outermost first; an aggregate's
    target and body with `into_aggregates`."""
    yield term
    match term:
        case ConstructorTerm(args=args) | RecordTerm(args=args) \
                | IntrinsicCall(args=args) | FunctorCall(args=args):
            for a in args:
                yield from subterms(a, into_aggregates)
        case UnaryTerm(arg=arg) | Cast(term=arg):
            yield from subterms(arg, into_aggregates)
        case BinaryTerm(lhs=lhs, rhs=rhs):
            yield from subterms(lhs, into_aggregates)
            yield from subterms(rhs, into_aggregates)
        case Aggregate(expr=expr, body=body) if into_aggregates:
            if expr is not None:
                yield from subterms(expr, into_aggregates)
            for lit in body:
                for t in literal_terms(lit):
                    yield from subterms(t, into_aggregates)
        case _:
            pass


def literal_terms(lit: BodyLiteral) -> tuple[Term, ...]:
    """The top-level terms of one literal; a disjunction's are its
    branches' and are read there."""
    match lit:
        case AtomLiteral(atom=atom):
            return atom.args
        case Comparison(lhs=lhs, rhs=rhs):
            return (lhs, rhs)
        case _:
            return ()


def term_vars(term: Term) -> set[str]:
    """The variables of a term, outside aggregates."""
    return {t.name for t in subterms(term) if isinstance(t, Variable)}


def literal_vars(lit: BodyLiteral | Atom) -> set[str]:
    """The variables of a literal or an atom, disjunction branches
    included, outside aggregates."""
    if isinstance(lit, Atom):
        return {v for a in lit.args for v in term_vars(a)}
    if isinstance(lit, Disjunction):
        return {v for b in lit.branches for x in b for v in literal_vars(x)}
    return {v for t in literal_terms(lit) for v in term_vars(t)}


def aggregates(lit: BodyLiteral | Atom) -> Iterator[Aggregate]:
    """The aggregates a literal holds, outermost first."""
    terms = lit.args if isinstance(lit, Atom) else literal_terms(lit)
    for t in terms:
        for s in subterms(t):
            if isinstance(s, Aggregate):
                yield s


def atoms_read(unit: Unit) -> Iterator[AtomLiteral]:
    """Every atom a clause reads: each body atom, negated or not,
    disjunction branches and aggregate bodies included, and the atoms of
    an aggregate in the head."""
    def walk(lits: Sequence[BodyLiteral]) -> Iterator[AtomLiteral]:
        for lit in lits:
            if isinstance(lit, AtomLiteral):
                yield lit
            elif isinstance(lit, Disjunction):
                for b in lit.branches:
                    yield from walk(b)
            for agg in aggregates(lit):
                yield from walk(agg.body)
    for agg in aggregates(unit.head):
        yield from walk(agg.body)
    yield from walk(unit.body or ())


def flatten(body: Sequence[BodyLiteral]) -> Iterator[list[BodyLiteral]]:
    """The conjunctions a body's disjunctions expand into, one per branch
    choice, each in source order."""
    for i, lit in enumerate(body):
        if isinstance(lit, Disjunction):
            for branch in lit.branches:
                yield from flatten([*body[:i], *branch, *body[i + 1:]])
            return
    yield list(body)


def conjunctions(unit: Unit) -> Iterator[list[BodyLiteral]]:
    """The body, each aggregate body, and each disjunct."""
    if unit.body is None:
        return
    yield list(unit.body)
    stack: list[BodyLiteral] = list(unit.body)
    while stack:
        lit = stack.pop()
        if isinstance(lit, Comparison):
            for side in (lit.lhs, lit.rhs):
                if isinstance(side, Aggregate):
                    yield list(side.body)
        elif isinstance(lit, Disjunction):
            for branch in lit.branches:
                yield list(branch)
                stack.extend(branch)


def disjunctions(unit: Unit) -> Iterator[Disjunction]:
    stack: list[BodyLiteral] = list(unit.body or ())
    while stack:
        lit = stack.pop()
        if isinstance(lit, Disjunction):
            yield lit
            for b in lit.branches:
                stack.extend(b)


def same_atom(a: Atom, b: Atom) -> bool:
    """Two atoms that name one relation with the same arguments, wherever
    they stand."""
    return a.relation == b.relation and a.args == b.args


def placed(lit: BodyLiteral | Atom, line: int
           ) -> Iterator[tuple[int, BodyLiteral | Atom | Term]]:
    """Each literal and term under `lit`, with the line of the literal
    that holds it; an aggregate's parts on the line of the literal that
    holds it, and each literal of its body on its own line."""
    if isinstance(lit, Atom):
        at = lit.line
    elif isinstance(lit, AtomLiteral):
        at = lit.atom.line
    elif isinstance(lit, Comparison | Disjunction):
        at = lit.line
    else:
        at = line
    yield at, lit
    if isinstance(lit, Disjunction):
        for b in lit.branches:
            for x in b:
                yield from placed(x, at)
        return
    terms = lit.args if isinstance(lit, Atom) else literal_terms(lit)
    for t in terms:
        for s in subterms(t):
            yield at, s
            if isinstance(s, Aggregate):
                for x in s.body:
                    yield from placed(x, at)


# Structural comparison


def bare[T](node: T) -> T:
    """`node` with every line number inside it set to 0, so that two
    literals, atoms or terms compare equal where they are the same code
    on different lines."""
    if isinstance(node, tuple):
        return cast(T, tuple(bare(x) for x in cast(tuple[object, ...], node)))
    if is_dataclass(node) and not isinstance(node, type):
        changes = {f.name: 0 if f.name == "line" else bare(getattr(node, f.name))
                   for f in fields(node)}
        return cast(T, replace(cast(Any, node), **changes))
    return node


# The program


def own(span_file: str | None) -> bool:
    """A part of the solver's own text, as opposed to the lib's."""
    return span_file is None


def owned(span: Span | None) -> bool:
    """A part of the solver's own text; a part with no span is one an
    operation wrote, in no text."""
    return span is not None and own(span.file)


def from_lib(span: Span | None) -> bool:
    """A part of the lib's text."""
    return span is not None and not own(span.file)


def spanned(span: Span | None) -> Span:
    """The span of a part of the solver's own text, which has one."""
    if span is None:
        raise ValueError("a part an operation wrote has no span")
    return span


@dataclass
class View:
    """One solver's program as the lint reads it."""

    solver: Solver
    index: Index
    memo: dict[str, object] = field(default_factory=dict)
    """What a check computes once for the checks after it."""

    @property
    def program(self):
        return self.solver.program

    @cached_property
    def units(self) -> dict[UnitId, Unit]:
        return {u.id: u for u in self.program.units}

    @cached_property
    def own_units(self) -> list[Unit]:
        """The units of the solver's own text, in source order."""
        return sorted((u for u in self.program.units
                       if u.span is not None and own(u.span.file)),
                      key=lambda u: (u.span.first if u.span else 0,
                                     u.id.index))

    @cached_property
    def decls(self) -> dict[DeclId, RelationDecl | TypeDecl | Component
                            | Instance | FunctorDecl]:
        p = self.program
        return {d.id: d for d in (*p.relations, *p.types, *p.components,
                                  *p.instances, *p.functors)}

    @cached_property
    def own_relations(self) -> list[RelationDecl]:
        return [r for r in self.program.relations if own(r.span.file)]

    @cached_property
    def own_types(self) -> list[TypeDecl]:
        return [t for t in self.program.types if own(t.span.file)]

    @cached_property
    def own_components(self) -> list[Component]:
        return [c for c in self.program.components if owned(c.span)]

    @cached_property
    def own_instances(self) -> list[Instance]:
        return [i for i in self.program.instances if owned(i.span)]

    @cached_property
    def lib_components(self) -> dict[str, Component]:
        return {c.name: c for c in self.program.components
                if from_lib(c.span)}

    @cached_property
    def components(self) -> dict[str, Component]:
        return {c.name: c for c in self.program.components}

    def relation(self, unit: Unit, atom: Atom) -> RelationDecl | None:
        """The relation an atom of `unit` names, None where it resolves to
        none."""
        r = self.index.resolve(atom.relation, unit.scope)
        if not isinstance(r, Resolved):
            return None
        d = self.decls.get(r.declaration)
        return d if isinstance(d, RelationDecl) else None

    def head(self, unit: Unit) -> RelationDecl | None:
        return self.relation(unit, unit.head)

    def is_lib(self, decl: RelationDecl | None) -> bool:
        """A relation of the lib, or one the program does not declare."""
        return decl is None or not own(decl.span.file)

    def defs(self, decl: RelationDecl) -> list[Unit]:
        """The units whose head is `decl`, in unit order."""
        return [self.units[o.unit] for o in self.index.feeding(decl.id)
                if o.unit in self.units]

    def uses(self, decl: RelationDecl) -> list[tuple[Unit, Atom, bool]]:
        """Each atom that reads `decl`, with its unit and whether it is
        negated."""
        return [(self.units[o.unit], o.atom, o.negated)
                for o in self.index.reading(decl.id)
                if o.role == Role.READS and o.unit in self.units]

    # Scopes

    @staticmethod
    def comp_of(scope: Scope) -> str | None:
        """The outermost component a scope stands in; None at the top."""
        return scope.components[0] if scope.components else None

    def program_scope(self, scope: Scope) -> bool:
        """A scope that holds program code: the top level, `Determine`,
        `Parse` and `Params`."""
        return scope == TOP or (len(scope.components) == 1
                                and scope.components[0] in STOCK_COMPS)

    def style_scope(self, scope: Scope) -> bool:
        """A scope program style applies to: the program scopes but
        `Params`."""
        return self.program_scope(scope) and self.comp_of(scope) != PARAMS

    @cached_property
    def enumeration(self) -> frozenset[str]:
        """The top-level relations whose clauses the program-style checks
        skip: `impl_choice`, its enumerators, and the relations only they
        read, transitively (history 1111)."""
        heads: dict[str, list[Unit]] = {}
        read_by: dict[str, set[str | None]] = {}
        for u in self.own_units:
            top = u.scope == TOP and not u.head.relation.instances
            head = u.head.relation.name if top else None
            if head is not None:
                heads.setdefault(head, []).append(u)
            for a in atoms_read(u):
                if not a.atom.relation.instances:
                    read_by.setdefault(a.atom.relation.name, set()).add(head)
        if ENUMERATOR not in heads:
            return frozenset()
        enums = self.enumerators

        def reads(names: set[str]) -> set[str]:
            return {a.atom.relation.name for n in names
                    for u in heads.get(n, [])
                    for a in atoms_read(u)
                    if not a.atom.relation.instances}

        found = {ENUMERATOR} | (reads({ENUMERATOR}) & enums)
        group = set(heads) - found
        while True:
            cut = {n for n in group
                   if not read_by.get(n) or not read_by[n] <= found | group}
            group -= cut
            reached: set[str] = set()
            work = set(found)
            while work:
                work = (reads(work) & group) - reached
                reached |= work
            if not cut and reached == group:
                return frozenset(found | group)
            group = reached

    @cached_property
    def enumerators(self) -> set[str]:
        """`impl_choice`, and each top-level relation whose every clause is
        a fact of one argument, a constructor or a record."""
        shape: dict[str, bool] = {}
        for u in self.own_units:
            if u.scope != TOP or u.head.relation.instances:
                continue
            one = (u.body is None and len(u.head.args) == 1
                   and isinstance(u.head.args[0],
                                  ConstructorTerm | RecordTerm))
            name = u.head.relation.name
            shape[name] = shape.get(name, True) and one
        return {n for n, one in shape.items() if one} | {ENUMERATOR}

    def in_enumeration(self, unit: Unit) -> bool:
        return (unit.scope == TOP and not unit.head.relation.instances
                and unit.head.relation.name in self.enumeration)

    def style_units(self) -> list[Unit]:
        """The own units program style applies to: the top level, less the
        case enumeration's clauses, and the clauses of `Determine` and
        `Parse`."""
        return [u for u in self.own_units
                if (u.scope == TOP and not self.in_enumeration(u))
                or (u.scope != TOP and self.comp_of(u.scope) in PROGRAM_COMPS)]

    def program_units(self) -> list[Unit]:
        """The own units of the program scopes, less the case
        enumeration's clauses."""
        return [u for u in self.own_units if self.program_scope(u.scope)
                and not self.in_enumeration(u)]

    def program_relations(self) -> list[RelationDecl]:
        """The own relations of the program scopes, less the case
        enumeration's."""
        return [r for r in self.written_relations
                if self.program_scope(r.scope)
                and not (r.scope == TOP and r.name in self.enumeration)]

    # Sections

    @cached_property
    def markers(self) -> list[CaseMarker]:
        return sorted(self.solver.annotations.markers, key=lambda m: m.line)

    @cached_property
    def top_markers(self) -> list[CaseMarker]:
        """The case markers outside every component: a marker inside a
        component names no top-level section."""
        spans = [(spanned(c.span).first, spanned(c.span).last)
                 for c in self.own_components]
        return [m for m in self.markers
                if not any(a <= m.line <= b for a, b in spans)]

    def marker_at(self, line: int) -> CaseMarker | None:
        """The case marker whose section a top-level line stands in: the
        last top-level one above it."""
        found = None
        for m in self.top_markers:
            if m.line <= line:
                found = m
        return found

    def section(self, unit: Unit) -> CaseMarker | None:
        """The case marker whose section a unit stands in; None inside a
        component and above the first marker."""
        if unit.scope != TOP or unit.span is None:
            return None
        return self.marker_at(unit.span.first)

    @cached_property
    def rigid_spans(self) -> list[tuple[int, int]]:
        """The lines of each `RIGID` call of the solver's text."""
        from engine.program import RigidCall
        return [(m.span.first, m.span.last) for m in self.program.macros
                if isinstance(m, RigidCall) and m.span is not None
                and m.span.file is None]

    def in_rigid(self, line: int) -> bool:
        return any(a <= line <= b for a, b in self.rigid_spans)

    @cached_property
    def written_relations(self) -> list[RelationDecl]:
        """The own relations less the charts a `RIGID` call declares, which
        take the names only its expansion writes; its placed relations
        stay."""
        return [r for r in self.own_relations if r.chart_of is None]

    # Types

    @cached_property
    def type_names(self) -> dict[str, TypeDecl]:
        return {t.name: t for t in self.program.types}


def type_refs(td: TypeDecl) -> list[str]:
    """The type names a type declaration's right-hand side names."""
    match td:
        case AdtType(constructors=cs):
            return [f.type for c in cs for f in c.fields]
        case RecordType(fields=fs):
            return [f.type for f in fs]
        case SubtypeType(base=base):
            return [base]
        case UnionType(members=members):
            return list(members)
        case AliasType(target=target):
            return [target]


def unqualified(name: str) -> str:
    """A type name read through an instance, `o.Pt`, as the `Pt` the comp
    declares."""
    return name.rsplit(".", 1)[-1]


_VIEWS: WeakKeyDictionary[Runs, View] = WeakKeyDictionary()


def view(solver: Solver, runs: Runs) -> View:
    """The lint's view of the solver, made once per command's `Runs`."""
    v = _VIEWS.get(runs)
    if v is None or v.solver is not solver:
        v = View(solver, runs.index)
        _VIEWS[runs] = v
    return v
