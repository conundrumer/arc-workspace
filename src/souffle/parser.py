"""Parse a Souffle text, and the files it includes, into a `Program` with
its layout."""

import re
from bisect import bisect_right
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path

from arc.task import COLORS
from engine.engine import ParseFailure
from engine.program import (
    AdtType,
    Aggregate,
    AggregateOperator,
    AliasType,
    Atom,
    AtomLiteral,
    BinaryOperator,
    BinaryTerm,
    BodyLiteral,
    BoolLiteral,
    Cast,
    Column,
    Comment,
    Comparison,
    ComparisonOperator,
    Component,
    ConstructorDecl,
    ConstructorTerm,
    DeclId,
    Define,
    DefinedName,
    Disjunction,
    FunctorCall,
    FunctorDecl,
    GridCall,
    GridCell,
    GridForm,
    GridLayout,
    MemberCell,
    Include,
    Instance,
    Intrinsic,
    IntrinsicCall,
    MacroCall,
    NumberTerm,
    Plan,
    Qualifier,
    RecordTerm,
    RecordType,
    RelationDecl,
    RelationName,
    RigidCall,
    Scope,
    Span,
    StringTerm,
    SubtypeType,
    Term,
    TypeDecl,
    TypeField,
    TypeName,
    UnaryOperator,
    UnaryTerm,
    UnionType,
    Unit,
    UnitId,
    Variable,
    Wildcard,
)
from souffle.layout import (
    CompBlock,
    IncludeBlock,
    Key,
    Layout,
    Part,
    Piece,
    Segment,
    SouffleProgram,
    Text,
)
from souffle.lexer import LINE_DIRECTIVE_RE, LexError, RawComment, Token, lex
from souffle.text import GRID_FORM_SEGMENT, PREFIX

_FORM_OF_SEGMENT = {v: k for k, v in GRID_FORM_SEGMENT.items()}
GRID_RE = re.compile(r"GRID_(STAMP_)?("
                     + "|".join(re.escape(v) for v in GRID_FORM_SEGMENT.values())
                     + r")(\d+)x(\d+)")
RIGID_CHART_PREFIX = "_rigid_"


def chart_prefix(block: str) -> str:
    """What the names of a RIGID block's chart relations start with."""
    return f"{RIGID_CHART_PREFIX}{block}_"


def chart_name(block: str, rel: str) -> str:
    """The chart relation a RIGID block declares for its relation `rel`."""
    return f"{chart_prefix(block)}{rel}"


def placed_name(block: str, rel: str) -> str:
    """The relation a RIGID block places its relation `rel`'s rows in."""
    return f"{block}_{rel}"

RIGID_ACTIONS = {
    "Box": "apply", "Position": "apply", "Offset": "apply",
    "Dir": "apply_dir", "DiagDir": "apply_diag_dir", "Dir8": "apply_dir8",
}
"""The D4 action of each RIGID column type that acts through its type's
action relation."""
RIGID_AXIS_ACTIONS = {
    "Axis": ("axis_of", "apply_dir"),
    "DiagAxis": ("diag_axis_of", "apply_diag_dir"),
}
"""The column types that act through the swap they induce on a member
direction: the member relation and the direction's action."""
RIGID_IDENTITY = frozenset({"Color", "number", "Ident", "symbol", "Example"})
"""The column types a D4 action leaves as they are."""


def rigid_type_acts(type_name: TypeName) -> bool:
    text = type_name.text
    return (text in RIGID_ACTIONS or text in RIGID_AXIS_ACTIONS
            or text in RIGID_IDENTITY)


DIRECTIVE_WORDS = frozenset({"comp", "decl", "init", "type", "functor", "plan",
                             "input", "output", "printsize", "limitsize",
                             "pragma"})
AGGREGATES = {op.value: op for op in AggregateOperator}
INTRINSICS = {op.value: op for op in Intrinsic}
QUALIFIERS = {q.value: q for q in Qualifier}
COMPARISONS = {op.value: op for op in ComparisonOperator}
BINARY: dict[str, tuple[int, BinaryOperator]] = {
    "lor": (1, BinaryOperator.LOR), "lxor": (2, BinaryOperator.LXOR),
    "land": (3, BinaryOperator.LAND), "bor": (4, BinaryOperator.BOR),
    "bxor": (5, BinaryOperator.BXOR), "band": (6, BinaryOperator.BAND),
    "bshl": (7, BinaryOperator.BSHL), "bshr": (7, BinaryOperator.BSHR),
    "bshru": (7, BinaryOperator.BSHRU),
    "+": (8, BinaryOperator.ADD), "-": (8, BinaryOperator.SUB),
    "*": (9, BinaryOperator.MUL), "/": (9, BinaryOperator.DIV),
    "%": (9, BinaryOperator.MOD), "^": (11, BinaryOperator.POW),
}
"""Each binary operator's precedence, as Souffle's grammar orders them;
`^` binds tighter than a unary operator (10) and groups to the right."""
UNARY_PRECEDENCE = 10


