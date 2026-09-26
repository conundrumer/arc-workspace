"""Parse solver .dl source into an AST, plus a reference index over it.

The grammar covers the dialect the solvers and lib.dl use, and nothing
more: anything outside it raises `ParseError`. Souffle itself owns the
real semantics, so the parser can be strict and fail loudly.

Comments are kept on the program (`Program.comments`) with position and
own-line flags, so renderers can reattach them.

`Index` resolves every atom to the relation it names — through comp
instantiations, inheritance, negation, and aggregate bodies — and
records the role of each reference. It is the shared layer the lints
query.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass, field
from functools import lru_cache

AGG_OPS = {"count", "sum", "max", "min", "mean"}
WORD_OPS = {"band", "bor", "bxor", "bshl", "bshr", "land", "lor", "lxor"}
ARITH_OPS = {"+", "-", "*", "/", "%", "^"}
CMP_OPS = {"=", "!=", "<", "<=", ">", ">="}
DECL_QUALIFIERS = {"inline", "btree", "brie", "eqrel", "override", "overridable"}
GRID_RE = re.compile(r"GRID_(STAMP_)?(MASK_|SPARSE_)?\d+x\d+$")
MACRO_CONST_RE = re.compile(r"(?:[A-Z][A-Z0-9]*_[A-Z0-9_]*|ZERO)$")


class ParseError(Exception):
    def __init__(self, line: int, msg: str):
        super().__init__(f"L{line}: {msg}")
        self.line = line
        self.msg = msg


# --- lexer ---

@dataclass(frozen=True)
class Token:
    kind: str   # 'ident' | 'num' | 'str' | 'punct' | 'hash' | 'eof'
    text: str
    line: int
    col: int


@dataclass(frozen=True)
class Comment:
    line: int
    col: int
    text: str       # includes the // or /* */ delimiters
    own_line: bool  # nothing but whitespace before it on its line


PUNCT_PAIRS = frozenset({":-", "<=", ">=", "!=", "<:"})  # tried before the one below
PUNCT_ONE = frozenset("<>=!()[]{},.:;$@|+-*/%^")
SPACE_RE = re.compile(r"[ \t\n\r]+")
WORD_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*|\d+")


def _lex(source: str) -> tuple[list[Token], list[Comment]]:
    tokens: list[Token] = []
    comments: list[Comment] = []
    line, col = 1, 1
    i, n = 0, len(source)

    def bump(text: str) -> None:
        nonlocal line, col
        nl = text.count("\n")
        if nl:
            line += nl
            col = len(text) - text.rfind("\n")
        else:
            col += len(text)

    while i < n:
        c = source[i]
        if c in " \t\n\r":
            m = SPACE_RE.match(source, i)
            assert m
            bump(m.group(0))
            i = m.end()
            continue
        if c == "/" and source.startswith("//", i):
            j = source.find("\n", i)
            j = n if j < 0 else j
            text = source[i:j]
            comments.append(Comment(line, col, text, _own_line(source, i)))
            bump(text)
            i = j
            continue
        if c == "/" and source.startswith("/*", i):
            j = source.find("*/", i)
            if j < 0:
                raise ParseError(line, "unterminated block comment")
            text = source[i:j + 2]
            comments.append(Comment(line, col, text, _own_line(source, i)))
            bump(text)
            i = j + 2
            continue
        if c == "#":
            j = source.find("\n", i)
            j = n if j < 0 else j
            tokens.append(Token("hash", source[i:j], line, col))
            bump(source[i:j])
            i = j
            continue
        if c == '"':
            j = i + 1
            while j < n and source[j] != '"':
                j += 2 if source[j] == "\\" else 1
            if j >= n:
                raise ParseError(line, "unterminated string")
            text = source[i:j + 1]
            tokens.append(Token("str", text, line, col))
            bump(text)
            i = j + 1
            continue
        if m := WORD_RE.match(source, i):
            text = m.group(0)
            tokens.append(Token("num" if c.isdigit() else "ident", text, line, col))
            col += len(text)
            i = m.end()
            continue
        pair = source[i:i + 2]
        if pair in PUNCT_PAIRS:
            p = pair
        elif c in PUNCT_ONE:
            p = c
        else:
            raise ParseError(line, f"unexpected character {c!r}")
        tokens.append(Token("punct", p, line, col))
        col += len(p)
        i += len(p)
    tokens.append(Token("eof", "", line, col))
    return tokens, comments


def _own_line(source: str, i: int) -> bool:
    start = source.rfind("\n", 0, i) + 1
    return not source[start:i].strip()


# --- AST ---

@dataclass(frozen=True)
class Var:
    name: str


@dataclass(frozen=True)
class Wild:
    pass


@dataclass(frozen=True)
class Num:
    text: str


@dataclass(frozen=True)
class Str:
    text: str


@dataclass(frozen=True)
class MacroConst:
    name: str


@dataclass(frozen=True)
class Ctor:
    name: str
    args: tuple[Term, ...]


@dataclass(frozen=True)
class Rec:
    args: tuple[Term, ...]


@dataclass(frozen=True)
class Call:
    name: str
    args: tuple[Term, ...]
    functor: bool  # @name(...) vs intrinsic name(...)


@dataclass(frozen=True)
class UnOp:
    op: str
    arg: Term


@dataclass(frozen=True)
class BinOp:
    op: str
    lhs: Term
    rhs: Term


@dataclass(frozen=True)
class Agg:
    op: str
    expr: Term | None     # None for count
    body: tuple[Lit, ...]


@dataclass(frozen=True)
class Bool:
    value: bool


@dataclass(frozen=True)
class Atom:
    qual: str | None   # dotted instance path ('c', 'c.out_along'), None if bare
    name: str
    args: tuple[Term, ...]
    line: int


@dataclass(frozen=True)
class Neg:
    atom: Atom


@dataclass(frozen=True)
class Cmp:
    op: str
    lhs: Term
    rhs: Term
    line: int


@dataclass(frozen=True)
class Disj:
    branches: tuple[tuple[Lit, ...], ...]
    line: int


@dataclass
class Include:
    path: str
    line: int


@dataclass
class Define:
    name: str
    value: str
    line: int


@dataclass
class Functor:
    name: str
    text: str
    line: int


@dataclass
class TypeDecl:
    name: str
    rhs: str            # raw right-hand side, '<: base' or '= ...'
    branches: list[str]  # ADT branch names, empty otherwise
    line: int


@dataclass
class Field:
    name: str
    type: str


@dataclass
class Decl:
    name: str
    fields: list[Field]
    qualifiers: list[str]
    line: int
    end_line: int
    # Souffle choice-domain specs: each entry an attribute name or a
    # parenthesized attribute tuple, e.g. ["b", "(a, c)"].
    choice_domain: list[str] = field(default_factory=list)


@dataclass
class Init:
    inst: str
    comp: str
    targs: list[str]
    line: int


@dataclass
class Rule:
    head: Atom
    body: list[Lit] | None   # None: fact; list: rule body literals
    line: int
    end_line: int
    grid: bool = False  # GRID macro fact
    sub: bool = False   # subsumptive clause; the dominant atom leads the body
    # Souffle `.plan` join orders, one (version, order) per entry. The
    # order is a permutation of the body's atom positions, 1-based.
    plan: list[tuple[int, tuple[int, ...]]] | None = None


@dataclass
class Rigid:
    """A RIGID block: chart decls and facts stated in one intrinsic frame,
    exposed only as D4 placements. The chart itself is unreadable outside
    the expansion."""
    name: str
    items: list[Item]   # chart Decls and fact Rules
    line: int
    end_line: int


@dataclass
class Comp:
    name: str
    params: list[str]
    items: list[Item]
    line: int
    end_line: int
    base: str | None = None      # inherited comp, single inheritance
    base_targs: list[str] = field(default_factory=list)


@dataclass
class Program:
    items: list[Item]
    comments: list[Comment]

    def comps(self) -> dict[str, Comp]:
        return {it.name: it for it in self.items if isinstance(it, Comp)}


type Term = Var | Wild | Num | Str | MacroConst | Ctor | Rec | Call | UnOp | BinOp | Agg
type Lit = Atom | Neg | Cmp | Bool | Disj
type Item = Include | Define | Functor | TypeDecl | Decl | Init | Rule | Comp | Rigid


# --- parser ---

class _Parser:
    def __init__(self, tokens: list[Token]):
        self.toks = tokens
        self.last = len(tokens) - 1
        self.pos = 0

    def peek(self, k: int = 0) -> Token:
        p = self.pos + k
        return self.toks[p if p < self.last else self.last]

    def next(self) -> Token:
        t = self.toks[self.pos]
        self.pos += 1
        return t

    def expect(self, text: str) -> Token:
        t = self.next()
        if t.text != text:
            raise ParseError(t.line, f"expected {text!r}, got {t.text!r}")
        return t

    def at(self, text: str, k: int = 0) -> bool:
        return self.peek(k).text == text

    # items

    def program(self) -> list[Item]:
        items: list[Item] = []
        while self.peek().kind != "eof":
            items.extend(self.item())
        return items

    def item(self) -> list[Item]:
        """The next item, or the rules of a clause with several heads,
        one per head."""
        t = self.peek()
        if (t.kind == "hash" or t.text == "."
                or (t.kind == "ident" and t.text == "RIGID"
                    and self.at("(", 1))):
            return [self.one_item()]
        return [*self.clause()]

    def one_item(self) -> Item:
        t = self.peek()
        if t.kind == "hash":
            return self.hash_directive()
        if t.text == ".":
            word = self.peek(1).text
            if word == "comp":
                return self.comp()
            if word == "decl":
                return self.decl()
            if word == "init":
                return self.init()
            if word == "type":
                return self.type_decl()
            if word == "functor":
                return self.functor()
            raise ParseError(t.line, f"unknown directive .{word}")
        return self.rigid()

    def rigid(self) -> Rigid:
        line = self.next().line  # RIGID
        self.expect("(")
        name = self.ident("rigid block name")
        self.expect(",")
        items: list[Item] = []
        while not self.at(")"):
            if self.peek().kind == "eof":
                raise ParseError(line, f"unterminated RIGID {name}")
            for it in self.item():
                if not (isinstance(it, Decl)
                        or (isinstance(it, Rule) and it.body is None)):
                    raise ParseError(line,
                                     f"RIGID {name} holds decls and facts only")
                items.append(it)
        end = self.next().line  # ')'
        return Rigid(name, items, line, end)

    def hash_directive(self) -> Include | Define:
        t = self.next()
        if m := re.match(r'#include\s+"([^"]*)"', t.text):
            return Include(m.group(1), t.line)
        if m := re.match(r"#define\s+(\w+)\s*(.*)", t.text):
            return Define(m.group(1), m.group(2).strip(), t.line)
        raise ParseError(t.line, f"unknown # directive: {t.text!r}")

    def comp(self) -> Comp:
        line = self.next().line  # '.'
        self.expect("comp")
        name = self.ident("comp name")
        params = self.targ_list()
        base, base_targs = None, []
        if self.at(":"):
            self.next()
            base = self.ident("base comp name")
            base_targs = self.targ_list()
        self.expect("{")
        items: list[Item] = []
        while not self.at("}"):
            if self.peek().kind == "eof":
                raise ParseError(line, f"unterminated comp {name}")
            items.extend(self.item())
        end = self.next().line  # '}'
        return Comp(name, params, items, line, end, base, base_targs)

    def decl(self) -> Decl:
        line = self.next().line
        self.expect("decl")
        name = self.ident("relation name")
        self.expect("(")
        fields: list[Field] = []
        while not self.at(")"):
            fname = self.ident("field name")
            self.expect(":")
            fields.append(Field(fname, self.type_name()))
            if not self.at(")"):
                self.expect(",")
        self.next()
        quals: list[str] = []
        while self.peek().kind == "ident" and self.peek().text in DECL_QUALIFIERS:
            quals.append(self.next().text)
        choice_dom = self.choice_domain()
        return Decl(name, fields, quals, line, self.toks[self.pos - 1].line,
                    choice_dom)

    def choice_domain(self) -> list[str]:
        """Souffle `choice-domain d1, d2` on a decl; each d an attribute or
        a parenthesized attribute tuple."""
        if not (self.peek().kind == "ident" and self.peek().text == "choice"
                and self.at("-", 1)):
            return []
        self.next()
        self.next()
        if not (self.peek().kind == "ident" and self.peek().text == "domain"):
            raise ParseError(self.peek().line, "expected 'domain' after 'choice-'")
        self.next()
        specs: list[str] = []
        while True:
            if self.at("("):
                self.next()
                parts = [self.ident("choice-domain attribute")]
                while self.at(","):
                    self.next()
                    parts.append(self.ident("choice-domain attribute"))
                self.expect(")")
                specs.append("(" + ", ".join(parts) + ")")
            else:
                specs.append(self.ident("choice-domain attribute"))
            if not self.at(","):
                return specs
            self.next()

    def init(self) -> Init:
        line = self.next().line
        self.expect("init")
        inst = self.ident("instance name")
        self.expect("=")
        comp = self.ident("comp name")
        return Init(inst, comp, self.targ_list(), line)

    def type_decl(self) -> TypeDecl:
        line = self.next().line
        self.expect("type")
        name = self.ident("type name")
        start = self.pos
        depth = 0
        # The rhs runs to end of line, continuing while brackets stay open,
        # a line ends mid-list ('|', '=', ','), or the next line opens with
        # a branch bar.
        while self.peek().kind != "eof":
            t = self.peek()
            if depth == 0 and t.line > self.toks[self.pos - 1].line and \
                    self.toks[self.pos - 1].text not in ("|", "=", ",") and \
                    t.text != "|":
                break
            depth += 1 if t.text in "([{" else -1 if t.text in ")]}" else 0
            self.next()
        rhs_toks = self.toks[start:self.pos]
        rhs = " ".join(t.text for t in rhs_toks)
        branches = [
            rhs_toks[i].text
            for i in range(len(rhs_toks) - 1)
            if rhs_toks[i].kind == "ident" and rhs_toks[i + 1].text == "{"
        ]
        return TypeDecl(name, rhs, branches, line)

    def functor(self) -> Functor:
        line = self.next().line
        self.expect("functor")
        name = self.ident("functor name")
        start = self.pos
        self.expect("(")
        depth = 1
        while depth:
            t = self.next()
            if t.kind == "eof":
                raise ParseError(line, f"unterminated functor {name}")
            depth += 1 if t.text == "(" else -1 if t.text == ")" else 0
        self.expect(":")
        ret = self.type_name()
        text = " ".join(t.text for t in self.toks[start:self.pos - 1]) + f": {ret}"
        if self.peek().text == "stateful":
            self.next()
            text += " stateful"
        return Functor(name, text, line)

    def clause(self) -> list[Rule]:
        """A clause's rules. A rule with several heads, `a(X), b(X) :-
        body.`, is one rule per head, each over the whole clause's span
        and body, as Souffle reads it."""
        if GRID_RE.match(self.peek().text) and self.at("(", 1):
            return [self.grid_fact()]
        head = self.atom()
        if self.at("."):
            end = self.next().line
            plan, end = self.plan(end)
            return [Rule(head, None, head.line, end, plan=plan)]
        if self.at("<="):
            self.next()
            dominant = self.atom()
            self.expect(":-")
            body = self.conj()
            end = self.expect(".").line
            plan, end = self.plan(end)
            return [Rule(head, [dominant, *body], head.line, end, sub=True,
                         plan=plan)]
        heads = [head]
        while self.at(","):
            self.next()
            heads.append(self.atom())
        self.expect(":-")
        body = self.conj()
        end = self.expect(".").line
        plan, end = self.plan(end)
        return [Rule(h, body, head.line, end, plan=plan) for h in heads]

    def grid_fact(self) -> Rule:
        """A GRID macro call. Its arguments are cell tokens, not terms, so
        the parser skips the list by paren depth and keeps the call's name
        alone. The runner expands the call before Souffle sees the file."""
        t = self.next()
        self.expect("(")
        depth = 1
        while depth:
            tok = self.next()
            if tok.kind == "eof":
                raise ParseError(t.line, f"unterminated {t.text}")
            depth += 1 if tok.text == "(" else -1 if tok.text == ")" else 0
        return Rule(Atom(None, t.text, (), t.line), None, t.line, t.line,
                    grid=True)

    def plan(self, end: int) -> tuple[list[tuple[int, tuple[int, ...]]] | None, int]:
        """A `.plan` directive following the rule's terminating period.

        Souffle writes it as `.plan v: (i, j, ...)`, one entry per version
        of the rule, and the order permutes the body's atom positions. The
        rule owns it, so it extends the rule's span.
        """
        if not (self.at(".") and self.at("plan", 1)):
            return None, end
        self.next()
        self.next()
        entries: list[tuple[int, tuple[int, ...]]] = []
        while True:
            entries.append((self.number("plan version"), self.plan_order()))
            if not self.at(","):
                return entries, self.toks[self.pos - 1].line
            self.next()

    def plan_order(self) -> tuple[int, ...]:
        self.expect(":")
        self.expect("(")
        order = [self.number("plan position")]
        while self.at(","):
            self.next()
            order.append(self.number("plan position"))
        self.expect(")")
        return tuple(order)

    def conj(self) -> list[Lit]:
        body: list[Lit] = [self.literal()]
        while self.at(","):
            self.next()
            body.append(self.literal())
        return body

    # body literals

    def _atom_ahead(self) -> bool:
        if self.peek().kind != "ident":
            return False
        k = 1
        while self.at(".", k) and self.peek(k + 1).kind == "ident":
            k += 2
        return self.at("(", k)

    def _op_ahead(self) -> bool:
        """Whether the next token continues an expression or a constraint."""
        t = self.peek()
        return t.text in CMP_OPS or t.text in ARITH_OPS or (
            t.kind == "ident" and t.text in WORD_OPS
        )

    def literal(self) -> Lit:
        if self.at("("):
            # A parenthesized body group; anything else backtracks into
            # the expression path below.
            if (disj := self.disjunction()) is not None:
                return disj
        if self.at("!"):
            self.next()
            return Neg(self.atom())
        if self.peek().kind == "ident" and self.peek().text in ("true", "false") \
                and not self.at("(", 1):
            return Bool(self.next().text == "true")
        if self._atom_ahead():
            # Atom-shaped; an intrinsic call in a constraint reads the same,
            # so decide by what follows the closing paren.
            mark = self.pos
            atom = self.atom()
            if self._op_ahead():
                self.pos = mark
            else:
                return atom
        lhs = self.expr()
        op = self.next()
        if op.text not in CMP_OPS:
            raise ParseError(op.line, f"expected comparison, got {op.text!r}")
        return Cmp(op.text, lhs, self.expr(), op.line)

    def disjunction(self) -> Disj | None:
        """A parenthesized body group, one branch per `;`.

        A single branch is a plain conjunction group, which reads the same
        as a parenthesized term, so it only counts as a group when no
        operator follows the closing paren.
        """
        mark = self.pos
        line = self.next().line  # '('
        try:
            branches = [self.conj()]
            while self.at(";"):
                self.next()
                branches.append(self.conj())
            self.expect(")")
        except ParseError:
            self.pos = mark
            return None
        if len(branches) < 2 and self._op_ahead():
            self.pos = mark
            return None
        return Disj(tuple(tuple(b) for b in branches), line)

    def atom(self) -> Atom:
        t = self.next()
        if t.kind != "ident":
            raise ParseError(t.line, f"expected atom, got {t.text!r}")
        parts = [t.text]
        while self.at(".") and self.peek(1).kind == "ident" and not self.at("("):
            self.next()
            parts.append(self.next().text)
        qual = ".".join(parts[:-1]) or None
        name = parts[-1]
        self.expect("(")
        args: list[Term] = []
        while not self.at(")"):
            args.append(self.expr())
            if not self.at(")"):
                self.expect(",")
        self.next()
        return Atom(qual, name, tuple(args), t.line)

    # terms

    def expr(self) -> Term:
        t = self.primary()
        while True:
            nxt = self.peek()
            if nxt.text in ARITH_OPS or (nxt.kind == "ident" and nxt.text in WORD_OPS):
                self.next()
                t = BinOp(nxt.text, t, self.primary())
            else:
                return t

    def primary(self) -> Term:
        t = self.next()
        if t.kind == "num":
            return Num(t.text)
        if t.kind == "str":
            return Str(t.text)
        if t.text == "-":
            return UnOp("-", self.primary())
        if t.text == "(":
            e = self.expr()
            self.expect(")")
            return e
        if t.text == "$":
            name = self.ident("constructor name")
            return Ctor(name, tuple(self.arg_list()) if self.at("(") else ())
        if t.text == "[":
            args: list[Term] = []
            while not self.at("]"):
                args.append(self.expr())
                if not self.at("]"):
                    self.expect(",")
            self.next()
            return Rec(tuple(args))
        if t.text == "@":
            return Call(self.ident("functor name"), tuple(self.arg_list()), True)
        if t.kind == "ident":
            if t.text == "_":
                return Wild()
            if t.text in AGG_OPS and not self.at("("):
                return self.aggregate(t)
            if self.at("("):
                return Call(t.text, tuple(self.arg_list()), False)
            if MACRO_CONST_RE.match(t.text):
                return MacroConst(t.text)
            return Var(t.text)
        raise ParseError(t.line, f"unexpected token {t.text!r} in term")

    def aggregate(self, t: Token) -> Agg:
        expr = None
        if not self.at(":"):
            expr = self.expr()
        self.expect(":")
        self.expect("{")
        body = self.conj()
        self.expect("}")
        return Agg(t.text, expr, tuple(body))

    # helpers

    def ident(self, what: str) -> str:
        t = self.next()
        if t.kind != "ident":
            raise ParseError(t.line, f"expected {what}, got {t.text!r}")
        return t.text

    def number(self, what: str) -> int:
        t = self.next()
        if t.kind != "num":
            raise ParseError(t.line, f"expected {what}, got {t.text!r}")
        return int(t.text)

    def type_name(self) -> str:
        return self.ident("type name")

    def targ_list(self) -> list[str]:
        if not self.at("<"):
            return []
        self.next()
        args = [self.type_name()]
        while self.at(","):
            self.next()
            args.append(self.type_name())
        self.expect(">")
        return args

    def arg_list(self) -> list[Term]:
        self.expect("(")
        args: list[Term] = []
        while not self.at(")"):
            args.append(self.expr())
            if not self.at(")"):
                self.expect(",")
        self.next()
        return args


# How many parsed programs `parse` keeps. One audit parses the same few
# hundred texts again and again: a solver, its deletion variants, and the
# proposers file on every probe.
PARSE_MEMO_SIZE = 256


@lru_cache(maxsize=PARSE_MEMO_SIZE)
def parse(source: str) -> Program:
    """The program `source` holds. The same text gives the same object, so
    a caller reads the tree and does not change it."""
    tokens, comments = _lex(source)
    return Program(_Parser(tokens).program(), comments)


# --- reference index ---

TOP = ""        # scope of top-level items
EXTERN = "!ext"  # scope of relations the file does not declare (lib)

type RelKey = tuple[str, str]  # (scope, name)


@dataclass(frozen=True)
class Ref:
    scope: str            # comp the referring rule sits in, TOP for program code
    key: RelKey           # resolved relation
    role: str             # 'head' | 'pos' | 'neg' | 'agg'
    rule: int             # index into Index.rules
    line: int
    atom: Atom


@dataclass
class RuleInfo:
    scope: str
    rule: Rule
    section: str | None   # enclosing `// --- <name> ---` section, top level only


