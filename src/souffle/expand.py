"""The GRID and RIGID macro calls of a program as the plain units they
state, each expansion's text as the lines it writes in place of the
call."""

from dataclasses import replace
from pathlib import Path

from engine.program import (
    first_line,
    Atom,
    GridCall,
    NumberTerm,
    Program,
    RecordTerm,
    RelationDecl,
    RigidCall,
    Term,
    TypeName,
    Unit,
    UnitId,
    Wildcard,
    cell_place,
    offset_place,
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
    SouffleProgram,
    Text,
    layout_of,
    next_unit,
)
from souffle.lexer import lex
from souffle.parser import (
    RIGID_ACTIONS,
    RIGID_AXIS_ACTIONS,
    RIGID_POSE,
    chart_prefix,
    grid_layout,
    placed_name,
    parse,
)
from souffle.text import columns


def rigid_rule(head: str, src: str, types: list[TypeName],
               kept: frozenset[int] = frozenset()) -> str:
    """The rule that derives `head`, the D4 placements of the chart
    `src`, each column of `kept` placed as it stands."""
    heads, srcs, atoms = [], [], []
    for i, t in enumerate(type_name.text for type_name in types):
        if i in kept:
            heads.append(f"A{i}")
            srcs.append(f"A{i}")
        elif t in RIGID_ACTIONS:
            heads.append(f"A{i}")
            srcs.append(f"B{i}")
            atoms.append(f"{RIGID_ACTIONS[t]}(D4, B{i}, A{i})")
        elif t in RIGID_AXIS_ACTIONS:
            member, act = RIGID_AXIS_ACTIONS[t]
            heads.append(f"A{i}")
            srcs.append(f"B{i}")
            atoms.append(f"{member}(Bd{i}, B{i}), {act}(D4, Bd{i}, Ad{i}), "
                         f"{member}(Ad{i}, A{i})")
        elif t == RIGID_POSE[0]:
            heads.append(f"A{i}")
            srcs.append(f"B{i}")
            atoms.append(f"{RIGID_POSE[1]}(A{i}, B{i}, D4)")
        else:
            heads.append(f"A{i}")
            srcs.append(f"A{i}")
    body = ", ".join([f"{src}({', '.join(srcs)})", "d4_elem(D4)", *atoms])
    return f"{head}(D4, {', '.join(heads)}) :- {body}."




def grid_facts(call: GridCall) -> list[tuple[int, Atom]]:
    """The fact heads a GRID call states, each with its grid row, in
    row-major order: every cell of a dense call, and else each cell that
    holds something; each fact's keys, then the cell's place (its offset
    from the anchor for a stamp), then its value where the form holds
    one."""
    form = call.layout
    h, w = form.height, form.width
    anchor = call.anchor or (0, 0)
    out: list[tuple[int, Atom]] = []
    for r in range(h):
        for c in range(w):
            cell = call.cells[r][c].term
            if not form.full and isinstance(cell, Wildcard):
                continue
            if form.stamp:
                place = offset_place(r - anchor[0], c - anchor[1])
            else:
                place = cell_place(r, c, h, w)
            args: tuple[Term, ...] = (*call.keys, RecordTerm(tuple(NumberTerm(v) for v in place)))
            if form.valued:
                args = (*args, cell)
            line = first_line(call.span)
            out.append((r, Atom(call.relation, args, line)))
    return out


def grid_text(call: GridCall, indent: str) -> str:
    """The lines a GRID call expands to, one per grid row that holds a
    fact."""
    rows: dict[int, list[str]] = {}
    for r, head in grid_facts(call):
        rows.setdefault(r, []).append(printer.atom(head) + ".")
    return f"\n{indent}".join(" ".join(facts) for facts in rows.values())


def _indent_at(text: str, offset: int) -> str:
    prefix = text[text.rfind("\n", 0, offset) + 1:offset]
    return prefix if not prefix.strip() else ""


