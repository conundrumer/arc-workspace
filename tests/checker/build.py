"""Hand-built solver models for the checker's tests: a program from its
declarations and units, an index over it, and a `Solver` around it."""

from dataclasses import dataclass, field

from engine import Occurrence, Resolved, Role, Unresolved
from engine.program import (
    Atom,
    AtomLiteral,
    BodyLiteral,
    Comment,
    Component,
    DeclId,
    Instance,
    Program,
    RelationDecl,
    RelationName,
    Scope,
    Span,
    Term,
    TypeDecl,
    Unit,
    UnitId,
    Variable,
)
from solver.annotations import Annotations
from solver.model import Lib, Params
from solver.aggregate import Solver

TOP = Scope(())


def span(first: int, last: int | None = None) -> Span:
    return Span(first, first if last is None else last, file=None)


def var(name: str) -> Variable:
    return Variable(name)


def atom(name: str, *args: Term, line: int, via: tuple[str, ...] = ()
         ) -> Atom:
    return Atom(RelationName(via, name), args, line)


def pos(a: Atom) -> AtomLiteral:
    return AtomLiteral(a, False)


@dataclass
class Builder:
    """A program built part by part, each part with a fresh id."""

    relations: list[RelationDecl] = field(default_factory=list)
    types: list[TypeDecl] = field(default_factory=list)
    components: list[Component] = field(default_factory=list)
    instances: list[Instance] = field(default_factory=list)
    units: list[Unit] = field(default_factory=list)
    comments: list[Comment] = field(default_factory=list)
    ids: int = 0

    def _id(self) -> DeclId:
        self.ids += 1
        return DeclId(self.ids)

    def relation(self, name: str, *columns: tuple[str, str], line: int,
                 scope: Scope = TOP) -> RelationDecl:
        from engine.program import Column, TypeName
        d = RelationDecl(self._id(), name, scope,
                         tuple(Column(n, TypeName((), t)) for n, t in columns),
                         (), (),
                         span(line))
        self.relations.append(d)
        return d

    def unit(self, head: Atom, *body: BodyLiteral, scope: Scope = TOP,
             last: int | None = None) -> Unit:
        u = Unit(UnitId(len(self.units)), scope, head,
                 tuple(body) if body else None, None,
                 span(head.line, last))
        self.units.append(u)
        return u

    def fact(self, head: Atom, scope: Scope = TOP) -> Unit:
        u = Unit(UnitId(len(self.units)), scope, head, None, None,
                 span(head.line))
        self.units.append(u)
        return u

    def program(self) -> Program:
        return Program(tuple(self.types), tuple(self.relations),
                       tuple(self.components), tuple(self.instances), (),
                       tuple(self.units), (), tuple(self.comments), (), ())


class FakeIndex:
    """The feeds, reads and resolution of a hand-built program: a name
    resolves in its scope, then at the top level; an instance path goes
    through the instances at the top level."""

    def __init__(self, program: Program):
        self.program = program

    def resolve(self, name: RelationName, scope: Scope
                ) -> Resolved | Unresolved:
        through: list[DeclId] = []
        at = scope
        for hop in name.instances:
            inst = next((i for i in self.program.instances
                         if i.name == hop), None)
            if inst is None:
                return Unresolved(name, scope)
            through.append(inst.id)
            at = Scope((inst.component,))
        for s in (at, TOP):
            d = next((r for r in self.program.relations
                      if r.name == name.name and r.scope == s), None)
            if d is not None:
                return Resolved(d.id, tuple(through), ())
        return Unresolved(name, scope)

    def type_decl(self, name: str, scope: Scope) -> TypeDecl | None:
        for s in (scope, TOP):
            d = next((t for t in self.program.types
                      if t.name == name and t.scope == s), None)
            if d is not None:
                return d
        return None

    def _occurrences(self, relation: DeclId, role: Role
                     ) -> tuple[Occurrence, ...]:
        out: list[Occurrence] = []
        for u in self.program.units:
            if role == Role.FEEDS:
                r = self.resolve(u.head.relation, u.scope)
                if isinstance(r, Resolved) and r.declaration == relation:
                    out.append(Occurrence(u.id, u.head, role, False))
                continue
            for lit in u.body or ():
                if isinstance(lit, AtomLiteral):
                    r = self.resolve(lit.atom.relation, u.scope)
                    if isinstance(r, Resolved) and r.declaration == relation:
                        out.append(Occurrence(u.id, lit.atom, role,
                                              lit.negated))
        return tuple(out)

    def feeding(self, relation: DeclId) -> tuple[Occurrence, ...]:
        return self._occurrences(relation, Role.FEEDS)

    def reading(self, relation: DeclId) -> tuple[Occurrence, ...]:
        return self._occurrences(relation, Role.READS)


def annotations(**parts: object) -> Annotations:
    base: dict[str, object] = dict(
        header=(), reviews=(), representative=None, claims=(), witnesses=(),
        derives=(), stores=(), claim_lines=(), ignores=(), markers=(),
        trailing=(), workarounds=(), header_prose=(), task_id=None)
    base.update(parts)
    return Annotations(**base)  # type: ignore[arg-type]


def solver(program: Program, ann: Annotations | None = None) -> Solver:
    return Solver(stem="0000test", task_id="0000test", program=program,
                  annotations=ann or annotations(), choice=None, branches=(),
                  params=Params(()), witness_file=None, task=None,
                  lib=Lib(frozenset(), {}, {}, {}), problems=(),
                  engine=FakeEngine())  # type: ignore[arg-type]


class FakeEngine:
    """An engine whose index is the fake one; nothing else is called."""

    def index(self, program: Program) -> FakeIndex:
        return FakeIndex(program)
