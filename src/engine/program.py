"""The parsed program an engine gives: declarations, units, macro calls and
comments, as values with no program text in them."""

from dataclasses import dataclass, field
from enum import StrEnum


@dataclass(frozen=True)
class Span:
    """The lines a unit, declaration or macro call takes in the text it was
    parsed from, 1-based and inclusive. `file` is None for the text handed
    to `parse`, else the path the engine resolved the include to."""

    first: int
    last: int
    file: str | None = field(kw_only=True)
    width: int | None = field(default=None, kw_only=True)
    """The length of the longest line the part occupies as written; None
    for a part an operation wrote."""


@dataclass(frozen=True)
class UnitId:
    """A unit's identity within one program and the programs the engine's
    operations make from it."""

    index: int


@dataclass(frozen=True)
class DeclId:
    """A declaration's identity within one program: a type, a relation, a
    component, an instance, or a functor."""

    index: int


@dataclass(frozen=True)
class Scope:
    """The component a declaration or unit stands in, as the path of
    component names from the top level; empty at the top level."""

    components: tuple[str, ...]


@dataclass(frozen=True)
class RelationName:
    """A relation as a statement names it: the instance path it is read
    through, empty for a relation of the statement's own scope, and the
    relation's name. `params.bg` is `RelationName(("params",), "bg")`."""

    instances: tuple[str, ...]
    name: str

    @property
    def text(self) -> str:
        """The name as a statement writes it, `params.bg`."""
        return ".".join((*self.instances, self.name))


# Values


@dataclass(frozen=True)
class RecordValue:
    """A record value: its fields in declaration order."""

    fields: tuple["Value", ...]

    def __hash__(self) -> int:
        # Held after the first call: a value is hashed at each lookup of
        # the tables that key by it, and its hash walks every field.
        h = self.__dict__.get("_hash")
        if h is None:
            h = hash(self.fields)
            object.__setattr__(self, "_hash", h)
        return h


@dataclass(frozen=True)
class AdtValue:
    """An ADT value: its constructor and the constructor's arguments."""

    constructor: str
    args: tuple["Value", ...]

    def __hash__(self) -> int:
        # Held after the first call, as `RecordValue`'s.
        h = self.__dict__.get("_hash")
        if h is None:
            h = hash((self.constructor, self.args))
            object.__setattr__(self, "_hash", h)
        return h


type Value = int | float | str | RecordValue | AdtValue
"""One column's value: a number, a float, a symbol, a record or an ADT
value."""


def value_text(value: Value) -> str:
    """A value as a program's text and its fact files write it: `$Count`,
    `$Rank($Big)`, `[$Count, $Or]`, a number or a symbol as it stands."""
    match value:
        case bool():
            return str(int(value))
        case int() | float() | str():
            return str(value)
        case RecordValue(fields=fields):
            return "[" + ", ".join(value_text(f) for f in fields) + "]"
        case AdtValue(constructor=c, args=()):
            return f"${c}"
        case AdtValue(constructor=c, args=args):
            return f"${c}(" + ", ".join(value_text(a) for a in args) + ")"

type Row = tuple[Value, ...]
type Rows = tuple[Row, ...]

type Grid = tuple[tuple[int, ...], ...]
"""Rows of colors."""


# Types


@dataclass(frozen=True)
class TypeField:
    """A named, typed field of a record type or of an ADT constructor.
    (The syntax `Field`; a header field is `solver.HeaderField`.)"""

    name: str
    type: str


@dataclass(frozen=True)
class ConstructorDecl:
    """One constructor of an ADT, with its fields and whether it opens a
    line of its own."""

    name: str
    fields: tuple[TypeField, ...]
    span: Span
    own_line: bool


@dataclass(frozen=True)
class AdtType:
    id: DeclId
    name: str
    scope: Scope
    constructors: tuple[ConstructorDecl, ...]
    span: Span


@dataclass(frozen=True)
class RecordType:
    id: DeclId
    name: str
    scope: Scope
    fields: tuple[TypeField, ...]
    span: Span


@dataclass(frozen=True)
class AliasType:
    """`.type A = B`."""

    id: DeclId
    name: str
    scope: Scope
    target: str
    span: Span


@dataclass(frozen=True)
class SubtypeType:
    """`.type A <: B`."""

    id: DeclId
    name: str
    scope: Scope
    base: str
    span: Span


@dataclass(frozen=True)
class UnionType:
    """`.type A = B | C`."""

    id: DeclId
    name: str
    scope: Scope
    members: tuple[str, ...]
    span: Span


type TypeDecl = AdtType | RecordType | AliasType | SubtypeType | UnionType


# Relations, components, instances


