"""Where the Souffle id at each leaf of type `Ident` in the relations of a
program comes from (`ident_sources`), and the text that stands for a minted
id (`Writer`), so that the rows of the concept case compare with the
engine's: an id a lib relation mints (a relation of a lib component with an
`Ident` column) denotes the set of its members, and an id a fact of the
solver writes is a number.

A leaf of a relation has one source (`Source`): `Minted` by a lib relation
(the id column of a lib relation that mints, or a leaf derived from one by
clauses; a key part that the clauses do not keep is found on the pair, from
the minting relation's rows), `Stored` (a number a clause writes), or
`Unresolved` with its reason. The sources of a program are the least
fixpoint over the clauses of the solver's own text, each at the instance
paths it runs at (`solver.graph.Graph`); a leaf of a lib relation whose
column is a type parameter of its component takes the source that the
clauses give the lib instance's columns of that parameter."""

from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass, replace
from enum import StrEnum
from typing import Final

from engine import AdtValue, Engine, NilValue, Program, RecordValue, RelationName, Row, Rows, UnitId, Value
from engine.program import (
    AliasType,
    Atom,
    AtomLiteral,
    BodyLiteral,
    Comparison,
    ComparisonOperator,
    ConstructorTerm,
    Disjunction,
    NumberTerm,
    RecordTerm,
    RecordType,
    RelationDecl,
    SubtypeType,
    Term,
    TypeName,
    Unit,
    Variable,
    own,
)
from solver.graph import Graph, InstancePath, followed
from solver.vocabulary import IDENT

EXAMPLE: Final = "Example"
"""The type of an Example leaf, which a minted id's member text leaves out."""

KEY: Final = "Key"
"""The type parameter whose columns key a lib relation that mints."""

MAX_DEPTH: Final = 8
"""How deep a record type the shape of a column follows."""

type Path = tuple[int, ...]
"""The index of a field of a record or of an argument of a constructor at
each step into a value."""


# Where a row holds the key of a minted id


@dataclass(frozen=True)
class At:
    """The value at `path` of column `column` of the row."""

    column: int
    path: Path


@dataclass(frozen=True)
class Within:
    """The value at `path` of the value that holds the id: the place of a
    key in a source that belongs to a type parameter, whichever column of
    whichever relation holds the value."""

    path: Path


@dataclass(frozen=True)
class Built:
    """A record (`constructor` None) or a constructor's value made of
    `parts`."""

    constructor: str | None
    parts: tuple["KeyValue", ...]


@dataclass(frozen=True)
class Free:
    """A key part that the row does not hold: the pair's rows of the minting
    relation give it, at every key that holds the id."""


type KeyValue = At | Within | Built | Free | int | float | str


# Sources


@dataclass(frozen=True)
class Minted:
    """The id comes from `relation`, a lib relation that mints: the id
    column of its rows, its key columns, its member columns, and, for each
    key column, how a row of the relation that holds the id holds the key's
    value. The id denotes the set of the members, the values of the member
    columns over the rows of `relation` that hold the id at that key, where
    a `Free` key part matches every value."""

    relation: RelationName
    id_column: int
    key_columns: tuple[int, ...]
    member_columns: tuple[int, ...]
    key: tuple[KeyValue, ...]


@dataclass(frozen=True)
class Stored:
    """The id is a number that a clause writes."""


@dataclass(frozen=True)
class Unresolved:
    """The leaf has no one source, for `reason`."""

    reason: str


type Source = Minted | Stored | Unresolved


class Kind(StrEnum):
    """What a column of a rows file (`parity.rerun.concept_rows`) holds at an
    Ident leaf: the text of the set of a minted id's members, or the number
    of a stored one."""

    MINTED = "minted"
    STORED = "stored"


def kind_of(source: Source | None) -> Kind | None:
    """The kind of column that a leaf with `source` makes in a rows file;
    None for a leaf that is no Ident, and for one that is unresolved, which
    the file leaves out."""
    match source:
        case Minted():
            return Kind.MINTED
        case Stored():
            return Kind.STORED
        case _:
            return None


def describe(source: Source) -> str:
    """The source in a reason."""
    match source:
        case Minted(relation=relation):
            return f"minted by {relation.text}"
        case Stored():
            return "stored"
        case Unresolved(reason=reason):
            return f"unresolved ({reason})"