SECTION_RE = re.compile(r"//\s*---\s*(.+?)\s*---")


def marker_names(name: str) -> list[str]:
    """The names a section marker holds, one per case it marks.

    A marker names its cases between commas. A comma inside parentheses
    belongs to a constructor application, so the split leaves it alone.
    Trailing prose after a colon is not a name and drops out.
    """
    head = name.split(":", 1)[0]
    out: list[str] = []
    depth = 0
    cur = ""
    for ch in head:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
        if ch == "," and depth == 0:
            out.append(cur)
            cur = ""
        else:
            cur += ch
    out.append(cur)
    return [s.strip() for s in out if s.strip()]


def marker_cases(name: str) -> list[str]:
    """The cases a section marker marks: each name it holds, with the
    fields a constructor application fixes dropped. `Derive(g=Iso)` marks
    the `Derive` case."""
    return [s.split("(", 1)[0].strip() for s in marker_names(name)]


class Index:
    """Symbols and references of one parsed program.

    `decls[scope][name]` holds each declaration; scope is TOP or a comp
    name. `refs_of(key)` returns every reference to a relation, heads
    included, each under the role `Ref` records for it.
    """

    def __init__(self, program: Program):
        self.program = program
        self.bases: dict[str, str] = {}
        self.decls: dict[str, dict[str, Decl]] = {TOP: {}}
        self.inits: dict[str, dict[str, Init]] = {TOP: {}}
        self.rules: list[RuleInfo] = []
        self.refs: list[Ref] = []
        # A marker inside a comp names no top-level section, and the
        # attribution below is top-level only.
        spans = [(it.line, it.end_line)
                 for it in program.items if isinstance(it, Comp)]
        self.sections: list[tuple[int, str]] = [
            (c.line, m.group(1))
            for c in program.comments
            if c.own_line and (m := SECTION_RE.match(c.text))
            and not any(a <= c.line <= b for a, b in spans)
        ]
        self._collect(program.items, TOP)
        for idx, info in enumerate(self.rules):
            self._index_rule(idx, info)
        self._by_key: dict[RelKey, list[Ref]] = {}
        for ref in self.refs:
            self._by_key.setdefault(ref.key, []).append(ref)

    def _collect(self, items: list[Item], scope: str) -> None:
        self.decls.setdefault(scope, {})
        self.inits.setdefault(scope, {})
        for it in items:
            if isinstance(it, Decl):
                self.decls[scope][it.name] = it
            elif isinstance(it, Init):
                self.inits[scope][it.inst] = it
            elif isinstance(it, Comp):
                # A comp is one scope wherever it is declared, so a nested
                # one indexes under its own name and its instance inside
                # the enclosing comp resolves through that scope.
                if it.base:
                    self.bases[it.name] = it.base
                self._collect(it.items, it.name)
            elif isinstance(it, Rule):
                self.rules.append(RuleInfo(scope, it, self._section(it.line, scope)))
            elif isinstance(it, Rigid):
                # The block indexes as its placed forms; the chart and its
                # facts stay opaque, as GRID cell values do.
                for sub in it.items:
                    if isinstance(sub, Decl):
                        placed = Decl(
                            f"{it.name}_{sub.name}",
                            [Field("d4", "D4"), *sub.fields],
                            [], sub.line, sub.end_line,
                        )
                        self.decls[scope][placed.name] = placed

    def _section(self, line: int, scope: str) -> str | None:
        if scope != TOP:
            return None
        name = None
        for at, s in self.sections:
            if at <= line:
                name = s
        return name

    def section_at(self, line: int) -> str | None:
        """The `// --- <name> ---` section a top-level line falls in."""
        return self._section(line, TOP)

    def chain(self, scope: str) -> list[str]:
        """The scope and its base comps, derived first."""
        out: list[str] = []
        cur: str | None = scope
        while cur is not None and cur not in out:
            out.append(cur)
            cur = self.bases.get(cur)
        return out

    def resolve(self, scope: str, qual: str | None, name: str) -> RelKey:
        if qual is None:
            for s in (*self.chain(scope), TOP):
                if name in self.decls.get(s, {}):
                    return (s, name)
            return (EXTERN, name)
        for hop in qual.split("."):
            init = next(
                (i for s in (*self.chain(scope), TOP)
                 if (i := self.inits.get(s, {}).get(hop))),
                None,
            )
            if init is None or init.comp not in self.decls:
                return (EXTERN, f"{qual}.{name}")
            scope = init.comp
        for s in self.chain(scope):
            if name in self.decls.get(s, {}):
                return (s, name)
        return (EXTERN, f"{qual}.{name}")

    def instance_of(self, scope: str, qual: str | None) -> tuple[str, str] | None:
        """The lib instance an atom's qualifier lands on, as (instance,
        comp). A hop naming a comp the file declares is followed into that
        comp; the first hop naming a comp it does not declare is a lib
        instance, and the relations of such an instance are opaque. None
        when the qualifier is absent or names no instance at all.
        """
        for hop in (qual or "").split("."):
            init = next(
                (i for s in (*self.chain(scope), TOP)
                 if (i := self.inits.get(s, {}).get(hop))),
                None,
            )
            if init is None:
                return None
            if init.comp not in self.decls:
                return (hop, init.comp)
            scope = init.comp
        return None

    def _index_rule(self, idx: int, info: RuleInfo) -> None:
        def add(atom: Atom, role: str) -> None:
            key = self.resolve(info.scope, atom.qual, atom.name)
            self.refs.append(Ref(info.scope, key, role, idx, atom.line, atom))

        def walk(lit: Lit) -> None:
            if isinstance(lit, Atom):
                add(lit, "pos")
                for agg in _aggs_in_terms(lit.args):
                    for sub in agg.body:
                        _add_agg(sub, add)
            elif isinstance(lit, Neg):
                add(lit.atom, "neg")
            elif isinstance(lit, Cmp):
                for agg in _aggs_in_terms((lit.lhs, lit.rhs)):
                    for sub in agg.body:
                        _add_agg(sub, add)
            elif isinstance(lit, Disj):
                for branch in lit.branches:
                    for sub in branch:
                        walk(sub)

        add(info.rule.head, "head")
        for lit in info.rule.body or ():
            walk(lit)

    def refs_of(self, key: RelKey) -> list[Ref]:
        return self._by_key.get(key, [])

    def rules_of(self, key: RelKey) -> list[tuple[int, RuleInfo]]:
        return [
            (r.rule, self.rules[r.rule])
            for r in self.refs_of(key)
            if r.role == "head"
        ]


