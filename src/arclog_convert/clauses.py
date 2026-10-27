"""`ClauseWriter`, which writes one clause body as arclog lines."""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from engine.program import (
    Aggregate,
    Atom,
    AtomLiteral,
    BoolLiteral,
    Comparison,
    ConstructorTerm,
    DefinedName,
    Disjunction,
    NumberTerm,
    RecordTerm,
    RelationName,
    Variable,
    Wildcard,
)
from souffle.printer import term as souffle_term
from arclog_convert.literals import collect_vars
from arclog_convert import libmap
from typing import TYPE_CHECKING

from arclog_convert.forms import Dead, wrap
from arclog_convert.lib import ALGEBRA_MODES, Col, field_names, field_sites, pascal
from arclog_convert.terms import NEG_OP, agrees_but_wildcards, ctor_names, subst

if TYPE_CHECKING:
    from arclog_convert.leaves import Converter, Leaf


# --------------------------------------------------------------------------
# Clause conversion


@dataclass(frozen=True)
class Site:
    """Where a kept leaf of a Souffle column is read in arclog: the column
    `label` of the arclog relation, and, for a record column of a type
    parameter or the `key` column of an instance or of an id-keyed chart's
    part, the `field` within it."""

    leaf: "Leaf"
    label: str
    field: str | None


def kept_leaf(leaf: "Leaf") -> bool:
    """The leaf is read by a site: it is no case, drop or rule leaf."""
    return leaf.kind not in ("case", "drop", "rule")


def chart_key(col, inst) -> bool:
    """Whether `col` is the `key` column of a part of an id-keyed chart: the
    column of an arclog relation that is no instance's, named `key`, which
    holds the part's id (`Converter.rigid_keyed`)."""
    return inst is None and col.name == "key"


def case_ctors(leaves: list["Leaf"], terms: list) -> set[str]:
    """The constructors that the `terms` of a column's `leaves` name at its case leaves."""
    return {x for leaf, t in zip(leaves, terms) if leaf.kind == "case" for x in ctor_names(t)}


def site_columns(c: "Converter", cols: list, inst) -> list[list[Site]]:
    """For each Souffle column of `cols` (`Converter.resolve`), the `Site`
    of each of its leaves that `kept_leaf` keeps, in order. `ClauseWriter.sites`
    writes its sites with these labels, and `names.column_map` writes
    them, so a label is chosen here alone."""
    out: list[list[Site]] = []
    for i, (col, leaves) in enumerate(cols):
        kept = [l for l in leaves if kept_leaf(l)]
        sites: list[Site] = []
        nonex = [l for l in kept if l.kind != "example"]
        if inst is not None and i == 0 and col.name == "key":
            kn_all = c.key_names.get(inst) or []
            by_path = dict(zip(c.key_paths.get(inst, []), kn_all))
            names_by_leaf = dict(zip(map(id, kept), kn_all)) if len(kn_all) == len(kept) else \
                dict(zip(map(id, nonex), kn_all)) if len(kn_all) == len(nonex) else \
                {id(l): by_path[l.path] for l in nonex} if all(l.path in by_path for l in nonex) else {}
            names = [names_by_leaf[id(l)] for l in nonex] if names_by_leaf else \
                [n for n in kn_all if n != "E"] or [pascal(l.name) for l in nonex]
            if len(names) != len(nonex):
                names = [pascal(l.name) for l in nonex]
            named = iter(names)
            sites = [Site(l, "E", None) if l.kind == "example" else Site(l, "key", next(named)) for l in kept]
        elif chart_key(col, inst):
            # the id of a part of an id-keyed chart, read at the form's key
            sites = [Site(l, "key", l.name) for l in kept]
        else:
            rest = nonex if inst is not None else kept
            nkeep = sum(1 for l in kept if l.kind == "keep")
            if col.tparam and len(rest) > 1:
                fields = iter(field_names(rest))
                sites = [Site(l, "E", None) if l.kind == "example" and inst is not None
                         else Site(l, col.name, next(fields)) for l in kept]
            else:
                sites = [Site(l, "E" if l.kind == "example" else l.name if nkeep > 1 else col.name, None)
                         for l in kept]
        out.append(sites)
    return out