def merged(sources: list[Source]) -> Source | None:
    """The one source of a leaf that clauses give `sources`: the first
    unresolved one, else the one source they all are, else the minted source
    they all are but for the key, with each key part they disagree on
    `Free`, else unresolved for two sources; None where they are none."""
    if not sources:
        return None
    unresolved = next((s for s in sources if isinstance(s, Unresolved)), None)
    if unresolved is not None:
        return unresolved
    distinct = list(dict.fromkeys(sources))
    if len(distinct) == 1:
        return distinct[0]
    minted = [s for s in distinct if isinstance(s, Minted)]
    if len(minted) == len(distinct) and len({replace(m, key=()) for m in minted}) == 1:
        first = minted[0]
        return replace(first, key=tuple(part if all(m.key[i] == part for m in minted) else Free()
                                        for i, part in enumerate(first.key)))
    return Unresolved("two sources: " + "; ".join(describe(s) for s in distinct))


# The shape of a column


@dataclass(frozen=True)
class Plain:
    """A type with no leaf of its own to treat apart."""


@dataclass(frozen=True)
class IdentLeaf:
    """A leaf of type `Ident`."""


@dataclass(frozen=True)
class ExampleLeaf:
    """A leaf of type `Example`."""


@dataclass(frozen=True)
class Fields:
    """A record's fields."""

    fields: tuple["Shape", ...]


type Shape = Plain | IdentLeaf | ExampleLeaf | Fields


def shape_at(shape: Shape, path: Path) -> Shape | None:
    """The shape at `path` of `shape`; None where it has none there."""
    for index in path:
        if not isinstance(shape, Fields) or index >= len(shape.fields):
            return None
        shape = shape.fields[index]
    return shape


def ident_paths(shape: Shape, prefix: Path = ()) -> Iterator[Path]:
    """The path of each leaf of type `Ident` in `shape`."""
    match shape:
        case IdentLeaf():
            yield prefix
        case Fields(fields=fields):
            for i, f in enumerate(fields):
                yield from ident_paths(f, (*prefix, i))
        case _:
            pass


@dataclass(frozen=True)
class Minting:
    """The columns of a lib relation that mints."""

    id_column: int
    key_columns: tuple[int, ...]
    member_columns: tuple[int, ...]


@dataclass(frozen=True)
class Info:
    """A relation of the program: its columns' shapes; for a lib relation,
    the type parameter each column is declared with, and, where it mints,
    its columns."""

    shapes: tuple[Shape, ...]
    lib: bool
    parameters: tuple[str | None, ...]
    minting: Minting | None


# The clauses


@dataclass(frozen=True)
class Static:
    """What a clause at an instance path gives, independent of the sources:
    the relation its head names, the place of each variable in the head,
    the atoms that bind each variable, and the variables a `=` fixes to a
    number."""

    head: RelationName
    places: Mapping[str, At]
    bindings: Mapping[str, tuple[tuple[RelationName, Atom, int, Path], ...]]
    numbers: frozenset[str]


@dataclass(frozen=True)
class LeafSlot:
    """A leaf of a relation of the solver's own text."""

    relation: RelationName
    column: int
    path: Path


@dataclass(frozen=True)
class ParameterSlot:
    """A leaf of the value of a type parameter at a lib instance."""

    instance: InstancePath
    parameter: str
    path: Path


type Slot = LeafSlot | ParameterSlot


def positive_atoms(body: tuple[BodyLiteral, ...]) -> Iterator[Atom]:
    """The atoms of `body` that bind variables: those outside a negation
    and an aggregate, through disjunctions."""
    for lit in body:
        match lit:
            case AtomLiteral(atom=atom, negated=False):
                yield atom
            case Disjunction(branches=branches):
                for branch in branches:
                    yield from positive_atoms(branch)
            case _:
                pass


def variables_in(term: Term, column: int, path: Path) -> Iterator[tuple[str, int, Path]]:
    """Each variable that `term` holds directly or through records and
    constructors, with the column and the path into the column's value."""
    match term:
        case Variable(name=name):
            yield name, column, path
        case RecordTerm(args=args) | ConstructorTerm(args=args):
            for i, arg in enumerate(args):
                yield from variables_in(arg, column, (*path, i))
        case _:
            pass


