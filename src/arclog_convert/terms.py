"""The helpers on terms, literals and clauses of a Souffle program: the
renaming of relations, the substitution of terms, the variable uses, the
inlining of helper clauses and the records' equalities."""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from engine.program import (
    Atom,
    AtomLiteral,
    Comparison,
    ConstructorTerm,
    Disjunction,
    RecordTerm,
    RelationName,
    Unit,
    Variable,
    Wildcard,
    ComparisonOperator,
)
from dataclasses import fields as dc_fields, is_dataclass, replace as dc_replace
from arclog_convert.literals import collect_vars
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from arclog_convert.lib import Lib


def agrees_but_wildcards(a, b) -> bool:
    """Whether the terms `a` and `b` are the same wherever neither is `_`,
    and a variable stands only against `_` or itself."""
    if isinstance(a, Wildcard) or isinstance(b, Wildcard):
        return True
    if isinstance(a, RecordTerm) and isinstance(b, RecordTerm):
        return len(a.args) == len(b.args) and all(agrees_but_wildcards(x, y) for x, y in zip(a.args, b.args))
    if isinstance(a, ConstructorTerm) and isinstance(b, ConstructorTerm):
        return a.name == b.name and len(a.args) == len(b.args) and all(
            agrees_but_wildcards(x, y) for x, y in zip(a.args, b.args))
    return False


def ctor_names(t) -> tuple[str, ...]:
    if isinstance(t, ConstructorTerm):
        return (t.name,) + sum((ctor_names(a) for a in t.args), ())
    if isinstance(t, RecordTerm):
        return sum((ctor_names(a) for a in t.args), ())
    return ()


MOVED_RELS: dict[str, str] = {}
"""The solver at hand's relations of an expanded instance that a witness
name spells, `tiling.divider`, by the relation of the shape that stands
for each, `tiling_divider`."""


def name_of(n: str, many: set[str] = frozenset()) -> str:
    """A witness-file case name in arcdata's spelling; `many` holds the
    parameters whose @derive lines give several proposers, a derived side
    per proposer."""
    if n.startswith("&"):
        return n
    parts = [p.strip() for p in n.split("&")]
    out = []
    for p in parts:
        m = re.match(r"([\w.]+)=(\w+)", p)
        if m:
            rel, side = m.groups()
            side = {"stored": "$Stored", "derived": "$Derived"}.get(side, side if rel in many else "$Derived")
            rel = MOVED_RELS.get(rel, rel)
            out.append(f"&{rel}={side}")
        elif p in ("concept", "any", "other", "derived", "stored"):
            out.append(p)
        else:
            out.append(p if p.startswith("$") else "$" + p)
    return out[0] if len(out) == 1 else "(" + " ".join(out) + ")"


NEG_OP = {ComparisonOperator.LT: ComparisonOperator.GE, ComparisonOperator.GE: ComparisonOperator.LT,
          ComparisonOperator.LE: ComparisonOperator.GT, ComparisonOperator.GT: ComparisonOperator.LE,
          ComparisonOperator.EQ: ComparisonOperator.NE, ComparisonOperator.NE: ComparisonOperator.EQ}


