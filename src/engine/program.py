"""The parsed program an engine gives: declarations, units, macro calls and
comments, as values with no program text in them."""

from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass, field, replace
from enum import StrEnum
from functools import cached_property


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
        """The name as a statement writes it, `params.bg`: the one text
        through which every package prints and compares a relation's
        name."""
        return dotted((*self.instances, self.name))


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


class Primitive(StrEnum):
    """Souffle's primitive types, by name."""

    NUMBER = "number"
    UNSIGNED = "unsigned"
    FLOAT = "float"
    SYMBOL = "symbol"

    @property
    def values(self) -> tuple[type, ...]:
        """The Python types a value of the type is of."""
        match self:
            case Primitive.NUMBER | Primitive.UNSIGNED:
                return (int,)
            case Primitive.FLOAT:
                return (int, float)
            case Primitive.SYMBOL:
                return (str,)

    @staticmethod
    def named(name: str) -> "Primitive | None":
        """The primitive type `name` names; None where it names none."""
        return Primitive(name) if name in PRIMITIVES else None


PRIMITIVES = frozenset(Primitive)
"""The names of Souffle's primitive types."""


type Value = int | float | str | RecordValue | AdtValue
"""One column's value: a number, a float, a symbol, a record or an ADT
value."""


type Row = tuple[Value, ...]
type Rows = tuple[Row, ...]

type Grid = tuple[tuple[int, ...], ...]
"""Rows of colors."""


def as_grid(rows: Sequence[Sequence[int]]) -> Grid:
    """Rows of colors as a `Grid`, rows of tuples: a task's grid or a
    witness file's, rows of lists."""
    return tuple(tuple(r) for r in rows)


def cell_place(r: int, c: int, h: int, w: int) -> tuple[int, int, int, int]:
    """The place of the cell at row `r` and column `c` of a grid of `h`
    rows and `w` columns: its distances to the top, bottom, left and right
    edges."""
    return (r, h - 1 - r, c, w - 1 - c)


def offset_place(dr: int, dc: int) -> tuple[int, int, int, int]:
    """The place of the translation by `dr` rows and `dc` columns: the
    amounts it adds to the distances to the top, bottom, left and right
    edges."""
    return (dr, -dr, dc, -dc)


def grid_size(grid: Grid) -> tuple[int, int]:
    """The height and width of `grid`, a grid of one row or more, as a task
    file and a witness file give it."""
    return len(grid), len(grid[0])


def grid_lists(grid: Grid) -> list[list[int]]:
    """A `Grid` as rows of lists, the form a task file and a witness file
    write."""
    return [list(r) for r in grid]


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
    relation. A reader asks this, never a prefix of the name."""

    @property
    def scoped_name(self) -> RelationName:
        """The relation's name as a statement of its own scope writes it,
        with no instance part."""
        return RelationName((), self.name)


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
    """The line the atom stands on; 0 for an atom of a part an operation
    wrote (`first_line`)."""


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
class GridLayout:
    """What a GRID macro's name states of its calls: the form, whether each
    emitted cell is placed as its offset from an anchor cell, and the
    height and width."""

    form: GridForm
    stamp: bool
    height: int
    width: int

    @property
    def full(self) -> bool:
        """Every cell holds a value and is emitted."""
        return self.form is GridForm.DENSE and not self.stamp

    @property
    def valued(self) -> bool:
        """Each emitted fact holds the cell's value after its place; the
        other layouts take `1` for a member cell and `0` or `_` for an
        empty one."""
        return self.form is GridForm.SPARSE or self.full


class MemberCell(StrEnum):
    """A cell of a layout that takes members alone (`GridLayout.valued`
    false), by its spelling in the GRID text: a member, `1`, which is 1 in
    a grid; or an empty cell, `_`, which is 0 in a grid."""

    MEMBER = "1"
    EMPTY = "_"

    @property
    def grid_value(self) -> int:
        """The cell's value in a grid."""
        return 1 if self is MemberCell.MEMBER else 0

    @property
    def term(self) -> "Term":
        """The cell's term in a GRID call."""
        return NumberTerm(1) if self is MemberCell.MEMBER else Wildcard()

    @staticmethod
    def of_value(value: object) -> "MemberCell | None":
        """The cell a grid's `value` is; None for a value other than 0
        and 1."""
        return next((m for m in MemberCell if m.grid_value == value
                     and type(value) is int), None)

    @staticmethod
    def of_term(term: "Term") -> "MemberCell | None":
        """The cell a GRID call's `term` is; None for any other term."""
        return next((m for m in MemberCell if m.term == term), None)


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
    layout: GridLayout
    relation: RelationName
    keys: tuple[Term, ...]
    cells: tuple[tuple[GridCell, ...], ...]
    span: Span | None

    @property
    def anchor(self) -> tuple[int, int] | None:
        """The row and column of the cell marked `@`, None where no cell
        is."""
        return next(((r, c) for r, row in enumerate(self.cells)
                     for c, cell in enumerate(row) if cell.anchor), None)


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

    def is_chart(self, decl: RelationDecl) -> bool:
        """Whether `decl` is a chart relation the call declares: one of
        its block, at its scope."""
        return decl.scope == self.scope and decl.chart_of == self.block

    def binds(self, decl: RelationDecl) -> bool:
        """Whether the call declares or binds `decl`: a chart relation of
        the call (`is_chart`), or the relation of a name it binds, at its
        scope."""
        return self.is_chart(decl) \
            or (decl.scope == self.scope and decl.name in self.names)


