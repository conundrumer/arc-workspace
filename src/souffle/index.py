"""Which units feed and read each relation, and the resolution of a
qualified name through instances."""

import threading
import weakref
from collections.abc import Iterable, Iterator
from dataclasses import dataclass

from engine.engine import Occurrence, Resolved, Role, Unresolved
from engine.program import (
    Aggregate,
    Atom,
    AtomLiteral,
    BinaryTerm,
    BodyLiteral,
    Cast,
    Comparison,
    Component,
    ConstructorTerm,
    DeclId,
    Disjunction,
    FunctorCall,
    GridCall,
    Instance,
    IntrinsicCall,
    MacroCall,
    Program,
    RecordTerm,
    RelationDecl,
    RelationName,
    RigidCall,
    Scope,
    Term,
    TypeDecl,
    UnaryTerm,
    Unit,
    UnitId,
    Wildcard,
)
from souffle.parser import Shape

type Path = tuple[str, ...]


def body_atoms(body: tuple[BodyLiteral, ...]) -> Iterator[tuple[Atom, bool]]:
    """Every atom a body reads, in order, with whether it stands negated:
    through disjunctions and the bodies of aggregates."""
    for lit in body:
        match lit:
            case AtomLiteral(atom, negated):
                yield from _term_atoms(atom.args)
                yield atom, negated
            case Comparison(_, lhs, rhs):
                yield from _term_atoms((lhs, rhs))
            case Disjunction(branches):
                for branch in branches:
                    yield from body_atoms(branch)


def _term_atoms(terms: tuple[Term, ...]) -> Iterator[tuple[Atom, bool]]:
    for t in terms:
        match t:
            case Aggregate(_, expr, body):
                if expr is not None:
                    yield from _term_atoms((expr,))
                yield from body_atoms(body)
            case ConstructorTerm(_, args) | RecordTerm(args) | IntrinsicCall(_, args) \
                    | FunctorCall(_, args):
                yield from _term_atoms(args)
            case UnaryTerm(_, arg) | Cast(arg, _):
                yield from _term_atoms((arg,))
            case BinaryTerm(_, lhs, rhs):
                yield from _term_atoms((lhs, rhs))


class Level:
    """One instance on a path from the top level: the chain of its
    component, derived first; for each component of the chain, what each
    of its type parameters stands for; and `outer_start`, the place in the
    chain of the instance above whose text declares this one."""

    def __init__(self, chain: tuple[Path, ...], outer_start: int):
        self.chain = chain
        self.env: dict[Path, dict[str, TypeRef]] = {}
        self.outer_start = outer_start


@dataclass(frozen=True)
class TypeRef:
    """A type name and where it is read: the instances on the way down,
    and the place in the innermost one's chain whose text names it."""

    name: str
    place: tuple[Level, ...]
    start: int


PRIMITIVES = frozenset({"number", "unsigned", "float", "symbol"})


@dataclass(frozen=True)
class _Hit:
    decl: RelationDecl
    through: tuple[DeclId, ...]
    type_arguments: tuple[tuple[str, str], ...]
    place: tuple[Level, ...]
    """The instances on the way down to the declaration."""
    start: int
    """The place in the innermost instance's chain whose text declares
    it."""