class ClauseWriter:
    """Writes one clause body as arclog lines."""

    def __init__(self, conv: Converter, scope: tuple[str, ...], sub: dict[str, str],
                 rename: dict[str, str], own_inst=None) -> None:
        self.c = conv
        self.scope = scope
        self.sub = sub
        self.rename = rename
        self.reads: set[str] = set()
        self.branches: set[str] = set()
        self.own_inst = own_inst
        self.depth = 0
        self.top_pos: set[str] = set()
        self.top_neg: set[str] = set()
        self.nested: set[str] = set()
        self.drop_neg: frozenset[str] = getattr(conv, "cur_empty", frozenset())
        self.clause_vars: set[str] = set()   # the labels of the lists written so far
        self.fields: dict[str, dict[str, str]] = {}   # a variable spread into fields: field name -> the field's variable
        self.stuck = False   # a top-level body whose algebra atoms no order makes safe

    def label(self, v: str) -> str:
        return self.rename.get(v, v)

    def field_labels(self, v: str, label: str, bound: set[str]) -> dict[str, str]:
        """The labels of the fields of the record variable `v`, whose own label
        is `label`, by field name: those the sites made by `split`, and those
        of `bound` that a record term of variables `<label>_<field>` made."""
        out = {x[len(label) + 1:]: x for x in bound if x.startswith(label + "_")}
        out.update({f: self.label(n) for f, n in self.fields.get(v, {}).items()})
        return out

    def term_text(self, t) -> str:
        if isinstance(t, Variable):
            return self.label(t.name)
        if isinstance(t, NumberTerm) and t.value == 0:
            return "0"
        if isinstance(t, DefinedName) and t.name == "ZERO":
            return "0"
        if isinstance(t, DefinedName):
            self.c.todo.add("literal", t.name)
            return t.name
        if isinstance(t, NumberTerm):
            self.c.todo.add("literal", str(t.value))
            return str(t.value)
        if isinstance(t, ConstructorTerm):
            if t.name in self.c.select_ctors:
                return "$" + t.name   # a selected rule: the instance's TODO names it
            self.c.todo.add("constructor", souffle_term(t))
            return "$" + t.name
        if isinstance(t, Aggregate):
            self.c.todo.add("aggregate", souffle_term(t))
            return "{" + souffle_term(t) + "}"
        self.c.todo.add("term", souffle_term(t))
        return "{" + souffle_term(t) + "}"

    def split(self, term, leaves: list[Leaf]):
        """The terms of a column's leaves, matched by the record structure."""
        if len(leaves) == 1 and not leaves[0].path:
            return [term]
        return self._split(term, leaves, 0)

    def _split(self, term, leaves: list[Leaf], depth: int):
        if len(leaves) == 1 and len(leaves[0].path) == depth:
            return [term]
        if all(l.kind == "drop" for l in leaves):
            return [Wildcard()] * len(leaves)
        if isinstance(term, Wildcard):
            return [Wildcard()] * len(leaves)
        if isinstance(term, Variable):
            if sum(l.kind in ("keep", "example") for l in leaves) == 1:
                # one leaf kept: the leaf is the variable
                return [term if l.kind in ("keep", "example") else Wildcard() for l in leaves]
            inner = [l.field[depth:] for l in leaves]
            last = [f[-1] if f else l.name.lower() for f, l in zip(inner, leaves)]
            tags = last if len(set(last)) == len(last) else \
                ["_".join(f) if f else l.name.lower() for f, l in zip(inner, leaves)]
            out = []
            for l, t in zip(leaves, tags):
                if l.kind in ("keep", "example"):
                    self.fields.setdefault(term.name, {})[t] = f"{term.name}_{t}"
                    out.append(Variable(f"{term.name}_{t}"))
                else:
                    out.append(Wildcard())
            return out
        if isinstance(term, RecordTerm):
            groups: dict[int, list[Leaf]] = defaultdict(list)
            for l in leaves:
                groups[l.path[depth] if len(l.path) > depth else -1].append(l)
            if len(groups) == len(term.args) and -1 not in groups:
                out = []
                for i, a in enumerate(term.args):
                    out.extend(self._split(a, groups[i], depth + 1))
                return out
        if isinstance(term, ConstructorTerm) and term.name == "U" and all(l.kind == "drop" for l in leaves):
            return [Wildcard()] * len(leaves)
        self.c.todo.add("record-shape", souffle_term(term))
        return [Wildcard()] * len(leaves)

    def sites(self, atom: Atom, bound: set[str] | None, key_join: bool = True) -> tuple[str, list[str]]:
        name, cols, kind, inst = self.c.resolve(atom.relation, self.scope, self.sub)
        if atom in self.c.lib_judgment:
            self.c.todo.add("lib-judgment", self.c.lib_judgment[atom])
        if cols is None:
            self.c.todo.add("unresolved", atom.relation.text)
            return name, [souffle_term(a) for a in atom.args]
        if kind in ("derived", "param", "inst"):
            self.reads.add(name.split(".")[0])
        if kind == "inst" and inst in self.c.demo_insts and atom.relation.name != "@demonstrated" \
                and self.own_inst != inst:
            self.c.todo.add("demonstrated-read", f"{name}: a read of a rule or an input "
                            "of a DEMONSTRATED form, whose relation has no rule column; the doc gives no form")
        if name == "in" and any(l.kind == "example" for _, ls in cols for l in ls):
            name = "ex_in"
        if len(cols) != len(atom.args):
            self.c.todo.add("arity", f"{atom.relation.text}")
            return name, [souffle_term(a) for a in atom.args]
        out: list[str] = []
        placed = site_columns(self.c, cols, inst)
        # the key of an id-keyed chart's part leads its sites, as the outputs of
        # the form hold the key's columns first
        order = sorted(enumerate(zip(cols, atom.args)), key=lambda column: not chart_key(column[1][0][0], inst))
        for i, ((col, leaves), arg) in order:
            terms = self.split(arg, leaves)
            self.branches.update(case_ctors(leaves, terms))
            live = [(leaf, t) for leaf, t in zip(leaves, terms) if kept_leaf(leaf)]
            kept = [(site, t) for site, (_, t) in zip(placed[i], live)]
            if not kept:
                continue
            self.c.read_sites.setdefault(name, set()).update(
                (site.label, site.field) for site, t in kept if not isinstance(t, Wildcard))
            is_key = chart_key(col, inst) or inst is not None and i == 0 and col.name == "key"
            if is_key:
                kept = self.example_sites(kept, bound, out)
                if not kept:
                    continue
                if key_join and inst is not None and inst == self.own_inst and all(
                        isinstance(t, Variable) and self.label(t.name) == site.field for site, t in kept):
                    continue
                inner = []
                for site, t in kept:
                    if isinstance(t, Wildcard):
                        continue
                    s = self.one(t, bound)
                    lab = s.lstrip("*^")
                    inner.append(s if lab == site.field else f"(:{site.field} {s})")
                if inner:
                    out.append("(:key " + " ".join(inner) + ")")
                continue
            if inst is not None:
                # the Example label is its own site, whichever column of the instance's relation holds it
                kept = self.example_sites(kept, bound, out)
                if not kept:
                    continue
            if kept[0][0].field is not None:
                inner = field_sites([site.field for site, t in kept if not isinstance(t, Wildcard)],
                                    [self.one(t, bound) for _, t in kept if not isinstance(t, Wildcard)])
                if inner:
                    out.append(f"(:{col.name} " + " ".join(inner) + ")")
                continue
            for site, t in kept:
                if isinstance(t, Wildcard):
                    continue
                s = self.one(t, bound)
                lab = s.lstrip("*^")
                if not col.tparam and lab == site.label:
                    out.append(s)
                else:
                    out.append(f"(:{site.label} {s})")
        return name, out

    def example_sites(self, kept, bound: set[str] | None, out: list[str]):
        """Append to `out` the site of each Example leaf of `kept`, and give
        the other leaves."""
        for site, t in kept:
            if site.leaf.kind == "example" and not isinstance(t, Wildcard):
                s = self.one(t, bound)
                out.append(s if s.lstrip("*^") == "E" else f"(:E {s})")
        return [(site, t) for site, t in kept if site.leaf.kind != "example"]

    def one(self, t, bound: set[str] | None) -> str:
        if isinstance(t, Variable):
            lab = self.label(t.name)
            if bound is not None and lab not in bound:
                bound.add(lab)
                return "*" + lab
            return lab
        return self.term_text(t)

    def skips(self, l: AtomLiteral) -> bool:
        """Whether `l` is an atom of a `skip_rels` relation, such as `impl_choice`,
        which writes no text."""
        rel = l.atom.relation
        return rel.name in self.c.skip_rels and (not rel.instances or rel.instances[0] in ("parse", "ex"))

    def is_gate(self, l: AtomLiteral) -> bool:
        """Whether `l` is a skipped atom that holds no case set: its arguments
        fix the case the clause stands in."""
        return self.skips(l) and l.atom.relation.name not in getattr(self.c, "case_sets", ())

    def gate_ctors(self, l: AtomLiteral) -> set[str] | None:
        """The constructors that the arguments of the gate atom `l` name at case
        leaves, or None where the atom's columns do not resolve."""
        _, cols, _, _ = self.c.resolve(l.atom.relation, self.scope, self.sub)
        if cols is None or len(cols) != len(l.atom.args):
            return None
        ctors: set[str] = set()
        for (_, leaves), arg in zip(cols, l.atom.args):
            ctors |= case_ctors(leaves, self.split(arg, leaves))
        return ctors

    def gate(self, l: AtomLiteral) -> None:
        """A gate atom: the constructors its arguments name at case leaves are
        the branches the clause stands in, as `sites` gives them for any other
        atom. A negated atom that names a constructor is no branch, and gives a
        TODO."""
        ctors = self.gate_ctors(l)
        if ctors is None:
            self.c.todo.add("choice-gate", souffle_term(l.atom))
        elif l.negated and ctors:
            self.c.todo.add("choice-gate", "!" + souffle_term(l.atom))
        elif not l.negated:
            self.branches |= ctors

    def lit(self, l, bound: set[str]) -> list[str]:
        if isinstance(l, AtomLiteral):
            if self.skips(l):
                if self.is_gate(l):
                    self.gate(l)
                else:
                    self.note("%" + l.atom.relation.name, l.negated)
                    self.reads.add("%" + l.atom.relation.name)
                    if "%" + l.atom.relation.name in self.drop_neg and not l.negated:
                        raise Dead
                return []
            if l.negated and not l.atom.relation.instances and self.defect(l.atom.relation.name):
                return self.universal(l.atom, bound)
            if l.negated:
                name, s = self.sites(l.atom, None)
                self.note(name, True)
                if name.split(".")[0] in self.drop_neg:
                    return []
                return [f"(NOT ({name}{''.join(' ' + x for x in s)}))"]
            name, s = self.sites(l.atom, bound)
            self.note(name, False)
            if name.split(".")[0] in self.drop_neg:
                raise Dead
            return [f"({name}{''.join(' ' + x for x in s)})"]
        if isinstance(l, Comparison):
            lhs, rhs = l.lhs, l.rhs
            if l.op.value in ("=", "!=") and isinstance(lhs, Variable) and isinstance(rhs, Variable):
                a, b = self.label(lhs.name), self.label(rhs.name)
                if a not in bound and b not in bound:
                    fa, fb = self.field_labels(lhs.name, a, bound), self.field_labels(rhs.name, b, bound)
                    common = sorted(fa.keys() & fb.keys())
                    if common and fa.keys() == fb.keys():
                        if l.op.value == "=":
                            return [f"(= {fa[x]} {fb[x]})" for x in common]
                        if len(common) == 1:
                            return [f"(!= {fa[common[0]]} {fb[common[0]]})"]
                        return wrap("(OR ", [[f"(!= {fa[x]} {fb[x]})"] for x in common])
            if l.op.value == "=" and isinstance(lhs, RecordTerm) and isinstance(rhs, RecordTerm) \
                    and agrees_but_wildcards(lhs, rhs):
                # two records that differ only where one holds `_`: the test names the
                # constructors they share, the case the clause stands in
                self.branches.update(ctor_names(lhs))
                return []
            if l.op.value == "=":
                # `=` makes its first label: `(= *X Y)`, the made label first
                lfree = isinstance(lhs, Variable) and self.label(lhs.name) not in bound
                rfree = isinstance(rhs, Variable) and self.label(rhs.name) not in bound
                if rfree and not lfree:
                    lhs, rhs = rhs, lhs
                parts = [self.one(lhs, bound) if isinstance(lhs, Variable) else self.term_text(lhs),
                         self.one(rhs, bound) if isinstance(rhs, Variable) else self.term_text(rhs)]
                return [f"(= {parts[0]} {parts[1]})"]
            parts = [self.term_text(t) for t in (lhs, rhs)]
            op = l.op.value
            if parts[0] == "0" and parts[1] != "0":
                # `0` stands second: the constraint mirrored
                parts.reverse()
                op = {"<": ">", ">": "<", "<=": ">=", ">=": "<="}.get(op, op)
            return [f"({op} {parts[0]} {parts[1]})"]
        if isinstance(l, Disjunction):
            return self.disj(l, bound)
        if isinstance(l, BoolLiteral):
            self.c.todo.add("bool", str(l.value))
            return [f"({'true' if l.value else 'false'})"]
        self.c.todo.add("literal-kind", type(l).__name__)
        return [repr(l)]

    def defect(self, name: str) -> bool:
        """The relation `name` read in this scope is a defect relation."""
        got = getattr(self.c, "all_inline", {}).get(name)
        if got is None:
            return False
        for i in range(len(self.scope), -1, -1):
            if (self.scope[:i], name) in self.c.rels:
                return self.scope[:i] == got[0].scope.components
        return False

    def universal(self, atom: Atom, bound: set[str]) -> list[str]:
        """`!R(args)` where R is a defect relation: ALL over R's domain."""
        u, test_i = self.c.all_inline[atom.relation.name]
        m: dict[str, str] = {}
        taken = set(bound) | set(self.rename) | set(self.rename.values()) | self.clause_vars
        for h, a in zip(u.head.args, atom.args):
            if isinstance(a, Variable):
                m[h.name] = a.name
        inner: set[str] = set()
        collect_vars(list(u.body), inner)
        for v in sorted(inner):
            if v not in m:
                n = v
                while n in taken or n in m.values():
                    n += "m"
                m[v] = n
        key_vars = {m[h.name] for h, a in zip(u.head.args, atom.args) if isinstance(a, Variable)}
        body = [subst(l, m) for l in u.body]
        test = body[test_i]
        dom = []
        for i, l in enumerate(body):
            if i == test_i:
                continue
            if isinstance(l, AtomLiteral) and not l.negated:
                vs: set[str] = set()
                collect_vars([l], vs)
                if vs and vs <= key_vars:
                    continue   # the key's own guard
            dom.append(l)
        if isinstance(test, AtomLiteral):
            flipped = AtomLiteral(test.atom, False)
        else:
            flipped = Comparison(NEG_OP[test.op], test.lhs, test.rhs, test.line)
        bb = set(bound)
        self.depth += 1
        try:
            dl = self.lits(dom, bb)
        except Dead:
            return []    # the defect relation is empty, so its negation holds
        finally:
            self.depth -= 1
        self.depth += 1
        try:
            tl = self.lits([flipped], bb)
        finally:
            self.depth -= 1
        return wrap("(ALL ", [dl, tl])

    def note(self, name: str, negated: bool) -> None:
        n = name.split(".")[0]
        if self.depth:
            self.nested.add(n)
        else:
            (self.top_neg if negated else self.top_pos).add(n)

    def lits(self, lits, bound: set[str], bound_before: set[str] | None = None) -> list[str]:
        """`bound` holds the labels already written, which a later site names
        without `*`; `bound_before` holds the labels the atoms before bind, where
        that is fewer, as in a later branch of an `OR`."""
        vs: set[str] = set()
        collect_vars(list(lits), vs)
        self.clause_vars |= {self.label(v) for v in vs}
        out: list[str] = []
        for l in self.reorder(list(lits), bound if bound_before is None else bound_before):
            out.extend(self.lit(l, bound))
        return out

    def reorder(self, lits, bound: set[str]):
        """The literals with each test after the literals that bind its
        labels: a comparison or a negation waits for its last binder; a fact
        atom waits for an algebra atom that makes labels the fact atom reads,
        so the `*` stands on the algebra atom."""
        def vs(t) -> set[str]:
            out: set[str] = set()
            collect_vars([AtomLiteral(Atom(RelationName((), "_"), (t,), 0), False)], out)
            return {self.label(v) for v in out}

        def binds(l) -> set[str]:
            if isinstance(l, AtomLiteral) and not l.negated:
                return set().union(*(vs(a) for a in l.atom.args)) if l.atom.args else set()
            if isinstance(l, Comparison) and l.op.value == "=":
                return vs(l.lhs) | vs(l.rhs)
            if isinstance(l, Disjunction):
                sets = []
                for b in l.branches:
                    bb: set[str] = set()
                    for x in b:
                        bb |= binds(x)
                    sets.append(bb)
                return set.intersection(*sets) if sets else set()
            return set()

        def ready(l, B: set[str]) -> bool:
            if isinstance(l, Comparison):
                if isinstance(l.lhs, Aggregate) or isinstance(l.rhs, Aggregate):
                    return True
                lv, rv = vs(l.lhs), vs(l.rhs)
                if lv | rv <= B:
                    return True
                if l.op.value == "=":
                    return (isinstance(l.lhs, Variable) and rv <= B) or (isinstance(l.rhs, Variable) and lv <= B)
                return False
            if isinstance(l, AtomLiteral) and l.negated:
                return set().union(*(vs(a) for a in l.atom.args)) <= B if l.atom.args else True
            if isinstance(l, Disjunction):
                return all(placeable(b, B) for b in l.branches)
            got = algebra_modes(l)
            if got is not None:
                name, cols, args = got
                return any(all(pascal(c) in cols and is_bound(args[cols.index(pascal(c))], B) for c in m)
                           for m in ALGEBRA_MODES[name])
            return True

        def placeable(branch, B0: set[str]) -> bool:
            """Every literal of a branch has its turn, given the labels B0."""
            B2, rem = set(B0), list(branch)
            while rem:
                for x in rem:
                    if ready(x, B2):
                        rem.remove(x)
                        B2 |= binds(x)
                        break
                else:
                    return False
            return True

        def is_bound(t, B: set[str]) -> bool:
            return not isinstance(t, Wildcard) and vs(t) <= B

        def algebra_modes(l):
            """(column names, args) of a positive atom of an algebra relation."""
            if not isinstance(l, AtomLiteral) or l.negated or l.atom.relation.instances not in ((), ("@lib",)):
                return None
            name, cols, kind, _ = self.c.resolve(l.atom.relation, self.scope, self.sub)
            if kind != "lib" or cols is None or len(cols) != len(l.atom.args):
                return None
            # the atom still reads the lib's own names, which the emission renames
            ren = libmap.REL.get(name)
            if ren is not None:
                name, cols = ren.name, [(Col(ren.parts.get(c.name, c.name), c.type, c.tparam), x) for c, x in cols]
            if name not in ALGEBRA_MODES:
                return None
            return name, [c.name for c, _ in cols], l.atom.args

        B = set(bound)
        everything: set[str] = set(B)
        for l in lits:
            everything |= binds(l)
        # A label no literal binds, such as a stripped case label, waits for
        # nothing.
        mentioned: set[str] = set()
        for l in lits:
            if isinstance(l, AtomLiteral):
                for a in l.atom.args:
                    mentioned |= vs(a)
            elif isinstance(l, Comparison):
                mentioned |= vs(l.lhs) | vs(l.rhs)
        unbound = mentioned - everything
        B |= unbound
        everything |= unbound
        # A body whose algebra atoms no order makes safe, such as an `inline`
        # helper's, keeps its written order.
        rem, B3, moved = list(lits), set(B), True
        while moved:
            moved = False
            for x in list(rem):
                if isinstance(x, Comparison) and not ready(x, B3):
                    continue
                if (algebra_modes(x) is not None or isinstance(x, Disjunction)) and not ready(x, B3):
                    continue
                rem.remove(x)
                B3 |= binds(x)
                moved = True
        orderable = not any(algebra_modes(x) is not None or isinstance(x, Disjunction) for x in rem)
        if not orderable and self.depth == 0:
            self.stuck = True
        def is_fact(l) -> bool:
            return isinstance(l, AtomLiteral) and not l.negated and self.c.resolve(l.atom.relation, self.scope, self.sub)[2] == "fact"

        def made_by_waiting(i: int, B: set[str]) -> set[str]:
            """The labels of the fact atom `lits[i]` that an algebra atom
            waiting for the other literals makes, which no other literal binds."""
            made: set[str] = set()
            for j, m in enumerate(lits):
                if j == i or algebra_modes(m) is None or ready(m, B):
                    continue
                others = B.union(*(binds(k) for n, k in enumerate(lits) if n not in (i, j)))
                if ready(m, others):
                    made |= (binds(lits[i]) & binds(m)) - others
            return made

        out, pending, after = [], [], {}
        for i, l in enumerate(lits):
            if orderable and is_fact(l) and (waits_for := made_by_waiting(i, B)):
                after[id(l)] = waits_for
                pending.append(l)
                continue
            if orderable and (algebra_modes(l) is not None or isinstance(l, Disjunction)):
                # an algebra atom or an `OR` waits for the other literals' labels, never its own
                others = set(bound) | unbound
                for j, m in enumerate(lits):
                    if j != i:
                        others |= binds(m)
                wait = not ready(l, B) and ready(l, others)
            else:
                wait = (isinstance(l, Comparison) or isinstance(l, AtomLiteral) and l.negated) \
                    and not ready(l, B) and ready(l, everything)
            if wait:
                pending.append(l)
                continue
            out.append(l)
            B |= binds(l)
            moved = True
            while moved:
                moved = False
                for p_ in list(pending):
                    if ready(p_, B) and after.get(id(p_), set()) <= B:
                        out.append(p_)
                        B |= binds(p_)
                        pending.remove(p_)
                        moved = True
        return out + pending

    def disj(self, d: Disjunction, bound: set[str]) -> list[str]:
        self.depth += 1
        try:
            return self._disj(d, bound)
        finally:
            self.depth -= 1

    def _disj(self, d: Disjunction, bound: set[str]) -> list[str]:
        if len(d.branches) == 2:
            iff = self.as_if(d, bound)
            if iff is not None:
                return iff
        # A first pass finds each branch's labels; the exported ones, made in
        # every branch, are made in the first branch, at a site where some
        # branch makes them all at sites, else by `(= *X Y)`, and the later
        # branches name them.
        live = []
        for b in d.branches:
            bb = set(bound)
            saved = list(self.c.todo.pending), Counter(self.c.todo.kinds)
            try:
                text = self.lits(b, bb)
            except Dead:
                continue
            finally:
                self.c.todo.pending, self.c.todo.kinds = saved
            live.append((b, bb - bound, " ".join(text)))
        if not live:
            raise Dead
        shared = set.intersection(*(a for _, a, _ in live))
        def at_sites(t: str) -> int:
            return sum(1 for v in shared if re.search(rf"(?<!\(= )\*{re.escape(v)}(?![\w])", t))
        first = max(range(len(live)), key=lambda k: (at_sites(live[k][2]), -k))
        order = [live[first], *(x for k, x in enumerate(live) if k != first)]
        groups = []
        for k, (b, _, _) in enumerate(order):
            bb = set(bound) | (shared if k else set())
            groups.append(self.lits(b, bb, set(bound)))
        bound |= shared
        if len(groups) == 1:
            return groups[0]
        return wrap("(OR ", groups)

    def as_if(self, d: Disjunction, bound: set[str]):
        b1, b2 = d.branches
        for i, l in enumerate(b1):
            if not isinstance(l, AtomLiteral) or l.negated:
                continue
            for j, m in enumerate(b2):
                if isinstance(m, AtomLiteral) and m.negated and m.atom.relation == l.atom.relation \
                        and m.atom.args == l.atom.args:
                    eb = set(bound)
                    tb = set(bound)
                    try:
                        test = self.lits([l], tb)
                    except Dead:      # the test never holds: the else alone
                        return self.lits(b2[:j] + b2[j + 1:], bound)
                    try:
                        then = self.lits(b1[:i] + b1[i + 1:], tb)
                    except Dead:      # the then never holds: the else under the negated test
                        return self.lits(list(b2), bound)
                    try:
                        els = self.lits(b2[:j] + b2[j + 1:], eb)
                    except Dead:      # the else never holds: the test and the then
                        return self.lits(list(b1), bound)
                    made_in_test = set()
                    collect_vars([l], made_in_test)
                    made_in_test = {self.label(v) for v in made_in_test} - bound
                    else_vars: set[str] = set()
                    collect_vars(list(b2[:j] + b2[j + 1:]), else_vars)
                    if made_in_test & {self.label(v) for v in else_vars}:
                        return None   # the else reads the test's labels: no IF
                    exported = (tb & eb) - bound
                    then_text, els_text = " ".join(then), " ".join(els)
                    if any(re.search(rf"\(= \*{re.escape(v)} ", then_text) and re.search(rf"(?<!\(= )\*{re.escape(v)}(?!\w)", els_text)
                           for v in exported):
                        return None   # the export is made at the else's site: an OR puts it first
                    bound |= exported
                    return wrap("(IF ", [test, then, els])
        return None