class _Fail(Exception):
    def __init__(self, line: int, col: int, message: str):
        super().__init__(message)
        self.line = line
        self.col = col
        self.message = message


def _dotted_name(parts: Sequence[str]) -> RelationName:
    """The name whose dotted parts are `parts`, the relation's name last."""
    return RelationName(tuple(parts[:-1]), parts[-1])


def relation_name(text: str) -> RelationName:
    """The name a statement writes as `text`, `params.bg`: the inverse of
    `RelationName.text`."""
    return _dotted_name(text.split("."))


def grid_layout(name: str) -> GridLayout | None:
    """What a GRID macro's name states of its calls; None for a name that is
    no GRID macro's."""
    m = GRID_RE.fullmatch(name)
    if m is None:
        return None
    return GridLayout(_FORM_OF_SEGMENT[m[2]], bool(m[1]), int(m[3]), int(m[4]))


@dataclass
class _Build:
    """What the parse of a text and its includes gathers."""

    base_dir: Path
    decl_n: int = 0
    unit_n: int = 0
    types: list[TypeDecl] = field(default_factory=list)
    relations: list[RelationDecl] = field(default_factory=list)
    components: list[Component] = field(default_factory=list)
    instances: list[Instance] = field(default_factory=list)
    functors: list = field(default_factory=list)
    units: list[Unit] = field(default_factory=list)
    macros: list[MacroCall] = field(default_factory=list)
    comments: list[Comment] = field(default_factory=list)
    includes: list[Include] = field(default_factory=list)
    defines: list[Define] = field(default_factory=list)
    defined: set[str] = field(default_factory=set)
    including: list[str] = field(default_factory=list)

    def decl_id(self) -> DeclId:
        self.decl_n += 1
        return DeclId(self.decl_n - 1)

    def unit_id(self) -> UnitId:
        self.unit_n += 1
        return UnitId(self.unit_n - 1)