POSE_COLUMN = 0
"""The column of a RIGID call's placed relation that holds the pose, the
D4 element the chart's rows are placed by, before the chart's columns."""


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

    @property
    def declarations(self) -> tuple["Declaration", ...]:
        """Every declaration: the types, relations, components, instances
        and functors, in that order."""
        return (*self.types, *self.relations, *self.components,
                *self.instances, *self.functors)

    @cached_property
    def _by_id(self) -> tuple[dict[DeclId, "Declaration"],
                              dict[UnitId, "Unit"],
                              dict[DeclId, RelationDecl]]:
        """The declarations, units and relation declarations by id, the
        first of each id, built on the first lookup."""
        return ({d.id: d for d in reversed(self.declarations)},
                {u.id: u for u in reversed(self.units)},
                {r.id: r for r in reversed(self.relations)})

    def declaration(self, id: DeclId) -> "Declaration | None":
        """The declaration whose id is `id`; None where none is."""
        return self._by_id[0].get(id)

    def unit(self, id: UnitId) -> "Unit | None":
        """The unit whose id is `id`; None where none is."""
        return self._by_id[1].get(id)

    def relation(self, id: DeclId) -> RelationDecl | None:
        """The relation declaration whose id is `id`; None where none
        is."""
        return self._by_id[2].get(id)

    def declared(self, id: DeclId) -> "Declaration":
        """The declaration whose id is `id`, an id read from this program.
        Raises `ValueError` where none is."""
        got = self.declaration(id)
        if got is None:
            raise ValueError(f"no declaration has the id {id}")
        return got

    def declared_relation(self, id: DeclId) -> RelationDecl:
        """The relation declaration whose id is `id`, an id read from this
        program. Raises `ValueError` where none is."""
        got = self.relation(id)
        if got is None:
            raise ValueError(f"no relation declaration has the id {id}")
        return got

    def next_decl_index(self) -> int:
        """The index past every declaration id of the program."""
        return 1 + max((d.id.index for d in self.declarations), default=-1)

    def next_unit_index(self) -> int:
        """The index past every unit and macro call id of the program."""
        return 1 + max((u.id.index for u in (*self.units, *self.macros)),
                       default=-1)

    def charts(self, call: RigidCall) -> tuple[RelationDecl, ...]:
        """The chart relations a RIGID call declares (`RigidCall.is_chart`),
        in their order."""
        return tuple(r for r in self.relations if call.is_chart(r))

    def placed(self, call: RigidCall) -> tuple[RelationDecl, ...]:
        """The relations of the names a RIGID call binds, at its scope, in
        declaration order."""
        return tuple(r for r in self.relations
                     if r.scope == call.scope and r.name in call.names)

    def bound_names(self, call: RigidCall) -> tuple[str, ...]:
        """The names of the relations a RIGID call declares or binds
        (`RigidCall.binds`): the names it binds, then its charts'."""
        return (*call.names, *(r.name for r in self.charts(call)))

    def in_rigid_body(self, unit: UnitId) -> bool:
        """Whether `unit` stands in the body of a RIGID call."""
        return any(isinstance(m, RigidCall) and unit in m.body
                   for m in self.macros)

    def rigid_bound(self, decl: RelationDecl) -> bool:
        """Whether some RIGID call of the program declares or binds `decl`
        (`RigidCall.binds`)."""
        return any(isinstance(m, RigidCall) and m.binds(decl)
                   for m in self.macros)

    def bound_charts(self, call: RigidCall
                     ) -> tuple[tuple[str, RelationDecl], ...] | None:
        """Each name a RIGID call binds with the chart relation that holds
        its facts, in the call's order; None where the call's charts
        (`charts`) are not one per name."""
        charts = self.charts(call)
        if len(charts) != len(call.names):
            return None
        return tuple(zip(call.names, charts, strict=True))


