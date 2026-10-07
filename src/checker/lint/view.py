"""The views of a solver's parsed program the lint checks read: its own
parts, the scopes program style applies to, the case enumeration, the
units that feed and read each relation, and walks over terms and
literals. A lint compares terms and literals by these walks, never by the
renderer's text."""

from collections.abc import Callable, Iterable, Iterator, Sequence
from dataclasses import dataclass, fields, is_dataclass, replace
from functools import cached_property
from typing import Any, cast

from checker.finding import AtLine, Finding, Kind, LintPayload
from checker.runs import Runs
from engine import Index, Resolved, Role
from engine.memo import ByIdentity
from engine.program import (
    Aggregate,
    Atom,
    AtomLiteral,
    BodyLiteral,
    Comparison,
    Component,
    ConstructorTerm,
    DeclId,
    Disjunction,
    FunctorDecl,
    Instance,
    RecordTerm,
    RelationDecl,
    Scope,
    Span,
    Term,
    TypeDecl,
    Unit,
    UnitId,
    Variable,
    body_atoms,
    literal_aggregates,
    own,
    term_aggregates,
)
from engine.program import literal_terms as top_terms
from engine.program import subterms as direct_subterms
from solver.annotations import CaseMarker
from solver.category import HINTS
from solver.aggregate import TOP, Solver
from solver.readers import marker_at
from solver.vocabulary import (
    DETERMINE,
    ENUMERATOR,
    PARAMS,
    PARSE,
)

STOCK_COMPS = (PARAMS, DETERMINE, PARSE)
"""The comps a solver holds as its own (solver-file.md, under "Components")."""

PROGRAM_COMPS = (DETERMINE, PARSE)
"""The comps whose clauses program style reads beside the top level."""


def lint(line: int, payload: LintPayload,
         units: tuple[UnitId, ...] = ()) -> Finding:
    """A lint finding on a solver line, standing on `units`: a hint where
    its category is one (`solver.category.HINTS`)."""
    kind = Kind.HINT if payload.category in HINTS else Kind.LINT
    return Finding(kind, AtLine(line, units), payload)


# Terms and literals


def subterms(term: Term, into_aggregates: bool = False) -> Iterator[Term]:
    """`term` and every term inside it, outermost first; an aggregate's
    target and body with `into_aggregates`."""
    yield term
    if isinstance(term, Aggregate):
        if into_aggregates:
            if term.expr is not None:
                yield from subterms(term.expr, into_aggregates)
            for lit in term.body:
                for t in literal_terms(lit):
                    yield from subterms(t, into_aggregates)
        return
    for t in direct_subterms(term):
        yield from subterms(t, into_aggregates)


def literal_terms(lit: BodyLiteral, branches: bool = False
                  ) -> tuple[Term, ...]:
    """The top-level terms of one literal (`engine.program.literal_terms`);
    a disjunction's are its branches', read here with `branches` and there
    otherwise."""
    if isinstance(lit, Disjunction) and branches:
        return tuple(t for b in lit.branches for x in b
                     for t in literal_terms(x, True))
    return top_terms(lit)


def term_vars(term: Term) -> set[str]:
    """The variables of a term, outside aggregates."""
    return {t.name for t in subterms(term) if isinstance(t, Variable)}


def literal_vars(lit: BodyLiteral | Atom) -> set[str]:
    """The variables of a literal or an atom, disjunction branches
    included, outside aggregates."""
    if isinstance(lit, Atom):
        return {v for a in lit.args for v in term_vars(a)}
    return {v for t in literal_terms(lit, True) for v in term_vars(t)}


def aggregates(lit: BodyLiteral | Atom) -> Iterator[Aggregate]:
    """The aggregates a literal or an atom holds, outermost first
    (`engine.program.literal_aggregates`)."""
    if isinstance(lit, Atom):
        yield from (a for t in lit.args for a in term_aggregates(t))
    else:
        yield from literal_aggregates(lit)


def atoms_read(unit: Unit) -> Iterator[Atom]:
    """Every atom a clause reads: the atoms of an aggregate in the head,
    then each body atom, negated or not (`engine.program.body_atoms`)."""
    for agg in aggregates(unit.head):
        yield from (a for a, _negated in body_atoms(agg.body))
    yield from (a for a, _negated in body_atoms(unit.body or ()))