def _add_agg(lit: Lit, add: Callable[[Atom, str], None]) -> None:
    if isinstance(lit, Atom):
        add(lit, "agg")
    elif isinstance(lit, Neg):
        add(lit.atom, "neg")
    elif isinstance(lit, Disj):
        for branch in lit.branches:
            for sub in branch:
                _add_agg(sub, add)


def _aggs_in_terms(terms: Iterable[Term]) -> list[Agg]:
    out: list[Agg] = []
    stack: list[Term] = list(terms)
    while stack:
        t = stack.pop()
        if isinstance(t, Agg):
            out.append(t)
        elif isinstance(t, (Ctor, Rec, Call)):
            stack.extend(t.args)
        elif isinstance(t, BinOp):
            stack.extend((t.lhs, t.rhs))
        elif isinstance(t, UnOp):
            stack.append(t.arg)
    return out


def body_literals(rule: Rule, into_aggs: bool = True) -> Iterator[Lit]:
    """The rule's body literals, `Disj` branches expanded in place.

    With `into_aggs`, the literals of each aggregate body follow the
    literal that holds the aggregate. `Neg` comes as-is; the caller
    unwraps it.
    """
    def walk(lits: Iterable[Lit]) -> Iterator[Lit]:
        for lit in lits:
            if isinstance(lit, Disj):
                for branch in lit.branches:
                    yield from walk(branch)
                continue
            yield lit
            if not into_aggs:
                continue
            if isinstance(lit, Atom):
                aggs = _aggs_in_terms(lit.args)
            elif isinstance(lit, Cmp):
                aggs = _aggs_in_terms((lit.lhs, lit.rhs))
            else:
                continue
            for agg in aggs:
                yield from walk(agg.body)

    yield from walk(rule.body or ())