type Declaration = TypeDecl | RelationDecl | Component | Instance | FunctorDecl


def dotted(path: tuple[str, ...]) -> str:
    """A qualified name's text, its parts joined by dots, `params.bg`: the
    one text of a relation's name (`RelationName.text`), an instance path
    or a type of a component."""
    return ".".join(path)


def enclosing[T](path: tuple[T, ...]) -> Iterator[tuple[T, ...]]:
    """`path` and each path around it, innermost first, the empty path
    last: where a name read at `path` is looked for."""
    return (path[:n] for n in range(len(path), -1, -1))


def own(at: Span | Comment | Include | Define | None) -> bool:
    """Whether a part is of the text handed to `parse`, not of an include
    or written by an operation: `at` is the part's span, or a comment,
    include or define. A solver's own text is these parts: a check on the
    solver's form reads those alone, and reads the lib's parts only for
    what the solver refers to."""
    return at is not None and at.file is None


def first_line(span: Span | None) -> int:
    """The first line of a part whose span is `span`; 0 for a part an
    operation wrote, which stands on no line of the text."""
    return 0 if span is None else span.first


def subterms(term: Term) -> tuple[Term, ...]:
    """The terms `term` holds directly, left to right; none for an
    aggregate, whose terms stand in its own body."""
    match term:
        case ConstructorTerm(args=args) | RecordTerm(args=args) \
                | IntrinsicCall(args=args) | FunctorCall(args=args):
            return args
        case UnaryTerm(arg=arg) | Cast(term=arg):
            return (arg,)
        case BinaryTerm(lhs=lhs, rhs=rhs):
            return (lhs, rhs)
    return ()


def with_subterms(term: Term, fn: Callable[[Term], Term]) -> Term:
    """`term` with each term it holds directly (`subterms`) as `fn` gives
    it, `fn` called left to right; an aggregate as it stands."""
    match term:
        case ConstructorTerm(args=args) | RecordTerm(args=args) \
                | IntrinsicCall(args=args) | FunctorCall(args=args):
            return replace(term, args=tuple(fn(a) for a in args))
        case UnaryTerm(arg=arg):
            return replace(term, arg=fn(arg))
        case Cast(term=arg):
            return replace(term, term=fn(arg))
        case BinaryTerm(lhs=lhs, rhs=rhs):
            new_lhs = fn(lhs)
            return replace(term, lhs=new_lhs, rhs=fn(rhs))
    return term


def literal_terms(lit: BodyLiteral) -> tuple[Term, ...]:
    """The terms an atom literal or a comparison holds at its top level,
    left to right; none for another literal."""
    match lit:
        case AtomLiteral(atom=atom):
            return atom.args
        case Comparison(lhs=lhs, rhs=rhs):
            return (lhs, rhs)
    return ()


