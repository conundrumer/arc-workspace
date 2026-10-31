"""`ClauseWriter`, which writes one clause body as arclog lines."""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass, replace as dc_replace
from engine.program import (
    POSE_COLUMN,
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
from souffle.parser import RIGID_POSE
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


POSE_TESTS = frozenset({"c4_elem", "sym_member"})
"""The lib relations that test, at their last column, a D4 element for a subgroup of D4. A `Pose` label stands at no
such column (`docs/arclog/rigid.md#the-pose`)."""


def column_site(column: str, label: str) -> str:
    """The site of the column `column` that reads `label`, `label` alone where
    it is the column's name (`docs/arclog/arclog.md#sites`)."""
    return label if label.lstrip("*^") == column else f"(:{column} {label})"


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


def site_columns(c: "Converter", cols: list, inst, port: str | None = None) -> list[list[Site]]:
    """For each Souffle column of `cols` (`Converter.resolve`), the `Site`
    of each of its leaves that `kept_leaf` keeps, in order. `ClauseWriter.sites`
    writes its sites with these labels, and `names.column_map` writes
    them, so a label is chosen here alone. `column_map` gives the `port` of
    the instance's relation, and for the `prediction` of a `DEMONSTRATED`
    form (`Solver.demonstrated_form`), each leaf of a column after the
    key and the alternative takes the label its `&prediction` clause holds it
    at, the label of the `value` head site, with no field, where the head site
    has a label for each kept leaf."""
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
    demo = getattr(c, "demo_value_labels", {}).get(inst) if port == "prediction" else None
    for i, labels in enumerate(demo or [], start=2):
        if i < len(out) and len(labels) == len(out[i]):
            out[i] = [Site(site.leaf, label, None) for site, label in zip(out[i], labels)]
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

    def field_labels(self, v: str, bound: set[str]) -> dict[str, str]:
        """The labels of the fields of the record variable `v`, by field name:
        those the sites made by `split`, and the labels in `bound` of the
        variables `<v>_<field>` that a record term made, whatever label the
        clause's head renames them to."""
        out = {n[len(v) + 1:]: self.label(n) for n in self.rename.keys() | bound
               if n.startswith(v + "_") and self.label(n) in bound}
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
            inner = [l.field[depth:] for l in leaves]
            last = [f[-1] if f else l.name.lower() for f, l in zip(inner, leaves)]
            tags = last if len(set(last)) == len(last) else \
                ["_".join(f) if f else l.name.lower() for f, l in zip(inner, leaves)]
            if sum(l.kind in ("keep", "example") for l in leaves) == 1:
                # one leaf kept: the leaf is the variable, or the label the clause's head gives that field of it
                return [Wildcard() if l.kind not in ("keep", "example") else
                        Variable(f"{term.name}_{t}") if f"{term.name}_{t}" in self.rename else term
                        for l, t in zip(leaves, tags)]
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
        elif kind == "lib" and name not in self.c.sig.top and name not in libmap.REL:
            # a lib relation the lib of the signature lacks, which no expansion replaced: it has no arclog name
            cols = None
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
            if (column := self.d4_column(l.atom)) is not None:
                keyed = self.c.rigid[l.atom.relation.name][0] in self.c.rigid_keyed
                if not l.negated and len(l.atom.args) == POSE_COLUMN + 2 + keyed:
                    return self.d4_part(l.atom, column, bound)
                self.c.todo.add("rigid-d4", f"{souffle_term(l.atom)}: only a positive read of a part that holds the "
                                "stored pose and the part's key has a form")
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
                    fa, fb = self.field_labels(lhs.name, bound), self.field_labels(rhs.name, bound)
                    if l.op.value == "=" and (bool(fa) != bool(fb)):
                        # a record variable that the fields of another make whole: a label per field,
                        # named as a later read of the variable names them
                        made, src = (rhs, fa) if fa else (lhs, fb)
                        got = {t: f"{made.name}_{t}" for t in src}
                        self.fields.setdefault(made.name, {}).update(got)
                        bound.update(got.values())
                        fa, fb = (src, got) if fa else (got, src)
                        return [f"(= *{fa[x]} {fb[x]})" if made is lhs else f"(= *{fb[x]} {fa[x]})"
                                for x in sorted(src)]
                    common = sorted(fa.keys() & fb.keys())
                    if common and fa.keys() == fb.keys():
                        if l.op.value == "=":
                            out = []
                            for first, second in ((fa[x], fb[x]) for x in common):
                                if first in bound and second not in bound:
                                    first, second = second, first
                                # `=` makes its first label, where the other stands bound
                                made = first not in bound and second in bound
                                bound.update({first} if made else ())
                                out.append(f"(= {'*' if made else ''}{first} {second})")
                            return out
                        if len(common) == 1:
                            return [f"(!= {fa[common[0]]} {fb[common[0]]})"]
                        return wrap("(OR ", [[f"(!= {fa[x]} {fb[x]})"] for x in common])
            if l.op.value == "=" and isinstance(lhs, RecordTerm) and isinstance(rhs, RecordTerm) \
                    and agrees_but_wildcards(lhs, rhs):
                # two records that differ only where one holds `_`: the test names the
                # constructors they share, the case the clause stands in
                self.branches.update(ctor_names(lhs))
                return []
            if l.op.value in ("=", "!=") and isinstance(lhs, RecordTerm) and isinstance(rhs, RecordTerm) \
                    and len(lhs.args) == len(rhs.args) \
                    and not any(isinstance(t, Wildcard) for t in (*lhs.args, *rhs.args)):
                # two records compare by their fields: `=` holds where each pair of fields is equal, and `!=` where
                # some pair differs
                pairs = [(x, y) for x, y in zip(lhs.args, rhs.args) if x != y]
                parts = [self.lit(Comparison(l.op, x, y, l.line), bound) for x, y in pairs]
                if l.op.value == "=":
                    return [text for part in parts for text in part]
                if not parts:
                    raise Dead
                return parts[0] if len(parts) == 1 else wrap("(OR ", parts)
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
        that is fewer, as in a later branch of an `OR`. A test of a pose (`pose_chart`) stands after the rest, which
        bind that pose."""
        vs: set[str] = set()
        collect_vars(list(lits), vs)
        self.clause_vars |= {self.label(v) for v in vs}
        charts = {id(l): chart for l in lits if (chart := self.pose_chart(l, lits)) is not None}
        rest = [l for l in lits if id(l) not in charts]
        out: list[str] = []
        for l in self.equals_first(self.reorder(rest, bound if bound_before is None else bound_before), bound):
            out.extend(self.lit(l, bound))
        for l in lits:
            if id(l) in charts:
                out.extend(self.pose_subgroup(l.atom, charts[id(l)], bound))
        return out

    def pose_chart(self, l, lits) -> Atom | None:
        """Where `l` is a positive `POSE_TESTS` atom on the pose of a read of a RIGID block's placed relation among
        `lits`, that read."""
        if not (isinstance(l, AtomLiteral) and not l.negated and not l.atom.relation.instances
                and l.atom.relation.name in POSE_TESTS and isinstance(l.atom.args[-1], Variable)):
            return None
        return next((x.atom for x in lits if isinstance(x, AtomLiteral) and not x.negated
                     and x.atom.relation.instances == ("params",) and x.atom.relation.name in self.c.rigid
                     and x.atom.args[POSE_COLUMN] == l.atom.args[-1]), None)

    def new_label(self, stem: str, bound: set[str]) -> Variable:
        """A variable of a label no list of the clause holds so far: `stem`, or `stem` and a number."""
        taken = self.clause_vars | bound | self.rename.keys() | set(self.rename.values())
        name = next(n for n in (stem, *(f"{stem}{k}" for k in range(2, len(taken) + 3))) if n not in taken)
        self.clause_vars.add(name)
        return Variable(name)

    def d4_column(self, atom: Atom) -> int | None:
        """Where `atom` reads a RIGID block's placed relation with a D4 column, that column."""
        rel = atom.relation
        if rel.name not in self.c.rigid or rel.instances != (() if self.scope == ("Params",) else ("params",)):
            return None
        columns = self.c.rels[(("Params",), rel.name)].columns
        return next((i for i, c in enumerate(columns) if i != POSE_COLUMN and c.type.name == RIGID_POSE), None)

    def d4_part(self, part: Atom, column: int, bound: set[str]) -> list[str]:
        """`part`, a read of the D4 column `column` of a RIGID block's part, written as its pose's difference from a
        training pose of the block. A placement leaves a D4 column as it is (`docs/arclog/rigid.md#semantics`), where
        Souffle's takes a stored pose S to the P of `d4_compose(P, S, D)`, the element that takes S onto the pose D."""
        read, trained = self.pose_read(part, bound)
        name = self.c.rel_name(("Params",), part.relation.name)
        self.note(name, False)
        if name.split(".")[0] in self.drop_neg:
            raise Dead
        return [read, self.pose_difference(trained, part.args[POSE_COLUMN], part.args[column], bound)]

    def pose_read(self, chart: Atom, bound: set[str]) -> tuple[str, Variable]:
        """The read of a training pose of the block that `chart` reads, and that pose's new label."""
        trained = self.new_label("D0", bound)
        args: list = [Wildcard()] * len(chart.args)
        args[POSE_COLUMN] = trained
        if self.c.rigid[chart.relation.name][0] in self.c.rigid_keyed:
            args[POSE_COLUMN + 1] = chart.args[POSE_COLUMN + 1]   # each key is an assembly of its own
        name, sites = self.sites(dc_replace(chart, args=tuple(args)), bound)
        return "(" + " ".join([f"{name.split('.')[0]}.pose", *sites]) + ")", trained

    def pose_difference(self, trained: Variable, pose, difference, bound: set[str]) -> str:
        """The atom that gives `difference`, the element that takes the placement at `trained` onto that at `pose`."""
        sites = [column_site(column, self.one(term, bound))
                 for column, term in (("A", trained), ("B", pose), ("D", difference))]
        return f"(pose_difference {' '.join(sites)})"

    def pose_subgroup(self, test: Atom, chart: Atom, bound: set[str]) -> list[str]:
        """The narrowing of `docs/arclog/rigid.md#subgroups`: `test` on the pose that `chart` reads, written as `test`
        on that pose's difference from a training pose of the block, which reads no single pose."""
        read, trained = self.pose_read(chart, bound)
        difference = self.new_label("T", bound)
        return [read, self.pose_difference(trained, test.args[-1], difference, bound),
                *self.lit(AtomLiteral(dc_replace(test, args=(*test.args[:-1], difference)), False), bound)]

    def equals_first(self, lits: list, bound: set[str]) -> list:
        """`lits` with each `X = Y` whose `Y` stands in `bound`, and whose `X` a later site would make, before the
        first atom that holds `X`: the `=` makes `X`, `(= *X Y)`, and the atom reads it. A site that makes `X` would
        leave the `=` a test of a label its own list makes, which arclog writes at the site."""
        out = list(lits)
        for l in lits:
            if not (isinstance(l, Comparison) and l.op.value == "=" and isinstance(l.lhs, Variable)
                    and isinstance(l.rhs, Variable)):
                continue
            made = [x for x in (l.lhs.name, l.rhs.name) if self.label(x) not in bound]
            if len(made) != 1:
                continue

            def holds(x) -> bool:
                held: set[str] = set()
                collect_vars([x], held)
                return made[0] in held
            binders = [i for i, x in enumerate(out[:out.index(l)])
                       if isinstance(x, AtomLiteral) and not x.negated and holds(x)]
            if binders:
                out.remove(l)
                out.insert(binders[0], l)
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

        def dropped_only(atom: Atom) -> set[str]:
            """The labels that the atom has at the fields of a record column that the relation drops, and nowhere
            else: the atom writes no site for them, so it binds none of them."""
            saved = list(self.c.todo.pending), Counter(self.c.todo.kinds)
            name, cols, kind, inst = self.c.resolve(atom.relation, self.scope, self.sub)
            self.c.todo.pending, self.c.todo.kinds = saved
            if cols is None or len(cols) != len(atom.args):
                return set()
            dropped: set[str] = set()
            kept: set[str] = set()
            for (col, leaves), arg in zip(cols, atom.args):
                if isinstance(arg, RecordTerm) and any(l.kind == "drop" and len(l.path) == 1 for l in leaves):
                    for i, a in enumerate(arg.args):
                        here = [l for l in leaves if l.path[:1] == (i,)]
                        (dropped if here and all(l.kind == "drop" for l in here) else kept).update(vs(a))
                else:
                    kept |= vs(arg)
            return dropped - kept

        def vs_atom(l) -> set[str]:
            return set().union(*(vs(a) for a in l.atom.args)) if l.atom.args else set()

        def binds(l) -> set[str]:
            if isinstance(l, AtomLiteral) and not l.negated:
                return set().union(*(vs(a) for a in l.atom.args)) - dropped_only(l.atom) if l.atom.args else set()
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

        def own_read(l) -> bool:
            """A read of an output of the instance whose input this is: every site of it joins."""
            if self.own_inst is None or not isinstance(l, AtomLiteral) or l.negated or l.atom.relation.instances[:1] == ():
                return False
            saved = list(self.c.todo.pending), Counter(self.c.todo.kinds)
            inst = self.c.resolve(l.atom.relation, self.scope, self.sub)[3]
            self.c.todo.pending, self.c.todo.kinds = saved
            return inst == self.own_inst

        out, pending, after = [], [], {}
        for i, l in enumerate(lits):
            if orderable and own_read(l):
                # the labels that another literal binds are bound before the read
                need = vs_atom(l) & set().union(*(binds(m) for j, m in enumerate(lits) if j != i and not own_read(m)), set(bound))
                if not need <= B:
                    after[id(l)] = need
                    pending.append(l)
                    continue
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