class _Expander:
    def __init__(self, program: Program):
        self.program = program
        self.next_unit = next_unit(program)
        self.units: dict[UnitId, Unit] = {u.id: u for u in program.units}
        self.macros = {m.id: m for m in program.macros}
        self.done: set[UnitId] = set()

    def fresh(self) -> UnitId:
        self.next_unit += 1
        return UnitId(self.next_unit - 1)

    def grid_units(self, call: GridCall) -> list[Unit]:
        out = []
        for _, head in grid_facts(call):
            unit = Unit(self.fresh(), call.scope, head, None, None, call.span)
            self.units[unit.id] = unit
            out.append(unit)
        self.done.add(call.id)
        return out

    def rigid_units(self, call: RigidCall) -> list[Unit]:
        """The closure rules of a RIGID call's placed relations."""
        charts = self.charts(call)
        text = "\n".join(
            rigid_rule(placed_name(call.block, d.name.removeprefix(self.prefix(call))), d.name,
                       [c.type for c in d.columns])
            for d in charts)
        parsed = parse(text, Path("."))
        assert isinstance(parsed, SouffleProgram), parsed
        out = []
        for u in parsed.units:
            unit = replace(u, id=self.fresh(), scope=call.scope, span=call.span,
                           head=replace(u.head, line=first_line(call.span)))
            self.units[unit.id] = unit
            out.append(unit)
        self.done.add(call.id)
        return out

    def prefix(self, call: RigidCall) -> str:
        return chart_prefix(call.block)

    def charts(self, call: RigidCall) -> list[RelationDecl]:
        return list(self.program.charts(call))

    # layout

    def segments(self, segments: tuple[Segment, ...], text_before: str) -> tuple[Segment, ...]:
        out: list[Segment] = []
        before = text_before
        for s in segments:
            match s:
                case Piece(text, line, parts) if parts and isinstance(
                        parts[0][1], GridCall | RigidCall):
                    key = parts[0][0]
                    macro = self.macros.get(key)  # type: ignore[arg-type]
                    if macro is None:
                        out.append(s)
                    else:
                        indent = _indent_at(before + text, len(before))
                        out.append(self.generated(macro, text, line, indent, parts))
                case CompBlock():
                    out.append(replace(s, body=self.segments(s.body, s.head)))
                case IncludeBlock():
                    out.append(replace(s, body=self.segments(s.body, "")))
                case _:
                    out.append(s)
            before = _tail(before, s)
        return tuple(out)

    def generated(self, macro: Part, text: str, line: int, indent: str,
                  parts: tuple[tuple[Key, Part], ...]) -> Generated:
        if isinstance(macro, GridCall):
            units = self.grid_units(macro)
            return Generated(grid_text(macro, indent), line,
                             tuple((u.id, u) for u in units))
        assert isinstance(macro, RigidCall)
        as_parsed = macro == parts[0][1] and all(
            self.current(key) == part for key, part in parts[1:])
        closure = self.rigid_units(macro)
        charts = self.charts(macro)
        placed = self.program.placed(macro)
        kept: list[tuple[Key, Part]] = [(d.id, d) for d in (*charts, *placed)]
        for key in macro.body:
            part = self.macros.get(key) or self.units.get(key)
            if isinstance(part, GridCall):
                kept += [(u.id, u) for u in self.grid_units(part)]
            elif isinstance(part, Unit):
                kept.append((key, part))
        if not as_parsed:
            # Some part of the call changed: its lines are the parts as
            # they stand now, not the text it was parsed from.
            lines = [printer.declaration(p) if isinstance(p, RelationDecl) else
                     printer.unit(p) for _, p in (*kept, *((u.id, u) for u in closure))
                     if isinstance(p, RelationDecl | Unit)]
            return Generated(f"\n{indent}".join(lines), line,
                             (*kept, *((u.id, u) for u in closure)))
        body_text = [self.rigid_body(macro, text, indent)]
        generated = []
        for chart in self.charts(macro):
            rel = chart.name.removeprefix(self.prefix(macro))
            fields = columns(chart.columns)
            generated += [
                f".decl {placed_name(macro.block, rel)}(d4: D4, {fields})",
                rigid_rule(placed_name(macro.block, rel), chart.name, [c.type for c in chart.columns]),
            ]
        full = body_text[0] + "\n" + "\n".join(f"{indent}{g}" for g in generated)
        return Generated(full, line, (*kept, *((u.id, u) for u in closure)))

    def current(self, key: Key) -> Part | None:
        """The part `key` names in the program being expanded."""
        if isinstance(key, UnitId):
            return self.units.get(key) or self.macros.get(key)
        return self.program.relation(key)

    def rigid_body(self, call: RigidCall, text: str, indent: str) -> str:
        """The body of a RIGID call's text, each name of a relation it
        declares written as its chart's, stripped, with each GRID call in
        it expanded."""
        tokens, _, _ = lex(text)
        declared = {c.name.removeprefix(self.prefix(call)) for c in self.charts(call)}
        comma = next(i for i, t in enumerate(tokens) if t.text == "," and t.kind == "punct")
        start = tokens[comma].end
        close = tokens[-2]
        pieces: list[str] = []
        at = start
        for t in tokens[comma + 1:-2]:
            if t.kind == "ident" and t.text in declared:
                pieces += [text[at:t.offset], self.prefix(call) + t.text]
                at = t.end
        pieces.append(text[at:close.offset])
        body = "".join(pieces).strip()
        grids = [self.macros.get(k) for k in call.body]
        grids = [g for g in grids if isinstance(g, GridCall)]
        return _expand_grids_in(indent + body, grids)[len(indent):]

    def program_out(self, layout_segments: tuple[Segment, ...]) -> Program:
        remaining = [m for m in self.program.macros if m.id not in self.done]
        for m in remaining:
            if isinstance(m, GridCall):
                self.grid_units(m)
            else:
                self.rigid_units(m)
                for k in m.body:
                    g = self.macros.get(k)
                    if isinstance(g, GridCall) and g.id not in self.done:
                        self.grid_units(g)
        units = tuple(u for u in sorted(self.units.values(), key=lambda u: u.id.index))
        old = layout_of(self.program)
        return SouffleProgram(
            self.program.types, self.program.relations, self.program.components,
            self.program.instances, self.program.functors, units, (),
            self.program.comments, self.program.includes, self.program.defines,
            layout=replace(old, segments=layout_segments))