def with_literal_terms(lit: BodyLiteral,
                       fn: Callable[[Term], Term]) -> BodyLiteral:
    """`lit` with each term `literal_terms` gives as `fn` gives it, `fn`
    called left to right; another literal as it stands."""
    match lit:
        case AtomLiteral(atom=atom):
            return replace(lit, atom=replace(
                atom, args=tuple(fn(a) for a in atom.args)))
        case Comparison(lhs=lhs, rhs=rhs):
            new_lhs = fn(lhs)
            return replace(lit, lhs=new_lhs, rhs=fn(rhs))
    return lit


def term_aggregates(term: Term) -> list[Aggregate]:
    """The aggregates a term holds, left to right, not those inside
    another aggregate."""
    if isinstance(term, Aggregate):
        return [term]
    return [a for x in subterms(term) for a in term_aggregates(x)]


def literal_aggregates(lit: BodyLiteral) -> list[Aggregate]:
    """The aggregates the terms of an atom or a comparison hold, left to
    right, not those inside another aggregate; none for another
    literal."""
    return [a for t in literal_terms(lit) for a in term_aggregates(t)]


def body_atoms(body: tuple[BodyLiteral, ...]) -> Iterator[tuple[Atom, bool]]:
    """Every atom a body reads, in order, with whether it stands negated:
    an atom before the atoms of the aggregates its terms hold, through
    disjunctions and the bodies of aggregates."""
    for lit in body:
        if isinstance(lit, Disjunction):
            for branch in lit.branches:
                yield from body_atoms(branch)
            continue
        if isinstance(lit, AtomLiteral):
            yield lit.atom, lit.negated
        for agg in literal_aggregates(lit):
            yield from _aggregate_atoms(agg)


def _aggregate_atoms(agg: Aggregate) -> Iterator[tuple[Atom, bool]]:
    """Every atom an aggregate reads: those of the aggregates its
    expression holds, then those of its body."""
    if agg.expr is not None:
        for inner in term_aggregates(agg.expr):
            yield from _aggregate_atoms(inner)
    yield from body_atoms(agg.body)


def term_value(term: Term, defined: Callable[[str], "Value | None"]
               ) -> "Value | None":
    """The value a term states with no variable or call in it: a number, a
    symbol, a constructor or record of such, a cast of one, a negation,
    `+`, `-` or `*` of two numbers, or a defined name whose value
    `defined` gives; None for any other term."""
    match term:
        case NumberTerm(value=v) | StringTerm(value=v):
            return v
        case DefinedName(name=name):
            return defined(name)
        case ConstructorTerm(args=args) | RecordTerm(args=args):
            vals = [term_value(a, defined) for a in args]
            if any(v is None for v in vals):
                return None
            held = tuple(v for v in vals if v is not None)
            return AdtValue(term.name, held) \
                if isinstance(term, ConstructorTerm) else RecordValue(held)
        case Cast(term=arg):
            return term_value(arg, defined)
        case UnaryTerm(op=UnaryOperator.NEGATE, arg=arg):
            v = term_value(arg, defined)
            return -v if isinstance(v, int | float) else None
        case BinaryTerm(op=op, lhs=lhs, rhs=rhs) if op in (
                BinaryOperator.ADD, BinaryOperator.SUB, BinaryOperator.MUL):
            a, b = term_value(lhs, defined), term_value(rhs, defined)
            if not isinstance(a, int | float) or not isinstance(b, int | float):
                return None
            return a + b if op == BinaryOperator.ADD else (
                a - b if op == BinaryOperator.SUB else a * b)
    return None


def term_of(v: Value) -> Term:
    """The term that states a value, the one `term_value` reads back."""
    match v:
        case bool():
            return NumberTerm(int(v))
        case int() | float():
            return NumberTerm(v)
        case str():
            return StringTerm(v)
        case RecordValue(fields):
            return RecordTerm(tuple(term_of(f) for f in fields))
        case AdtValue(name, args):
            return ConstructorTerm(name, tuple(term_of(a) for a in args))
    raise TypeError(f"not a value: {v!r}")