def static_of(graph: Graph, unit: Unit, at: InstancePath) -> Static | None:
    """The `Static` of `unit` at `at`; None where its head names no
    relation."""
    head = graph.place(at, unit.head.relation)
    if head is None:
        return None
    places: dict[str, At] = {}
    for column, arg in enumerate(unit.head.args):
        for name, c, path in variables_in(arg, column, ()):
            places.setdefault(name, At(c, path))
    bindings: dict[str, list[tuple[RelationName, Atom, int, Path]]] = {}
    numbers: set[str] = set()
    for atom in positive_atoms(unit.body or ()):
        place = graph.place(at, atom.relation)
        if place is None:
            continue
        for column, arg in enumerate(atom.args):
            for name, c, path in variables_in(arg, column, ()):
                bindings.setdefault(name, []).append((place, atom, c, path))
    for lit in unit.body or ():
        match lit:
            case Comparison(op=ComparisonOperator.EQ, lhs=Variable(name=name), rhs=NumberTerm()) \
                    | Comparison(op=ComparisonOperator.EQ, lhs=NumberTerm(), rhs=Variable(name=name)):
                numbers.add(name)
            case _:
                pass
    return Static(head, places, {k: tuple(v) for k, v in bindings.items()}, frozenset(numbers))


def term_key(term: Term, path: Path, places: Mapping[str, At]) -> KeyValue | None:
    """The value at `path` of the value of `term`, as a row of the clause's
    head holds it; None where the head does not hold it."""
    match term:
        case RecordTerm(args=args) | ConstructorTerm(args=args) if path:
            return term_key(args[path[0]], path[1:], places) if path[0] < len(args) else None
        case Variable(name=name):
            place = places.get(name)
            return None if place is None else At(place.column, (*place.path, *path))
        case _ if path:
            return None
        case NumberTerm(value=value):
            return value
        case RecordTerm(args=args):
            return built(None, args, places)
        case ConstructorTerm(name=name, args=args):
            return built(name, args, places)
        case _:
            return None


def built(constructor: str | None, args: tuple[Term, ...], places: Mapping[str, At]) -> Built | None:
    """The `Built` value of `args` as the head holds them; None where it
    does not hold one."""
    parts = tuple(term_key(a, (), places) for a in args)
    return None if any(p is None for p in parts) else Built(constructor, tuple(p for p in parts if p is not None))


type KeyMap = Callable[[At | Within], KeyValue | None]
"""Where a key value that stands at a place now stands; None where it stands
nowhere."""


def map_key(key: KeyValue, where: KeyMap) -> KeyValue | None:
    """`key` with each `At` and `Within` as `where` places it; None where
    `where` places one nowhere. A `Free` stays."""
    match key:
        case At() | Within():
            return where(key)
        case Built(constructor=constructor, parts=parts):
            mapped = tuple(map_key(p, where) for p in parts)
            return None if any(p is None for p in mapped) else Built(constructor, tuple(p for p in mapped if p is not None))
        case _:
            return key


def with_keys(source: Source, where: KeyMap) -> Source:
    """`source` with each key part as `where` places it, and `Free` for a
    part it places nowhere."""
    if not isinstance(source, Minted):
        return source
    return replace(source, key=tuple(Free() if (k := map_key(part, where)) is None else k for part in source.key))