def record_eqs(u: Unit, fields_of=None) -> Unit:
    """The clause with each `V = [..]` resolved: at the body's top level V
    is the record in every other place, and where each branch of a
    disjunction gives V a record of one width, V is a record of one variable
    per component, `V_1`, `V_2`, ..., each branch gives the components, and
    a component that a branch alone makes is that component's variable."""
    if u.body is None:
        return u
    taken: set[str] = set()
    collect_vars(list(u.body), taken)
    collect_vars([AtomLiteral(u.head, False)], taken)

    def fresh(base: str) -> Variable:
        n = base
        k = 2
        while n in taken:
            n, k = f"{base}{k}", k + 1
        taken.add(n)
        return Variable(n)

    def eq_of(l):
        if not (isinstance(l, Comparison) and l.op == ComparisonOperator.EQ):
            return None
        for v, t in ((l.lhs, l.rhs), (l.rhs, l.lhs)):
            if isinstance(v, Variable) and isinstance(t, RecordTerm):
                vs: set[str] = set()
                collect_vars([AtomLiteral(Atom(RelationName((), "_"), (t,), 0), False)], vs)
                if v.name not in vs:
                    return v.name, t
        return None

    def uses(lits, head, v: str) -> int:
        n = 0
        for l in lits:
            if isinstance(l, AtomLiteral) and not (not l.atom.relation.instances and l.atom.relation.name == "impl_choice"):
                vs: list[str] = []
                def walk(t):
                    if isinstance(t, Variable):
                        vs.append(t.name)
                    for a in getattr(t, "args", ()) or ():
                        walk(a)
                for a in l.atom.args:
                    walk(a)
                n += vs.count(v)
            elif isinstance(l, (Comparison, Disjunction)):
                vs2: set[str] = set()
                collect_vars([l], vs2)
                n += v in vs2
        hv: set[str] = set()
        collect_vars([AtomLiteral(head, False)], hv)
        return n + (v in hv)

    def fill(t, v: str, top: bool = True):
        """The record with each wildcard a fresh variable, named after its
        field where the record's type is known."""
        if isinstance(t, Wildcard):
            return fresh(f"{v}_w")
        if isinstance(t, RecordTerm):
            names = (fields_of(u, v) if fields_of and top else None) or []
            return RecordTerm(tuple(fresh(f"{v}_{names[k]}") if isinstance(a, Wildcard) and k < len(names)
                                    and len(names) == len(t.args) else fill(a, v, False)
                                    for k, a in enumerate(t.args)))
        return t

    head, body = u.head, list(u.body)
    changed = True
    while changed:
        changed = False
        for i, l in enumerate(body):
            got = eq_of(l)
            if got is None:
                continue
            v, t = got
            rest = body[:i] + body[i + 1:]
            if uses(rest, head, v) > 1:
                t = fill(t, v)
            m = {v: t}
            head = subst_terms(head, m)
            body = [subst_terms(x, m) for x in rest]
            changed = True
            break
    # a record a disjunction's branches give
    out = []
    for i, l in enumerate(body):
        if not isinstance(l, Disjunction):
            out.append(l)
            continue
        outside: set[str] = set()
        collect_vars(body[:i] + body[i + 1:], outside)
        collect_vars([AtomLiteral(head, False)], outside)
        per = [[(j, eq_of(x)) for j, x in enumerate(b) if eq_of(x) is not None] for b in l.branches]
        cands = {v for b in per for _, (v, _) in b if v in outside}
        for v in sorted(cands):
            got = [[(j, t) for j, (w, t) in b if w == v] for b in per]
            if any(len(g) > 1 for g in got) or len({len(g[0][1].args) for g in got if g}) != 1:
                continue
            width = next(len(g[0][1].args) for g in got if g)
            names = fields_of(u, v) if fields_of else None
            if names is None or len(names) != width:
                names = [str(k + 1) for k in range(width)]
            comps = [fresh(f"{v}_{n}") for n in names]
            rec = RecordTerm(tuple(comps))
            branches = []
            for b, g in zip(l.branches, got):
                if not g:
                    branches.append(tuple(subst_terms(x, {v: rec}) for x in b))
                    continue
                j, t = g[0]
                lits = list(b[:j] + b[j + 1:])
                mine: set[str] = set()
                collect_vars(lits, mine)
                ren: dict[str, object] = {}
                eqs = []
                for c_, a in zip(comps, t.args):
                    if isinstance(a, Variable) and a.name not in outside and a.name not in ren \
                            and a.name not in {x.name for x in comps}:
                        ren[a.name] = c_
                    else:
                        eqs.append(Comparison(ComparisonOperator.EQ, c_, ren.get(a.name, a) if isinstance(a, Variable) else a, l.line))
                lits = [subst_terms(x, ren) for x in lits] + eqs
                branches.append(tuple(lits))
            l = dc_replace(l, branches=tuple(branches))
            m = {v: rec}
            head = subst_terms(head, m)
            body = [subst_terms(x, m) if k != i else x for k, x in enumerate(body)]
            per = [[(j, eq_of(x)) for j, x in enumerate(b) if eq_of(x) is not None] for b in l.branches]
        # a record a branch alone gives: the record in the branch's other places
        branches = []
        for b in l.branches:
            b = list(b)
            again = True
            while again:
                again = False
                for j, x in enumerate(b):
                    got = eq_of(x)
                    if got is None or got[0] in outside:
                        continue
                    v, t = got
                    rest = b[:j] + b[j + 1:]
                    if uses(rest, Atom(RelationName((), "_"), (), 0), v) > 1:
                        t = fill(t, v)
                    b = [subst_terms(y, {v: t}) for y in rest]
                    again = True
                    break
            branches.append(tuple(b))
        l = dc_replace(l, branches=tuple(branches))
        out.append(l)
    if head == u.head and out == list(u.body):
        return u
    return dc_replace(u, head=head, body=tuple(out))


def walk_lits(lits):
    """Each literal of a body, those inside a disjunction's branches included."""
    for l in lits:
        yield l
        if isinstance(l, Disjunction):
            for b in l.branches:
                yield from walk_lits(b)