type TypeReading[P] = Callable[[str, P], "tuple[TypeDecl | Primitive, P]"]
"""What a type name read at a place of type `P` stands for: a primitive,
or the declaration with the place its own names are read at. Raises
ValueError where nothing answers the name."""


@dataclass(frozen=True)
class ValueReading[S]:
    """How a source of type `S` gives a value: as a primitive's value, as
    the parts of a record, or as a constructor's name and parts; None
    where the source is not of that form."""

    primitive: Callable[[S, Primitive], "Value | None"]
    record: Callable[[S], Sequence[S] | None]
    constructor: Callable[[S], tuple[str, Sequence[S]] | None]


MAX_TYPE_DEPTH = 64
"""How many type names deep a reading of a type goes before it stops as a
cycle."""


def check_type_depth(name: str, depth: int) -> None:
    """Raises ValueError where a reading of a type has gone `depth` names
    deep at the name `name`, past `MAX_TYPE_DEPTH`: the type does not end
    in a declaration."""
    if depth > MAX_TYPE_DEPTH:
        raise ValueError(f"type `{name}` does not end in a declaration")


def _kind[P](name: str, at: P, types: TypeReading[P], depth: int
             ) -> "Primitive | type[AdtType] | type[RecordType]":
    """The kind of the type `name`, read at `at`: the primitive an alias,
    subtype or union of primitives comes to, or the kind of declaration
    a record or ADT is (`typed_value`). A union's kind is its first
    member's."""
    check_type_depth(name, depth)
    decl, inner = types(name, at)
    match decl:
        case Primitive():
            return decl
        case AliasType(target=t) | SubtypeType(base=t):
            return _kind(t, inner, types, depth + 1)
        case UnionType(members=members):
            return _kind(members[0], inner, types, depth + 1)
        case AdtType() | RecordType():
            return type(decl)


def typed_value[S, P](source: S, name: str, at: P, types: TypeReading[P],
                      reading: ValueReading[S], depth: int = 0
                      ) -> "Value | None":
    """The value of the type `name`, read at `at`, that `source` gives: of
    a primitive a value of that primitive, of an alias or subtype a value
    of its target, of a union a value of its first member that reads one,
    of a record a record of values of its fields' types, and of an ADT one
    of its constructors over values of its fields' types; None where
    `source` gives no value of the type. Raises ValueError where `types`
    answers no name, for a type that does not end in a declaration, and
    for a union whose members are of different kinds, which Souffle
    rejects at compile, so that a run never prints one."""
    check_type_depth(name, depth)
    decl, inner = types(name, at)

    def of(s: S, n: str) -> "Value | None":
        return typed_value(s, n, inner, types, reading, depth + 1)

    def each(parts: Sequence[S], fields: tuple[TypeField, ...]
             ) -> "tuple[Value, ...] | None":
        if len(parts) != len(fields):
            return None
        got = [of(p, f.type) for p, f in zip(parts, fields, strict=True)]
        held = tuple(v for v in got if v is not None)
        return held if len(held) == len(got) else None

    match decl:
        case Primitive():
            return reading.primitive(source, decl)
        case AliasType(target=target):
            return of(source, target)
        case SubtypeType(base=base):
            return of(source, base)
        case UnionType(members=members):
            kinds = {_kind(m, inner, types, depth + 1) for m in members}
            if len(kinds) > 1:
                raise ValueError(f"the union `{name}` has members of "
                                 f"different kinds, which Souffle rejects")
            return next((v for m in members
                         if (v := of(source, m)) is not None), None)
        case RecordType(fields=fields):
            parts = reading.record(source)
            held = None if parts is None else each(parts, fields)
            return None if held is None else RecordValue(held)
        case AdtType(constructors=ctors):
            got = reading.constructor(source)
            if got is None:
                return None
            ctor = next((c for c in ctors if c.name == got[0]), None)
            held = None if ctor is None else each(got[1], ctor.fields)
            return None if held is None else AdtValue(got[0], held)
