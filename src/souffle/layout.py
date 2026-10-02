"""Where each part of a parsed program stands in the text it was parsed
from, so that a rendering copies the text of each part no operation
changed, and the program that carries it."""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field

from engine.memo import ByIdentity
from engine.program import (
    Component,
    DeclId,
    FunctorDecl,
    Instance,
    MacroCall,
    Program,
    RelationDecl,
    TypeDecl,
    Unit,
    UnitId,
)

type Key = UnitId | DeclId
type Part = TypeDecl | RelationDecl | Component | Instance | FunctorDecl | Unit | MacroCall
"""A unit, a declaration or a macro call."""


@dataclass(frozen=True)
class Text:
    """Text between parts: whitespace, comments, and the tokens no part
    holds. `line` is the line its first character stands on."""

    text: str
    line: int


@dataclass(frozen=True)
class Piece:
    """The text of one statement and the parts it states, each with its
    value as parsed: a declaration, a macro call, an include or a define, or
    a clause with the unit of each of its heads."""

    text: str
    line: int
    parts: tuple[tuple[Key, Part], ...]


@dataclass(frozen=True)
class CompBlock:
    """A component: its header text up to and including `{`, its body, and
    its closing `}`. Units an operation adds to its scope render before the
    closing brace."""

    key: DeclId
    comp: Part
    head: str
    line: int
    body: tuple["Segment", ...]
    tail: str
    tail_line: int


@dataclass(frozen=True)
class IncludeBlock:
    """An `#include` directive and the layout of the file it names. It
    renders as the directive while no part of the file changed."""

    text: str
    line: int
    path: str
    body: tuple["Segment", ...]


@dataclass(frozen=True)
class Generated:
    """Text an expansion wrote for a macro call at `line`, and the parts it
    states. It renders as written while none of those parts changed."""

    text: str
    line: int
    parts: tuple[tuple[Key, Part], ...]


type Segment = Text | Piece | CompBlock | IncludeBlock | Generated


@dataclass(frozen=True)
class Layout:
    segments: tuple[Segment, ...]


@dataclass(frozen=True)
class SouffleProgram(Program):
    """A `Program` with the layout of the text it was parsed from."""

    layout: Layout = field(default=Layout(()), kw_only=True, compare=False,
                           repr=False)


def layout_of(program: Program) -> Layout:
    return program.layout if isinstance(program, SouffleProgram) else Layout(())


def layout_keys(segments: Iterable[Segment]) -> set[Key]:
    """The key of every part the segments hold."""
    out: set[Key] = set()
    for s in segments:
        if isinstance(s, Piece | Generated):
            out |= {k for k, _ in s.parts}
        elif isinstance(s, CompBlock):
            out.add(s.key)
            out |= layout_keys(s.body)
        elif isinstance(s, IncludeBlock):
            out |= layout_keys(s.body)
    return out


_HELD_UNITS: ByIdentity[Layout, int] = ByIdentity()


def _held_unit(layout: Layout) -> int:
    """The greatest unit id index `layout` holds, -1 where it holds none;
    read once per layout while it lives, as the programs an operation
    derives from one share its layout."""
    return _HELD_UNITS.compute(layout, lambda: max(
        (k.index for k in layout_keys(layout.segments)
         if isinstance(k, UnitId)), default=-1))


def next_unit(program: Program) -> int:
    """The index of the next unit id an operation writes: past every unit
    and macro call of the program and every one its layout holds, so that
    no id of a removed part comes back on another."""
    return max(program.next_unit_index(), 1 + _held_unit(layout_of(program)))


def next_decl(program: Program) -> int:
    """The index of the next declaration id an operation writes, past
    every one the program and its layout hold."""
    held = [k.index for k in layout_keys(layout_of(program).segments) if isinstance(k, DeclId)]
    return max(program.next_decl_index(), 1 + max(held, default=-1))


def written_lines(lines: Sequence[str], first: int, last: int) -> list[str]:
    """The lines `first` to `last`, 1-based and inclusive, of a text split
    into `lines`, each without the spaces at its end: a part as written,
    by the first and last line of its span."""
    return [lines[n - 1].rstrip() for n in range(first, last + 1)]