class IdentSources:
    """The sources of the Ident leaves of the relations of `program`."""

    def __init__(self, engine: Engine, program: Program) -> None:
        program = engine.expand(program)
        self.graph = Graph(program, engine)
        graph = self.graph
        self._links = {k: graph.link(t) for k, (t, _at) in graph.type_decls.items()
                       if isinstance(t, AliasType | SubtypeType)}
        self._infos: dict[RelationName, Info | None] = {}
        self._contributions: dict[Slot, dict[tuple[UnitId, InstancePath], Source]] = {}
        placed = [(u, at) for u in program.units if u.span is None or own(u.span) for at in graph.paths_of(u)]
        statics = [(u, at, s) for u, at in placed if (s := static_of(graph, u, at)) is not None]
        for _ in range(len(statics) + 2):
            if not self._round(statics):
                break

    # The shapes

    def shape(self, key: str, depth: int = 0) -> Shape:
        """The shape of a column whose type, as `Graph` reads it, is `key`."""
        chain = followed(self._links, key)
        if IDENT in chain:
            return IdentLeaf()
        if EXAMPLE in chain:
            return ExampleLeaf()
        held = self.graph.type_decls.get(key)
        decl, at = held if held is not None else (None, None)
        if isinstance(decl, RecordType) and depth < MAX_DEPTH:
            return Fields(tuple(self.shape(self.graph.reading(f.type, decl.scope.components, at), depth + 1)
                                for f in decl.fields))
        return Plain()

    def info(self, relation: RelationName) -> Info | None:
        """The `Info` of `relation`, named by its instance path and its name;
        None where the program declares no relation there."""
        if relation not in self._infos:
            self._infos[relation] = self._info(relation)
        return self._infos[relation]

    def _info(self, relation: RelationName) -> Info | None:
        at, name = relation.instances, RelationName((), relation.name)
        got = self.graph.decl(at, name)
        types = self.graph.column_types(at, name)
        if got is None or types is None or len(types) != len(got[0].columns):
            return None
        decl, args = got
        shapes = tuple(self.shape(t) for t in types)
        lib = not own(decl.span)
        parameters = tuple(c.type.name if c.type.argument(args) is not None else None for c in decl.columns) \
            if lib else (None,) * len(decl.columns)
        return Info(shapes, lib, parameters, self._minting(decl, parameters) if lib else None)

    @staticmethod
    def _minting(decl: RelationDecl, parameters: tuple[str | None, ...]) -> Minting | None:
        """The columns of `decl`, a lib relation, where a column of it is
        declared with the type `Ident`, not through a type parameter; None
        where none is. Raises `ValueError` where several are, a case the
        lib has none of."""
        ids = [i for i, c in enumerate(decl.columns) if c.type == TypeName((), IDENT)]
        if len(ids) > 1:
            raise ValueError(f"the lib relation {decl.name} has {len(ids)} columns of type {IDENT}")
        if not ids:
            return None
        keys = tuple(i for i, p in enumerate(parameters) if p == KEY)
        return Minting(ids[0], keys, tuple(i for i in range(len(decl.columns)) if i != ids[0] and i not in keys))

    # The fixpoint

    def _round(self, statics: list[tuple[Unit, InstancePath, Static]]) -> bool:
        """One pass over the clauses: the source each gives the leaves of its
        head, as the sources read stand; whether one changed."""
        changed = False
        for unit, at, static in statics:
            info = self.info(static.head)
            if info is None or len(unit.head.args) != len(info.shapes):
                continue
            for column, arg in enumerate(unit.head.args):
                for path in ident_paths(info.shapes[column]):
                    source = merged(self._sourced(arg, path, static))
                    if source is None:
                        continue
                    if info.lib:
                        parameter = info.parameters[column]
                        if parameter is None:
                            continue
                        slot: Slot = ParameterSlot(static.head.instances, parameter, path)
                        source = self._within(source, column)
                    else:
                        slot = LeafSlot(static.head, column, path)
                    held = self._contributions.setdefault(slot, {})
                    if held.get((unit.id, at)) != source:
                        held[(unit.id, at)] = source
                        changed = True
        return changed

    def _sourced(self, term: Term, path: Path, static: Static) -> list[Source]:
        """The sources of the leaf at `path` of the value of `term` in a
        clause head."""
        match term:
            case RecordTerm(args=args) | ConstructorTerm(args=args) if path:
                if path[0] >= len(args):
                    return [Unresolved("the head holds no such field")]
                return self._sourced(args[path[0]], path[1:], static)
            case NumberTerm() if not path:
                return [Stored()]
            case Variable(name=name):
                out: list[Source] = []
                for place, atom, column, at in static.bindings.get(name, ()):
                    source = self.read(place, column, (*at, *path))
                    if source is not None:
                        out.append(self._translated(source, atom, static))
                if name in static.numbers:
                    out.append(Stored())
                if not static.bindings.get(name) and name not in static.numbers:
                    out.append(Unresolved(f"no atom binds {name}"))
                return out
            case _:
                return [Unresolved("the clause computes the id")]

    @staticmethod
    def _translated(source: Source, atom: Atom, static: Static) -> Source:
        """`source`, a source of a leaf of a row of `atom`, with each key
        value as a row of the clause's head holds it."""
        def hold(key: At | Within) -> KeyValue | None:
            if not isinstance(key, At) or key.column >= len(atom.args):
                return None
            return term_key(atom.args[key.column], key.path, static.places)
        return with_keys(source, hold)

    @staticmethod
    def _within(source: Source, column: int) -> Source:
        """`source`, of a leaf in `column` of a row of a lib relation, with
        each key value as a place within the value of the type parameter of
        that column."""
        def inside(key: At | Within) -> KeyValue | None:
            return Within(key.path) if isinstance(key, At) and key.column == column else None
        return with_keys(source, inside)

    # The sources

    def merged(self, slot: Slot) -> Source | None:
        """The source that the clauses give `slot`; None where they give
        none yet."""
        return merged(list(self._contributions.get(slot, {}).values()))

    def read(self, relation: RelationName, column: int, path: Path) -> Source | None:
        """The source of the leaf at `path` of `column` of `relation`, as
        the clauses read stand; None where it has none yet or is no Ident
        leaf."""
        info = self.info(relation)
        if info is None or column >= len(info.shapes) or shape_at(info.shapes[column], path) != IdentLeaf():
            return None
        if not info.lib:
            return self.merged(LeafSlot(relation, column, path))
        minting = info.minting
        if minting is not None and column == minting.id_column:
            return Minted(relation, minting.id_column, minting.key_columns, minting.member_columns,
                          tuple(At(k, ()) for k in minting.key_columns))
        parameter = info.parameters[column]
        if parameter is None:
            return None
        got = self.merged(ParameterSlot(relation.instances, parameter, path))
        if got is None:
            return None

        def here(key: At | Within) -> KeyValue | None:
            return At(column, key.path) if isinstance(key, Within) else None
        return with_keys(got, here)

    def of(self, relation: RelationName, column: int, path: Path) -> Source | None:
        """The source of the leaf at `path` of `column` of `relation`; None
        where the leaf is no leaf of type `Ident`. A minted source whose
        members hold an id that is not minted is unresolved."""
        info = self.info(relation)
        if info is None or column >= len(info.shapes) or shape_at(info.shapes[column], path) != IdentLeaf():
            return None
        return self._usable(self.read(relation, column, path) or Unresolved("no clause gives it"), ())

    def _usable(self, source: Source, inside: tuple[RelationName, ...]) -> Source:
        """`source`, or the unresolved source for a member of a minted
        source that is not minted."""
        if not isinstance(source, Minted) or source.relation in inside:
            return source
        info = self.info(source.relation)
        assert info is not None
        for column in source.member_columns:
            for path in ident_paths(info.shapes[column]):
                member = self._usable(self.read(source.relation, column, path) or Unresolved("no clause gives it"),
                                      (*inside, source.relation))
                if not isinstance(member, Minted):
                    return Unresolved(f"a member of {source.relation.text} holds an id that is {describe(member)}")
        return source

    def minting(self, source: Minted) -> list[RelationName]:
        """The relations whose rows write `source`: its relation and, at any
        depth, those that the ids of its members are minted by."""
        out: dict[RelationName, None] = {}

        def walk(s: Minted) -> None:
            if s.relation in out:
                return
            out[s.relation] = None
            info = self.info(s.relation)
            assert info is not None
            for column in s.member_columns:
                for path in ident_paths(info.shapes[column]):
                    member = self.read(s.relation, column, path)
                    if isinstance(member, Minted):
                        walk(member)

        walk(source)
        return list(out)


