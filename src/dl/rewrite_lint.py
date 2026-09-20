"""Flag patterns that usually get rewritten away.

Each rule mirrors an edit family observed across the solver corpus:
relations that restate another relation, references reachable only
through negation, dead declarations, mergeable Choice-tagged rules, and
so on. Findings are diagnostics only — the rewrite stays with the author.

Some rules read the style doc rather than an edit family:
`typed-order` flags an order taken over a type that carries none,
`choice-domain` flags a declaration that keeps one arbitrary tuple, and
`shared-read` flags a shared parameter some case never reads. The first
two need the declared type of a rule variable, which the column tables
here already infer; the last walks the dataflow back from `out` under
each case.

A rewrite finding carries its fix. A hint — a pattern with real
counterexamples in the corpus, worth a look rather than a rewrite — is
behind the `hints` flag.

Relation-level rules run over the scopes that hold program code, which
`PROGRAM_SCOPES` names. Other `.comp` interiors are proposal comps,
lib code on its way out of the solver, and stay out, matching `lint.py`.

The public entry point is `lint_rewrites`; findings share `lint_program`'s
tuple shape.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Iterator
from functools import lru_cache

from dl.dlparse import (
    EXTERN,
    TOP,
    Agg,
    Atom,
    BinOp,
    Bool,
    Call,
    Cmp,
    Comp,
    Ctor,
    Decl,
    Disj,
    Index,
    Init,
    Item,
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
    body_literals,
    literal_vars,
    parse,
    term_vars,
)
from dl.lint import PLAN_RE, _lib_source
from dl.source import shared_params

LINE_LIMIT = 100   # code only; a trailing comment does not count
PROGRAM_SCOPES = (TOP, "Determine", "Parse", "Params")
COMMON_SUBEXPR_MIN = 2   # literals a shared window must span

# The hint categories, for callers that render hints apart from findings.
HINTS = frozenset({
    "pass-through", "chain-join", "single-consumer", "domain-enumerator",
    "argmax", "common-subexpr", "const-join", "comp-idiom",
})

# Relations the runner fills per example; everything else at lib's top
# level is record arithmetic, independent of the task's grids.
EXAMPLE_SRC = frozenset({"in", "ex_in", "ex_out"})

type Finding = tuple[str, int, str, str]

# Every sentence this lint prints, keyed by the category the finding carries.
# A category whose text is built from the rule it read holds the form of that
# text. A slot, `{name}`, is filled at the site that fires.
MESSAGES = {
    "keep": "; to keep it, paste above the declaration: "
            "`// @allow: {cat} \u2014 <reason>`",
    "choice-domain": "`{name}` keeps one arbitrary tuple per `{over}`; state "
                     "what picks it",
    "shared-read": "`{name}` is shared, and {cases} never reads it; move it "
                   "under the marker of the cases that read it",
    "typed-order": "{how} `{var}`, a `{type}`, which has no order; store the "
                   "order as a parameter",
    "choice-tag": "same body under `{one}` and `{other}`; one clause ranges "
                  "over the tags",
    "cross-choice": "branches bind {tags}; keep each choice in its own clause",
    "raw-aggregate": "`{op}` in the program; read it through a lib component",
    "subsumed-atom-twice": "`{atom}` appears twice in the body",
    "subsumed-atom": "`{atom}` adds nothing next to `{other}`",
    "negated-value": "`{atom}, {var} != {value}` \u21d2 `!{rewritten}`",
    "named-complement": "`{atom}, {cmp}` \u21d2 `!{rewritten}`",
    "decl-placement": "all uses of `{name}` are in {spot}",
    "long-rule": "{width} > {limit} chars of code on one line; wrap the body",
    "domain-enumerator": "`{atom}`; `{var}` is already bound by `{binder}`",
    "argmax": "`{name}` is max/min via self-join; read it through a lib "
              "component",
    "common-subexpr": "{width} literals shared with `{name}` (line {line})",
    "merge-tails": "; merge the tails into a disjunction",
    "complement-rewrite": "`!{name}({args})` \u21d2 {parts}",
    "other-member": "{pair} states the other member of a two-member type; "
                    "write `{rel}({x}, {y})`",
    "image-link": "{pair} through `{link}` is `{comp}`",
}

# The directive that keeps a relation against a hint, on the line above
# the relation's declaration: `// @allow: <category> — <why>`.
_ALLOW_RE = re.compile(r"//\s*@allow:\s*([\w-]+)")

# The hint categories `@allow` can silence: the ones whose finding sits on
# the relation's declaration line, which is where the directive is read.
ALLOWABLE_HINTS = frozenset({"pass-through", "single-consumer", "chain-join"})


def keep_line(cat: str) -> str:
    """The line an author pastes above the declaration to keep the code
    against this hint, tacked onto the hint's message."""
    return MESSAGES["keep"].format(cat=cat)

# Souffle's primitive types. A column typed by one states no domain, so
# it never counts as wider than an element type.
_PRIMITIVE_TYPES = frozenset({"number", "unsigned", "float", "symbol"})
_UNION_RE = re.compile(r"=\s*(\w+(?:\s*\|\s*\w+)+)\s*")


@lru_cache(maxsize=2)
def _elem_tables(text: str) -> tuple[dict[str, str], dict[str, set[str]]]:
    """Two tables read off lib.dl's text: each `*_elem` relation and the
    element type it holds, and each type and the types wider than it. A
    union `.type X = A | B` makes X wider than A and B; a subtype
    `.type A <: B` makes B wider than A; the closure is transitive. An
    atom over an elem relation narrows a variable bound at a column of a
    wider type, so that binding is a filter and the enumeration reading
    does not apply. Keyed on the text, so an edit to lib.dl reaches a
    process that already linted against it."""
    try:
        items = parse(text).items
    except ParseError:
        return {}, {}
    elem_type = {
        it.name: it.fields[0].type
        for it in items
        if isinstance(it, Decl) and it.name.endswith("_elem")
        and len(it.fields) == 1
    }
    wider: dict[str, set[str]] = {}
    for it in items:
        if not isinstance(it, TypeDecl):
            continue
        if it.rhs.startswith("<:"):
            wider.setdefault(it.name, set()).add(it.rhs[2:].strip())
        elif m := _UNION_RE.fullmatch(it.rhs):
            for member in m.group(1).split("|"):
                wider.setdefault(member.strip(), set()).add(it.name)
    for ws in wider.values():
        ws.difference_update(_PRIMITIVE_TYPES)
    changed = True
    while changed:
        changed = False
        for ws in wider.values():
            more = set().union(*(wider.get(w, set()) for w in ws)) - ws
            if more:
                ws |= more
                changed = True
    return elem_type, wider


