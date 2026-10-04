"""The operations a language implements for the rest: parse, index, the
rewrites that return a new program, run, expand, render and format."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Protocol

from engine.program import (
    Atom,
    Component,
    DeclId,
    Grid,
    GridLayout,
    Program,
    RelationName,
    Row,
    Rows,
    Scope,
    TypeDecl,
    UnitId,
)

# Parse


@dataclass(frozen=True)
class ParseFailure:
    """Text outside the grammar: the line and column where parsing stopped,
    and the parser's message."""

    line: int
    column: int
    message: str


# Index


class Role(Enum):
    FEEDS = "feeds"
    READS = "reads"


@dataclass(frozen=True)
class Occurrence:
    """One atom of a unit that names a relation: the unit, the atom, and
    whether the atom feeds the relation (a head) or reads it (a body atom,
    negated or not). (The syntax `Ref`; a `@claim` line is
    `solver.ClaimLine`.)"""

    unit: UnitId
    atom: Atom
    role: Role
    negated: bool


@dataclass(frozen=True)
class Resolved:
    """A qualified name resolved to its declaration: the declaration, the
    instances the name passes through, outermost first, and the type
    arguments bound along that path, as (parameter, argument) pairs."""

    declaration: DeclId
    through: tuple[DeclId, ...]
    type_arguments: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class Unresolved:
    """A qualified name that denotes no declaration from the scope it is
    read in."""

    name: RelationName
    scope: Scope


class Index(Protocol):
    """Which units feed a relation, which read it, and the resolution of a
    qualified name through instances (§D3 `index`)."""

    def feeding(self, relation: DeclId) -> tuple[Occurrence, ...]:
        """The head atoms, in unit order, whose relation is `relation`."""
        ...

    def reading(self, relation: DeclId) -> tuple[Occurrence, ...]:
        """The body atoms, in unit order, whose relation is `relation`."""
        ...

    def resolve(self, name: RelationName, scope: Scope) -> Resolved | Unresolved:
        """The declaration `name` denotes when read in `scope`."""
        ...

    def component(self, name: str, scope: Scope) -> Component | None:
        """The component `name` denotes when read in `scope`: the one the
        innermost scope around it declares; None where none does."""
        ...

    def chain(self, component: Component) -> tuple[Component, ...]:
        """`component` and each component it extends in turn, nearest
        first, as far as the bases resolve and until one comes again."""
        ...

    def type_decl(self, name: str, scope: Scope) -> TypeDecl | None:
        """The type declaration `name` denotes when read in the text of
        `scope`: declared there, in a component it extends, or in a text
        around it; `o.T` reads `T` in the component of the instance `o`.
        None for a primitive type, a component's type parameter, or a name
        nothing declares."""
        ...


def unresolved(name: RelationName) -> ValueError:
    """The error of a caller that holds `name` to be declared where it
    resolves to no declaration."""
    return ValueError(f"`{name.text}` resolves to no declaration")


def resolved(index: Index, name: RelationName, scope: Scope) -> Resolved:
    """`index.resolve` of a name the caller holds to be declared. Raises
    `unresolved` where it resolves to no declaration."""
    got = index.resolve(name, scope)
    if not isinstance(got, Resolved):
        raise unresolved(name)
    return got


# Remove


@dataclass(frozen=True)
class RemoveUnit:
    unit: UnitId


@dataclass(frozen=True)
class RemoveAtom:
    """One atom of a unit's body, by its position: the index of each
    literal on the way down. Past a disjunction the step is (branch,
    literal); past any other literal it is (aggregate, literal), the
    aggregate by its place among the literal's aggregates, left to right,
    and the literal of that aggregate's body."""

    unit: UnitId
    path: tuple[int, ...]


@dataclass(frozen=True)
class RemoveDisjunct:
    """One branch of a disjunction in a unit's body: `path` leads to the
    disjunction as `RemoveAtom`'s does, then gives the branch's index."""

    unit: UnitId
    path: tuple[int, ...]


@dataclass(frozen=True)
class RemoveColumn:
    """A column of a relation, removed at its declaration and at every atom
    of the relation."""

    relation: DeclId
    column: int


@dataclass(frozen=True)
class RemoveFact:
    """One fact: the row the relation's statement gives, wherever it is
    stated, a macro call included."""

    relation: RelationName
    row: Row


type RemovalTarget = (RemoveUnit | RemoveAtom | RemoveDisjunct | RemoveColumn
                      | RemoveFact)


# Fix


@dataclass(frozen=True)
class GridValue:
    """A relation's value as one grid of a GRID macro call: the call's
    keys, the grid, and for a stamp the row and column of its anchor cell.
    The engine writes the cells."""

    keys: Row
    grid: Grid
    anchor: tuple[int, int] | None = None


type RelationValue = Rows | GridValue


@dataclass(frozen=True)
class AnchorOffStamp:
    """A grid given with an anchor for a call that is no stamp."""


@dataclass(frozen=True)
class CellOffForm:
    """A grid for a layout that takes members alone, with a cell other than
    0 and 1: the first such cell's row and column, and its value."""

    cell: tuple[int, int]
    value: int