def term_vars(term: Term) -> set[str]:
    """Variable names a term mentions."""
    out: set[str] = set()
    stack: list[Term] = [term]
    while stack:
        t = stack.pop()
        if isinstance(t, Var):
            out.add(t.name)
        elif isinstance(t, (Ctor, Rec, Call)):
            stack.extend(t.args)
        elif isinstance(t, BinOp):
            stack.extend((t.lhs, t.rhs))
        elif isinstance(t, UnOp):
            stack.append(t.arg)
        elif isinstance(t, Agg):
            if t.expr is not None:
                stack.append(t.expr)
            for lit in t.body:
                out |= literal_vars(lit)
    return out


def literal_vars(lit: Lit) -> set[str]:
    if isinstance(lit, Atom):
        out: set[str] = set()
        for a in lit.args:
            out |= term_vars(a)
        return out
    if isinstance(lit, Neg):
        return literal_vars(lit.atom)
    if isinstance(lit, Cmp):
        return term_vars(lit.lhs) | term_vars(lit.rhs)
    if isinstance(lit, Disj):
        out = set()
        for branch in lit.branches:
            for sub in branch:
                out |= literal_vars(sub)
        return out
    return set()  # Bool


def rule_vars(rule: Rule) -> set[str]:
    out = literal_vars(rule.head)
    for lit in rule.body or ():
        out |= literal_vars(lit)
    return out