class Tree:
    """The components, relations, types and instances of a program by the
    path of the text that declares them."""

    def __init__(self, program: Program):
        self.comps: dict[Path, Component] = {
            (*c.scope.components, c.name): c for c in program.components}
        self.decls: dict[Path, dict[str, RelationDecl]] = {}
        for r in program.relations:
            self.decls.setdefault(r.scope.components, {}).setdefault(r.name, r)
        self.inits: dict[Path, dict[str, Instance]] = {}
        for i in program.instances:
            self.inits.setdefault(i.scope.components, {}).setdefault(i.name, i)
        self.types: dict[Path, dict[str, TypeDecl]] = {}
        for t in program.types:
            self.types.setdefault(t.scope.components, {}).setdefault(t.name, t)

    def comp(self, name: str, at: Path) -> Path | None:
        """The component `name` read in the text of `at`: declared there or
        in a text around it."""
        for k in range(len(at), -1, -1):
            if (*at[:k], name) in self.comps:
                return (*at[:k], name)
        return None

    def chain(self, path: Path) -> list[Path]:
        """The component and the ones it extends, derived first."""
        out: list[Path] = []
        cur: Path | None = path
        while cur is not None and cur not in out and cur in self.comps:
            out.append(cur)
            base = self.comps[cur].base
            cur = self.comp(base, cur[:-1]) if base else None
        return out

    def base_arguments(self, path: Path) -> tuple[tuple[str, str], ...]:
        """The type argument each base of `path` gets from the component
        that extends it."""
        out: list[tuple[str, str]] = []
        chain = self.chain(path)
        for below, base in zip(chain, chain[1:], strict=False):
            params = self.comps[base].type_params
            out += zip(params, self.comps[below].base_type_args, strict=False)
        return tuple(out)

    def levels(self, at: Path) -> Iterator[list[Path]]:
        """Where a name read in the text of `at` is looked up, innermost
        first: each enclosing component with the ones it extends, then the
        top level."""
        for k in range(len(at), 0, -1):
            yield self.chain(at[:k]) or [at[:k]]
        yield [()]

    def find_decl(self, texts: list[Path], name: str) -> RelationDecl | None:
        for p in texts:
            if (d := self.decls.get(p, {}).get(name)) is not None:
                return d
        return None

    def find_init(self, texts: list[Path], name: str) -> Instance | None:
        for p in texts:
            if (i := self.inits.get(p, {}).get(name)) is not None:
                return i
        return None

    def resolve(self, name: RelationName, scope: Scope) -> _Hit | None:
        if not name.instances:
            for texts in self.levels(scope.components):
                if (d := self.find_decl(texts, name.name)) is not None:
                    return _Hit(d, (), (), (), 0)
            return None
        first = name.instances[0]
        for texts in self.levels(scope.components):
            init = self.find_init(texts, first)
            if init is not None:
                return self._down(init, name.instances[1:], name.name)
        return None

    def enter(self, place: tuple[Level, ...], start: int,
              init: Instance) -> tuple[Level, ...] | None:
        """The instances down to `init`, an instance declared at `place`
        in the text of the component at `start` of the innermost chain;
        None where no component answers its name."""
        path = self.comp(init.component, init.scope.components)
        if path is None:
            return None
        level = Level(tuple(self.chain(path)), start)
        inner = (*place, level)
        level.env[path] = {p: TypeRef(a, place, start) for p, a in zip(
            self.comps[path].type_params, init.type_args, strict=False)}
        for k, c in enumerate(level.chain[:-1]):
            base = level.chain[k + 1]
            level.env[base] = {p: TypeRef(a, inner, k) for p, a in zip(
                self.comps[base].type_params, self.comps[c].base_type_args,
                strict=False)}
        return inner

    def _down(self, init: Instance, rest: tuple[str, ...], rel: str) -> _Hit | None:
        through: list[DeclId] = []
        args: list[tuple[str, str]] = []
        place: tuple[Level, ...] = ()
        start = 0
        while True:
            through.append(init.id)
            entered = self.enter(place, start, init)
            if entered is None:
                return None
            place = entered
            chain = place[-1].chain
            args += zip(self.comps[chain[0]].type_params, init.type_args, strict=False)
            args += self.base_arguments(chain[0])
            if not rest:
                for k, c in enumerate(chain):
                    d = self.decls.get(c, {}).get(rel)
                    if d is not None:
                        return _Hit(d, tuple(through), tuple(args), place, k)
                return None
            hit = next(((k, i) for k, c in enumerate(chain)
                        if (i := self.inits.get(c, {}).get(rest[0])) is not None), None)
            if hit is None:
                return None
            start, init = hit
            rest = rest[1:]

    def resolve_type(self, name: str, place: tuple[Level, ...], start: int,
                     depth: int = 0) -> tuple[TypeDecl | str, tuple[Level, ...], int]:
        """What the type `name` stands for, read at `place` in the text at
        `start` of the innermost chain: a primitive, or a declaration with
        the place and start its own names are read at. A component's type
        parameter reads as what its instance binds it to, and `o.T` reads
        `T` in the instance `o`. Raises ValueError where nothing answers the
        name."""
        if depth > 64:
            raise ValueError(f"type `{name}` does not end in a declaration")
        if name in PRIMITIVES:
            return name, (), 0
        head, dot, rest = name.partition(".")
        for k in range(len(place) - 1, -1, -1):
            level = place[k]
            first = start if k == len(place) - 1 else place[k + 1].outer_start
            for j in range(first, len(level.chain)):
                c = level.chain[j]
                if not dot:
                    if (ref := level.env.get(c, {}).get(name)) is not None:
                        return self.resolve_type(ref.name, ref.place, ref.start, depth + 1)
                    if (t := self.types.get(c, {}).get(name)) is not None:
                        return t, place[:k + 1], j
                elif (init := self.inits.get(c, {}).get(head)) is not None:
                    inner = self.enter(place[:k + 1], j, init)
                    if inner is None:
                        break
                    return self.resolve_type(rest, inner, 0, depth + 1)
        if not dot and (t := self.types.get((), {}).get(name)) is not None:
            return t, (), 0
        if dot and (init := self.inits.get((), {}).get(head)) is not None:
            inner = self.enter((), 0, init)
            if inner is not None:
                return self.resolve_type(rest, inner, 0, depth + 1)
        raise ValueError(f"no declaration of type `{name}`")