@lru_cache(maxsize=2)
def _enum_sizes(text: str) -> dict[str, int]:
    """Member count per lib type whose `*_elem` relation is stated as
    facts, counted off those facts. A type whose elem relation derives
    through a rule gets no count."""
    elem_type, _ = _elem_tables(text)
    try:
        items = parse(text).items
    except ParseError:
        return {}
    sizes: dict[str, int] = {}
    for it in items:
        if isinstance(it, Rule) and it.body is None and it.head.name in elem_type:
            t = elem_type[it.head.name]
            sizes[t] = sizes.get(t, 0) + 1
    return sizes


# The ARC value types, with `Ident`: types with identity and no order.
# Each is declared a `number` subtype, so `Col1 < Col2` typechecks; the
# order it states is not in the type.
_UNORDERED_BASE = frozenset({
    "Color", "Dir", "DiagDir", "Axis", "DiagAxis", "D4", "Sym", "Sense",
    "Ident",
})
_ORDER_OPS = frozenset({"<", "<=", ">", ">="})
_ORDER_AGGS = frozenset({"min", "max"})
# The lib comp that ranks a numeric set, and the relation it ranks.
_ORDINAL_COMP = "Ordinal"
_ORDINAL_SET = "idx_set"


@lru_cache(maxsize=2)
def _unordered_types(text: str) -> frozenset[str]:
    """The type names an ordering may not read: the ARC value types, the
    subtypes they reach, and the unions whose every member is one. Read
    off lib.dl's text, keyed on it."""
    try:
        items = parse(text).items
    except ParseError:
        return _UNORDERED_BASE
    subs: dict[str, str] = {}
    unions: dict[str, list[str]] = {}
    for it in items:
        if not isinstance(it, TypeDecl):
            continue
        if it.rhs.startswith("<:"):
            subs[it.name] = it.rhs[2:].strip()
        elif m := _UNION_RE.fullmatch(it.rhs):
            unions[it.name] = [x.strip() for x in m.group(1).split("|")]
    out = set(_UNORDERED_BASE)
    changed = True
    while changed:
        changed = False
        for name, base in subs.items():
            if name not in out and base in out:
                out.add(name)
                changed = True
        for name, members in unions.items():
            if name not in out and all(m in out for m in members):
                out.add(name)
                changed = True
    return frozenset(out)


_RECORD_RE = re.compile(r"=\s*\[(.*)\]\s*$", re.DOTALL)
_FIELD_RE = re.compile(r"\w+\s*:\s*(\w+)")


def _record_fields(items: Iterable[Item]) -> dict[str, list[str]]:
    """Each record type an item tree declares, with its field types."""
    out: dict[str, list[str]] = {}
    for it in items:
        if isinstance(it, TypeDecl) and (m := _RECORD_RE.search(it.rhs)):
            out[it.name] = _FIELD_RE.findall(m.group(1))
        elif isinstance(it, Comp):
            out |= _record_fields(it.items)
    return out


def _calls_range(t: Term) -> bool:
    match t:
        case Call(name, args, functor):
            return (name == "range" and not functor) or any(_calls_range(a) for a in args)
        case Rec(args) | Ctor(_, args):
            return any(_calls_range(a) for a in args)
        case BinOp(_, lhs, rhs):
            return _calls_range(lhs) or _calls_range(rhs)
        case UnOp(_, arg):
            return _calls_range(arg)
    return False


@lru_cache(maxsize=2)
def _lib_inline(text: str) -> tuple[frozenset[str], frozenset[str]]:
    """Two sets read off the lib's text: its top-level inline relations,
    and those among them whose expansion introduces no variable: every
    clause binds only head variables, with no wildcard, range, or
    aggregate, through relations that are themselves such. Souffle accepts
    `!prim(...)` at one of these when the use binds every column, and
    rejects the negation of any other inline relation."""
    try:
        items = parse(text).items
    except ParseError:
        return frozenset(), frozenset()
    inline = frozenset(
        it.name for it in items
        if isinstance(it, Decl) and "inline" in it.qualifiers
    )
    clauses: dict[str, list[Rule]] = {}
    for it in items:
        if isinstance(it, Rule) and it.body is not None \
                and it.head.qual is None and it.head.name in inline:
            clauses.setdefault(it.head.name, []).append(it)

    def closed(r: Rule) -> bool:
        head_vars = literal_vars(r.head)
        for lit in r.body or []:
            if isinstance(lit, Bool):
                continue
            if not isinstance(lit, (Atom, Cmp)):
                return False
            if literal_vars(lit) - head_vars:
                return False
            if isinstance(lit, Atom) and any(_has_wild(a) for a in lit.args):
                return False
            if isinstance(lit, Cmp) and (_calls_range(lit.lhs) or _calls_range(lit.rhs)):
                return False
        return True

    negatable = {n for n in inline if all(closed(r) for r in clauses.get(n, []))}
    changed = True
    while changed:
        changed = False
        for n in list(negatable):
            for r in clauses.get(n, []):
                for lit in r.body or []:
                    if isinstance(lit, Atom) and lit.qual is None \
                            and lit.name in inline and lit.name not in negatable:
                        negatable.discard(n)
                        changed = True
                        break
    return inline, frozenset(negatable)


@lru_cache(maxsize=2)
def _lib_records(text: str) -> dict[str, list[str]]:
    """lib.dl's record types, keyed on its text."""
    try:
        return _record_fields(parse(text).items)
    except ParseError:
        return {}