def positive_atoms(flats: Iterable[list[BodyLiteral]]) -> list[Atom]:
    """The distinct positive atoms of the conjunctions `flats`
    (`flatten`), by identity, in the order they first stand."""
    seen: dict[int, Atom] = {}
    for f in flats:
        for x in f:
            if isinstance(x, AtomLiteral) and not x.negated:
                seen.setdefault(id(x.atom), x.atom)
    return list(seen.values())


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


def from_lib(span: Span | None) -> bool:
    """A part of the lib's text."""
    return span is not None and not own(span)


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
    def held[T](self, compute: Callable[["View"], T]) -> T:
        """`compute(self)`, computed once per view: what a check computes
        once for the checks after it."""
        got = _HELD.keyed(self, compute, lambda: compute(self))
        return got  # type: ignore[return-value]

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
                       if u.span is not None and own(u.span)),
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
        return [r for r in self.program.relations if own(r.span)]

    @cached_property
    def own_types(self) -> list[TypeDecl]:
        return [t for t in self.program.types if own(t.span)]

    @cached_property
    def own_types_by_id(self) -> dict[DeclId, TypeDecl]:
        return {t.id: t for t in self.own_types}

    @cached_property
    def own_components(self) -> list[Component]:
        return [c for c in self.program.components if own(c.span)]

    @cached_property
    def own_instances(self) -> list[Instance]:
        return [i for i in self.program.instances if own(i.span)]

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

    def column_types(self, unit: Unit, atom: Atom) -> list[str] | None:
        """The declared type of each column of an atom of `unit`, a
        component's type parameter read as the type its instance gives it;
        None where the atom names no relation of its arity."""
        r = self.index.resolve(atom.relation, unit.scope)
        if not isinstance(r, Resolved):
            return None
        d = self.decls.get(r.declaration)
        if not isinstance(d, RelationDecl) or len(d.columns) != len(atom.args):
            return None
        subst = dict(r.type_arguments)
        return [(c.type.argument(subst) or c.type).text for c in d.columns]

    def head(self, unit: Unit) -> RelationDecl | None:
        return self.relation(unit, unit.head)

    def is_lib(self, decl: RelationDecl | None) -> bool:
        """A relation of the lib, or one the program does not declare."""
        return decl is None or not own(decl.span)

    def defs(self, decl: RelationDecl) -> list[Unit]:
        """The units whose head is `decl`, in unit order."""
        return [self.units[o.unit] for o in self.index.feeding(decl.id)
                if o.unit in self.units]

    def marked_facts(self, decl: RelationDecl
                     ) -> list[tuple[Unit, int, CaseMarker | None]]:
        """Each fact of `decl` (`defs`) on a line of the file, with that
        line and the case marker it stands under
        (`solver.readers.marker_at`), None above the first marker that lists
        a case. A fact an operation wrote stands on no line."""
        return [(u, u.span.first,
                 marker_at(self.solver, u.scope, u.span.first))
                for u in self.defs(decl)
                if u.body is None and u.span is not None]

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
                if not a.relation.instances:
                    read_by.setdefault(a.relation.name, set()).add(head)
        if ENUMERATOR not in heads:
            return frozenset()
        enums = self.enumerators

        def reads(names: set[str]) -> set[str]:
            return {a.relation.name for n in names
                    for u in heads.get(n, [])
                    for a in atoms_read(u)
                    if not a.relation.instances}

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
            one = tag_fact(u)
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
    def marker_lines(self) -> frozenset[int]:
        """The lines of the case markers."""
        return frozenset(m.line for m in self.markers)

    @cached_property
    def comment_lines(self) -> frozenset[int]:
        """The lines of the solver's own comments that stand on a line of
        their own."""
        return frozenset(c.line for c in self.program.comments
                         if c.own_line and own(c))

    @cached_property
    def written_relations(self) -> list[RelationDecl]:
        """The own relations less the charts a `RIGID` call declares, which
        take the names only its expansion writes; its placed relations
        stay."""
        return [r for r in self.own_relations if r.chart_of is None]


def tag_fact(u: Unit) -> bool:
    """The unit is a fact of one argument, a constructor or a record."""
    return u.body is None and len(u.head.args) == 1 \
        and isinstance(u.head.args[0], ConstructorTerm | RecordTerm)


_HELD: ByIdentity[View, dict[Callable[[View], object], object]] = \
    ByIdentity()
_VIEWS: ByIdentity[Runs, View] = ByIdentity()


def view(solver: Solver, runs: Runs) -> View:
    """The lint's view of the solver, made once per command's `Runs`."""
    v = _VIEWS.get(runs)
    if v is None or v.solver is not solver:
        v = _VIEWS.put(runs, View(solver, runs.index))
    return v