class _Parser:
    def __init__(self, build: _Build, text: str, file: str | None, directory: Path):
        self.b = build
        self.text = text
        self.file = file
        self.dir = directory
        try:
            self.toks, self.raw_comments, self.renumbered = lex(text)
        except LexError as e:
            raise _Fail(e.line, e.col, e.message) from None
        self.pos = 0
        self.last = len(self.toks) - 1
        self.line_starts = [0] + [i + 1 for i, c in enumerate(text) if c == "\n"]
        self.item_lines: dict[int, Key] = {}

    # tokens

    def peek(self, k: int = 0) -> Token:
        p = self.pos + k
        return self.toks[p if p < self.last else self.last]

    def next(self) -> Token:
        t = self.toks[self.pos]
        if self.pos < self.last:
            self.pos += 1
        return t

    def at(self, text: str, k: int = 0) -> bool:
        return self.peek(k).text == text and self.peek(k).kind != "str"

    def fail(self, t: Token, message: str) -> _Fail:
        return _Fail(t.line, t.col, message)

    def expect(self, text: str) -> Token:
        t = self.next()
        if t.text != text or t.kind == "str":
            raise self.fail(t, f"expected {text!r}, got {t.text or 'the end'!r}")
        return t

    def ident(self, what: str) -> Token:
        t = self.next()
        if t.kind != "ident":
            raise self.fail(t, f"expected {what}, got {t.text or 'the end'!r}")
        return t

    def span(self, first: Token) -> Span:
        """The span from `first` to the last token read, with the length
        of the longest line of its code: each text line it occupies up to
        its last token, less any comment on the line."""
        last = self.toks[self.pos - 1]
        lo = self.line_starts[first.phys - 1]
        cuts = sorted([c.offset for c in self.raw_comments if lo <= c.offset < last.end]
                      + [last.end])
        width = 0
        start = lo
        for phys in range(first.phys, last.phys + 1):
            end = (self.line_starts[phys] - 1 if phys < len(self.line_starts)
                   else len(self.text))
            cut = next((c for c in cuts if start <= c <= end), end)
            width = max(width, len(self.text[start:cut].rstrip()))
            start = end + 1
        return Span(first.line, last.line, file=self.file, width=width)

    def line_of(self, offset: int) -> int:
        """The line, as the `#line` directives number it, that `offset`
        stands on."""
        phys = bisect_right(self.line_starts, offset)
        line = phys
        for start, number in self.renumbered:
            if phys >= start:
                line = number + phys - start
        return line

    def opens_line(self, t: Token) -> bool:
        start = self.line_starts[t.phys - 1]
        return not self.text[start:t.offset].strip()

    def mark_item(self, t: Token, key: Key) -> None:
        if self.opens_line(t):
            self.item_lines.setdefault(t.line, key)

    # items

    def items(self, scope: Scope, closing: bool) -> tuple[list[Segment], int]:
        """The segments of the items up to the end, or up to the `}` that
        closes a component when `closing`; and the offset where they end."""
        out: list[Segment] = []
        at = self._offset_after_prev()
        while True:
            t = self.peek()
            if t.kind == "eof":
                if closing:
                    raise self.fail(t, "unterminated component")
                break
            if closing and self.at("}"):
                break
            start = t.offset
            if start > at:
                out.append(Text(self.text[at:start], self.line_of(at)))
            seg = self.item(scope)
            out.append(seg)
            at = self.toks[self.pos - 1].end
            if isinstance(seg, Piece) and seg.text.endswith("\n"):
                at += 1
        stop = self.peek().offset
        if stop > at:
            out.append(Text(self.text[at:stop], self.line_of(at)))
        return out, stop

    def _offset_after_prev(self) -> int:
        return 0 if self.pos == 0 else self.toks[self.pos - 1].end

    def piece(self, start: Token, parts: list[tuple[Key, Part]]) -> Piece:
        end = self.toks[self.pos - 1].end
        return Piece(self.text[start.offset:end], start.line, tuple(parts))

    def item(self, scope: Scope) -> Segment:
        t = self.peek()
        if t.kind == "hash":
            return self.hash_line()
        if self.at("."):
            word = self.peek(1).text
            if word == "comp":
                return self.comp(scope)
            if word == "decl":
                return self.decl(scope)
            if word == "init":
                return self.init(scope)
            if word == "type":
                return self.type_decl(scope)
            if word == "functor":
                return self.functor()
            raise self.fail(t, f"unknown directive .{word}")
        if t.kind == "ident" and t.text == "RIGID" and self.at("(", 1):
            return self.rigid(scope)
        if t.kind == "ident" and grid_layout(t.text) and self.at("(", 1):
            call = self.grid(scope, None)
            self.mark_item(t, call.id)
            return self.piece(t, [(call.id, call)])
        return self.clause(scope)

    def hash_line(self) -> Segment:
        t = self.next()
        if LINE_DIRECTIVE_RE.match(t.text):
            # The directive's line break goes with it, so that the text
            # after it starts on the line the directive numbers.
            newline = self.text[t.end:t.end + 1] == "\n"
            return Piece(t.text + ("\n" if newline else ""), t.line, ())
        if m := re.match(r'#include\s+"([^"]*)"', t.text):
            return self.include(t, m.group(1))
        if m := re.match(r"#define\s+(\w+)(\(([^)]*)\))?\s*(.*)", t.text):
            name = m.group(1)
            params = (tuple(p.strip() for p in m.group(3).split(",") if p.strip())
                      if m.group(2) else None)
            value = None if params is not None else self.define_value(m.group(4).strip())
            self.b.defines.append(Define(name, params, value, t.line, file=self.file))
            self.b.defined.add(name)
            return Piece(t.text, t.line, ())
        raise self.fail(t, f"unknown # directive: {t.text!r}")

    def define_value(self, text: str) -> Term | None:
        if not text:
            return None
        try:
            sub = _Parser(self.b, text, self.file, self.dir)
            term = sub.expr()
            return term if sub.peek().kind == "eof" else None
        except _Fail:
            return None

    def include(self, t: Token, path: str) -> Segment:
        target = (self.dir / path).resolve()
        if not target.is_file():
            raise self.fail(t, f"#include \"{path}\": no file {target}")
        key = str(target)
        if key in self.b.including:
            raise self.fail(t, f"#include \"{path}\" includes itself")
        self.b.includes.append(Include(path, t.line, file=self.file))
        self.b.including.append(key)
        try:
            sub = _Parser(self.b, target.read_text(), key, target.parent)
            body = sub.file_items()
        except _Fail as e:
            raise self.fail(t, f"{path}:{e.line}:{e.col}: {e.message}") from None
        finally:
            self.b.including.pop()
        return IncludeBlock(t.text, t.line, key, tuple(body))

    def file_items(self) -> list[Segment]:
        segments, _ = self.items(Scope(()), False)
        self.gather_comments()
        return segments

    def gather_comments(self) -> None:
        raw = self.raw_comments
        above: list[Key | None] = [None] * len(raw)
        i = 0
        while i < len(raw):
            if not raw[i].own_line:
                i += 1
                continue
            j = i
            while (j + 1 < len(raw) and raw[j + 1].own_line
                   and raw[j + 1].line == raw[j].end_line + 1):
                j += 1
            key = self.item_lines.get(raw[j].end_line + 1)
            for k in range(i, j + 1):
                above[k] = key
            i = j + 1
        for c, key in zip(raw, above, strict=True):
            self.b.comments.append(_comment(c, key, self.file))

    def comp(self, scope: Scope) -> Segment:
        start = self.next()
        self.expect("comp")
        name = self.ident("component name").text
        params = self.type_params()
        base, base_args = None, ()
        if self.at(":"):
            self.next()
            base = self.ident("base component name").text
            base_args = self.type_args()
        brace = self.expect("{")
        key = self.b.decl_id()
        self.mark_item(start, key)
        inner = Scope((*scope.components, name))
        head = self.text[start.offset:brace.end]
        body, _ = self.items(inner, True)
        close = self.next()
        comp = Component(key, name, scope, params, base, base_args,
                         self.span(start))
        self.b.components.append(comp)
        return CompBlock(key, comp, head, start.line, tuple(body), close.text, close.line)

    def type_params(self) -> tuple[str, ...]:
        if not self.at("<"):
            return ()
        self.next()
        out = [self.ident("type parameter").text]
        while self.at(","):
            self.next()
            out.append(self.ident("type parameter").text)
        self.expect(">")
        return tuple(out)

    def type_args(self) -> tuple[TypeName, ...]:
        if not self.at("<"):
            return ()
        self.next()
        out = [self.type_name()]
        while self.at(","):
            self.next()
            out.append(self.type_name())
        self.expect(">")
        return tuple(out)

    def type_name(self) -> TypeName:
        parts = [self.ident("type name").text]
        while (self.at(".") and self.peek(1).kind == "ident"
               and self.peek(1).text not in DIRECTIVE_WORDS):
            self.next()
            parts.append(self.next().text)
        return TypeName(tuple(parts[:-1]), parts[-1])

    def fields(self, close: str) -> tuple[TypeField, ...]:
        out: list[TypeField] = []
        while not self.at(close):
            fname = self.ident("field name").text
            self.expect(":")
            out.append(TypeField(fname, self.type_name()))
            if not self.at(close):
                self.expect(",")
        self.next()
        return tuple(out)

    def decl(self, scope: Scope) -> Segment:
        start = self.next()
        self.expect("decl")
        name = self.ident("relation name").text
        self.expect("(")
        cols = tuple(Column(f.name, f.type) for f in self.fields(")"))
        quals: list[Qualifier] = []
        while self.peek().kind == "ident" and self.peek().text in QUALIFIERS:
            quals.append(QUALIFIERS[self.next().text])
        domain = self.choice_domain()
        key = self.b.decl_id()
        self.mark_item(start, key)
        rel = RelationDecl(key, name, scope, cols, tuple(quals), domain,
                           self.span(start))
        self.b.relations.append(rel)
        return self.piece(start, [(key, rel)])

    def choice_domain(self) -> tuple[str, ...]:
        if not (self.peek().kind == "ident" and self.peek().text == "choice"
                and self.at("-", 1)):
            return ()
        self.next()
        self.next()
        word = self.ident("'domain'")
        if word.text != "domain":
            raise self.fail(word, "expected 'domain' after 'choice-'")
        specs: list[str] = []
        while True:
            if self.at("("):
                self.next()
                parts = [self.ident("choice-domain attribute").text]
                while self.at(","):
                    self.next()
                    parts.append(self.ident("choice-domain attribute").text)
                self.expect(")")
                specs.append("(" + ", ".join(parts) + ")")
            else:
                specs.append(self.ident("choice-domain attribute").text)
            if not self.at(","):
                return tuple(specs)
            self.next()

    def init(self, scope: Scope) -> Segment:
        start = self.next()
        self.expect("init")
        name = self.ident("instance name").text
        self.expect("=")
        comp = self.ident("component name").text
        args = self.type_args()
        key = self.b.decl_id()
        self.mark_item(start, key)
        inst = Instance(key, name, scope, comp, args,
                        self.span(start))
        self.b.instances.append(inst)
        return self.piece(start, [(key, inst)])

    def type_decl(self, scope: Scope) -> Segment:
        start = self.next()
        self.expect("type")
        name = self.ident("type name").text
        key = self.b.decl_id()
        self.mark_item(start, key)
        decl: TypeDecl
        if self.at("<:"):
            self.next()
            base = self.type_name()
            decl = SubtypeType(key, name, scope, base, self.span(start))
        else:
            self.expect("=")
            if self.at("["):
                self.next()
                fields = self.fields("]")
                decl = RecordType(key, name, scope, fields,
                                  self.span(start))
            elif self.peek().kind == "ident" and self.at("{", 1):
                ctors = [self.constructor()]
                while self.at("|"):
                    self.next()
                    ctors.append(self.constructor())
                decl = AdtType(key, name, scope, tuple(ctors),
                               self.span(start))
            else:
                members = [self.type_name()]
                while self.at("|"):
                    self.next()
                    members.append(self.type_name())
                span = self.span(start)
                decl = (UnionType(key, name, scope, tuple(members), span)
                        if len(members) > 1 else
                        AliasType(key, name, scope, members[0], span))
        self.b.types.append(decl)
        return self.piece(start, [(key, decl)])

    def constructor(self) -> ConstructorDecl:
        at = self.peek()
        before = [t.text for t in self.toks[max(0, self.pos - 2):self.pos]
                  if t.line == at.line]
        name = self.ident("constructor name").text
        self.expect("{")
        fields = self.fields("}")
        return ConstructorDecl(name, fields, self.span(at),
                               before in ([], ["|"]))

    def functor(self) -> Segment:
        start = self.next()
        self.expect("functor")
        name = self.ident("functor name").text
        self.expect("(")
        params: list[TypeField] = []
        while not self.at(")"):
            first = self.ident("functor parameter")
            if self.at(":"):
                self.next()
                params.append(TypeField(first.text, self.type_name()))
            else:
                params.append(TypeField("", TypeName((), first.text)))
            if not self.at(")"):
                self.expect(",")
        self.next()
        self.expect(":")
        result = self.type_name()
        stateful = self.peek().kind == "ident" and self.peek().text == "stateful"
        if stateful:
            self.next()
        key = self.b.decl_id()
        self.mark_item(start, key)
        decl = FunctorDecl(key, name, tuple(params), result, self.span(start),
                           stateful=stateful)
        self.b.functors.append(decl)
        return self.piece(start, [(key, decl)])

    # macro calls

    def arg_spans(self, call: Token) -> list[tuple[int, int]]:
        """The token span of each argument of a call whose `(` was just
        read, split at the commas outside brackets."""
        spans: list[tuple[int, int]] = []
        start, depth = self.pos, 0
        while True:
            tok = self.next()
            if tok.kind == "eof":
                raise self.fail(call, f"unterminated {call.text}")
            if tok.kind == "str":
                continue
            if tok.text in ("(", "["):
                depth += 1
            elif tok.text == "]" or (tok.text == ")" and depth):
                depth -= 1
            elif tok.text in (",", ")") and not depth:
                spans.append((start, self.pos - 1))
                start = self.pos
                if tok.text == ")":
                    return spans

    def within[T](self, span: tuple[int, int], read: Callable[[], T]) -> T:
        mark = self.pos
        self.pos, end = span
        if self.pos == end:
            raise self.fail(self.toks[end], "empty argument")
        out = read()
        if self.pos != end:
            raise self.fail(self.peek(), f"unexpected token {self.peek().text!r}")
        self.pos = mark
        return out

    def cell(self) -> GridCell:
        if self.at("@"):
            self.next()
            return GridCell(self.primary(), True)
        return GridCell(self.expr(), False)

    def grid(self, scope: Scope, rename: dict[str, str] | None) -> GridCall:
        t = self.next()
        form = grid_layout(t.text)
        assert form is not None
        self.expect("(")
        spans = self.arg_spans(t)
        cells = form.height * form.width
        if len(spans) < 1 + cells:
            raise self.fail(t, f"{t.text} has {len(spans) - 1} arguments after the "
                               f"relation name, fewer than its {cells} cells")
        rel = self.within(spans[0], self.relation_name)
        if rename and not rel.instances and rel.name in rename:
            rel = RelationName((), rename[rel.name])
        nkeys = len(spans) - cells
        keys = tuple(self.within(s, self.expr) for s in spans[1:nkeys])
        flat = [self.within(s, self.cell) for s in spans[nkeys:]]
        rows = tuple(tuple(flat[r * form.width:(r + 1) * form.width])
                     for r in range(form.height))
        self.check_cells(t, form, rel, keys, flat)
        call = GridCall(self.b.unit_id(), scope, form, rel, keys, rows,
                        self.span(t))
        self.b.macros.append(call)
        return call

    def check_cells(self, t: Token, form: GridLayout, rel: RelationName,
                    keys: tuple[Term, ...], cells: list[GridCell]) -> None:
        """Fail where a cell is not one the call's form takes: a digit or
        `_` under a sparse name, `1` or `_` under a mask name, and one
        anchor cell in a stamp."""
        from souffle.printer import term
        label = f"{t.text}({', '.join([rel.text, *(term(k) for k in keys)])})"
        anchors = sum(c.anchor for c in cells)
        if form.stamp and anchors != 1:
            raise self.fail(t, f"{label}: {anchors} '@' anchor cells, need 1")
        if not form.stamp and anchors:
            raise self.fail(t, f"{label}: an '@' anchor cell outside a stamp")
        if form.full:
            return
        for c in cells:
            v = c.term
            if form.form is GridForm.SPARSE and MemberCell.of_term(v) is not MemberCell.EMPTY and not (
                    isinstance(v, NumberTerm) and isinstance(v.value, int) and v.value in COLORS):
                raise self.fail(t, f"{label}: cell {term(v)!r} is not a color digit or {str(MemberCell.EMPTY)!r}")
            if not form.valued and MemberCell.of_term(v) is None:
                cells_text = " or ".join(repr(str(m)) for m in MemberCell)
                raise self.fail(t, f"{label}: cell {term(v)!r} is not {cells_text}")

    def relation_name(self) -> RelationName:
        parts = [self.ident("relation name").text]
        while self.at("."):
            self.next()
            parts.append(self.ident("relation name").text)
        return _dotted_name(parts)

    def rigid(self, scope: Scope) -> Segment:
        start = self.next()
        self.expect("(")
        block = self.ident("rigid block name").text
        self.expect(",")
        # The names the block declares, read ahead so that each fact of the
        # body names its chart.
        mark = self.pos
        declared: list[str] = []
        depth = 0
        while not (depth == 0 and self.at(")")):
            tok = self.next()
            if tok.kind == "eof":
                raise self.fail(start, f"unterminated RIGID {block}")
            if tok.text in ("(", "[") and tok.kind == "punct":
                depth += 1
            elif tok.text in (")", "]") and tok.kind == "punct":
                depth -= 1
            elif tok.text == "decl" and self.toks[self.pos - 2].text == ".":
                declared.append(self.peek().text)
        self.pos = mark
        rename = {rel: chart_name(block, rel) for rel in declared}
        parts: list[tuple[Key, Part]] = []
        body: list[UnitId] = []
        while not self.at(")"):
            t = self.peek()
            if self.at(".") and self.at("decl", 1):
                self.next()
                self.next()
                name = self.ident("relation name").text
                self.expect("(")
                fields = self.fields(")")
                for f in fields:
                    if not rigid_type_acts(f.type):
                        raise self.fail(t, f"RIGID column type {f.type.text!r} has no D4 action")
                span = self.span(t)
                chart = RelationDecl(self.b.decl_id(), rename[name], scope,
                                     tuple(Column(f.name, f.type) for f in fields),
                                     (), (), span, chart_of=block)
                placed = RelationDecl(self.b.decl_id(), placed_name(block, name), scope,
                                      (Column("d4", TypeName((), "D4")),
                                       *(Column(f.name, f.type) for f in fields)),
                                      (), (), span)
                self.b.relations += [chart, placed]
                parts += [(chart.id, chart), (placed.id, placed)]
            elif t.kind == "ident" and grid_layout(t.text) and self.at("(", 1):
                call = self.grid(scope, rename)
                body.append(call.id)
                parts.append((call.id, call))
            else:
                for unit in self.clause_units(scope, rename):
                    if unit.body is not None:
                        raise self.fail(t, f"RIGID {block} holds decls and facts only")
                    body.append(unit.id)
                    parts.append((unit.id, unit))
        self.next()
        names = tuple(placed_name(block, rel) for rel in declared)
        call = RigidCall(self.b.unit_id(), scope, block, tuple(body), names,
                         self.span(start))
        self.b.macros.append(call)
        self.mark_item(start, call.id)
        return self.piece(start, [(call.id, call), *parts])

    # clauses

    def clause(self, scope: Scope) -> Segment:
        start = self.peek()
        units = self.clause_units(scope, None)
        self.mark_item(start, units[0].id)
        return self.piece(start, [(u.id, u) for u in units])

    def clause_units(self, scope: Scope, rename: dict[str, str] | None) -> list[Unit]:
        first = self.peek()
        head = self.atom()
        if rename and not head.relation.instances and head.relation.name in rename:
            head = Atom(RelationName((), rename[head.relation.name]), head.args, head.line)
        if self.at("."):
            self.next()
            plan = self.plan()
            unit = Unit(self.b.unit_id(), scope, head, None, plan,
                        self.span(first))
            self.b.units.append(unit)
            return [unit]
        if self.at("<="):
            self.next()
            dominant = self.atom()
            self.expect(":-")
            body = self.conj()
            self.expect(".")
            plan = self.plan()
            unit = Unit(self.b.unit_id(), scope, head,
                        (AtomLiteral(dominant, False), *body), plan,
                        self.span(first), subsumptive=True)
            self.b.units.append(unit)
            return [unit]
        heads = [head]
        while self.at(","):
            self.next()
            heads.append(self.atom())
        self.expect(":-")
        body = self.conj()
        self.expect(".")
        plan = self.plan()
        span = self.span(first)
        units = [Unit(self.b.unit_id(), scope, h, body, plan, span) for h in heads]
        self.b.units += units
        return units

    def plan(self) -> Plan | None:
        if not (self.at(".") and self.at("plan", 1)):
            return None
        self.next()
        self.next()
        entries: list[tuple[int, tuple[int, ...]]] = []
        while True:
            version = self.number("plan version")
            self.expect(":")
            self.expect("(")
            order = [self.number("plan position")]
            while self.at(","):
                self.next()
                order.append(self.number("plan position"))
            self.expect(")")
            entries.append((version, tuple(order)))
            if not self.at(","):
                return Plan(tuple(entries))
            self.next()

    def number(self, what: str) -> int:
        t = self.next()
        if t.kind != "num" or not t.text.isdigit():
            raise self.fail(t, f"expected {what}, got {t.text!r}")
        return int(t.text)

    def conj(self) -> tuple[BodyLiteral, ...]:
        body = [self.literal()]
        while self.at(","):
            self.next()
            body.append(self.literal())
        return tuple(body)

    def atom_ahead(self) -> bool:
        if self.peek().kind != "ident":
            return False
        k = 1
        while self.at(".", k) and self.peek(k + 1).kind == "ident":
            k += 2
        return self.at("(", k)

    def op_ahead(self) -> bool:
        t = self.peek()
        if t.kind == "str":
            return False
        return t.text in COMPARISONS or t.text in BINARY

    def literal(self) -> BodyLiteral:
        if self.at("("):
            mark = self.pos
            line = self.next().line
            try:
                branches = [self.conj()]
                while self.at(";"):
                    self.next()
                    branches.append(self.conj())
                self.expect(")")
                if len(branches) > 1 or not self.op_ahead():
                    return Disjunction(tuple(branches), line)
            except _Fail:
                pass
            self.pos = mark
        if self.at("!"):
            self.next()
            return AtomLiteral(self.atom(), True)
        t = self.peek()
        if t.kind == "ident" and t.text in ("true", "false") and not self.at("(", 1):
            self.next()
            return BoolLiteral(t.text == "true")
        if self.atom_ahead():
            mark = self.pos
            atom = self.atom()
            if not self.op_ahead():
                return atom_literal(atom)
            self.pos = mark
        lhs = self.expr()
        op = self.next()
        if op.text not in COMPARISONS or op.kind == "str":
            raise self.fail(op, f"expected comparison, got {op.text or 'the end'!r}")
        return Comparison(COMPARISONS[op.text], lhs, self.expr(), op.line)

    def atom(self) -> Atom:
        t = self.next()
        if t.kind != "ident":
            raise self.fail(t, f"expected atom, got {t.text or 'the end'!r}")
        parts = [t.text]
        while self.at(".") and self.peek(1).kind == "ident":
            self.next()
            parts.append(self.next().text)
        self.expect("(")
        args: list[Term] = []
        while not self.at(")"):
            args.append(self.expr())
            if not self.at(")"):
                self.expect(",")
        self.next()
        return Atom(_dotted_name(parts), tuple(args), t.line)

    # terms

    def expr(self, least: int = 1) -> Term:
        lhs = self.unary()
        while True:
            t = self.peek()
            if t.kind == "str" or t.text not in BINARY:
                return lhs
            prec, op = BINARY[t.text]
            if prec < least:
                return lhs
            self.next()
            rhs = self.expr(prec if op is BinaryOperator.POW else prec + 1)
            lhs = BinaryTerm(op, lhs, rhs)

    def unary(self) -> Term:
        t = self.peek()
        if self.at("-"):
            self.next()
            nxt = self.peek()
            if nxt.kind == "num" and not self.at("^", 1):
                self.next()
                return NumberTerm(-_number(nxt.text))
            return UnaryTerm(UnaryOperator.NEGATE, self.expr(UNARY_PRECEDENCE + 1))
        if t.kind == "ident" and t.text in ("bnot", "lnot") and not self.at("(", 1):
            self.next()
            op = UnaryOperator.BNOT if t.text == "bnot" else UnaryOperator.LNOT
            return UnaryTerm(op, self.expr(UNARY_PRECEDENCE + 1))
        return self.primary()

    def primary(self) -> Term:
        t = self.next()
        if t.kind == "num":
            return NumberTerm(_number(t.text))
        if t.kind == "str":
            return StringTerm(t.text[1:-1])
        if t.text == "(":
            e = self.expr()
            self.expect(")")
            return replace(e, parens=True) if isinstance(e, BinaryTerm) else e
        if t.text == PREFIX:
            name = self.ident("constructor name").text
            return ConstructorTerm(name, self.arg_list() if self.at("(") else ())
        if t.text == "[":
            args: list[Term] = []
            while not self.at("]"):
                args.append(self.expr())
                if not self.at("]"):
                    self.expect(",")
            self.next()
            return RecordTerm(tuple(args))
        if t.text == "@":
            name = self.ident("functor name").text
            return FunctorCall(name, self.arg_list())
        if t.kind == "ident":
            if t.text == "_":
                return Wildcard()
            if t.text in AGGREGATES and not self.at("("):
                return self.aggregate(AGGREGATES[t.text])
            if t.text == "as" and self.at("("):
                self.next()
                value = self.expr()
                self.expect(",")
                target = self.type_name()
                self.expect(")")
                return Cast(value, target)
            if self.at("("):
                if t.text not in INTRINSICS:
                    raise self.fail(t, f"unknown functor {t.text!r}")
                return IntrinsicCall(INTRINSICS[t.text], self.arg_list())
            if t.text in self.b.defined:
                return DefinedName(t.text)
            return Variable(t.text)
        raise self.fail(t, f"unexpected token {t.text or 'the end'!r} in term")

    def aggregate(self, op: AggregateOperator) -> Aggregate:
        expr = None if self.at(":") else self.expr()
        self.expect(":")
        if self.at("{"):
            self.next()
            body = self.conj()
            self.expect("}")
        else:
            body = (atom_literal(self.atom()),)
        return Aggregate(op, expr, body)

    def arg_list(self) -> tuple[Term, ...]:
        self.expect("(")
        args: list[Term] = []
        while not self.at(")"):
            args.append(self.expr())
            if not self.at(")"):
                self.expect(",")
        self.next()
        return tuple(args)


def atom_literal(atom: Atom) -> AtomLiteral:
    return AtomLiteral(atom, False)


def _number(text: str) -> int | float:
    return float(text) if "." in text else int(text)


def _comment(c: RawComment, key: Key | None, file: str | None) -> Comment:
    block = c.text.startswith("/*")
    text = c.text[2:-2] if block else c.text[2:]
    return Comment(c.line, c.col, text, c.own_line, key if c.own_line else None,
                   file=file, block=block)


def parse(text: str, base_dir: Path) -> SouffleProgram | ParseFailure:
    """The program `text` states, each `#include` resolved against
    `base_dir`, or where it leaves the grammar."""
    build = _Build(base_dir)
    try:
        parser = _Parser(build, text, None, base_dir)
        segments = parser.file_items()
    except _Fail as e:
        return ParseFailure(e.line, e.col, e.message)
    return SouffleProgram(
        tuple(build.types), tuple(build.relations), tuple(build.components),
        tuple(build.instances), tuple(build.functors), tuple(build.units),
        tuple(build.macros),
        tuple(sorted(build.comments,
                     key=lambda c: (c.file is not None, c.file or "", c.line, c.column))),
        tuple(build.includes), tuple(build.defines),
        layout=Layout(tuple(segments)))