def _comp_table(items: Iterable[Item]) -> dict[str, Comp]:
    """Every component in an item tree, nested ones included, by name."""
    table: dict[str, Comp] = {}
    for it in items:
        if isinstance(it, Comp):
            table[it.name] = it
            table |= _comp_table(it.items)
    return table


@lru_cache(maxsize=2)
def _lib_scopes(text: str) -> tuple[dict[str, Decl], dict[str, Comp]]:
    """lib.dl's top-level relations by name and its components by name.
    Keyed on the text, so an edit to lib.dl reaches a process that
    already linted against it."""
    try:
        items = parse(text).items
    except ParseError:
        return {}, {}
    top = {it.name: it for it in items if isinstance(it, Decl)}
    return top, _comp_table(items)


# Lib-idiom chains: a lib relation's defining body, as the two atoms a
# hand-written site carries. `a` and `b` are (relation, arity, linking
# slot) — b's slot is a tuple of the slots the link may sit in, more than
# one where the relation is commutative there. `out` assembles the
# replacement's arguments: ('a', i) / ('b', i) take that atom's argument;
# _PARTNER takes b's other commutative slot. Optional guards hold slot
# refs: `equal` / `distinct` — pairs that must / must not render alike;
# `wild` — slots that must be wildcards. To cover a new lib relation, add an
# entry.
_PARTNER = "partner"