class Qualifier(StrEnum):
    """A relation qualifier the language takes."""

    INLINE = "inline"
    NO_INLINE = "no_inline"
    MAGIC = "magic"
    NO_MAGIC = "no_magic"
    BRIE = "brie"
    BTREE = "btree"
    BTREE_DELETE = "btree_delete"
    EQREL = "eqrel"
    OVERRIDABLE = "overridable"


@dataclass(frozen=True)
class Column:
    """A relation's column: its attribute name and type."""

    name: str
    type: str


@dataclass(frozen=True)
class RelationDecl:
    id: DeclId
    name: str
    scope: Scope
    columns: tuple[Column, ...]
    qualifiers: tuple[Qualifier, ...]
    choice_domain: tuple[str, ...]
    """The columns a `choice-domain` clause names; empty where it has none."""
    span: Span
    chart_of: str | None = field(default=None, kw_only=True)
    """The RIGID block whose chart this relation is; None for any other
    relation."""


@dataclass(frozen=True)
class Component:
    id: DeclId
    name: str
    scope: Scope
    type_params: tuple[str, ...]
    base: str | None
    """The component it extends; None where it extends none."""
    base_type_args: tuple[str, ...]
    span: Span | None
    """None for a component an operation wrote."""


@dataclass(frozen=True)
class Instance:
    """`.init <name> = <component><type args>`."""

    id: DeclId
    name: str
    scope: Scope
    component: str
    type_args: tuple[str, ...]
    span: Span | None
    """None for an instance an operation wrote."""


@dataclass(frozen=True)
class FunctorDecl:
    """`.functor <name>(<params>): <result>`."""

    id: DeclId
    name: str
    params: tuple[TypeField, ...]
    result: str
    span: Span
    stateful: bool = field(default=False, kw_only=True)


# Terms


@dataclass(frozen=True)
class Variable:
    name: str


@dataclass(frozen=True)
class Wildcard:
    pass


@dataclass(frozen=True)
class NumberTerm:
    value: int | float


@dataclass(frozen=True)
class StringTerm:
    value: str


@dataclass(frozen=True)
class DefinedName:
    """A name a `#define` binds, as a term."""

    name: str


@dataclass(frozen=True)
class ConstructorTerm:
    """`$Name(args)`."""

    name: str
    args: tuple["Term", ...]


@dataclass(frozen=True)
class RecordTerm:
    """`[a, b]`."""

    args: tuple["Term", ...]


class Intrinsic(StrEnum):
    """A functor the language provides."""

    MIN = "min"
    MAX = "max"
    CAT = "cat"
    ORD = "ord"
    STRLEN = "strlen"
    SUBSTR = "substr"
    TO_NUMBER = "to_number"
    TO_STRING = "to_string"
    TO_FLOAT = "to_float"
    TO_UNSIGNED = "to_unsigned"
    RANGE = "range"
    AUTOINC = "autoinc"


@dataclass(frozen=True)
class IntrinsicCall:
    functor: Intrinsic
    args: tuple["Term", ...]


@dataclass(frozen=True)
class FunctorCall:
    """`@name(args)`: a call of a declared functor."""

    name: str
    args: tuple["Term", ...]


class UnaryOperator(StrEnum):
    NEGATE = "-"
    BNOT = "bnot"
    LNOT = "lnot"


class BinaryOperator(StrEnum):
    ADD = "+"
    SUB = "-"
    MUL = "*"
    DIV = "/"
    MOD = "%"
    POW = "^"
    BAND = "band"
    BOR = "bor"
    BXOR = "bxor"
    BSHL = "bshl"
    BSHR = "bshr"
    BSHRU = "bshru"
    LAND = "land"
    LOR = "lor"
    LXOR = "lxor"


@dataclass(frozen=True)
class Cast:
    """`as(term, type)`."""

    term: "Term"
    type: str


@dataclass(frozen=True)
class UnaryTerm:
    op: UnaryOperator
    arg: "Term"


@dataclass(frozen=True)
class BinaryTerm:
    op: BinaryOperator
    lhs: "Term"
    rhs: "Term"
    parens: bool = field(default=False, compare=False)
    """The text writes the term inside parentheses; a term an operation
    builds has none. Two terms that differ only here are equal."""


class AggregateOperator(StrEnum):
    COUNT = "count"
    SUM = "sum"
    MIN = "min"
    MAX = "max"
    MEAN = "mean"


@dataclass(frozen=True)
class Aggregate:
    op: AggregateOperator
    expr: "Term | None"
    """The aggregated term; None for `count`."""
    body: tuple["BodyLiteral", ...]


type Term = (Variable | Wildcard | NumberTerm | StringTerm | DefinedName
             | ConstructorTerm | RecordTerm | IntrinsicCall | FunctorCall
             | UnaryTerm | BinaryTerm | Aggregate | Cast)


# Literals and units


