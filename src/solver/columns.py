"""The column types of the relations of a solver's program as the model
reads them, a parameter's case columns among them, and the reading of a
witness `assign` argument as a value of a column's type."""

from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass

from engine.engine import unresolved
from engine.memo import ByIdentity
from engine import (
    AdtValue,
    Engine,
    Program,
    RecordValue,
    RelationName,
    Value,
)
from engine.program import (
    Primitive,
    declared_value,
    TypeName,
    ValueReading,
    own,
    AdtType,
    AliasType,
    RelationDecl,
    SubtypeType,
    TypeDecl,
)
from engine.quotes import quotes
from engine.text import prefixed
from solver.graph import (
    Graph,
    followed,
)
from solver.vocabulary import (
    CHOICE,
    IDENT,
)
from solver.witness import AssignArg
from solver.aggregate import Solver
from solver.readers import parameter


# Column types


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
    (`solver.readers.parameter`, `column_reading`)."""
    return column_reading(solver.engine, solver.program,
                          parameter(solver, name))


@dataclass(frozen=True)
class ColumnTypes:
    """A relation's column types: `types`, each as `Graph.column_types`
    reads it (`Graph.type_at`), which every comparison of types reads; and
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
    return ColumnTypes(tuple(c.type.text for c in decl.columns), tuple(got))


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
    links = {k: graph.link(t) for k, (t, _at) in graph.type_decls.items()
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
    read as the type the instance gives it
    (`engine.program.declared_value`). Raises ValueError for a type name
    that resolves to no declaration (`_by_key`)."""
    value = _arg_read(solver, arg, _nullary_constructors(solver.program))
    if isinstance(value, ArgUnknown):
        return value
    by_key = _by_key(solver.engine, solver.program)
    decl, at = by_key(type)
    fits = declared_value(value, decl, at,
                          lambda name, scope: by_key(scope(name)),
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


type _Scope = Callable[[TypeName], str]
"""The reading of a type name in the scope that declares the type it is
read in, as `column_types` names a type."""


def _by_key(engine: Engine, program: Program
            ) -> Callable[[str], tuple[TypeDecl | Primitive, _Scope]]:
    """The type a name of a type as `column_types` names it denotes: a
    primitive, or a type the program declares by its key
    (`Graph.type_decls`), with the reading of a name in the scope that
    declares it, at the instance path the key gives (`Graph.reading`).
    Raises ValueError for a name that is neither a primitive nor such a
    key."""
    graph = Graph(program, engine)

    def read(key: str) -> tuple[TypeDecl | Primitive, _Scope]:
        if (primitive := Primitive.named(key)) is not None:
            return primitive, _as_named
        held = graph.type_decls.get(key)
        if held is None:
            raise ValueError(f"type `{key}` resolves to no declaration")
        t, at = held
        own_scope = t.scope.components
        return t, ((lambda n: graph.reading(n, own_scope, at))
                   if own(t.span) else _as_named)

    return read


def _as_named(name: TypeName) -> str:
    return name.text


_VALUES = ValueReading[Value](
    primitive=lambda v, kind: v if isinstance(v, kind.values)
    and not isinstance(v, bool) else None,
    record=lambda v: v.fields if isinstance(v, RecordValue) else None,
    constructor=lambda v: (v.constructor, v.args)
    if isinstance(v, AdtValue) else None)
"""A value as the value it is."""


