"""Flag patterns the simplify pass usually rewrites.

Each rule mirrors an edit family from the simplify corpus: relations that
restate another relation, references reachable only through negation,
dead declarations, mergeable Choice-tagged rules, and so on. Findings are
diagnostics only — the rewrite stays with the author.

The decidable set is on by default. The advisory set — patterns with real
counterexamples in the corpus, worth a look rather than a rewrite — is
behind the `advisory` flag.

Relation-level rules run over the scopes that hold body code: top level,
`Fit`, `Parse`, and `Consts`. Other `.comp` interiors are lib-shaped code
and stay out, matching `lint.py`.

The public entry point is `lint_simplify`; findings share `lint_body`'s
tuple shape.
"""

from __future__ import annotations

import re
from collections.abc import Iterator

from dl.dlparse import (
    EXTERN,
    TOP,
    Agg,
    Atom,
    BinOp,
    Bool,
    Call,
    Cmp,
    Ctor,
    Decl,
    Index,
    Lit,
    MacroConst,
    Neg,
    Num,
    ParseError,
    Rec,
    Ref,
    RelKey,
    Rule,
    RuleInfo,
    Str,
    Term,
    UnOp,
    Var,
    Wild,
    literal_vars,
    parse,
    term_vars,
)

LINE_LIMIT = 100   # code only; a trailing comment does not count
BODY_SCOPES = (TOP, "Fit", "Parse", "Consts")
COMMON_SUBEXPR_MIN = 3   # literals a shared window must span

type Finding = tuple[str, int, str, str]


def lint_simplify(source: str, advisory: bool = False) -> list[Finding]:
    lines = source.splitlines()

    def raw(lineno: int) -> str:
        return lines[lineno - 1].rstrip() if 0 < lineno <= len(lines) else ""

    try:
        program = parse(source)
    except ParseError as e:
        return [("parse-error", e.line, e.msg, raw(e.line))]

    ix = Index(program)
    lint = _Lint(ix, lines)
    findings = lint.run(advisory)
    findings.sort(key=lambda f: (f[1], f[0]))
    return [(cat, ln, match, raw(ln)) for cat, ln, match, _ in findings]


