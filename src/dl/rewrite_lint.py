"""Flag patterns that usually get rewritten away.

Each rule mirrors an edit family observed across the solver corpus:
relations that restate another relation, references reachable only
through negation, dead declarations, mergeable Choice-tagged rules, and
so on. Findings are diagnostics only — the rewrite stays with the author.

A rewrite finding carries its fix. A hint — a pattern with real
counterexamples in the corpus, worth a look rather than a rewrite — is
behind the `hints` flag.

Relation-level rules run over the scopes that hold body code: top level,
`Fit`, `Parse`, and `Consts`. Other `.comp` interiors are lib-shaped code
and stay out, matching `lint.py`.

The public entry point is `lint_rewrites`; findings share `lint_body`'s
tuple shape.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Iterator

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
    Disj,
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
    TypeDecl,
    UnOp,
    Var,
    Wild,
    literal_vars,
    parse,
    term_vars,
)

LINE_LIMIT = 100   # code only; a trailing comment does not count
BODY_SCOPES = (TOP, "Fit", "Parse", "Consts")
COMMON_SUBEXPR_MIN = 2   # literals a shared window must span

# Categories of the hint tier, for callers that render the tiers apart.
HINTS = frozenset({
    "pass-through", "chain-join", "single-consumer", "domain-enumerator",
    "argmax", "common-subexpr", "const-join",
})

# Relations the runner fills per example; everything else at lib's top
# level is record arithmetic, independent of the task's grids.
EXAMPLE_SRC = frozenset({"in", "ex_in", "ex_out"})

# `*_elem` relations holding part of their element type rather than all of
# it: `c4_elem` is the rotation subgroup of `D4`. An atom over one of these
# tests membership, so a bound variable is a filter and the enumeration
# reading does not apply.
SUBSET_ELEMS = frozenset({"c4_elem"})

type Finding = tuple[str, int, str, str]

# Lib-idiom chains: a lib primitive's defining body, as the two atoms a
# hand-written site carries. `a` and `b` are (relation, arity, linking
# slot) — b's slot is a tuple of the slots the link may sit in, more than
# one where the relation is commutative there. `out` assembles the
# replacement's arguments: ('a', i) / ('b', i) take that atom's argument;
# _PARTNER takes b's other commutative slot. Optional guards hold slot
# refs: `equal` / `distinct` — pairs that must / must not render alike;
# `wild` — slots that must be wildcards. To cover a new primitive, add an
# entry.
_PARTNER = "partner"

_CHAINS: tuple[dict, ...] = (
    {
        "prim": "neighbor",
        "a": ("step_delta", 2, 1),
        "b": ("compose", 3, (0, 1)),
        "out": (_PARTNER, ("a", 0), ("b", 2)),
    },
    {
        "prim": "jump",
        "a": ("jump_delta", 3, 2),
        "b": ("compose", 3, (0, 1)),
        "out": (_PARTNER, ("a", 0), ("a", 1), ("b", 2)),
    },
    {
        "prim": "same_line",
        "a": ("split", 4, 3),
        "b": ("split", 4, (3,)),
        "out": (("a", 1), ("a", 0), ("b", 0)),
        "equal": ((("a", 1), ("b", 1)),),
        "wild": (("a", 2), ("b", 2)),
        "distinct": ((("a", 0), ("b", 0)),),
    },
)

# The slot where each delta primitive emits its Shift.
_DELTA_OUT = {"edge_delta": 2, "jump_delta": 2, "step_delta": 1}


def _delta_vars(ext: list[tuple[Atom, str]]) -> set[str]:
    """Variables holding a Shift: outputs of the delta primitives, plus
    compose outputs whose operands both hold one."""
    out: set[str] = set()
    for atom, name in ext:
        slot = _DELTA_OUT.get(name)
        if slot is not None and len(atom.args) > slot:
            out |= term_vars(atom.args[slot])
    changed = True
    while changed:
        changed = False
        for atom, name in ext:
            if name != "compose" or len(atom.args) != 3:
                continue
            operands = [term_vars(atom.args[i]) for i in (0, 1)]
            if all(vs and vs <= out for vs in operands):
                new = term_vars(atom.args[2]) - out
                if new:
                    out |= new
                    changed = True
    return out


def lint_rewrites(source: str, hints: bool = False) -> list[Finding]:
    lines = source.splitlines()

    def raw(lineno: int) -> str:
        return lines[lineno - 1].rstrip() if 0 < lineno <= len(lines) else ""

    try:
        program = parse(source)
    except ParseError as e:
        return [("parse-error", e.line, e.msg, raw(e.line))]

    ix = Index(program)
    lint = _Lint(ix, lines)
    findings = lint.run(hints)
    findings.sort(key=lambda f: (f[1], f[0]))
    return [(cat, ln, match, raw(ln)) for cat, ln, match, _ in findings]


class _Lint:
    def __init__(self, ix: Index, lines: list[str]):
        self.ix = ix
        self.lines = lines
        self.findings: list[Finding] = []
        self.claimed: set[RelKey] = set()  # relations an earlier rule flagged
        self._const_targets: set[tuple[str, str]] | None = None
        # Choice tags: branch names of the ADTs the file declares.
        self.choice_tags = {
            b
            for it in ix.program.items
            if isinstance(it, TypeDecl)
            for b in it.branches
        }

    def add(self, cat: str, line: int, match: str) -> None:
        self.findings.append((cat, line, match, ""))

    def claim(self, cat: str, key: RelKey, line: int, match: str) -> None:
        self.claimed.add(key)
        self.add(cat, line, match)

    def run(self, hints: bool) -> list[Finding]:
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
            self.cross_choice(info)
            self.raw_aggregate(info)
            self.subsumed_atoms(info)
            self.lib_idiom(info)
            self.named_complement(info)
            self.long_rule(info)
        self.decl_placement()
        if hints:
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
                self.const_join(info)
            self.common_subexpr()
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
            and not info.rule.sub
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
        decl = self.decl_of(key)
        if decl is not None and decl.choice_domain:
            return False  # the pick lives on the decl; substitution loses it
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
            self.claim("dead", key, self.decl_of(key).line,
                       f"`{key[1]}` has no uses")

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
                   f"`{_atom_str(defs[0].head)}` is `{_atom_str(atom)}` renamed")

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
        parts: list[str] = []
        for d in defs:
            names = {
                a.name: canon[i]
                for i, a in enumerate(d.head.args) if isinstance(a, Var)
            }
            atom = d.body[0] if d.body else None
            assert isinstance(atom, Atom)  # _projection admitted this def
            parts.append(f"!{_atom_str(atom, names)}")
        return f"`!{key[1]}({', '.join(canon)})` ⇒ `{', '.join(parts)}`"

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
        """Hint: consumed only by pure forwarding rules of one relation.
        The corpus keeps this shape as a named union member; flag it for
        the call."""
        if not self.inlinable(key) or self.recursive(key):
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
                   f"`{key[1]}` only feeds `{consumer[1]}`")

    def single_consumer(self, key: RelKey) -> None:
        """Hint: one rule, one positive use, a two-literal body. The
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
        if uses[0].role == "agg" and self._agg_op(uses[0]) in ("count", "sum") \
                and _drops_columns(defs[0]):
            return  # a projection deduplicates; inlining changes the count
        self.claim("single-consumer", key, self.decl_of(key).line,
                   f"`{key[1]}` has one rule and one use (line {uses[0].line})")

    def _agg_op(self, use: Ref) -> str | None:
        """The aggregate operator whose body holds this use, if any."""
        rule = self.ix.rules[use.rule].rule
        if rule.body is None:
            return None
        for lit in rule.body:
            if isinstance(lit, Cmp):
                for side in (lit.lhs, lit.rhs):
                    if isinstance(side, Agg) \
                            and any(b is use.atom for b in side.body):
                        return side.op
        return None

    def chain_join(self, key: RelKey) -> None:
        """A column that, at every use, only keys a join against one other
        relation the join fully absorbs: fuse and project the column out.
        Restricted to plumbing — every rule of the relation a single-atom
        body — so named stages stay. A partner with a life of its own
        (other readers, or a lib relation) is factoring, not a chain."""
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
            joined: list[Atom] = []
            ok = True
            for u in uses:
                partner = self._join_partner(u, col)
                if partner is None:
                    ok = False
                    break
                pkey, pcol, patom = partner
                partners.add((pkey, pcol))
                joined.append(patom)
            if not (ok and len(partners) == 1):
                continue
            q, _ = partners.pop()
            if q[0] == EXTERN or not self._absorbable(q, joined):
                continue
            self.claim(
                "chain-join", key, decl.line,
                f"`{key[1]}.{decl.fields[col].name}` only joins `{q[1]}`",
            )
            return

    def _absorbable(self, q: RelKey, joined: list[Atom]) -> bool:
        """Fusing deletes `q` only when these joins are all `q` does."""
        ids = {id(a) for a in joined}
        return all(
            r.role == "head" or id(r.atom) in ids for r in self.ix.refs_of(q)
        )

    def _join_partner(self, use: Ref, col: int) -> tuple[RelKey, int, Atom] | None:
        """The (relation, column, atom) the key var at `col` of this use
        joins, when the var appears exactly there and nowhere else."""
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
        partner: tuple[RelKey, int, Atom] | None = None
        for lit in rule.body:
            if isinstance(lit, Atom) and lit is not atom:
                hits = [i for i, a in enumerate(lit.args) if v in term_vars(a)]
                if len(hits) > 1 or (hits and partner is not None):
                    return None
                if hits:
                    if not isinstance(lit.args[hits[0]], Var):
                        return None
                    pkey = self.ix.resolve(use.scope, lit.qual, lit.name)
                    partner = (pkey, hits[0], lit)
            elif lit is not atom and v in literal_vars(lit):
                return None
        return partner

    def choice_tag(self, idx: int, info: RuleInfo) -> None:
        """Rules identical but for a distinct nullary constructor in one
        head argument: merge on a Choice variable. Fires only when some
        relation's facts already enumerate both tags — without one, the
        merge must add an enumerator and comes out larger."""
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
            names = [t.name for t in tags if isinstance(t, Ctor) and not t.args]
            if len(names) == len(tags) == 2 and self._tags_enumerated(names):
                self.add(
                    "choice-tag", rule.line,
                    f"same body under `{_term_str(tags[1])}` and "
                    f"`{_term_str(tags[0])}`; one rule ranges over the tags",
                )
                return

    def _tags_enumerated(self, names: list[str]) -> bool:
        """Whether some relation's facts range over all of `names`."""
        have: dict[RelKey, set[str]] = {}
        for info in self.ix.rules:
            r = info.rule
            if r.body is not None:
                continue
            key = self.ix.resolve(info.scope, r.head.qual, r.head.name)
            for a in r.head.args:
                if isinstance(a, Ctor) and not a.args:
                    have.setdefault(key, set()).add(a.name)
        return any(set(names) <= s for s in have.values())

    def cross_choice(self, info: RuleInfo) -> None:
        """A disjunction whose branches bind different choice tags. A
        disjunction is a case split inside one choice's derivation;
        choices stay separate rules."""
        for disj in _disjs_in(info.rule):
            binds = [
                _tags(" ".join(_lit_str(lit) for lit in branch))
                & self.choice_tags
                for branch in disj.branches
            ]
            named = [b for b in binds if b]
            if len(named) >= 2 and any(b != named[0] for b in named):
                tags: set[str] = set()
                for b in named:
                    tags |= b
                self.add(
                    "cross-choice", disj.line,
                    f"branches bind "
                    f"{', '.join(f'`${t}()`' for t in sorted(tags))}; "
                    f"choices stay separate rules",
                )

    def raw_aggregate(self, info: RuleInfo) -> None:
        """An aggregate in a body rule: read it through a lib comp."""
        for body in _conjunctions(info.rule):
            for lit in body:
                if not isinstance(lit, Cmp):
                    continue
                for side in (lit.lhs, lit.rhs):
                    if isinstance(side, Agg):
                        self.add(
                            "raw-aggregate", lit.line,
                            f"`{side.op}` in the body; read it through "
                            f"a lib comp",
                        )

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
                                     f"`{_atom_str(b)}` appears twice in the body")
                    elif all(
                        isinstance(x, Wild) or _term_str(x) == _term_str(y)
                        for x, y in pairs
                    ):
                        self.add(
                            "subsumed-atom", a.line,
                            f"`{_atom_str(a)}` adds nothing next to "
                            f"`{_atom_str(b)}`",
                        )

    def lib_idiom(self, info: RuleInfo) -> None:
        """A lib primitive's defining chain written out by hand, with the
        linking value confined to the chain: name it with the primitive.
        The chains are the `_CHAINS` table."""
        rule = info.rule
        if rule.body is None or rule.grid:
            return
        head_vars = literal_vars(rule.head)
        # (id(a), id(b)) -> [a, fix message, clean in every expansion]
        pairs: dict[tuple[int, int], list] = {}
        for flat in _flatten(rule.body):
            atoms = [
                (lit, self.ix.resolve(info.scope, lit.qual, lit.name))
                for lit in flat
                if isinstance(lit, Atom)
            ]
            for a, b, link, fix in self._idiom_pairs(atoms):
                clean = link not in head_vars and not any(
                    lit is not a and lit is not b and link in literal_vars(lit)
                    for lit in flat
                )
                entry = pairs.setdefault((id(a), id(b)), [a, fix, True])
                entry[2] = entry[2] and clean
        for a, fix, clean in pairs.values():
            if clean:
                self.add("lib-idiom", a.line, fix)

    def _idiom_pairs(
        self, atoms: list[tuple[Atom, RelKey]],
    ) -> Iterator[tuple[Atom, Atom, str, str]]:
        """(atom a, atom b, linking var, fix message) per `_CHAINS` match."""
        def var_at(atom: Atom, i: int) -> str | None:
            arg = atom.args[i]
            return arg.name if isinstance(arg, Var) else None

        ext = [(x, key[1]) for x, key in atoms if key[0] == EXTERN]
        deltas = _delta_vars(ext)
        for spec in _CHAINS:
            rel_a, ar_a, slot_a = spec["a"]
            rel_b, ar_b, slots_b = spec["b"]
            for a, name_a in ext:
                if name_a != rel_a or len(a.args) != ar_a:
                    continue
                link = var_at(a, slot_a)
                if link is None:
                    continue
                for b, name_b in ext:
                    if b is a or name_b != rel_b or len(b.args) != ar_b:
                        continue
                    if rel_a == rel_b and id(b) < id(a):
                        continue
                    slot_b = next(
                        (i for i in slots_b if var_at(b, i) == link), None,
                    )
                    if slot_b is None:
                        continue

                    def slot(ref) -> Term:
                        if ref == _PARTNER:
                            [i] = [i for i in slots_b if i != slot_b]
                            return b.args[i]
                        which, idx = ref
                        return (a if which == "a" else b).args[idx]

                    if any(
                        _term_str(slot(x)) != _term_str(slot(y))
                        for x, y in spec.get("equal", ())
                    ):
                        continue
                    if any(
                        not isinstance(slot(s), Wild)
                        for s in spec.get("wild", ())
                    ):
                        continue
                    if any(
                        _term_str(slot(x)) == _term_str(slot(y))
                        for x, y in spec.get("distinct", ())
                    ):
                        continue
                    # A compose over delta algebra steps no cell: when the
                    # would-be position operand holds a Shift, the chain is
                    # not the primitive.
                    if _PARTNER in spec["out"] and \
                            term_vars(slot(_PARTNER)) & deltas:
                        continue
                    out = [slot(ref) for ref in spec["out"]]
                    if any(link in term_vars(t) for t in out):
                        continue
                    fix = (f"`{_atom_str(a)}, {_atom_str(b)}` ⇒ "
                           f"`{spec['prim']}"
                           f"({', '.join(_term_str(t) for t in out)})`")
                    yield a, b, link, fix

    def named_complement(self, info: RuleInfo) -> None:
        """`R(V), X != V` against a singleton fact: `!R(X)` says it
        directly."""
        rule = info.rule
        if rule.body is None:
            return
        flats = list(_flatten(rule.body))
        for atom in {id(l): l for f in flats for l in f
                     if isinstance(l, Atom)}.values():
            if len(atom.args) != 1 or not isinstance(atom.args[0], Var):
                continue
            key = self.ix.resolve(info.scope, atom.qual, atom.name)
            if key[0] == EXTERN:
                continue
            defs = self.defs(key)
            if len(defs) != 1 or defs[0].body is not None:
                continue
            v = atom.args[0].name
            if v in literal_vars(rule.head):
                continue
            # The rewrite must hold, with one shared `!=`, in every
            # expansion the atom is in.
            found: tuple[Cmp, Term] | None = None
            ok = True
            for flat in flats:
                if not any(l is atom for l in flat):
                    continue
                others = [
                    lit for lit in flat
                    if lit is not atom and v in literal_vars(lit)
                ]
                if len(others) != 1:
                    ok = False
                    break
                cmp = others[0]
                if not (isinstance(cmp, Cmp) and cmp.op == "!="):
                    ok = False
                    break
                if isinstance(cmp.lhs, Var) and cmp.lhs.name == v:
                    other = cmp.rhs
                elif isinstance(cmp.rhs, Var) and cmp.rhs.name == v:
                    other = cmp.lhs
                else:
                    ok = False
                    break
                bound: set[str] = set()
                for lit in flat:
                    if isinstance(lit, Atom) and lit is not atom:
                        bound |= literal_vars(lit)
                if term_vars(other) - bound:
                    ok = False  # the negation would leave the value unbound
                    break
                if found is None:
                    found = (cmp, other)
                elif found[0] is not cmp:
                    ok = False
                    break
            if not ok or found is None:
                continue
            cmp, other = found
            qual = f"{atom.qual}." if atom.qual else ""
            self.add(
                "named-complement", atom.line,
                f"`{_atom_str(atom)}, {_lit_str(cmp)}` ⇒ "
                f"`!{qual}{atom.name}({_term_str(other)})`",
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
            self.add("decl-placement", decl.line,
                 f"all uses of `{name}` are in {spot}")

    def long_rule(self, info: RuleInfo) -> None:
        rule = info.rule
        if rule.body is None or rule.line != rule.end_line:
            return
        text = self.lines[rule.line - 1] if rule.line <= len(self.lines) else ""
        code = text.split("//")[0].rstrip()
        if len(code) > LINE_LIMIT:
            self.add("long-rule", rule.line,
                     f"{len(code)} > {LINE_LIMIT} chars of code; wrap the body")

    # --- hint rules ---

    def domain_enumerator(self, info: RuleInfo) -> None:
        """An `*_elem` atom whose variable another positive atom already
        binds. An `inline` relation does not count as a binder: it
        substitutes away, so its arguments stay ungrounded. A relation in
        `SUBSET_ELEMS` holds part of its element type, so the atom narrows
        the binding and stays."""
        rule = info.rule
        if rule.body is None:
            return
        flats = list(_flatten(rule.body))
        for atom in {id(l): l for f in flats for l in f
                     if isinstance(l, Atom)}.values():
            if not atom.name.endswith("_elem") or len(atom.args) != 1:
                continue
            if atom.name in SUBSET_ELEMS:
                continue
            if not isinstance(atom.args[0], Var):
                continue
            v = atom.args[0].name
            # Redundant only when every expansion the atom is in binds it.
            binder: Atom | None = None
            for flat in flats:
                if not any(l is atom for l in flat):
                    continue
                binder = next(
                    (o for o in flat
                     if isinstance(o, Atom) and o is not atom
                     and not o.name.endswith("_elem")
                     and v in literal_vars(o)
                     and self._grounds(info.scope, o)),
                    None,
                )
                if binder is None:
                    break
            if binder is not None:
                self.add(
                    "domain-enumerator", atom.line,
                    f"`{_atom_str(atom)}`; `{v}` is already bound by "
                    f"`{binder.name}`",
                )

    def _grounds(self, scope: str, atom: Atom) -> bool:
        """Whether this atom grounds its variables: a local, non-inline
        relation."""
        key = self.ix.resolve(scope, atom.qual, atom.name)
        if key[0] == EXTERN:
            return False
        decl = self.ix.decls.get(key[0], {}).get(key[1])
        return decl is not None and "inline" not in decl.qualifiers

    def argmax(self, idx: int, info: RuleInfo) -> None:
        """`beaten(X) :- score(X, N), score(_, N2), N2 > N`, read only
        negated: an aggregate in disguise."""
        rule = info.rule
        if rule.body is None:
            return
        for body in _flatten(rule.body):
            if len(body) != 3:
                return
            atoms = [lit for lit in body if isinstance(lit, Atom)]
            cmps = [lit for lit in body if isinstance(lit, Cmp)]
            if len(atoms) != 2 or len(cmps) != 1 or cmps[0].op not in ("<", ">"):
                return
            if (atoms[0].qual, atoms[0].name) != (atoms[1].qual, atoms[1].name):
                return
            cvars = literal_vars(cmps[0])
            if not (cvars & literal_vars(atoms[0])) \
                    or not (cvars & literal_vars(atoms[1])):
                return
        key = self.rule_head_key(idx)
        uses = self.uses(key)
        if uses and all(u.role == "neg" for u in uses):
            self.add("argmax", rule.line,
                     f"`{rule.head.name}` is max/min via self-join; "
                     f"read it through a lib comp")

    def const_join(self, info: RuleInfo) -> None:
        """Hint: a variable internal to a rule's Consts reads. The join
        states no per-example thing — it derives a task constant, which
        the corpus names in its own relation. Quiet inside Consts and
        under a head that is itself task-constant: those are the named
        forms."""
        rule = info.rule
        if rule.body is None or info.scope == "Consts":
            return
        head = self._target(info.scope, rule.head)
        if isinstance(head, tuple) and head in self.const_targets():
            return
        seen: set[str] = set()
        for body in _flatten(rule.body):
            creads = [
                lit for lit in body
                if isinstance(lit, (Atom, Neg))
                and (a := lit.atom if isinstance(lit, Neg) else lit).qual
                is not None
                and self._target(info.scope, a) == "const"
            ]
            if len(creads) < 2:
                continue
            cvars: set[str] = set()
            for lit in creads:
                cvars |= literal_vars(lit)
            ids = {id(lit) for lit in creads}
            others = literal_vars(rule.head)
            for lit in body:
                if id(lit) not in ids:
                    others |= literal_vars(lit)
            internal = cvars - others
            if not internal:
                continue
            rels: list[str] = []
            for lit in creads:
                a = lit.atom if isinstance(lit, Neg) else lit
                s = f"{a.qual}.{a.name}"
                if s not in rels:
                    rels.append(s)
            msg = (f"`{'`, `'.join(rels)}` join on `{', '.join(sorted(internal))}`; "
                   f"name the derived constant in Consts")
            if msg in seen:
                continue
            seen.add(msg)
            a0 = creads[0].atom if isinstance(creads[0], Neg) else creads[0]
            self.add("const-join", a0.line, msg)

    def const_targets(self) -> set[tuple[str, str]]:
        """Relations and comp instances whose derivations never reach a
        per-example source: named task constants."""
        if self._const_targets is not None:
            return self._const_targets
        heads: dict[tuple[str, str], list[tuple[str, Rule]]] = {}
        for info in self.ix.rules:
            t = self._target(info.scope, info.rule.head)
            if isinstance(t, tuple):
                heads.setdefault(t, []).append((info.scope, info.rule))
        tainted: set[tuple[str, str]] = set()
        changed = True
        while changed:
            changed = False
            for t, rules in heads.items():
                if t in tainted:
                    continue
                for scope, rule in rules:
                    if rule.body is None:
                        continue
                    for atom in _all_atoms(rule.body):
                        b = self._target(scope, atom)
                        if b == "example" or \
                                (isinstance(b, tuple) and b in tainted):
                            tainted.add(t)
                            changed = True
                            break
                    if t in tainted:
                        break
        self._const_targets = set(heads) - tainted
        return self._const_targets

    def _target(self, scope: str, atom: Atom) -> tuple[str, str] | str:
        """Where an atom's derivation comes from: 'const' for Consts data
        and grid-free lib relations, 'example' for the runner's per-example
        fills, else the (scope, name) node the taint runs through — the
        instance for qualified atoms, the declaring scope for bare ones."""
        if atom.qual is not None:
            hop = atom.qual.split(".")[0]
            for s in (*self.ix.chain(scope), TOP):
                init = self.ix.inits.get(s, {}).get(hop)
                if init is not None:
                    if init.comp == "Consts":
                        return "const"
                    return (s, hop)
            return "example"
        key = self.ix.resolve(scope, None, atom.name)
        if key[0] == EXTERN:
            return "example" if atom.name in EXAMPLE_SRC else "const"
        if key[0] == "Consts":
            return "const"
        return key

    def common_subexpr(self) -> None:
        """The same literal run, up to renaming, in two bodies of one
        scope. A cross-scope repeat is the fit architecture re-deriving a
        solve rule over the examples — the comp boundary blocks sharing.
        A pair that spans choices — different sections, or heads bound to
        different choice tags — stays quiet: sharing across choices is
        not a simplification of either choice."""
        seen: dict[tuple[str, ...], RuleInfo] = {}
        reported: set[tuple[int, int]] = set()
        for _, info in self.body_rules():
            body = info.rule.body or []
            n = len(body)
            for width in range(n, COMMON_SUBEXPR_MIN - 1, -1):
                for start in range(0, n - width + 1):
                    window = body[start:start + width]
                    canon = _canon_window(window)
                    if canon is None:
                        continue
                    sig = (info.scope, *canon)
                    if sig in seen and seen[sig].rule.line != info.rule.line:
                        prev = seen[sig]
                        pair = (prev.rule.line, info.rule.line)
                        if pair not in reported:
                            reported.add(pair)
                            msg = self._subexpr_msg(width, prev, info)
                            if msg is not None:
                                self.add("common-subexpr", info.rule.line, msg)
                    else:
                        seen.setdefault(sig, info)

    def _subexpr_msg(self, width: int, prev: RuleInfo, cur: RuleInfo) -> str | None:
        """The finding message, or None when the pair spans choices.
        Same-shaped heads make the pair a disjunction merge; the message
        says so. A different-head pair must share more to be worth a
        look, so it keeps a higher bar."""
        if prev.section != cur.section:
            return None
        ph, ch = prev.rule.head, cur.rule.head
        if _tags(_atom_str(ph)) & self.choice_tags \
                != _tags(_atom_str(ch)) & self.choice_tags:
            return None
        msg = f"{width} literals shared with `{ph.name}` (line {prev.rule.line})"
        if _canon_window([ph]) == _canon_window([ch]):
            return msg + "; merge the tails into a disjunction"
        return msg if width >= 3 else None


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
        case Disj(branches, _):
            inner = " ; ".join(
                ", ".join(_lit_str(sub) for sub in b) for b in branches
            )
            return f"({inner})"
    return repr(lit)


def _tags(text: str) -> set[str]:
    """Nullary constructor names a rendered literal mentions."""
    return set(re.findall(r"\$(\w+)\(\)", text))


def _disjs_in(rule: Rule) -> Iterator[Disj]:
    stack: list[Lit] = list(rule.body or ())
    while stack:
        lit = stack.pop()
        if isinstance(lit, Disj):
            yield lit
            for branch in lit.branches:
                stack.extend(branch)


def _atoms_in(lit: Lit) -> Iterator[Atom]:
    if isinstance(lit, Atom):
        yield lit
    elif isinstance(lit, Disj):
        for branch in lit.branches:
            for sub in branch:
                yield from _atoms_in(sub)


def _all_atoms(lits: Iterable[Lit]) -> Iterator[Atom]:
    """Every atom a body derives through: positive, negated, in aggregate
    bodies, and in disjunction branches."""
    for lit in lits:
        if isinstance(lit, Atom):
            yield lit
        elif isinstance(lit, Neg):
            yield lit.atom
        elif isinstance(lit, Cmp):
            for side in (lit.lhs, lit.rhs):
                if isinstance(side, Agg):
                    yield from _all_atoms(side.body)
        elif isinstance(lit, Disj):
            for branch in lit.branches:
                yield from _all_atoms(branch)


def _drops_columns(d: Rule) -> bool:
    """Whether the head loses information from the body: a body variable
    or wildcard no head column carries."""
    if d.body is None:
        return False
    head = literal_vars(d.head)
    if any(literal_vars(lit) - head for lit in d.body):
        return True
    return any(
        isinstance(a, Wild)
        for lit in d.body
        for atom in _atoms_in(lit)
        for a in atom.args
    )


def _flatten(body: list[Lit]) -> Iterator[list[Lit]]:
    """The conjunctions a body's disjunctions expand into: one per branch
    choice, with the enclosing literals kept."""
    for i, lit in enumerate(body):
        if isinstance(lit, Disj):
            rest = [*body[:i], *body[i + 1:]]
            for branch in lit.branches:
                yield from _flatten([*rest, *branch])
            return
    yield body


def _conjunctions(rule: Rule) -> Iterator[list[Lit]]:
    """The rule body, each aggregate body, and each disjunct: the scopes
    subsumption reasons over."""
    if rule.body is None:
        return
    yield rule.body
    stack: list[Lit] = list(rule.body)
    while stack:
        lit = stack.pop()
        if isinstance(lit, Cmp):
            for side in (lit.lhs, lit.rhs):
                if isinstance(side, Agg):
                    yield list(side.body)
        elif isinstance(lit, Disj):
            for branch in lit.branches:
                yield list(branch)
                stack.extend(branch)


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