def ident_sources(engine: Engine, program: Program) -> IdentSources:
    """The sources of the Ident leaves of the relations of `program`, a
    program that `Loaded.taking` gives for a case, read with its macro calls
    expanded."""
    return IdentSources(engine, program)


# The text of a minted id


class NoMembers(LookupError):
    """The minting relation's rows hold no row with the id at the key."""


class Ambiguous(LookupError):
    """The minting relation's rows give the id two member sets at the keys
    that agree with the row's key parts."""


def key_value(key: KeyValue, row: Row) -> Value | Free | None:
    """The value that `key` gives at `row`, `Free` for a part the row does
    not hold; None where the row holds no value there."""
    match key:
        case At(column=column, path=path):
            value: Value = row[column]
            for index in path:
                match value:
                    case RecordValue(fields=fields) | AdtValue(args=fields) if index < len(fields):
                        value = fields[index]
                    case _:
                        return None
            return value
        case Built(constructor=constructor, parts=parts):
            values = tuple(key_value(p, row) for p in parts)
            fields = tuple(v for v in values if v is not None and not isinstance(v, Free))
            if len(fields) != len(values):
                return None
            return RecordValue(fields) if constructor is None else AdtValue(constructor, fields)
        case Within():
            return None
        case _:
            return key


def leaves(value: Value) -> list[int | float | str]:
    """The leaves of `value`, as `rerun --json` writes a row's values."""
    match value:
        case RecordValue(fields=fields) | AdtValue(args=fields):
            return [leaf for field in fields for leaf in leaves(field)]
        case NilValue():
            return []
        case _:
            return [value]