class _Lint:
    def __init__(self, ix: Index, lines: list[str]):
        self.ix = ix
        self.lines = lines
        self.findings: list[Finding] = []
        self.claimed: set[RelKey] = set()  # relations an earlier rule flagged

    def add(self, cat: str, line: int, match: str) -> None:
        self.findings.append((cat, line, match, ""))

    def claim(self, cat: str, key: RelKey, line: int, match: str) -> None:
        self.claimed.add(key)
        self.add(cat, line, match)

    def run(self, advisory: bool) -> list[Finding]:
        # Relation-level rules, strongest claim first.
        self.dead_relations()
        for key in self.body_keys():
            if key not in self.claimed:
                self.alias_inline(key)
        for key in self.body_keys():
            if key not in self.claimed:
                self.negated_use(key)
        # Rule-level and lexical rules.
        for idx, info in self.body_rules():
            self.choice_tag(idx, info)
            self.subsumed_atoms(info)
            self.named_complement(info)
            self.long_rule(info)
        self.decl_placement()
        if advisory:
            for key in self.body_keys():
                if key not in self.claimed:
                    self.pass_through(key)
            for key in self.body_keys():
                if key not in self.claimed:
                    self.chain_join(key)
            for key in self.body_keys():
                if key not in self.claimed:
                    self.single_consumer(key)
            for idx, info in self.body_rules():
                self.domain_enumerator(info)
                self.argmax(idx, info)
            self.common_subexpr()
            self.single_init_comps()
        return self.findings

    # --- shared views ---

    def body_keys(self) -> list[RelKey]:
        return [
            (scope, name)
            for scope in BODY_SCOPES
            for name in self.ix.decls.get(scope, {})
        ]

    def body_rules(self) -> list[tuple[int, RuleInfo]]:
        return [
            (i, info)
            for i, info in enumerate(self.ix.rules)
            if info.scope in BODY_SCOPES and not info.rule.grid
        ]

    def decl_of(self, key: RelKey) -> Decl:
        return self.ix.decls[key[0]][key[1]]

    def defs(self, key: RelKey) -> list[Rule]:
        """Rules and facts whose head is `key`."""
        return [
            self.ix.rules[r.rule].rule
            for r in self.ix.refs_of(key)
            if r.role == "head"
        ]

    def uses(self, key: RelKey) -> list[Ref]:
        """References outside `key`'s own heads."""
        return [r for r in self.ix.refs_of(key) if r.role != "head"]

    def recursive(self, key: RelKey) -> bool:
        return any(self.rule_head_key(u.rule) == key for u in self.uses(key))

    def fitted_slots(self) -> set[str]:
        fit = self.ix.decls.get("Fit", {})
        consts = self.ix.decls.get("Consts", {})
        return set(fit) & set(consts)

    def inlinable(self, key: RelKey) -> bool:
        """Whether substituting `key` away is even on the table: a derived,
        non-interface relation whose rules and uses share its scope.

        Consts relations are data; `out` and fitted slots are read outside
        the file; a fact-only relation has no body to substitute; and a
        rule or use in another scope puts a comp boundary in the way.
        """
        scope, name = key
        if scope == "Consts" or key == (TOP, "out"):
            return False
        if scope in ("Fit", "Consts") and name in self.fitted_slots():
            return False
        defs = self.defs(key)
        if not any(d.body is not None for d in defs):
            return False
        return all(
            self.ix.rules[r.rule].scope == scope for r in self.ix.refs_of(key)
        )

    # --- decidable rules ---

    def dead_relations(self) -> None:
        """Zero references anywhere, to a fixpoint: removing a dead
        relation's rules can orphan the relations those rules read."""
        exempt = {(TOP, "out")}
        exempt |= {("Fit", n) for n in self.fitted_slots()}
        exempt |= {("Consts", n) for n in self.fitted_slots()}
        dead: set[RelKey] = set()
        changed = True
        while changed:
            changed = False
            for key in self.body_keys():
                if key in dead or key in exempt:
                    continue
                live_uses = [
                    u for u in self.uses(key)
                    if self.rule_head_key(u.rule) not in dead
                ]
                if not live_uses:
                    dead.add(key)
                    changed = True
        for key in sorted(dead, key=lambda k: self.decl_of(k).line):
            self.claim("dead", key, self.decl_of(key).line, key[1])

    def rule_head_key(self, rule_idx: int) -> RelKey:
        info = self.ix.rules[rule_idx]
        return self.ix.resolve(info.scope, info.rule.head.qual, info.rule.head.name)

    def alias_inline(self, key: RelKey) -> None:
        """A pure rename: one rule, one positive atom, every column carried
        through. A projection that drops or wildcards columns is a named
        predicate and stays."""
        if not self.inlinable(key):
            return
        defs = self.defs(key)
        if len(defs) != 1 or defs[0].body is None or len(defs[0].body) != 1:
            return
        atom = defs[0].body[0]
        if not isinstance(atom, Atom) or atom.qual is not None:
            return
        head_vars = [a.name for a in defs[0].head.args if isinstance(a, Var)]
        atom_vars = [a.name for a in atom.args if isinstance(a, Var)]
        if len(head_vars) != len(defs[0].head.args) or \
                len(atom_vars) != len(atom.args):
            return
        if len(set(head_vars)) != len(head_vars) or \
                set(head_vars) != set(atom_vars):
            return
        self.claim("alias-inline", key, self.decl_of(key).line,
                   f"{key[1]} = {_atom_str(atom)}")

    def negated_use(self, key: RelKey) -> None:
        """Referenced only under negation, every rule a single-atom body."""
        if not self.inlinable(key):
            return
        uses = self.uses(key)
        if not uses or any(u.role != "neg" for u in uses):
            return
        defs = self.defs(key)
        if not defs or any(not self._projection(d) for d in defs):
            return
        self.claim("negated-use", key, self.decl_of(key).line,
                   self._neg_rewrite(key, defs))

    def _neg_rewrite(self, key: RelKey, defs: list[Rule]) -> str:
        """The negation, then its inlined form: each def's body atom with
        the head variables carried through and the dropped columns
        wildcarded. The first def's head names are the canonical ones."""
        canon = [_term_str(a) for a in defs[0].head.args]
        parts = []
        for d in defs:
            names = {
                a.name: canon[i]
                for i, a in enumerate(d.head.args) if isinstance(a, Var)
            }
            atom = d.body[0]
            assert isinstance(atom, Atom)
            parts.append(f"!{_atom_str(atom, names)}")
        return f"!{key[1]}({', '.join(canon)}) ⇒ {', '.join(parts)}"

    def _projection(self, d: Rule) -> bool:
        """The rule projects a single positive atom: negating the head is
        negating the atom with the dropped columns wildcarded. A dropped
        variable used twice constrains the atom, so it blocks the rewrite."""
        if d.body is None or len(d.body) != 1 or not isinstance(d.body[0], Atom):
            return False
        counts: dict[str, int] = {}
        for arg in d.body[0].args:
            for v in term_vars(arg):
                counts[v] = counts.get(v, 0) + 1
        head_ok = all(
            isinstance(a, Var) and a.name in counts for a in d.head.args
        )
        head_vars = {a.name for a in d.head.args if isinstance(a, Var)}
        return head_ok and all(
            n == 1 for v, n in counts.items() if v not in head_vars
        )

    def pass_through(self, key: RelKey) -> None:
        """Advisory: consumed only by pure forwarding rules of one relation.
        The corpus keeps this shape as a named union member; flag it for
        the call."""
        if not self.inlinable(key):
            return
        uses = self.uses(key)
        ext = [u for u in uses if self.rule_head_key(u.rule) != key]
        if not ext or any(u.role != "pos" for u in ext):
            return
        heads = {self.rule_head_key(u.rule) for u in ext}
        if len(heads) != 1:
            return
        consumer = heads.pop()
        if consumer == key or consumer[0] in (EXTERN, "Consts") \
                or consumer == (TOP, "out"):
            return
        for u in ext:
            rule = self.ix.rules[u.rule].rule
            if rule.body is None or len(rule.body) != 1:
                return
            head_vars = [a.name for a in rule.head.args if isinstance(a, Var)]
            if {a.name for a in u.atom.args if isinstance(a, Var)} \
                    - set(head_vars):
                return  # drops a column: a named projection, not a forward
        self.claim("pass-through", key, self.decl_of(key).line,
                   f"{key[1]} only feeds {consumer[1]}")

    def single_consumer(self, key: RelKey) -> None:
        """Advisory: one rule, one positive use, a two-literal body. The
        corpus both inlines and keeps this shape — the name's value is the
        call."""
        if not self.inlinable(key):
            return
        defs = self.defs(key)
        if len(defs) != 1 or defs[0].body is None or self.recursive(key):
            return
        body = defs[0].body
        if len(body) > 2 or not any(isinstance(lit, Atom) for lit in body):
            return
        uses = self.uses(key)
        if len(uses) != 1 or uses[0].role not in ("pos", "agg"):
            return
        self.claim("single-consumer", key, self.decl_of(key).line,
                   f"{key[1]}: one rule, one use")

    def chain_join(self, key: RelKey) -> None:
        """A column that, at every use, only keys a join against one other
        relation: fuse and project the column out. Restricted to plumbing —
        every rule of the relation a single-atom body — so named stages
        stay."""
        if key[0] != TOP or not self.inlinable(key):
            return
        if any(
            d.body is None or len(d.body) != 1 or not isinstance(d.body[0], Atom)
            for d in self.defs(key)
        ):
            return
        decl = self.decl_of(key)
        uses = self.uses(key)
        if not uses or any(u.role != "pos" for u in uses):
            return
        for col in range(len(decl.fields)):
            partners: set[tuple[RelKey, int]] = set()
            ok = True
            for u in uses:
                partner = self._join_partner(u, col)
                if partner is None:
                    ok = False
                    break
                partners.add(partner)
            if ok and len(partners) == 1:
                q, _ = partners.pop()
                self.claim(
                    "chain-join", key, decl.line,
                    f"{key[1]}.{decl.fields[col].name} only joins {q[1]}",
                )
                return

    def _join_partner(self, use: Ref, col: int) -> tuple[RelKey, int] | None:
        """The (relation, column) the key var at `col` of this use joins,
        when the var appears exactly there and nowhere else."""
        atom = use.atom
        if col >= len(atom.args):
            return None
        key_arg = atom.args[col]
        if not isinstance(key_arg, Var):
            return None
        v = key_arg.name
        rule = self.ix.rules[use.rule].rule
        if rule.body is None or v in literal_vars(rule.head):
            return None
        if sum(1 for a in atom.args if v in term_vars(a)) != 1:
            return None
        partner: tuple[RelKey, int] | None = None
        for lit in rule.body:
            if isinstance(lit, Atom) and lit is not atom:
                hits = [i for i, a in enumerate(lit.args) if v in term_vars(a)]
                if len(hits) > 1 or (hits and partner is not None):
                    return None
                if hits:
                    if not isinstance(lit.args[hits[0]], Var):
                        return None
                    pkey = self.ix.resolve(use.scope, lit.qual, lit.name)
                    partner = (pkey, hits[0])
            elif lit is not atom and v in literal_vars(lit):
                return None
        return partner

    def choice_tag(self, idx: int, info: RuleInfo) -> None:
        """Rules identical but for a distinct nullary constructor in one
        head argument: merge on a Choice variable."""
        rule = info.rule
        if rule.body is None:
            return
        for jdx, other in self.body_rules():
            if jdx >= idx:
                break
            o = other.rule
            if o.body is None or other.scope != info.scope \
                    or other.section != info.section:
                continue
            if (o.head.qual, o.head.name) != (rule.head.qual, rule.head.name):
                continue
            if len(o.head.args) != len(rule.head.args):
                continue
            if [_lit_str(x) for x in o.body] != [_lit_str(x) for x in rule.body]:
                continue
            diff = [
                i for i, (a, b) in
                enumerate(zip(rule.head.args, o.head.args, strict=True))
                if _term_str(a) != _term_str(b)
            ]
            tags = [r.head.args[diff[0]] for r in (rule, o)] if len(diff) == 1 \
                else []
            if tags and all(isinstance(t, Ctor) and not t.args for t in tags):
                self.add(
                    "choice-tag", rule.line,
                    f"{rule.head.name}: same body under {_term_str(tags[1])} "
                    f"and {_term_str(tags[0])} — one rule ranging over the tags",
                )
                return

    def subsumed_atoms(self, info: RuleInfo) -> None:
        """R(X, _) next to R(X, Y) in one body: the wildcard atom adds
        nothing."""
        for body in _conjunctions(info.rule):
            atoms = [lit for lit in body if isinstance(lit, Atom)]
            for i, a in enumerate(atoms):
                for j, b in enumerate(atoms):
                    if i == j or (a.qual, a.name) != (b.qual, b.name):
                        continue
                    if len(a.args) != len(b.args):
                        continue
                    pairs = list(zip(a.args, b.args, strict=True))
                    if all(_term_str(x) == _term_str(y) for x, y in pairs):
                        if i < j:
                            self.add("subsumed-atom", b.line,
                                     f"duplicate {_atom_str(b)}")
                    elif all(
                        isinstance(x, Wild) or _term_str(x) == _term_str(y)
                        for x, y in pairs
                    ):
                        self.add("subsumed-atom", a.line,
                                 f"{_atom_str(a)} subsumed by {_atom_str(b)}")

    def named_complement(self, info: RuleInfo) -> None:
        """`R(V), X != V` against a singleton fact: `!R(X)` says it
        directly."""
        rule = info.rule
        if rule.body is None:
            return
        for atom in rule.body:
            if not isinstance(atom, Atom) or len(atom.args) != 1:
                continue
            if not isinstance(atom.args[0], Var):
                continue
            key = self.ix.resolve(info.scope, atom.qual, atom.name)
            if key[0] == EXTERN:
                continue
            defs = self.defs(key)
            if len(defs) != 1 or defs[0].body is not None:
                continue
            v = atom.args[0].name
            others = [
                lit for lit in rule.body
                if lit is not atom and v in literal_vars(lit)
            ]
            if v in literal_vars(rule.head) or len(others) != 1:
                continue
            cmp = others[0]
            if not (isinstance(cmp, Cmp) and cmp.op == "!="):
                continue
            if isinstance(cmp.lhs, Var) and cmp.lhs.name == v:
                other = cmp.rhs
            elif isinstance(cmp.rhs, Var) and cmp.rhs.name == v:
                other = cmp.lhs
            else:
                continue
            bound: set[str] = set()
            for lit in rule.body:
                if isinstance(lit, Atom) and lit is not atom:
                    bound |= literal_vars(lit)
            if term_vars(other) - bound:
                continue  # the negation would leave the value unbound
            qual = f"{atom.qual}." if atom.qual else ""
            self.add(
                "named-complement", atom.line,
                f"{_atom_str(atom)}, {_lit_str(cmp)} ⇒ "
                f"!{qual}{atom.name}({_term_str(other)})",
            )

    def decl_placement(self) -> None:
        """Every reference inside one section or comp the declaration is
        not in: move the declaration there."""
        for name, decl in self.ix.decls[TOP].items():
            key = (TOP, name)
            spots: set[str | None] = set()
            for r in self.ix.refs_of(key):
                info = self.ix.rules[r.rule]
                spots.add(info.scope if info.scope != TOP else info.section)
            if len(spots) != 1:
                continue
            spot = spots.pop()
            if spot is None or spot == self.ix.section_at(decl.line):
                continue
            self.add("decl-placement", decl.line, f"{name}: all uses in {spot}")

    def long_rule(self, info: RuleInfo) -> None:
        rule = info.rule
        if rule.body is None or rule.line != rule.end_line:
            return
        text = self.lines[rule.line - 1] if rule.line <= len(self.lines) else ""
        code = text.split("//")[0].rstrip()
        if len(code) > LINE_LIMIT:
            self.add("long-rule", rule.line, f"{len(code)} chars")

    # --- advisory rules ---

    def domain_enumerator(self, info: RuleInfo) -> None:
        """An `*_elem` atom whose variable another positive atom already
        binds."""
        rule = info.rule
        if rule.body is None:
            return
        pos = [lit for lit in rule.body if isinstance(lit, Atom)]
        for atom in pos:
            if not atom.name.endswith("_elem") or len(atom.args) != 1:
                continue
            if not isinstance(atom.args[0], Var):
                continue
            v = atom.args[0].name
            binder = next(
                (o for o in pos
                 if o is not atom and not o.name.endswith("_elem")
                 and v in literal_vars(o)
                 and self.ix.resolve(info.scope, o.qual, o.name)[0] != EXTERN),
                None,
            )
            if binder is not None:
                self.add("domain-enumerator", atom.line,
                         f"{_atom_str(atom)}: {v} already bound by {binder.name}")

    def argmax(self, idx: int, info: RuleInfo) -> None:
        """`beaten(X) :- score(X, N), score(_, N2), N2 > N`, read only
        negated: an aggregate in disguise."""
        rule = info.rule
        if rule.body is None or len(rule.body) != 3:
            return
        atoms = [lit for lit in rule.body if isinstance(lit, Atom)]
        cmps = [lit for lit in rule.body if isinstance(lit, Cmp)]
        if len(atoms) != 2 or len(cmps) != 1 or cmps[0].op not in ("<", ">"):
            return
        if (atoms[0].qual, atoms[0].name) != (atoms[1].qual, atoms[1].name):
            return
        cvars = literal_vars(cmps[0])
        if not (cvars & literal_vars(atoms[0])) or not (cvars & literal_vars(atoms[1])):
            return
        key = self.rule_head_key(idx)
        uses = self.uses(key)
        if uses and all(u.role == "neg" for u in uses):
            self.add("argmax", rule.line, f"{rule.head.name}: max/min as self-join")

    def common_subexpr(self) -> None:
        """The same literal run, up to renaming, in two bodies."""
        seen: dict[tuple[str, ...], tuple[int, str]] = {}
        reported: set[tuple[int, int]] = set()
        rules = self.body_rules()
        for _, info in rules:
            body = info.rule.body or []
            n = len(body)
            for width in range(n, COMMON_SUBEXPR_MIN - 1, -1):
                for start in range(0, n - width + 1):
                    window = body[start:start + width]
                    sig = _canon_window(window)
                    if sig is None:
                        continue
                    at = (info.rule.line, info.rule.head.name)
                    if sig in seen and seen[sig][0] != info.rule.line:
                        pair = (seen[sig][0], info.rule.line)
                        if pair not in reported:
                            reported.add(pair)
                            self.add(
                                "common-subexpr", info.rule.line,
                                f"{width} literals shared with "
                                f"{seen[sig][1]} (L{seen[sig][0]})",
                            )
                    else:
                        seen.setdefault(sig, at)

    def single_init_comps(self) -> None:
        """A task-local comp with a single instantiation: possibly plain
        relations staged early."""
        inits: dict[str, list[int]] = {}
        for scope in self.ix.inits.values():
            for init in scope.values():
                inits.setdefault(init.comp, []).append(init.line)
        for comp in self.ix.program.comps().values():
            if comp.name in ("Consts", "Fit", "Parse"):
                continue
            if len(inits.get(comp.name, [])) == 1:
                self.add("single-init-comp", comp.line,
                         f"{comp.name}: instantiated once — could be plain relations")