@dataclass(frozen=True)
class SizeOffLayout:
    """A grid given with no anchor for a stamp, whose height and width are
    not the call's: the grid's height and width."""

    given: tuple[int, int]


type GridMisfit = AnchorOffStamp | CellOffForm | SizeOffLayout
"""Why a grid is no value of a relation one GRID call stores."""


# Run


@dataclass(frozen=True)
class GridInput:
    """A grid as a relation's input: the engine writes its cell facts."""

    grid: Grid


@dataclass(frozen=True)
class IndexedGrids:
    """Grids as one relation's input, one per example: the cell facts carry
    the example's index in a leading column."""

    grids: tuple[Grid, ...]


type InputValue = Rows | GridInput | IndexedGrids


@dataclass(frozen=True)
class Limits:
    cpu_seconds: float
    wall_seconds: float


@dataclass(frozen=True)
class Tuples:
    """A run's result: the rows of each output relation asked for."""

    relations: Mapping[RelationName, Rows]


@dataclass(frozen=True)
class CompileError:
    """The engine rejects the program. `line` is the origin line of the
    error in the parsed text, None where the error stands in a line an
    operation wrote."""

    line: int | None
    message: str


@dataclass(frozen=True)
class UngroundedVariable:
    variable: str
    line: int | None


@dataclass(frozen=True)
class CpuLimit:
    seconds: float


@dataclass(frozen=True)
class WallLimit:
    seconds: float


@dataclass(frozen=True)
class UndefinedOutput:
    """An output relation asked for that the program does not declare."""

    relations: tuple[RelationName, ...]


@dataclass(frozen=True)
class Exited:
    """The run ended with an exit code of its own, no limit reached."""

    code: int
    message: str


type RunFailure = (CompileError | UngroundedVariable | CpuLimit | WallLimit
                   | UndefinedOutput | Exited)
type RunResult = Tuples | RunFailure


# Render


@dataclass(frozen=True)
class RenderedLine:
    text: str
    origin: int | None
    """The line of the parsed text this line renders; None for a line an
    operation wrote."""


@dataclass(frozen=True)
class Rendered:
    lines: tuple[RenderedLine, ...]


@dataclass(frozen=True)
class Classed:
    """A program with the rules `Engine.classify` adds: `rows` holds the
    classified relation's rows at each class's representative alone, and
    `classes` each value of the column with its class's representative."""

    program: Program
    rows: RelationName
    classes: RelationName


class Engine(Protocol):
    """The interface between a language and the rest. Every rewrite returns
    a new program; no caller touches program text."""

    def parse(self, text: str, base_dir: Path) -> Program | ParseFailure:
        """The program `text` states, with each `#include` resolved against
        `base_dir` and the included declarations in it, or where it leaves
        the grammar."""
        ...

    def index(self, program: Program) -> Index:
        """The feeds, reads and name resolution of `program`."""
        ...

    def fix_relation(self, program: Program, relation: RelationName,
                     value: RelationValue) -> Program:
        """`program` with `relation` holding exactly `value`, fed by none of
        its own rules; every other relation's tuples are what they would be
        with that value."""
        ...

    def place_grid(self, layout: GridLayout, mark: tuple[int, int] | None,
                   value: GridValue) -> GridValue | GridMisfit:
        """`value` as the value of a relation that one GRID call of `layout`
        stores, the call's cell marked `@` at `mark`: with an anchor, a
        stamp's grid of any size; with none, a stamp's grid of the call's
        size, anchored at `mark`, or a grid of any other layout. A layout
        that takes members alone takes 1 and 0 cells only. Where the grid
        is placed by none of these, why. `fix_relation` places a grid by
        this rule."""
        ...

    def remove(self, program: Program, target: RemovalTarget) -> Program:
        """`program` without `target`."""
        ...

    def instantiate(self, program: Program, component: str, name: str) -> Program:
        """`program` with an instance `name` of `component`."""
        ...

    def run(self, program: Program, inputs: Mapping[RelationName, InputValue],
            outputs: Sequence[RelationName], limits: Limits,
            caps: Mapping[RelationName, int] | None = None) -> RunResult:
        """The rows of each of `outputs` after a run over `inputs`, or the
        typed failure of the run. An output `caps` gives a cap holds at most
        cap plus one of its rows, all of them where it has at most cap; the
        engine prints no row of it past those."""
        ...

    def classify(self, program: Program, relation: RelationName,
                 column: int) -> Classed:
        """`program` with rules that class the values `relation`, a
        top-level relation, holds in `column` by its rows at each: two
        values are of one class where the relation holds the same rows at
        both, the other columns' values. A run of the result then compares
        the values in the run and prints one value's rows per class.
        Raises `ValueError` where no top-level declaration answers
        `relation`."""
        ...

    def expand(self, program: Program) -> Program:
        """`program` with its GRID and RIGID macro calls as plain units."""
        ...

    def render(self, program: Program) -> Rendered:
        """`program` as text, each line with its origin line."""
        ...