def rename_rel(x, old: RelationName, new: RelationName):
    """`x` with each read of relation `old` a read of `new`."""
    if isinstance(x, RelationName):
        return new if x == old else x
    if isinstance(x, tuple):
        return tuple(rename_rel(y, old, new) for y in x)
    if is_dataclass(x) and not isinstance(x, type):
        ch = {}
        for f_ in dc_fields(x):
            v = getattr(x, f_.name)
            if isinstance(v, (tuple, RelationName)) or (is_dataclass(v) and not isinstance(v, type)):
                ch[f_.name] = rename_rel(v, old, new)
        return dc_replace(x, **ch) if ch else x
    return x


def subst(x, m: dict[str, str]):
    """`x` with each variable renamed by `m`."""
    if isinstance(x, Variable):
        return Variable(m.get(x.name, x.name))
    if isinstance(x, tuple):
        return tuple(subst(y, m) for y in x)
    if is_dataclass(x) and not isinstance(x, type):
        changes = {}
        for f in dc_fields(x):
            v = getattr(x, f.name)
            if isinstance(v, (tuple, Variable)) or (is_dataclass(v) and not isinstance(v, type)):
                changes[f.name] = subst(v, m)
        return dc_replace(x, **changes) if changes else x
    return x


def subst_terms(x, m: dict):
    """`x` with each variable named in `m` replaced by its term."""
    if isinstance(x, Variable):
        return m.get(x.name, x)
    if isinstance(x, tuple):
        return tuple(subst_terms(y, m) for y in x)
    if is_dataclass(x) and not isinstance(x, type):
        changes = {}
        for f in dc_fields(x):
            v = getattr(x, f.name)
            if isinstance(v, (tuple, Variable)) or (is_dataclass(v) and not isinstance(v, type)):
                changes[f.name] = subst_terms(v, m)
        return dc_replace(x, **changes) if changes else x
    return x


def var_uses(x, counts: Counter) -> None:
    """Count each variable's occurrences in a term, a literal or a tuple of them."""
    if isinstance(x, Variable):
        counts[x.name] += 1
    elif isinstance(x, tuple):
        for y in x:
            var_uses(y, counts)
    elif is_dataclass(x) and not isinstance(x, type):
        for f_ in dc_fields(x):
            var_uses(getattr(x, f_.name), counts)


def inlined(prog, names: frozenset[str], lib: Lib):
    """`prog` with each relation of `names` written no relation: its clauses'
    bodies stand at each call, the head's variables replaced by the call's
    terms and the other variables by fresh ones, an `OR` of the bodies where
    it has several clauses. The converter passes the `inline` relations that
    its first pass writes as arclog relations."""
    if not names:
        return prog
    defs: dict[str, list[Unit]] = defaultdict(list)
    for u in prog.units:
        if u.head.relation.name in names and not u.head.relation.instances and u.body is not None:
            defs[u.head.relation.name].append(u)
    for n in names:
        assert n in defs and n not in lib.top, n
        for u in defs[n]:
            hs = [a.name for a in u.head.args if isinstance(a, Variable)]
            assert len(hs) == len(u.head.args) == len(set(hs)), (n, u.head)

    def instance(h: Unit, args, taken: set[str]) -> list:
        uses: Counter = Counter()
        var_uses(h.body, uses)
        m: dict[str, object] = {}
        hv = {a.name for a in h.head.args}

        def fresh(v: str) -> Variable:
            k, w = 1, v
            while w in taken:
                k += 1
                w = f"{v}{k}"
            taken.add(w)
            return Variable(w)
        for a, t in zip(h.head.args, args):
            m[a.name] = fresh(a.name) if isinstance(t, Wildcard) and uses[a.name] > 1 else t
        for v in uses:
            if v not in hv:
                m[v] = fresh(v)
        return expand([subst_terms(x, m) for x in h.body], taken, 0)

    def expand(lits, taken: set[str], depth: int) -> list:
        assert depth < 8
        out: list = []
        for l in lits:
            if isinstance(l, AtomLiteral) and not l.atom.relation.instances and l.atom.relation.name in defs:
                assert not l.negated, l
                bodies = [instance(h, l.atom.args, taken) for h in defs[l.atom.relation.name]]
                if len(bodies) == 1:
                    out.extend(bodies[0])
                else:
                    out.append(Disjunction(tuple(tuple(b) for b in bodies), l.atom.line))
            elif isinstance(l, Disjunction):
                out.append(dc_replace(l, branches=tuple(tuple(expand(b, taken, depth)) for b in l.branches)))
            else:
                out.append(l)
        return out

    units = []
    for u in prog.units:
        if u.head.relation.name in names and not u.head.relation.instances:
            continue
        if u.body is not None:
            taken: set[str] = set()
            collect_vars([*u.body, AtomLiteral(u.head, False)], taken)
            u = dc_replace(u, body=tuple(expand(u.body, taken, 0)))
        units.append(u)
    rels = tuple(r for r in prog.relations if r.name not in names)
    return dc_replace(prog, units=tuple(units), relations=rels)