# --- literal rendering (line-blind, for structural comparison) ---

def _term_str(t: Term, names: dict[str, str] | None = None) -> str:
    """Render a term. With `names`, variables substitute through it and
    absent ones render as `_` — the negation-inlining view."""
    def sub(x: Term) -> str:
        return _term_str(x, names)
    match t:
        case Var(name):
            return name if names is None else names.get(name, "_")
        case Wild():
            return "_"
        case Num(text):
            return text
        case Str(text):
            return text
        case MacroConst(name):
            return name
        case Ctor(name, args):
            return f"${name}({', '.join(map(sub, args))})"
        case Rec(args):
            return f"[{', '.join(map(sub, args))}]"
        case Call(name, args, functor):
            at = "@" if functor else ""
            return f"{at}{name}({', '.join(map(sub, args))})"
        case UnOp(op, arg):
            return f"{op}{sub(arg)}"
        case BinOp(op, lhs, rhs):
            return f"({sub(lhs)} {op} {sub(rhs)})"
        case Agg(op, expr, body):
            e = f" {sub(expr)}" if expr is not None else ""
            inner = ", ".join(map(_lit_str, body))
            return f"{op}{e} : {{ {inner} }}"
    return repr(t)


def _atom_str(a: Atom, names: dict[str, str] | None = None) -> str:
    qual = f"{a.qual}." if a.qual else ""
    return f"{qual}{a.name}({', '.join(_term_str(x, names) for x in a.args)})"


