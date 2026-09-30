"""The operations a language implements for the rest: parse, index, the
rewrites that return a new program, run, expand, render and format."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Protocol

from engine.program import (
    Atom,
    DeclId,
    Grid,
    Program,
    RelationName,
    Row,
    Rows,
    Scope,
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
    keys and the grid. The engine writes the cells."""

    keys: Row
    grid: Grid


type RelationValue = Rows | GridValue


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

    def expand(self, program: Program) -> Program:
        """`program` with its GRID and RIGID macro calls as plain units."""
        ...

    def render(self, program: Program) -> Rendered:
        """`program` as text, each line with its origin line."""
        ...

    def format(self, program: Program) -> str:
        """`program` as text in the formatting rewrites' form."""
        ...