def _tail(before: str, s: Segment) -> str:
    """The text of the line the output stands on after `s`, as far as a
    text segment tells."""
    if isinstance(s, Text):
        joined = before + s.text
        return joined[joined.rfind("\n") + 1:]
    return "x"


def _expand_grids_in(text: str, calls: list[GridCall]) -> str:
    """`text` with each GRID call in it, in order, replaced by its lines."""
    tokens, _, _ = lex(text)
    out: list[str] = []
    at = 0
    i = 0
    n = 0
    while i < len(tokens):
        t = tokens[i]
        if (t.kind == "ident" and grid_layout(t.text) is not None and i + 1 < len(tokens)
                and tokens[i + 1].text == "(" and n < len(calls)):
            depth = 0
            j = i + 1
            while True:
                tj = tokens[j]
                if tj.kind == "punct" and tj.text in ("(", "["):
                    depth += 1
                elif tj.kind == "punct" and tj.text in (")", "]"):
                    depth -= 1
                    if depth == 0:
                        break
                j += 1
            out += [text[at:t.offset], grid_text(calls[n], _indent_at(text, t.offset))]
            at = tokens[j].end
            n += 1
            i = j + 1
        else:
            i += 1
    out.append(text[at:])
    return "".join(out)


def expand(program: Program) -> Program:
    expander = _Expander(program)
    segments = expander.segments(layout_of(program).segments, "")
    return expander.program_out(segments)