def _lit_str(lit: Lit) -> str:
    match lit:
        case Atom():
            return _atom_str(lit)
        case Neg(atom):
            return f"!{_atom_str(atom)}"
        case Cmp(op, lhs, rhs, _):
            return f"{_term_str(lhs)} {op} {_term_str(rhs)}"
        case Bool(value):
            return "true" if value else "false"
    return repr(lit)


def _conjunctions(rule: Rule) -> Iterator[list[Lit]]:
    """The rule body plus each aggregate body: the scopes subsumption
    reasons over."""
    if rule.body is None:
        return
    yield rule.body
    for lit in rule.body:
        if isinstance(lit, Cmp):
            for side in (lit.lhs, lit.rhs):
                if isinstance(side, Agg):
                    yield list(side.body)


def _canon_window(window: list[Lit]) -> tuple[str, ...] | None:
    """The window's literals with variables de Bruijn-renamed; None when
    the window has no atom."""
    if not any(isinstance(lit, Atom) for lit in window):
        return None
    names: dict[str, str] = {}

    def rename(s: str) -> str:
        return names.setdefault(s, f"v{len(names)}")

    out: list[str] = []
    for lit in window:
        text = _lit_str(lit)
        canon = "".join(
            rename(tok) if tok in _window_vars(window) else tok
            for tok in _split_idents(text)
        )
        out.append(canon)
    return tuple(out)


def _window_vars(window: list[Lit]) -> set[str]:
    out: set[str] = set()
    for lit in window:
        out |= literal_vars(lit)
    return out


def _split_idents(text: str) -> list[str]:
    return re.split(r"(\b[A-Za-z_][A-Za-z0-9_]*\b)", text)
