"""A program as text, each line with the line of the parsed text it
renders."""

from dataclasses import dataclass, field

from engine.engine import Rendered, RenderedLine
from engine.program import (
    Component,
    DeclId,
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


def parts_of(program: Program) -> dict[Key, Part]:
    """Every part of `program` by its key."""
    out: dict[Key, Part] = {}
    for group in (program.types, program.relations, program.components,
                  program.instances, program.functors):
        for d in group:
            out[d.id] = d
    for u in program.units:
        out[u.id] = u
    for m in program.macros:
        out[m.id] = m
    return out


def scope_of(part: Part) -> Scope | None:
    return getattr(part, "scope", None)


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
    def __init__(self, program: Program, canonical: bool, absolute: bool = False):
        self.program = program
        self.canonical = canonical
        self.absolute = absolute
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
        return any(isinstance(m, RigidCall) and isinstance(key, UnitId) and key in m.body
                   for m in self.program.macros)

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
                    out.add(text, line if own else None, True)
                case Piece(text, line, parts):
                    if not parts and LINE_DIRECTIVE_RE.match(text):
                        # Never printed: each rendered line's origin
                        # carries the number the directive gives it.
                        continue
                    if not parts or self.unchanged(parts) and not (
                            self.canonical and not self._rigid_piece(parts)):
                        out.add(text, line if own else None, True)
                    else:
                        out.add(self.print_parts(parts, _indent_before(out)),
                                line if own else None, False)
                case Generated(text, line, parts):
                    if self.unchanged(parts) and not self.canonical:
                        out.add(text, line if own else None, False)
                    else:
                        out.add(self.print_parts(parts, _indent_before(out)),
                                line if own else None, False)
                case CompBlock(key, comp, head, line, body, tail, tail_line):
                    if key not in self.current:
                        continue
                    now = self.current[key]
                    assert isinstance(now, Component) and isinstance(comp, Component)
                    if now == comp and not self.canonical:
                        out.add(head, line if own else None, True)
                    else:
                        out.add(printer.declaration(now), line if own else None, False)
                    inner = indent + printer.INDENT
                    self.segments(body, out, own, inner)
                    new = self.new_parts((*now.scope.components, now.name), inner)
                    if new:
                        out.add("\n" + new + "\n", None, False)
                    out.add(tail, tail_line if own else None, True)
                case IncludeBlock(text, line, path, body):
                    if self.clean(body):
                        directive = f'#include "{path}"' if self.absolute else text
                        out.add(directive, line if own else None, True)
                    else:
                        self.segments(body, out, False, "")

    def _rigid_piece(self, parts: tuple[tuple[Key, Part], ...]) -> bool:
        return isinstance(parts[0][1], RigidCall)

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
        charts = [r for r in self.program.relations
                  if r.chart_of == call.block and r.scope == call.scope]
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
        return any(isinstance(m, RigidCall) and m.scope == d.scope
                   and (d.chart_of == m.block or d.name in m.names)
                   for m in self.program.macros)


def _order(p: Part) -> tuple[int, int]:
    """Declarations first, then units, each in the order of its id."""
    key = p.id
    return (0 if isinstance(key, DeclId) else 1, key.index)


def _indent_before(out: _Out) -> str:
    """The whitespace that opens the line the output ends in, where nothing
    else stands on it."""
    if not out.chunks:
        return ""
    text = out.chunks[-1][0]
    tail = text.rsplit("\n", 1)[-1]
    return tail if not tail.strip() else ""


def render(program: Program) -> Rendered:
    return Rendered(_Renderer(program, False).render())


def rendered_for_run(program: Program) -> list[tuple[str, int | None]]:
    """`program` as Souffle reads it, each include naming its file by its
    full path."""
    return [(line.text, line.origin)
            for line in _Renderer(program, False, absolute=True).render()]


def format_program(program: Program) -> str:
    lines = _Renderer(program, True).render()
    return "".join(line.text + "\n" for line in lines)
