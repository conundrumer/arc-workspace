"""A program as text, each line with the line of the parsed text it
renders."""

from collections.abc import Iterable
from dataclasses import dataclass, field

from engine.engine import Rendered, RenderedLine
from engine.program import (
    Component,
    DeclId,
    FunctorDecl,
    GridCall,
    Program,
    RelationDecl,
    RigidCall,
    Scope,
    Unit,
    UnitId,
)
from souffle import printer
from souffle.layout import (
    CompBlock,
    Generated,
    IncludeBlock,
    Key,
    Part,
    Piece,
    Segment,
    Text,
    layout_keys,
    layout_of,
)
from souffle.lexer import LINE_DIRECTIVE_RE


def include(path: str) -> str:
    """The `#include` directive of the file at `path`."""
    return f'#include "{path}"'


def parts_of(program: Program) -> dict[Key, Part]:
    """Every part of `program` by its key."""
    out: dict[Key, Part] = {}
    for d in program.declarations:
        out[d.id] = d
    for u in program.units:
        out[u.id] = u
    for m in program.macros:
        out[m.id] = m
    return out


def scope_of(part: Part) -> Scope | None:
    """The scope a part stands in; None for a functor declaration, which
    stands at the top level and carries no scope."""
    return None if isinstance(part, FunctorDecl) else part.scope


@dataclass
class _Out:
    """Chunks of text, each with the origin of its first line and whether
    the lines after it advance from that origin."""

    chunks: list[tuple[str, int | None, bool]] = field(default_factory=list)

    def add(self, text: str, origin: int | None, advancing: bool) -> None:
        if text:
            self.chunks.append((text, origin, advancing))

    def lines(self) -> tuple[RenderedLine, ...]:
        out: list[RenderedLine] = []
        buf: list[str] = []
        origin: int | None = None
        fresh = True
        for text, start, advancing in self.chunks:
            at = start
            for piece in text.splitlines(keepends=True):
                if fresh:
                    origin = at
                    fresh = False
                body = piece.rstrip("\n")
                buf.append(body)
                if piece.endswith("\n"):
                    out.append(RenderedLine("".join(buf), origin))
                    buf = []
                    fresh = True
                    if advancing and at is not None:
                        at += 1
        if buf:
            out.append(RenderedLine("".join(buf), origin))
        return tuple(out)