class SouffleIndex:
    def __init__(self, program: Program):
        self.tree = Tree(program)
        self._feeding: dict[DeclId, list[Occurrence]] = {}
        self._reading: dict[DeclId, list[Occurrence]] = {}
        for unit in program.units:
            self._add_unit(unit)
        for macro in program.macros:
            self._add_macro(macro)

    def _add_unit(self, unit: Unit) -> None:
        for decl, occurrence in self._unit_occurrences(unit):
            self._put(decl, occurrence)

    def _add_macro(self, macro: MacroCall) -> None:
        for decl, occurrence in self._macro_occurrences(macro):
            self._put(decl, occurrence)

    def _put(self, decl: DeclId, occurrence: Occurrence) -> None:
        into = self._feeding if occurrence.role is Role.FEEDS else self._reading
        into.setdefault(decl, []).append(occurrence)

    def _unit_occurrences(self, unit: Unit) -> Iterator[tuple[DeclId, Occurrence]]:
        yield from self._occurrence(unit.head, unit.scope, unit.id, Role.FEEDS, False)
        if unit.body is not None:
            for atom, negated in body_atoms(unit.body):
                yield from self._occurrence(atom, unit.scope, unit.id, Role.READS, negated)

    def _macro_occurrences(self, macro: MacroCall
                           ) -> Iterator[tuple[DeclId, Occurrence]]:
        if isinstance(macro, GridCall):
            width = 2 if Shape.of_call(macro).valued else 1
            atom = Atom(macro.relation, (*macro.keys, *(Wildcard(),) * width),
                        macro.span.first if macro.span else 0)
            yield from self._occurrence(atom, macro.scope, macro.id, Role.FEEDS, False)
        elif isinstance(macro, RigidCall):
            for placed in macro.names:
                hit = self.tree.resolve(RelationName((), placed), macro.scope)
                arity = len(hit.decl.columns) if hit else 1
                atom = Atom(RelationName((), placed), (Wildcard(),) * arity,
                            macro.span.first if macro.span else 0)
                yield from self._occurrence(atom, macro.scope, macro.id, Role.FEEDS,
                                            False)

    def _occurrence(self, atom: Atom, scope: Scope, unit: UnitId, role: Role,
                    negated: bool) -> Iterator[tuple[DeclId, Occurrence]]:
        hit = self.tree.resolve(atom.relation, scope)
        if hit is not None:
            yield hit.decl.id, Occurrence(unit, atom, role, negated)

    def changed(self, removed: tuple[Iterable[Unit], Iterable[MacroCall]],
                added: tuple[Iterable[Unit], Iterable[MacroCall]]) -> "SouffleIndex":
        """The index of the program this one indexes with the units and
        macro calls of `removed` taken out and those of `added` put in, its
        declarations the same. Shares every list it leaves as it is."""
        out = SouffleIndex.__new__(SouffleIndex)
        out.tree = self.tree
        out._feeding = dict(self._feeding)
        out._reading = dict(self._reading)
        units, macros = removed
        gone: set[UnitId] = set()
        touched: set[tuple[Role, DeclId]] = set()
        for decl, o in [*(x for u in units for x in self._unit_occurrences(u)),
                        *(x for m in macros for x in self._macro_occurrences(m))]:
            gone.add(o.unit)
            touched.add((o.role, decl))
        for role, decl in touched:
            into = out._feeding if role is Role.FEEDS else out._reading
            into[decl] = [o for o in into.get(decl, ()) if o.unit not in gone]
        units, macros = added
        copied: set[tuple[Role, DeclId]] = set(touched)
        for decl, o in [*(x for u in units for x in out._unit_occurrences(u)),
                        *(x for m in macros for x in out._macro_occurrences(m))]:
            into = out._feeding if o.role is Role.FEEDS else out._reading
            if (o.role, decl) not in copied:
                into[decl] = list(into.get(decl, ()))
                copied.add((o.role, decl))
            into[decl].append(o)
        return out

    def feeding(self, relation: DeclId) -> tuple[Occurrence, ...]:
        return tuple(sorted(self._feeding.get(relation, ()), key=lambda o: o.unit.index))

    def reading(self, relation: DeclId) -> tuple[Occurrence, ...]:
        return tuple(sorted(self._reading.get(relation, ()), key=lambda o: o.unit.index))

    def resolve(self, name: RelationName, scope: Scope) -> Resolved | Unresolved:
        hit = self.tree.resolve(name, scope)
        if hit is None:
            return Unresolved(name, scope)
        return Resolved(hit.decl.id, hit.through, hit.type_arguments)


_HELD: dict[int, tuple[weakref.ref[Program], SouffleIndex]] = {}
_HELD_LOCK = threading.Lock()


def held_index(program: Program) -> SouffleIndex | None:
    """The index held for `program`, where one is."""
    with _HELD_LOCK:
        got = _HELD.get(id(program))
    return got[1] if got is not None and got[0]() is program else None


def index_of(program: Program) -> SouffleIndex:
    """The index of `program`: the one held for it, else one built and held
    while the program lives."""
    got = held_index(program)
    if got is None:
        got = SouffleIndex(program)
        hold(program, got)
    return got


def hold(program: Program, index: SouffleIndex) -> None:
    """Holds `index` as `program`'s while the program lives."""
    key = id(program)
    with _HELD_LOCK:
        _HELD[key] = (weakref.ref(program, lambda _p, key=key: _drop(key)), index)


def _drop(key: int) -> None:
    with _HELD_LOCK:
        held = _HELD.get(key)
        if held is not None and held[0]() is None:
            del _HELD[key]
