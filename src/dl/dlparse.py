"""Parse solver .dl source into an AST, plus a reference index over it.

The grammar covers the dialect the solvers and lib.dl use: `#include`,
`#define`, `.functor`, `.type`, single-level `.comp`, `.init`, `.decl`
(with `inline` and same-line facts), facts, rules with negation,
aggregates, and parenthesized disjunctions, constructors, records,
functor calls, and GRID macro facts (which take no terminating period). Anything outside that raises
`ParseError` — Souffle itself owns the real semantics, so the parser can
be strict and fail loudly.

Comments are kept on the program (`Program.comments`) with position and
own-line flags, so renderers can reattach them.

`Index` resolves every atom to the relation it names — through comp
instantiations, negation, and aggregate bodies — and records the role of
each reference. It is the shared layer the lints query.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass

AGG_OPS = {"count", "sum", "max", "min", "mean"}
WORD_OPS = {"band", "bor", "bxor", "bshl", "bshr", "land", "lor", "lxor"}
ARITH_OPS = {"+", "-", "*", "/", "%", "^"}
CMP_OPS = {"=", "!=", "<", "<=", ">", ">="}
DECL_QUALIFIERS = {"inline", "btree", "brie", "eqrel", "override", "overridable"}
GRID_RE = re.compile(r"GRID_(MASK_|SPARSE_)?\d+x\d+$")
MACRO_CONST_RE = re.compile(r"[A-Z][A-Z0-9]*_[A-Z0-9_]*$")


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


PUNCT2 = (":-", "<=", ">=", "!=", "<:", "<", ">", "=", "!", "(", ")", "[", "]",
          "{", "}", ",", ".", ":", ";", "$", "@", "|", "+", "-", "*", "/", "%", "^")
IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
NUM_RE = re.compile(r"\d+")


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
            bump(c)
            i += 1
            continue
        if source.startswith("//", i):
            j = source.find("\n", i)
            j = n if j < 0 else j
            text = source[i:j]
            comments.append(Comment(line, col, text, _own_line(source, i)))
            bump(text)
            i = j
            continue
        if source.startswith("/*", i):
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
        if m := NUM_RE.match(source, i):
            tokens.append(Token("num", m.group(0), line, col))
            bump(m.group(0))
            i = m.end()
            continue
        if m := IDENT_RE.match(source, i):
            tokens.append(Token("ident", m.group(0), line, col))
            bump(m.group(0))
            i = m.end()
            continue
        for p in PUNCT2:
            if source.startswith(p, i):
                tokens.append(Token("punct", p, line, col))
                bump(p)
                i += len(p)
                break
        else:
            raise ParseError(line, f"unexpected character {c!r}")
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


@dataclass
class Comp:
    name: str
    params: list[str]
    items: list[Item]
    line: int
    end_line: int


@dataclass
class Program:
    items: list[Item]
    comments: list[Comment]

    def comps(self) -> dict[str, Comp]:
        return {it.name: it for it in self.items if isinstance(it, Comp)}


type Term = Var | Wild | Num | Str | MacroConst | Ctor | Rec | Call | UnOp | BinOp | Agg
type Lit = Atom | Neg | Cmp | Bool | Disj
type Item = Include | Define | Functor | TypeDecl | Decl | Init | Rule | Comp


# --- parser ---

class _Parser:
    def __init__(self, tokens: list[Token]):
        self.toks = tokens
        self.pos = 0

    def peek(self, k: int = 0) -> Token:
        return self.toks[min(self.pos + k, len(self.toks) - 1)]

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
            items.append(self.item(top=True))
        return items

    def item(self, top: bool) -> Item:
        t = self.peek()
        if t.kind == "hash":
            return self.hash_directive()
        if t.text == ".":
            word = self.peek(1).text
            if word == "comp" and top:
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
        return self.clause()

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
        self.expect("{")
        items: list[Item] = []
        while not self.at("}"):
            if self.peek().kind == "eof":
                raise ParseError(line, f"unterminated comp {name}")
            items.append(self.item(top=False))
        end = self.next().line  # '}'
        return Comp(name, params, items, line, end)

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
        return Decl(name, fields, quals, line, self.toks[self.pos - 1].line)

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
        # The rhs runs to end of line, continuing while brackets stay open or
        # a line ends mid-list ('|', '=', ',').
        while self.peek().kind != "eof":
            t = self.peek()
            if depth == 0 and t.line > self.toks[self.pos - 1].line and \
                    self.toks[self.pos - 1].text not in ("|", "=", ","):
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
        return Functor(name, text, line)

    def clause(self) -> Rule:
        head = self.atom()
        if GRID_RE.match(head.name):
            return Rule(head, None, head.line, head.line, grid=True)
        if self.at("."):
            end = self.next().line
            return Rule(head, None, head.line, end)
        self.expect(":-")
        body = self.conj()
        end = self.expect(".").line
        return Rule(head, body, head.line, end)

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

    def literal(self) -> Lit:
        if self.at("("):
            # A parenthesized `;`-list is a disjunction; anything else
            # backtracks into the expression path below.
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
            if self.peek().text in CMP_OPS or self.peek().text in ARITH_OPS \
                    or self.peek().text in WORD_OPS:
                self.pos = mark
            else:
                return atom
        lhs = self.expr()
        op = self.next()
        if op.text not in CMP_OPS:
            raise ParseError(op.line, f"expected comparison, got {op.text!r}")
        return Cmp(op.text, lhs, self.expr(), op.line)

    def disjunction(self) -> Disj | None:
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
        if len(branches) < 2:
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


def parse(source: str) -> Program:
    tokens, comments = _lex(source)
    return Program(_Parser(tokens).program(), comments)


# --- reference index ---

TOP = ""        # scope of top-level items
EXTERN = "!ext"  # scope of relations the file does not declare (lib)

type RelKey = tuple[str, str]  # (scope, name)


@dataclass(frozen=True)
class Ref:
    scope: str            # comp the referring rule sits in, TOP for body code
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


class Index:
    """Symbols and references of one parsed program.

    `decls[scope][name]` holds each declaration; scope is TOP or a comp
    name. `refs_of(key)` returns every reference to a relation, heads
    included; aggregate-body atoms carry role 'agg', negated ones 'neg'.
    """

    def __init__(self, program: Program):
        self.program = program
        self.decls: dict[str, dict[str, Decl]] = {TOP: {}}
        self.inits: dict[str, dict[str, Init]] = {TOP: {}}
        self.rules: list[RuleInfo] = []
        self.refs: list[Ref] = []
        self.sections: list[tuple[int, str]] = [
            (c.line, m.group(1))
            for c in program.comments
            if c.own_line and (m := SECTION_RE.match(c.text))
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
                self._collect(it.items, it.name)
            elif isinstance(it, Rule):
                self.rules.append(RuleInfo(scope, it, self._section(it.line, scope)))

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

    def resolve(self, scope: str, qual: str | None, name: str) -> RelKey:
        if qual is None:
            for s in (scope, TOP):
                if name in self.decls.get(s, {}):
                    return (s, name)
            return (EXTERN, name)
        for hop in qual.split("."):
            init = self.inits.get(scope, {}).get(hop) or self.inits[TOP].get(hop)
            if init is None or init.comp not in self.decls:
                return (EXTERN, f"{qual}.{name}")
            scope = init.comp
        if name in self.decls[scope]:
            return (scope, name)
        return (EXTERN, f"{qual}.{name}")

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