@dataclass(frozen=True)
class Atom:
    relation: RelationName
    args: tuple[Term, ...]
    line: int


@dataclass(frozen=True)
class AtomLiteral:
    """A body atom, negated or not."""

    atom: Atom
    negated: bool


class ComparisonOperator(StrEnum):
    EQ = "="
    NE = "!="
    LT = "<"
    LE = "<="
    GT = ">"
    GE = ">="


@dataclass(frozen=True)
class Comparison:
    op: ComparisonOperator
    lhs: Term
    rhs: Term
    line: int


@dataclass(frozen=True)
class Disjunction:
    """`(a ; b)`: each branch a conjunction of literals."""

    branches: tuple[tuple["BodyLiteral", ...], ...]
    line: int


@dataclass(frozen=True)
class BoolLiteral:
    """`true` or `false`."""

    value: bool


type BodyLiteral = AtomLiteral | Comparison | Disjunction | BoolLiteral


@dataclass(frozen=True)
class Plan:
    """A unit's `.plan`: per version, the order of its body atoms."""

    orders: tuple[tuple[int, tuple[int, ...]], ...]


@dataclass(frozen=True)
class Unit:
    """One rule or fact. A clause with several heads gives one unit per
    head."""

    id: UnitId
    scope: Scope
    head: Atom
    body: tuple[BodyLiteral, ...] | None
    """None for a fact."""
    plan: Plan | None
    span: Span | None
    """None for a unit an operation wrote."""
    subsumptive: bool = field(default=False, kw_only=True)
    """A subsumptive clause, `head <= dominating :- rest.`: the body leads
    with the dominating atom."""


# Macro calls


class GridForm(StrEnum):
    """Which cells a GRID call emits: every cell with its value (`dense`),
    each cell marked `1` (`mask`), or each cell holding a color digit with
    its value (`sparse`); `_` marks an empty cell in the last two."""

    DENSE = "dense"
    MASK = "mask"
    SPARSE = "sparse"


@dataclass(frozen=True)
class GridCell:
    """One cell of a GRID call: its term, and whether it is a stamp's
    anchor cell, written `@<term>`."""

    term: "Term"
    anchor: bool


@dataclass(frozen=True)
class GridCall:
    """A GRID macro call, which states a relation's value as a grid of
    cells, a unit of its own."""

    id: UnitId
    scope: Scope
    form: GridForm
    stamp: bool
    """Each emitted cell's place is its offset from the anchor cell."""
    height: int
    width: int
    relation: RelationName
    keys: tuple[Term, ...]
    cells: tuple[tuple[GridCell, ...], ...]
    span: Span | None


@dataclass(frozen=True)
class RigidCall:
    """A RIGID macro call, a unit of its own: the block's name, the units
    of its body, and the names it binds."""

    id: UnitId
    scope: Scope
    block: str
    body: tuple[UnitId, ...]
    names: tuple[str, ...]
    span: Span | None


type MacroCall = GridCall | RigidCall


# Preprocessor items and comments


@dataclass(frozen=True)
class Include:
    path: str
    line: int
    file: str | None = field(default=None, kw_only=True)
    """None for the text handed to `parse`, else the path the engine
    resolved the include to."""


@dataclass(frozen=True)
class Define:
    """`#define <name> <value>`, or a macro with parameters."""

    name: str
    params: tuple[str, ...] | None
    """The macro's parameters; None for a constant."""
    value: Term | None
    """The value parsed as a term; None where the body is no term (a macro
    with parameters)."""
    line: int
    file: str | None = field(default=None, kw_only=True)
    """None for the text handed to `parse`, else the path the engine
    resolved the include to."""


@dataclass(frozen=True)
class Comment:
    """One comment. `above` is the unit or declaration that the comment's
    block of own-line comments stands directly above, None where it stands
    above none; a trailing comment has `own_line` false and `above` None."""

    line: int
    column: int
    text: str
    """The comment's text without its delimiters, `//` or `/*` and `*/`."""
    own_line: bool
    above: UnitId | DeclId | None
    file: str | None = field(kw_only=True)
    """None for the text handed to `parse`, else the path the engine
    resolved the include to."""
    block: bool = field(default=False, kw_only=True)
    """A `/* */` comment; a `//` comment otherwise."""


@dataclass(frozen=True)
class Program:
    """A parsed program ([engine](src/engine/engine.py) `Engine.parse`)."""

    types: tuple[TypeDecl, ...]
    relations: tuple[RelationDecl, ...]
    components: tuple[Component, ...]
    instances: tuple[Instance, ...]
    functors: tuple[FunctorDecl, ...]
    units: tuple[Unit, ...]
    macros: tuple[MacroCall, ...]
    comments: tuple[Comment, ...]
    includes: tuple[Include, ...]
    defines: tuple[Define, ...]