class _Renderer:
    def __init__(self, program: Program, absolute: bool = False,
                 bare: bool = False):
        self.program = program
        self.absolute = absolute
        self.bare = bare
        self.layout = layout_of(program)
        self.current = parts_of(program)
        placed = layout_keys(self.layout.segments)
        self.new: dict[tuple[str, ...], list[Part]] = {}
        for key, part in self.current.items():
            if key in placed:
                continue
            if isinstance(part, Unit) and self._in_rigid(key):
                continue
            scope = scope_of(part)
            path = scope.components if scope is not None else ()
            self.new.setdefault(path, []).append(part)
        self.clean_cache: dict[int, bool] = {}

    def _in_rigid(self, key: Key) -> bool:
        return isinstance(key, UnitId) and self.program.in_rigid_body(key)

    # cleanliness

    def unchanged(self, parts: tuple[tuple[Key, Part], ...]) -> bool:
        for key, part in parts:
            now = self.current.get(key)
            if now is not part and now != part:
                return False
        return True

    def clean(self, segments: tuple[Segment, ...]) -> bool:
        """Whether no part of `segments` changed and no new part goes into
        a scope they declare."""
        for s in segments:
            if isinstance(s, Piece | Generated) and not self.unchanged(s.parts):
                return False
            if isinstance(s, CompBlock):
                comp = s.comp
                assert isinstance(comp, Component)
                path = (*comp.scope.components, comp.name)
                if (not self.unchanged(((s.key, s.comp),)) or path in self.new
                        or not self.clean(s.body)):
                    return False
            if isinstance(s, IncludeBlock) and not self.clean(s.body):
                return False
        return True

    # rendering

    def render(self) -> tuple[RenderedLine, ...]:
        out = _Out()
        self.segments(self.layout.segments, out, True, "")
        new = self.new_parts((), "")
        if new:
            out.add("\n" + new + "\n", None, False)
        return out.lines()

    def segments(self, segments: tuple[Segment, ...], out: _Out, own: bool,
                 indent: str) -> None:
        for s in segments:
            match s:
                case Text(text, line):
                    if not self.bare:
                        out.add(text, line if own else None, True)
                case Piece(text, line, parts):
                    if not parts and LINE_DIRECTIVE_RE.match(text):
                        # Never printed: each rendered line's origin
                        # carries the number the directive gives it.
                        continue
                    if not parts or self.unchanged(parts):
                        out.add(text, line if own else None, True)
                    else:
                        out.add(self.print_parts(parts, _indent_before(out)),
                                line if own else None, False)
                case Generated(text, line, parts):
                    if self.unchanged(parts):
                        out.add(text, line if own else None, False)
                    else:
                        out.add(self.print_parts(parts, _indent_before(out)),
                                line if own else None, False)
                case CompBlock(key, comp, head, line, body, tail, tail_line):
                    if key not in self.current:
                        continue
                    now = self.current[key]
                    assert isinstance(now, Component) and isinstance(comp, Component)
                    if now == comp:
                        out.add(head, line if own else None, True)
                    else:
                        out.add(printer.declaration(now), line if own else None, False)
                    inner = indent + printer.INDENT
                    if self.bare:
                        _end_line(out)
                    self.segments(body, out, own, inner)
                    new = self.new_parts((*now.scope.components, now.name), inner)
                    if new:
                        out.add("\n" + new + "\n", None, False)
                    out.add(tail, tail_line if own else None, True)
                case IncludeBlock(text, line, path, body):
                    if self.clean(body):
                        directive = include(path) if self.absolute else text
                        out.add(directive, line if own else None, True)
                    else:
                        self.segments(body, out, False, "")
            if self.bare:
                _end_line(out)

    def print_parts(self, parts: tuple[tuple[Key, Part], ...], indent: str) -> str:
        """The surviving parts of a statement, in their canonical form."""
        now = [self.current[k] for k, _ in parts if k in self.current]
        if not now:
            return ""
        first = now[0]
        if isinstance(first, RigidCall):
            return self.rigid(first, indent)
        return f"\n{indent}".join(self.part(p, indent) for p in now)

    def part(self, p: Part, indent: str) -> str:
        if isinstance(p, Unit):
            return printer.unit(p)
        if isinstance(p, GridCall):
            return printer.grid_call(p, indent)
        if isinstance(p, RigidCall):
            return self.rigid(p, indent)
        if isinstance(p, Component):
            return self.component(p, indent)
        return printer.declaration(p)

    def rigid(self, call: RigidCall, indent: str) -> str:
        charts = list(self.program.charts(call))
        body = [self.part(self.current[k], indent + printer.INDENT)
                for k in call.body if k in self.current]
        return printer.rigid_call(call, charts, body, indent)

    def component(self, comp: Component, indent: str) -> str:
        inner = indent + printer.INDENT
        body = self.new_parts((*comp.scope.components, comp.name), inner)
        return (printer.declaration(comp) + "\n" + (body + "\n" if body else "")
                + indent + "}")

    def new_parts(self, path: tuple[str, ...], indent: str) -> str:
        """The parts no segment holds whose scope is `path`, one statement
        per line."""
        parts = self.new.pop(path, [])
        placed_rigid = {k for p in parts if isinstance(p, RigidCall) for k in p.body}
        lines: list[str] = []
        for p in sorted(parts, key=_order):
            if isinstance(p, RelationDecl) and self._rigid_decl(p):
                continue
            if isinstance(p, Unit) and p.id in placed_rigid:
                continue
            lines.append(indent + self.part(p, indent))
        return "\n".join(lines)

    def _rigid_decl(self, d: RelationDecl) -> bool:
        return self.program.rigid_bound(d)


def _order(p: Part) -> tuple[int, int]:
    """Declarations first, then units, each in the order of its id."""
    key = p.id
    return (0 if isinstance(key, DeclId) else 1, key.index)


def _end_line(out: _Out) -> None:
    """End the line the output ends in, where it ends in text."""
    if out.chunks and not out.chunks[-1][0].endswith("\n"):
        out.add("\n", None, False)


def _indent_before(out: _Out) -> str:
    """The whitespace that opens the line the output ends in, where nothing
    else stands on it."""
    if not out.chunks:
        return ""
    text = out.chunks[-1][0]
    tail = text.rsplit("\n", 1)[-1]
    return tail if not tail.strip() else ""


def render(program: Program) -> Rendered:
    return Rendered(_Renderer(program).render())


def rendered_for_run(program: Program) -> list[tuple[str, int | None]]:
    """`program` as Souffle reads it, each include naming its file by its
    full path: its statements alone, each from a line of its own, with no
    comment or blank line between them, so that the text is the same
    wherever the statements stand in the file and whatever comments stand
    between them."""
    return [(line.text, line.origin)
            for line in _Renderer(program, absolute=True, bare=True).render()]


def lines_text(lines: Iterable[str]) -> str:
    """`lines` as one text, each line ended by a newline."""
    return "".join(line + "\n" for line in lines)
