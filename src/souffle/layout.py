"""Where each part of a parsed program stands in the text it was parsed
from, so that a rendering copies the text of each part no operation
changed, and the program that carries it."""

import threading
import weakref
from collections.abc import Iterable
from dataclasses import dataclass, field

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


_HELD_UNITS: dict[int, tuple[weakref.ref[Layout], int]] = {}
_HELD_UNITS_LOCK = threading.Lock()


def _held_unit(layout: Layout) -> int:
    """The greatest unit id index `layout` holds, -1 where it holds none;
    read once per layout while it lives, as the programs an operation
    derives from one share its layout."""
    key = id(layout)
    with _HELD_UNITS_LOCK:
        got = _HELD_UNITS.get(key)
    if got is not None and got[0]() is layout:
        return got[1]
    top = max((k.index for k in layout_keys(layout.segments) if isinstance(k, UnitId)),
              default=-1)

    def drop(_r: object, key: int = key) -> None:
        with _HELD_UNITS_LOCK:
            held = _HELD_UNITS.get(key)
            if held is not None and held[0]() is None:
                del _HELD_UNITS[key]

    with _HELD_UNITS_LOCK:
        _HELD_UNITS[key] = (weakref.ref(layout, drop), top)
    return top


def next_unit(program: Program) -> int:
    """The index of the next unit id an operation writes: past every unit
    and macro call of the program and every one its layout holds, so that
    no id of a removed part comes back on another."""
    return 1 + max((*(u.id.index for u in (*program.units, *program.macros)),
                    _held_unit(layout_of(program))), default=-1)


def next_decl(program: Program) -> int:
    """The index of the next declaration id an operation writes, past
    every one the program and its layout hold."""
    held = [k.index for k in layout_keys(layout_of(program).segments) if isinstance(k, DeclId)]
    return 1 + max((*(d.id.index for d in (*program.types, *program.relations,
                                             *program.components, *program.instances,
                                             *program.functors)), *held), default=-1)