_CHAINS: tuple[dict, ...] = (
    {
        "prim": "neighbor",
        "a": ("step_offset", 2, 1),
        "b": ("compose", 3, (0, 1)),
        "out": (_PARTNER, ("a", 0), ("b", 2)),
    },
    {
        "prim": "jump",
        "a": ("jump_offset", 3, 2),
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

# The slot where each constructor emits its Offset or Box.
_DELTA_OUT = {"edge_inset": 2, "edge_outset": 2, "jump_offset": 2, "step_offset": 1}

# The comp whose defining rule reads one valued cell set at a cell and at
# its image, by the lib relation that takes the cell onto the image.
_IMAGE_COMPS = {"apply": "D4Map.conflict", "compose": "OffsetInvariance.mismatch"}

# The lib relation stating the other member of a two-member type.
_OTHER_MEMBER = {"Axis": "perp", "DiagAxis": "diag_perp"}


def _delta_vars(ext: list[tuple[Atom, str]]) -> set[str]:
    """Variables holding an Offset: outputs of the delta relations, plus
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
    at_decl = {lint.decl_of(key).line: key for key in lint.program_keys()}
    findings = [
        f for f in findings
        if (key := at_decl.get(f[1])) is None or not lint.allowed(f[0], key)
    ]
    findings.sort(key=lambda f: (f[1], f[0]))
    return [(cat, ln, match, raw(ln)) for cat, ln, match, _ in findings]


class _Lint:
    def __init__(self, ix: Index, lines: list[str]):
        self.ix = ix
        self.lines = lines
        self.findings: list[Finding] = []
        self.claimed: set[RelKey] = set()  # relations an earlier rule flagged
        self._const_targets: set[tuple[str, str]] | None = None
        self._comps: dict[str, Comp] | None = None
        self._records: dict[str, list[str]] | None = None
        # The category each `@allow:` directive names, by its line.
        self.allows = {
            c.line: m.group(1)
            for c in ix.program.comments
            if c.own_line and (m := _ALLOW_RE.match(c.text))
        }
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
        for key in self.program_keys():
            if key not in self.claimed:
                self.alias_inline(key)
        for key in self.program_keys():
            if key not in self.claimed:
                self.negated_use(key)
        # Rule-level and lexical rules.
        self.choice_domain()
        self.shared_read()
        for idx, info in self.program_rules():
            self.choice_tag(idx, info)
            self.typed_order(info)
            self.cross_choice(info)
            self.raw_aggregate(info)
            self.subsumed_atoms(info)
            self.lib_idiom(info)
            self.named_complement(info)
            self.negated_value(info)
            self.long_rule(info)
        self.decl_placement()
        if hints:
            for key in self.program_keys():
                if key not in self.claimed:
                    self.pass_through(key)
            for key in self.program_keys():
                if key not in self.claimed:
                    self.chain_join(key)
            for key in self.program_keys():
                if key not in self.claimed:
                    self.single_consumer(key)
            for idx, info in self.program_rules():
                self.domain_enumerator(info)
                self.argmax(idx, info)
                self.const_join(info)
                self.comp_idiom(info)
            self.common_subexpr()
        return self.findings

    # --- shared views ---

    def program_keys(self) -> list[RelKey]:
        return [
            (scope, name)
            for scope in PROGRAM_SCOPES
            for name in self.ix.decls.get(scope, {})
        ]

    def program_rules(self) -> list[tuple[int, RuleInfo]]:
        return [
            (i, info)
            for i, info in enumerate(self.ix.rules)
            if info.scope in PROGRAM_SCOPES and not info.rule.grid
            and not info.rule.sub
        ]

    def decl_of(self, key: RelKey) -> Decl:
        return self.ix.decls[key[0]][key[1]]

    def allowed(self, cat: str, key: RelKey) -> bool:
        """Whether the relation carries an `@allow:` directive naming this
        category, on the line above its declaration: the author kept the
        relation against that category, so it does not fire here."""
        return self.allows.get(self.decl_of(key).line - 1) == cat

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

    def determined_params(self) -> set[str]:
        determine = self.ix.decls.get("Determine", {})
        params = self.ix.decls.get("Params", {})
        return set(determine) & set(params)

    def inlinable(self, key: RelKey) -> bool:
        """Whether substituting `key` away is even on the table: a derived,
        non-interface relation whose rules and uses share its scope.
        """
        scope, name = key
        if scope == "Params" or key == (TOP, "out"):
            return False
        if scope in ("Determine", "Params") and name in self.determined_params():
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
        exempt |= {("Determine", n) for n in self.determined_params()}
        exempt |= {("Params", n) for n in self.determined_params()}
        dead: set[RelKey] = set()
        changed = True
        while changed:
            changed = False
            for key in self.program_keys():
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
        inline, negatable = _lib_inline(_lib_source())
        if self.ix.resolve(key[0], atom.qual, atom.name)[0] == EXTERN \
                and atom.qual is None and atom.name in inline \
                and atom.name not in negatable \
                and any(u.role == "neg" for u in self.uses(key)):
            return  # the rename is what lets Souffle negate the relation
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
        if not defs or any(not self._projection(d, key[0]) for d in defs):
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
        return MESSAGES["complement-rewrite"].format(
            name=key[1], args=", ".join(canon),
            parts="`" + ", ".join(parts) + "`")

    def _projection(self, d: Rule, scope: str) -> bool:
        """The rule projects a single positive atom: negating the head is
        negating the atom with the dropped columns wildcarded. A dropped
        variable used twice constrains the atom, so it blocks the rewrite.
        So does a dropped column inside a record or constructor argument:
        Souffle cannot ground a wildcard inside a record under negation.
        A lib inline atom negates only when its expansion introduces no
        variable and the use binds every column."""
        if d.body is None or len(d.body) != 1 or not isinstance(d.body[0], Atom):
            return False
        atom = d.body[0]
        inline, negatable = _lib_inline(_lib_source())
        if self.ix.resolve(scope, atom.qual, atom.name)[0] == EXTERN \
                and atom.qual is None and atom.name in inline:
            head_vars = {a.name for a in d.head.args if isinstance(a, Var)}
            if atom.name not in negatable or literal_vars(atom) - head_vars \
                    or any(_has_wild(a) for a in atom.args):
                return False
        counts: dict[str, int] = {}
        for arg in d.body[0].args:
            for v in term_vars(arg):
                counts[v] = counts.get(v, 0) + 1
        head_ok = all(
            isinstance(a, Var) and a.name in counts for a in d.head.args
        )
        head_vars = {a.name for a in d.head.args if isinstance(a, Var)}
        nested_drop = any(
            isinstance(arg, (Rec, Ctor))
            and (_has_wild(arg) or term_vars(arg) - head_vars)
            for arg in d.body[0].args
        )
        return head_ok and not nested_drop and all(
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
        if consumer == key or consumer[0] in (EXTERN, "Params") \
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
                   f"`{key[1]}` only feeds `{consumer[1]}`"
                   + keep_line("pass-through"))

    def single_consumer(self, key: RelKey) -> None:
        """Hint: one rule, one positive use, a two-literal body. The
        corpus both inlines and keeps this shape — the name's value is the
        call. `// @allow: single-consumer — <reason>` above the declaration
        states that call, and silences the hint for that relation."""
        if key[1] == "impl_choice":
            return  # the corpus-wide case enumerator keeps its name
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
                   f"`{key[1]}` has one clause and one use "
                   f"(line {uses[0].line})" + keep_line("single-consumer"))

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
                f"`{key[1]}.{decl.fields[col].name}` only joins `{q[1]}`"
                + keep_line("chain-join"),
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

    def choice_domain(self) -> None:
        """A `choice-domain` declaration in program code: the relation
        keeps one arbitrary tuple per key, so which one it keeps is a
        choice the program does not state."""
        for scope in PROGRAM_SCOPES:
            for name, decl in self.ix.decls.get(scope, {}).items():
                if not decl.choice_domain:
                    continue
                self.add(
                    "choice-domain", decl.line,
                    MESSAGES["choice-domain"].format(
                        name=name, over=", ".join(decl.choice_domain)),
                )

    def shared_read(self) -> None:
        """A shared parameter some case never reads. A shared parameter
        serves every case, so a case that reads none of it holds a
        parameter of its own, under that case's marker.

        Reads come from a dataflow walk back from `out` under each case:
        a rule joins the walk when its head is already reached and its
        own Choice tag admits the case. A lib instance is opaque, so
        every relation under it collapses to the instance and an input
        there reaches every output; the walk over-approximates the
        reads, and so only misses a case, never invents one.
        """
        shared = shared_params("\n".join(self.lines))
        universes = self._case_universes()
        if not shared or not universes:
            return
        params = self.ix.decls.get("Params", {})
        rules = self._flow_rules()
        for cases in universes:
            live = self._live_relations(rules, cases)
            for name in sorted(shared):
                decl = params.get(name)
                node = self._flow_node("Params", None, name)
                missing = sorted(c for c in cases if node not in live[c])
                if decl is None or not missing:
                    continue
                self.add(
                    "shared-read", decl.line,
                    MESSAGES["shared-read"].format(
                        name=name,
                        cases=", ".join(f"`${c}()`" for c in missing)),
                )

    def _case_universes(self) -> list[frozenset[str]]:
        """The case sets `Choice` ranges over: its branch names, or, for a
        record `Choice`, the branch names of each component in turn."""
        types = {it.name: it for it in self.ix.program.items
                 if isinstance(it, TypeDecl)}
        choice = types.get("Choice")
        if choice is None:
            return []
        if len(choice.branches) > 1:
            return [frozenset(choice.branches)]
        return [
            frozenset(component.branches)
            for field in self.records().get("Choice", [])
            if (component := types.get(field)) and len(component.branches) > 1
        ]

    def _flow_node(self, scope: str, qual: str | None, name: str) -> tuple[str, str]:
        """The dataflow node an atom reads or writes. A qualified name
        under an opaque lib instance collapses to that instance."""
        if qual is None:
            for s in (*self.ix.chain(scope), TOP):
                if name in self.ix.decls.get(s, {}):
                    return (s, name)
            return (EXTERN, name)
        for hop in qual.split("."):
            at, init = next(
                ((s, i) for s in (*self.ix.chain(scope), TOP)
                 if (i := self.ix.inits.get(s, {}).get(hop))),
                (scope, None),
            )
            if init is None or init.comp not in self.ix.decls:
                # An opaque instance keys by where it is declared, so its
                # own rules and its readers meet at one node.
                return (at, f"{hop}.")
            scope = init.comp
        for s in self.ix.chain(scope):
            if name in self.ix.decls.get(s, {}):
                return (s, name)
        return (scope, f"{qual}.{name}")

    def _flow_rules(self) -> list[tuple[tuple, set[tuple], set[str]]]:
        """Each rule as its head node, the nodes its body reads, and the
        Choice tags its head states."""
        out = []
        for info in self.ix.rules:
            head = self._flow_node(
                info.scope, info.rule.head.qual, info.rule.head.name)
            body = {
                self._flow_node(info.scope, a.qual, a.name)
                for a in _all_atoms(body_literals(info.rule))
            }
            tags = set()
            for arg in info.rule.head.args:
                tags |= _ctor_names(arg)
            out.append((head, body - {head}, tags))
        return out

    def _live_relations(
        self, rules: list[tuple[tuple, set[tuple], set[str]]],
        cases: frozenset[str],
    ) -> dict[str, set[tuple]]:
        """The relations each case's derivation of `out` reads.

        An untagged rule takes the tags of the relations it reads, to a
        fixpoint, so a stage between a tagged rule and its consumer keeps
        the case it serves.
        """
        own = [tags & cases for _, _, tags in rules]
        rule_tags = [set(t) for t in own]
        rel_tags: dict[tuple, set[str]] = {}
        changed = True
        while changed:
            changed = False
            for i, (head, body, _) in enumerate(rules):
                new = set(own[i])
                if not own[i]:
                    for node in body:
                        new |= rel_tags.get(node, set())
                if new != rule_tags[i]:
                    rule_tags[i] = new
                    changed = True
                held = rel_tags.setdefault(head, set())
                if not new <= held:
                    held |= new
                    changed = True
        live: dict[str, set[tuple]] = {}
        for case in cases:
            reached = {self._flow_node(TOP, None, "out")}
            grew = True
            while grew:
                grew = False
                for i, (head, body, _) in enumerate(rules):
                    if head not in reached:
                        continue
                    if rule_tags[i] and case not in rule_tags[i]:
                        continue
                    for node in body:
                        if node not in reached:
                            reached.add(node)
                            grew = True
            live[case] = reached
        return live

    def typed_order(self, info: RuleInfo) -> None:
        """An order read off a type that has none: a comparison or a
        `min`/`max` over a variable typed by an ARC value type, or such a
        variable fed to `Ordinal`. A number-typed variable, a distance
        among them, is program style and stays. Equality and inequality
        state identity, not order, and stay."""
        unordered = _unordered_types(_lib_source())
        types = self._var_types(info)

        def named(term: Term) -> list[tuple[str, str]]:
            return [
                (v, t)
                for v in sorted(term_vars(term))
                for t in sorted(types.get(v, ()))
                if t in unordered
            ]

        seen: set[tuple[int, str]] = set()

        def flag(line: int, term: Term, how: str) -> None:
            for v, t in named(term):
                if (line, v) in seen:
                    continue
                seen.add((line, v))
                self.add(
                    "typed-order", line,
                    MESSAGES["typed-order"].format(how=how, var=v, type=t),
                )

        for lit in body_literals(info.rule):
            if isinstance(lit, Cmp):
                if lit.op in _ORDER_OPS:
                    flag(lit.line, lit.lhs, f"`{lit.op}` compares")
                    flag(lit.line, lit.rhs, f"`{lit.op}` compares")
                for side in (lit.lhs, lit.rhs):
                    if isinstance(side, Agg) and side.op in _ORDER_AGGS \
                            and side.expr is not None:
                        flag(lit.line, side.expr, f"`{side.op}` orders")
        for atom in (info.rule.head, *_all_atoms(body_literals(info.rule))):
            if atom.name != _ORDINAL_SET:
                continue
            _, chain = self._atom_cols(info.scope, atom)
            if _ORDINAL_COMP not in chain or len(atom.args) != 2:
                continue
            flag(atom.line, atom.args[1], f"`{_ORDINAL_COMP}` ranks")

    # --- column types ---

    def _var_types(self, info: RuleInfo) -> dict[str, set[str]]:
        """Each rule variable and the declared types of the columns that
        bind it."""
        out: dict[str, set[str]] = {}

        def bind(arg: Term, type_: str) -> None:
            if isinstance(arg, Var):
                out.setdefault(arg.name, set()).add(type_)
            elif isinstance(arg, Rec):
                fields = self.records().get(type_, [])
                for sub, ft in zip(arg.args, fields, strict=False):
                    bind(sub, ft)

        for atom in (info.rule.head, *_all_atoms(body_literals(info.rule))):
            cols, _ = self._atom_cols(info.scope, atom)
            for i, arg in enumerate(atom.args):
                if i < len(cols) and cols[i]:
                    bind(arg, cols[i])
        return out

    def records(self) -> dict[str, list[str]]:
        """Every record type in scope, the solver's own over lib's."""
        if self._records is None:
            self._records = (
                _lib_records(_lib_source())
                | _record_fields(self.ix.program.items)
            )
        return self._records

    def comps(self) -> dict[str, Comp]:
        """Every component in scope, the solver's own over lib's."""
        if self._comps is None:
            _, lib = _lib_scopes(_lib_source())
            self._comps = lib | _comp_table(self.ix.program.items)
        return self._comps

    def _atom_cols(self, scope: str, atom: Atom) -> tuple[list[str], list[str]]:
        """The declared type of each of an atom's columns, and the comps
        the atom resolved through, outermost first. A column whose type
        is unknown comes back empty."""
        if atom.qual is None:
            key = self.ix.resolve(scope, None, atom.name)
            decl = self.ix.decls.get(key[0], {}).get(key[1])
            if decl is None:
                decl = _lib_scopes(_lib_source())[0].get(atom.name)
            return ([f.type for f in decl.fields] if decl else []), []
        comp, subst = None, {}
        chain: list[str] = []
        for hop in atom.qual.split("."):
            init = (
                self._comp_init(comp, hop, subst) if comp is not None
                else next(
                    (i for s in (*self.ix.chain(scope), TOP)
                     if (i := self.ix.inits.get(s, {}).get(hop))),
                    None,
                )
            )
            if init is None:
                return [], chain
            comp = init.comp
            chain.append(comp)
            params = self.comps()[comp].params if comp in self.comps() else []
            subst = {
                p: subst.get(t, t)
                for p, t in zip(params, init.targs, strict=False)
            }
        return self._comp_cols(comp, atom.name, subst, chain)

    def _comp_init(
        self, comp: str, inst: str, subst: dict[str, str],
    ) -> Init | None:
        """An `.init` inside a component or the components it inherits,
        its type arguments substituted through `subst`."""
        for name, sub in self._comp_walk(comp, subst):
            for it in self.comps()[name].items:
                if isinstance(it, Init) and it.inst == inst:
                    return Init(
                        it.inst, it.comp,
                        [sub.get(t, t) for t in it.targs], it.line,
                    )
        return None

    def _comp_cols(
        self, comp: str, name: str, subst: dict[str, str], chain: list[str],
    ) -> tuple[list[str], list[str]]:
        """A relation's column types inside a component, read through its
        inheritance chain."""
        for base, sub in self._comp_walk(comp, subst):
            if base not in chain:
                chain.append(base)
            for it in self.comps()[base].items:
                if isinstance(it, Decl) and it.name == name:
                    return [sub.get(f.type, f.type) for f in it.fields], chain
        return [], chain

    def _comp_walk(
        self, comp: str, subst: dict[str, str],
    ) -> Iterator[tuple[str, dict[str, str]]]:
        """A component and the ones it inherits, each with the type
        substitution that reaches it."""
        seen: set[str] = set()
        cur: str | None = comp
        while cur is not None and cur in self.comps() and cur not in seen:
            seen.add(cur)
            yield cur, subst
            c = self.comps()[cur]
            if c.base is None or c.base not in self.comps():
                return
            subst = {
                p: subst.get(t, t)
                for p, t in zip(
                    self.comps()[c.base].params, c.base_targs, strict=False,
                )
            }
            cur = c.base

    def choice_tag(self, idx: int, info: RuleInfo) -> None:
        """Rules identical but for a distinct nullary constructor in one
        head argument: merge on a Choice variable. Fires only when some
        relation's facts already enumerate both tags — without one, the
        merge must add an enumerator and comes out larger."""
        rule = info.rule
        if rule.body is None:
            return
        for jdx, other in self.program_rules():
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
                    MESSAGES["choice-tag"].format(
                        one=_term_str(tags[1]), other=_term_str(tags[0])),
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
                    MESSAGES["cross-choice"].format(
                                tags=", ".join(f"`${t}()`" for t in sorted(tags))),
                )

    def raw_aggregate(self, info: RuleInfo) -> None:
        """An aggregate in a program rule: read it through a lib comp."""
        for body in _conjunctions(info.rule):
            for lit in body:
                if not isinstance(lit, Cmp):
                    continue
                for side in (lit.lhs, lit.rhs):
                    if isinstance(side, Agg):
                        self.add(
                            "raw-aggregate", lit.line,
                            MESSAGES["raw-aggregate"].format(op=side.op),
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
                                     MESSAGES["subsumed-atom-twice"].format(
                                         atom=_atom_str(b)))
                    elif all(
                        isinstance(x, Wild) or _term_str(x) == _term_str(y)
                        for x, y in pairs
                    ):
                        self.add(
                            "subsumed-atom", a.line,
                            MESSAGES["subsumed-atom"].format(
                                atom=_atom_str(a), other=_atom_str(b)),
                        )

    def lib_idiom(self, info: RuleInfo) -> None:
        """A lib relation's defining chain written out by hand, with the
        linking value confined to the chain: name it with the relation.
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
                    # would-be position operand holds an Offset, the chain is
                    # not the relation.
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

    def comp_idiom(self, info: RuleInfo) -> None:
        """Hint: a lib comp's defining rule, or a top-level lib relation,
        written out by hand — one relation read twice with a `!=` between
        the two reads. Which lib component that is depends on how the reads
        differ, and a pair of reads that stands for something else is not
        flagged; `_comp_idiom_fix` decides both."""
        rule = info.rule
        if rule.body is None or rule.grid:
            return
        head_vars = literal_vars(rule.head)
        seen: set[tuple[int, int]] = set()
        for flat in _flatten(rule.body):
            neq = {
                frozenset((lit.lhs.name, lit.rhs.name))
                for lit in flat
                if isinstance(lit, Cmp) and lit.op == "!="
                and isinstance(lit.lhs, Var) and isinstance(lit.rhs, Var)
            }
            if not neq:
                continue
            atoms = [lit for lit in flat if isinstance(lit, Atom)]
            # The valued sets: solver relations, comp instances, and the
            # runner's grids — not lib's record arithmetic.
            local = [
                a for a in atoms
                if self.ix.resolve(info.scope, a.qual, a.name)[0] != EXTERN
            ]
            sets = [
                a for a in atoms
                if a in local or a.qual is not None or a.name in EXAMPLE_SRC
            ]
            for i, a in enumerate(sets):
                for b in sets[i + 1:]:
                    if (id(a), id(b)) in seen:
                        continue
                    fix = self._comp_idiom_fix(
                        info.scope, a, b, atoms, local, neq, head_vars)
                    if fix is not None:
                        seen.add((id(a), id(b)))
                        self.add("comp-idiom", a.line, fix)

    def _comp_idiom_fix(
        self, scope: str, a: Atom, b: Atom, atoms: list[Atom],
        local: list[Atom], neq: set[frozenset[str]], head_vars: set[str],
    ) -> str | None:
        if (a.qual, a.name) != (b.qual, b.name) or len(a.args) != len(b.args):
            return None
        if len(a.args) < 2:
            return None
        if sum((x.qual, x.name) == (a.qual, a.name) for x in atoms) > 2:
            return None
        diff = [
            i for i, (x, y) in enumerate(zip(a.args, b.args, strict=True))
            if _term_str(x) != _term_str(y)
        ]
        compared = [
            i for i in diff
            if isinstance(a.args[i], Var) and isinstance(b.args[i], Var)
            and frozenset((a.args[i].name, b.args[i].name)) in neq
        ]
        if len(compared) != 1:
            return None
        v = compared[0]
        x, y = a.args[v].name, b.args[v].name
        if x in head_vars or y in head_vars:
            return None
        # Some other atom reads both compared values, a solver pairing map
        # or a lib relation such as `same_line`: it relates the pair, so
        # this is not a clash.
        if any(
            z is not a and z is not b and {x, y} <= literal_vars(z)
            for z in atoms
        ):
            return None
        pair = f"`{_atom_str(a)}, {_atom_str(b)}, {x} != {y}`"
        if len(diff) == 1:
            # A hint names a lib relation. A disequality over a
            # two-member type states the other member, so the hint is
            # the lib relation over that type, where lib holds one.
            cols, _ = self._atom_cols(scope, a)
            t = cols[v] if v < len(cols) else ""
            if _enum_sizes(_lib_source()).get(t) != 2:
                return None
            rel = _OTHER_MEMBER.get(t)
            if rel is None:
                return None
            return MESSAGES["other-member"].format(
                pair=pair, rel=rel, x=x, y=y)
        if len(diff) != 2:
            return None
        [p] = [i for i in diff if i != v]
        if not (isinstance(a.args[p], Var) and isinstance(b.args[p], Var)):
            return None
        link = self._image_link(a.args[p].name, b.args[p].name, atoms)
        if link is None:
            return None
        return MESSAGES["image-link"].format(
            pair=pair, link=link, comp=_IMAGE_COMPS[link])

    def _image_link(self, p: str, q: str, atoms: list[Atom]) -> str | None:
        """The lib relation carrying p onto q — `apply` for a D4 image,
        `compose` for a shift — when one sits in the body."""
        for atom in atoms:
            if atom.qual is not None or atom.name not in _IMAGE_COMPS:
                continue
            if len(atom.args) != 3:
                continue
            names = [x.name if isinstance(x, Var) else None for x in atom.args]
            src = names[:2] if atom.name == "compose" else names[1:2]
            if names[2] in (p, q) and ({p, q} - {names[2]}) & set(src):
                return atom.name
        return None

    def negated_value(self, info: RuleInfo) -> None:
        """`prim(..., K), K != c`, with K read nowhere else: `!prim(..., c)`
        says it directly. Only at a lib inline relation whose negation
        Souffle accepts, and only when the rewrite binds every column."""
        rule = info.rule
        if rule.body is None or rule.grid:
            return
        _, negatable = _lib_inline(_lib_source())
        head_vars = literal_vars(rule.head)
        flats = list(_flatten(rule.body))
        atoms = {id(l): l for f in flats for l in f if isinstance(l, Atom)}
        for atom in atoms.values():
            if atom.qual is not None or atom.name not in negatable \
                    or self.ix.resolve(info.scope, None, atom.name)[0] != EXTERN \
                    or any(_has_wild(a) for a in atom.args):
                continue
            for i, arg in enumerate(atom.args):
                if not isinstance(arg, Var) or arg.name in head_vars:
                    continue
                v = arg.name
                if sum(1 for a in atom.args if v in term_vars(a)) != 1:
                    continue
                const = self._sole_complement(atom, v, flats)
                if const is None:
                    continue
                rest = [a for j, a in enumerate(atom.args) if j != i]
                if not all(
                    self._bound_elsewhere(atom, w, flats)
                    for a in rest for w in term_vars(a)
                ):
                    continue
                new_atom = Atom(atom.qual, atom.name,
                                tuple(const if j == i else a for j, a in enumerate(atom.args)),
                                atom.line)
                self.add("negated-value", atom.line,
                         MESSAGES["negated-value"].format(
                             atom=_atom_str(atom), var=v,
                             value=_term_str(const),
                             rewritten=_atom_str(new_atom)))
                break

    def _sole_complement(
        self, atom: Atom, v: str, flats: list[list[Lit]],
    ) -> Term | None:
        """The constant `v` is compared against by `!=` in one literal, the
        only other literal reading `v`, in every expansion holding `atom`."""
        const: Term | None = None
        for flat in flats:
            if not any(l is atom for l in flat):
                continue
            others = [lit for lit in flat if lit is not atom and v in literal_vars(lit)]
            if len(others) != 1 or not isinstance(others[0], Cmp) or others[0].op != "!=":
                return None
            cmp = others[0]
            if isinstance(cmp.lhs, Var) and cmp.lhs.name == v:
                t = cmp.rhs
            elif isinstance(cmp.rhs, Var) and cmp.rhs.name == v:
                t = cmp.lhs
            else:
                return None
            if not isinstance(t, (Num, MacroConst)) or (const is not None and const != t):
                return None
            const = t
        return const

    @staticmethod
    def _bound_elsewhere(atom: Atom, w: str, flats: list[list[Lit]]) -> bool:
        """`w` is read by a literal other than `atom` in every expansion
        holding `atom`, so the negation of `atom` leaves it grounded."""
        return all(
            any(lit is not atom and not isinstance(lit, (Neg, Cmp)) and w in literal_vars(lit)
                for lit in flat)
            for flat in flats if any(l is atom for l in flat)
        )

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
                MESSAGES["named-complement"].format(
                        atom=_atom_str(atom), cmp=_lit_str(cmp),
                        rewritten=f"{qual}{atom.name}({_term_str(other)})"),
            )

    def decl_placement(self) -> None:
        """Every reference inside one section or comp the declaration is
        not in: move the declaration there. `out` is the interface, declared
        under `Choice`, so its placement is fixed."""
        for name, decl in self.ix.decls[TOP].items():
            if name == "out":
                continue
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
                 MESSAGES["decl-placement"].format(name=name, spot=spot))

    def long_rule(self, info: RuleInfo) -> None:
        """A rule whose whole body stands on its first line and runs past
        the limit. The code the limit counts ends at the terminating
        period, so a `.plan` after it counts for nothing; a body that runs
        on to later lines is already wrapped and stays."""
        rule = info.rule
        if rule.body is None:
            return
        text = self.lines[rule.line - 1] if rule.line <= len(self.lines) else ""
        code = PLAN_RE.sub("", text.split("//")[0]).rstrip()
        if not code.endswith("."):
            return
        if len(code) > LINE_LIMIT:
            self.add("long-rule", rule.line,
                     MESSAGES["long-rule"].format(
                             width=len(code), limit=LINE_LIMIT))

    # --- hint rules ---

    def domain_enumerator(self, info: RuleInfo) -> None:
        """An `*_elem` atom whose variable another positive atom already
        binds. An `inline` relation does not count as a binder: it
        substitutes away, so its arguments stay ungrounded. When the binder's
        column has a wider type than the atom's element type, the atom
        narrows the binding and stays."""
        rule = info.rule
        if rule.body is None:
            return
        flats = list(_flatten(rule.body))
        for atom in {id(l): l for f in flats for l in f
                     if isinstance(l, Atom)}.values():
            if not atom.name.endswith("_elem") or len(atom.args) != 1:
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
            if binder is not None and not self._narrows(info.scope, atom, binder, v):
                self.add(
                    "domain-enumerator", atom.line,
                    MESSAGES["domain-enumerator"].format(
                        atom=_atom_str(atom), var=v, binder=binder.name),
                )

    def _narrows(self, scope: str, elem: Atom, binder: Atom, v: str) -> bool:
        """The elem atom's type is a strict subtype of the column that
        binds v: the atom narrows the binding and stays."""
        key = self.ix.resolve(scope, binder.qual, binder.name)
        decl = self.ix.decls.get(key[0], {}).get(key[1])
        if decl is None:
            return False
        elem_type, wider_of = _elem_tables(_lib_source())
        wider = wider_of.get(elem_type.get(elem.name, ""), set())
        for i, arg in enumerate(binder.args):
            if isinstance(arg, Var) and arg.name == v and i < len(decl.fields):
                return decl.fields[i].type in wider
        return False

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
        negated: an aggregate in disguise. A head that takes, from each
        of the two atoms, a variable the other does not bind stays
        quiet: it states a pairwise comparison, not an extremum."""
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
            head_vars = literal_vars(rule.head)
            v0, v1 = literal_vars(atoms[0]), literal_vars(atoms[1])
            if (v0 - v1) & head_vars and (v1 - v0) & head_vars:
                return
        key = self.rule_head_key(idx)
        uses = self.uses(key)
        if uses and all(u.role == "neg" for u in uses):
            self.add("argmax", rule.line,
                     MESSAGES["argmax"].format(name=rule.head.name))

    def const_join(self, info: RuleInfo) -> None:
        """Hint: a variable internal to a rule's Params reads. The join
        states no per-example thing — it derives a task constant, which
        the corpus names in its own relation. Quiet inside Params and
        under a head that is itself task-constant: those are the named
        forms."""
        rule = info.rule
        if rule.body is None or info.scope == "Params":
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
                   f"name the derived constant in Params")
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
        """Where an atom's derivation comes from: 'const' for Params data
        and grid-free lib relations, 'example' for the runner's per-example
        fills, else the (scope, name) node the taint runs through — the
        instance for qualified atoms, the declaring scope for bare ones."""
        if atom.qual is not None:
            hop = atom.qual.split(".")[0]
            for s in (*self.ix.chain(scope), TOP):
                init = self.ix.inits.get(s, {}).get(hop)
                if init is not None:
                    if init.comp == "Params":
                        return "const"
                    return (s, hop)
            return "example"
        key = self.ix.resolve(scope, None, atom.name)
        if key[0] == EXTERN:
            return "example" if atom.name in EXAMPLE_SRC else "const"
        if key[0] == "Params":
            return "const"
        return key

    def common_subexpr(self) -> None:
        """The same literal run, up to renaming, in two bodies of one
        scope. A cross-scope repeat is the determination architecture re-deriving a
        solve rule over the examples — the comp boundary blocks sharing.
        A pair that spans choices — different sections, or heads bound to
        different choice tags — stays quiet: sharing across choices is
        not a simplification of either choice."""
        seen: dict[tuple[str, ...], RuleInfo] = {}
        reported: set[tuple[int, int]] = set()
        for _, info in self.program_rules():
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
        look, so it keeps a higher bar. A later body that negates the
        earlier head is a defect-negation universal: it restates that
        rule's frame by construction, so the pair stays quiet."""
        if prev.section != cur.section:
            return None
        ph, ch = prev.rule.head, cur.rule.head
        if _tags(_atom_str(ph)) & self.choice_tags \
                != _tags(_atom_str(ch)) & self.choice_tags:
            return None
        if any(isinstance(lit, Neg) and lit.atom.qual is None
               and lit.atom.name == ph.name
               for body in _flatten(cur.rule.body or [])
               for lit in body):
            return None
        msg = MESSAGES["common-subexpr"].format(
            width=width, name=ph.name, line=prev.rule.line)
        if _canon_window([ph]) == _canon_window([ch]):
            return msg + MESSAGES["merge-tails"]
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



def _ctor_names(term: Term) -> set[str]:
    """Constructor names anywhere inside a term."""
    names: set[str] = set()
    stack: list[Term] = [term]
    while stack:
        t = stack.pop()
        if isinstance(t, Ctor):
            names.add(t.name)
        if isinstance(t, (Ctor, Rec, Call)):
            stack.extend(t.args)
        elif isinstance(t, BinOp):
            stack.extend((t.lhs, t.rhs))
        elif isinstance(t, UnOp):
            stack.append(t.arg)
    return names

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


def _has_wild(t: Term) -> bool:
    """Whether a wildcard sits anywhere inside the term."""
    stack: list[Term] = [t]
    while stack:
        x = stack.pop()
        if isinstance(x, Wild):
            return True
        if isinstance(x, (Ctor, Rec, Call)):
            stack.extend(x.args)
    return False


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