class Writer:
    """The text of a minted id: its members' leaves, a member as
    `[leaf,leaf,...]` with each Example leaf left out and each Ident leaf
    as the text of its own set, and the set as `{member,member,...}` with
    the members sorted by their text. `rows` gives the rows of each relation
    that `IdentSources.minting` names."""

    def __init__(self, sources: IdentSources, rows: Mapping[RelationName, Rows]) -> None:
        self.sources = sources
        self.rows = rows
        self._held: dict[RelationName, dict[Value, dict[tuple[Value, ...], list[Row]]]] = {}
        self._texts: dict[tuple[RelationName, tuple[Value | Free, ...], Value], str] = {}

    def text(self, source: Minted, ident: Value, row: Row) -> str:
        """The text of the id `ident` that `source` gives at the key `row`
        holds: the set of the members at the keys of the minting relation's
        rows that hold the id and agree with each key part that is not
        `Free`. Raises `NoMembers` where no row holds the id at such a key,
        and `Ambiguous` where the keys give the id two member sets."""
        keys = tuple(key_value(k, row) for k in source.key)
        at = tuple(k for k in keys if k is not None)
        if len(at) != len(keys):
            raise NoMembers(f"the row holds no key of {source.relation.text}")
        got = self._texts.get((source.relation, at, ident))
        if got is None:
            found = self._found(source, at, ident)
            if not found:
                raise NoMembers(f"the id {ident} has no row of {source.relation.text} at the key of the row")
            texts = {"{" + ",".join(sorted(self._member(source, m) for m in members)) + "}" for members in found}
            if len(texts) > 1:
                raise Ambiguous(f"the id {ident} of {source.relation.text} has other members at two keys")
            got = self._texts[source.relation, at, ident] = texts.pop()
        return got

    def _found(self, source: Minted, at: tuple[Value | Free, ...], ident: Value) -> list[list[Row]]:
        """The rows of the minting relation that hold `ident`, grouped by
        key, at the keys that equal `at` at each part that is not `Free`."""
        keyed = self._index(source).get(ident, {})
        if not any(isinstance(part, Free) for part in at):
            members = keyed.get(tuple(part for part in at if not isinstance(part, Free)))
            return [members] if members else []
        return [members for key, members in keyed.items()
                if all(isinstance(part, Free) or part == value for part, value in zip(at, key, strict=True))]

    def _index(self, source: Minted) -> dict[Value, dict[tuple[Value, ...], list[Row]]]:
        """The rows of the minting relation by id, then by key."""
        if source.relation not in self._held:
            index: dict[Value, dict[tuple[Value, ...], list[Row]]] = {}
            for r in self.rows[source.relation]:
                index.setdefault(r[source.id_column], {}).setdefault(tuple(r[k] for k in source.key_columns), []).append(r)
            self._held[source.relation] = index
        return self._held[source.relation]

    def _member(self, source: Minted, row: Row) -> str:
        info = self.sources.info(source.relation)
        assert info is not None
        leaves: list[str] = []
        for column in source.member_columns:
            leaves += self._leaves(row[column], info.shapes[column], source.relation, column, (), row)
        return "[" + ",".join(leaves) + "]"

    def _leaves(self, value: Value, shape: Shape, relation: RelationName, column: int, path: Path, row: Row
                ) -> list[str]:
        match shape:
            case ExampleLeaf():
                return []
            case IdentLeaf():
                member = self.sources.read(relation, column, path)
                assert isinstance(member, Minted)
                return [self.text(member, value, row)]
            case Fields(fields=fields) if isinstance(value, RecordValue):
                return [t for i, (f, v) in enumerate(zip(fields, value.fields, strict=False))
                        for t in self._leaves(v, f, relation, column, (*path, i), row)]
            case _:
                return [str(leaf) for leaf in leaves(value)]
