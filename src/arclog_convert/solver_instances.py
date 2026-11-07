"""The part of `Solver` that converts clauses, builds their instances and
writes the pick forms."""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from engine.program import (
    AdtType,
    Atom,
    AtomLiteral,
    Comparison,
    ConstructorTerm,
    DefinedName,
    NumberTerm,
    RecordTerm,
    RelationName,
    Scope,
    Unit,
    UnitId,
    Variable,
    Wildcard,
)
from dataclasses import replace as dc_replace
from souffle.printer import term as souffle_term
from arclog_convert.literals import collect_vars
from arclog_convert import libmap
from arclog_convert.libmap.instances import GROUNDED, term_vars

from arclog_convert.clauses import ClauseWriter
from arclog_convert.forms import (
    Dead,
    Form,
    MERGES,
    close,
    comment_text,
    demo_lines,
    directives,
    drop_implied,
    label_names,
    mark_key,
    nest_keyed,
    or_body,
    params_to_amp,
    relabel,
    share_labels,
    wrap,
)
from arclog_convert.implied import ELEM
from arclog_convert.leaves import Written
from arclog_convert.lib import (ALGEBRA_MODES, COPIED_INPUTS, FROM_KEY, NEEDED_INPUTS, domain_proposer, field_names,
                                field_sites, pascal)
from arclog_convert.terms import ctor_names, subst_terms

LABEL = re.compile(r"(?<![(:\w&.])[*^]?([A-Z]\w*)")
"""A label of a written form, as it stands in a form line."""


def set_name(amp: str) -> str:
    """The relation that holds the set an open parameter's Souffle determination
    derives, whose `(ONE)` pick the parameter's own name holds."""
    return amp + "_set"


def leaves_a_need(component: str, us: list[Unit]) -> bool:
    """Whether the input clauses `us` of an instance of `component` hold no
    clause of an input that the registry marks `required`, or of any input of
    its `one-of` group: the component then gives no output, so the instance
    holds no row."""
    renamed = libmap.COMP.get(component)
    required, one_of = NEEDED_INPUTS.get(renamed.name if renamed else component, (frozenset(), frozenset()))
    written = {renamed.parts.get(u.head.relation.name, u.head.relation.name) if renamed else u.head.relation.name
               for u in us}
    return bool(required - written) or (bool(one_of) and not one_of & written)


READ = re.compile(r"\((&\w+)(?=[\s)]|$)")
"""A relation a form line reads, `(&name` up to the end of the name."""

DET_HEAD = re.compile(r"\((?:DET|DET_OR_RULE) (&\w+)(?=[\s)]|$)")
"""The head of a determination, and the relation it derives."""

BY_PROPOSER = re.compile(r"\(DET &\w+ (\w+)\)")
"""A `DET` with no body that names one proposer, and that proposer."""

MEMBERS = {domain_proposer([t]): rel for rel, t in ELEM.items()}
"""The lib relation that lists the members of an orientation type, by the
type-domain proposer of that type."""


def fresh(base: str, taken: set[str]) -> str:
    """`base`, or `base` with the least number from 2 that makes it a label
    outside `taken`; the label joins `taken`."""
    lab, n = base, 2
    while lab in taken:
        lab, n = f"{base}{n}", n + 1
    taken.add(lab)
    return lab


FRAME_2D = "Frame2D"
"""The component whose `cell` holds a key's cells only where `extent` has that
key on each of two perpendicular axes."""


def perpendicular_join(body: list[str], axis: str, knames: list[str]) -> list[str]:
    """The key clause `body`, which makes the label `axis` as the axis of a key's
    extent row, joined with a copy of itself on the key labels `knames`, whose
    other labels are renamed, at an axis perpendicular to `axis`: the keys that
    `body` gives on each of two perpendicular axes."""
    taken = label_names(body) | set(knames)
    ren = {x: fresh(x, taken) for x in sorted(label_names(body) - set(knames))}
    copy = relabel(body, lambda mark, x: x if x in knames else mark + ren[x])
    sites = [lab if lab == col else f"(:{col} {lab})" for col, lab in (("A", axis), ("A2", ren.get(axis, axis)))]
    return [*body, *copy, f"(perp {' '.join(sites)})"]


def extent_axis(gens: list[Unit], kren, knames: list[str]) -> str:
    """The label of the axis of the extent row in the key clause of every
    generator in `gens`: the label they share where it is no key label, else a
    label that no generator holds. `kren` gives a generator's renames of its
    key variables."""
    held = {kren(u).get(u.head.args[1].name, u.head.args[1].name) for u in gens}
    if len(held) == 1 and not held & set(knames):
        return next(iter(held))
    taken = set(knames)
    for u in gens:
        vs: set[str] = set()
        collect_vars(list(u.body) + [AtomLiteral(u.head, False)], vs)
        taken |= {kren(u).get(v, v) for v in vs}
    return fresh("A", taken)


def line_reads(f: Form) -> set[str]:
    """The relations a form's lines read."""
    return {m.group(1) for l in f.lines for m in READ.finditer(l)}


class InstancesMixin:
    """The clauses of a solver, their instances and its pick forms."""

    used_sets: frozenset[str] = frozenset()
    """The open parameters that `settle_sets` writes as a set and a pick."""

    def clause(self, u: Unit, side: str, scope, sub, name_scope=None, drop_neg=frozenset()) -> Form:
        c = self.c
        src = (u, side, scope, dict(sub), name_scope)
        sub = dict(sub)
        hname, hcols, kind, inst = c.resolve(u.head.relation, name_scope or scope, sub)
        rename: dict[str, str] = {}
        extra: list[str] = []
        branches: set[str] = set()
        rules: set[str] = set()   # the demonstrated rule the head names
        # unify var = var at top level
        body = list(u.body or [])
        eqs = [l for l in body if isinstance(l, Comparison) and l.op.value == "="
               and isinstance(l.lhs, Variable) and isinstance(l.rhs, Variable)]
        head_cols: list[tuple[str, object]] = []
        col_names: list[list[str]] = []   # per head column, the names of its kept leaves
        if hcols is not None and len(hcols) == len(u.head.args):
            w = ClauseWriter(c, scope, sub, {})
            for (col, leaves), arg in zip(hcols, u.head.args):
                col_names.append([])
                kept = []
                for leaf, t in zip(leaves, w.split(arg, leaves)):
                    if leaf.kind == "case":
                        branches.update(ctor_names(t))
                        continue
                    if leaf.kind == "rule":
                        rules.update(ctor_names(t))
                        continue
                    if leaf.kind == "drop":
                        continue
                    kept.append((leaf, t))
                nkeep = sum(1 for l, _ in kept if l.kind == "keep")
                for leaf, t in kept:
                    head_cols.append(("E" if leaf.kind == "example" else leaf.name if nkeep > 1 else col.name, t))
                    col_names[-1].append(head_cols[-1][0])
        else:
            self.todo.add("head", souffle_term(u.head))
        head_branches = frozenset(branches)
        head_vars = {t.name for _, t in head_cols if isinstance(t, Variable)}
        for e in eqs:
            a, b = e.lhs.name, e.rhs.name
            if b in head_vars and a not in head_vars:
                a, b = b, a
            rename[b] = a
            body.remove(e)
        given: dict[str, str] = {}   # a head variable -> the column it names
        repeats: list[tuple[str, str]] = []
        eqmap = dict(rename)
        for colname, t in head_cols:
            if isinstance(t, Variable):
                v = eqmap.get(t.name, t.name)
                if v in given:
                    extra.append(f"(= {colname} {given[v]})")
                    repeats.append((colname, given[v]))
                    continue
                given[v] = colname
                for k, val in eqmap.items():
                    if val == v:
                        rename[k] = colname
                rename[v] = colname
            elif (isinstance(t, NumberTerm) and t.value == 0) or (isinstance(t, DefinedName) and t.name == "ZERO"):
                extra.append(f"(= {colname} 0)")
            elif isinstance(t, DefinedName):
                self.todo.add("literal", t.name)
                extra.append(f"(= {colname} {t.name})")
            else:
                if not set(ctor_names(t)) & c.select_ctors:
                    self.todo.add("head-term", f"{colname} = {souffle_term(t)}")
                extra.append(f"(= {colname} {souffle_term(t)})")
        # avoid capturing: a body variable whose name a head column took; a
        # variable that an equation unified into it takes its new label too
        targets = set(rename.values())
        vars_ = set()
        collect_vars(body, vars_)
        for v in vars_:
            if v not in rename and v in targets:
                n = 2
                while f"{v}{n}" in targets or f"{v}{n}" in vars_:
                    n += 1
                rename[v] = f"{v}{n}"
                for k, val in eqmap.items():
                    if val == v and rename[k] == v:
                        rename[k] = rename[v]
        w = ClauseWriter(c, scope, sub, rename)
        w.drop_neg = frozenset(drop_neg)
        w.heads = frozenset(n for n, _ in head_cols)
        bound: set[str] = set()
        try:
            lines = w.lits(body, bound)
        except Dead:
            return None
        if w.stuck:
            c.unsafe.add(u.head.relation.name)
        # a top-level `(= *X Y)` left where a disjunction kept one branch is
        # a rename: Y's site makes X
        cols_here = {n for n, _ in head_cols}
        for line in list(lines):
            m = re.fullmatch(r"\(= \*(\w+) ([A-Z]\w*)\)", line)
            if m and m.group(2) not in cols_here and m.group(2) != m.group(1):
                x, y = m.groups()
                lines.remove(line)
                lines = relabel(lines, lambda mark, v: mark + (x if v == y else v))
            elif m and m.group(1) in cols_here and m.group(2) in cols_here and m.group(2) != m.group(1):
                repeats.append(m.groups())   # the kept branch makes one head column the other's
        for e in extra:
            m = re.match(r"\(= (\w+) ", e)
            if m and m.group(1) not in bound:
                bound.add(m.group(1))
                e = f"(= *{e[3:]}"
            lines.append(e)
        branches |= w.branches
        marks = self.one_lines(u, col_names)
        if side == "DET" and hname in self.open_amps() and "(ONE)" not in marks:
            marks.append("(ONE)")   # an open parameter: each of its values is a model; `settle_sets` writes its set
        todos = self.todo.take()
        name = hname
        head_line = f"({side} {name}"
        f = Form([head_line] + ["  " + l for l in lines + marks], name, w.reads, line=u.span.first if u.span else 0)
        close(f.lines, ")")
        f.body = list(lines)
        f.marks = marks
        f.cols = [n for n, _ in head_cols]
        f.col_labels = col_names
        f.side = side
        if side == "DET":
            c.det_heads.add(name)
        if len(f.lines) == 1:
            pass
        f.branches = tuple(sorted(branches))
        f.head_branches = tuple(sorted(head_branches))
        f.pins = {k: frozenset(v) for k, v in w.pins.items()}
        f.comments = [*(";; " + t for t in self.plain_comments(f.line)), *todos]
        p = None if u.head.relation.instances else c.one_marks.get((u.scope.components, u.head.relation.name))
        if p is not None and u.span and u.span.first == min(
                x.span.first for x in c.prog.units if x.span and x.head.relation == u.head.relation
                and x.scope == u.scope):
            # the pick's own comments, on its first clause
            f.comments[:0] = [";; " + t for t in self.plain_comments(p.line)]
            for d, rest, _ in directives(self.comments_above(p.line)):
                if d == "claim":
                    f.claim_slugs = rest.split()
        f.src = src
        f.head_repeat = repeats
        f.top_pos, f.top_neg, f.nested = w.top_pos, w.top_neg, w.nested
        if len(rules) == 1:
            f.demo_rule = next(iter(rules))
        return f

    def one_lines(self, u: Unit, col_names: list[list[str]]) -> list[str]:
        """The ONE marks of a clause of a folded pick, over its column labels."""
        if note := self.c.unpicked.get((u.head.relation.name, u.span.first if u.span else 0)):
            self.todo.add("pick", note)
        p = None if u.head.relation.instances else self.c.one_marks.get((u.scope.components, u.head.relation.name))
        if p is None:
            return []
        for note in p.notes:
            self.todo.add("pick-read", note)
        if len(col_names) != len(p.fold):
            self.todo.add("one", "the picked relation's columns")
            return []
        name: dict[str, list[str]] = {}   # a column variable -> the labels of its column
        gone = set()   # a column the clause drops: a case's or a lifted key
        for v, ns in zip(p.fold, col_names):
            if v is not None and ns:
                name[v] = ns
            elif v is not None:
                gone.add(v)
        out = []
        for key in p.ones:
            key = [v for v in key if v not in gone]
            if any(v not in name for v in key):
                self.todo.add("one", f"a key column of {' '.join(key)}")
                continue
            out.append("(" + " ".join(["ONE"] + [x for v in key for x in name[v]]) + ")")
        return out

    # ---- the set of an open parameter

    @staticmethod
    def det_side(f: Form) -> bool:
        return (f.src is not None and f.src[1] == "DET") or (f.src_inst is not None and f.src_inst[2] == "DET")

    def settle_sets(self, forms: list[Form]) -> list[Form]:
        """`forms`, with each open parameter that a `DET` body reads written in
        two determinations: the Souffle determination as a `DET` of `set_name`
        with no `ONE` mark, and a `DET` that picks one row of that set. Each
        read of the parameter in a `DET` body reads the set. A set's value
        holds several rows, and a type-domain proposer gives one value per
        row, so the set's `DET` of such a proposer states the body of the
        type's members. Where no clause of the solver derives the set, the
        parameter's stored rows are the set's record, and the `param` form of
        the rows names the set."""
        names = {self.c.rel_name(("Params",), n): n for n in self.c.open_params}
        determined = {m.group(1) for f in forms if (m := DET_HEAD.match(f.lines[0])) and m.group(1) in names}
        self.used_sets = frozenset(determined & {r for f in forms if self.det_side(f) for r in line_reads(f)})
        out = [self.settled(f) for f in forms]
        for amp in sorted(self.used_sets):
            n = names[amp]
            cols = self.c.rels[(("Params",), n)].columns
            args = tuple(Variable(f"V{i}") for i in range(len(cols)))
            atom = Atom(RelationName(("params",), n), args, 0)
            pick = Unit(UnitId(self.c.prog.next_unit_index()), Scope(("Determine",)), atom,
                        (AtomLiteral(atom, False),), None, None)
            out.append(self.settled(self.clause(pick, "DET", ("Determine",), {})))
        return out

    def settled(self, f: Form | None) -> Form | None:
        """`f` as `settle_sets` writes it."""
        if f is None or not self.used_sets:
            return f
        if self.det_side(f):
            sets = line_reads(f) & self.used_sets

            def reading(text: str) -> str:
                return READ.sub(lambda m: "(" + set_name(m.group(1)) if m.group(1) in sets else m.group(0), text)
            f.lines = [reading(l) for l in f.lines]
            if f.body is not None:
                f.body = [reading(l) for l in f.body]
            for attr in ("reads", "top_pos", "top_neg", "nested"):
                setattr(f, attr, {set_name(r) if r in sets else r for r in getattr(f, attr)})
        m = DET_HEAD.match(f.lines[0])
        if m and m.group(1) in self.used_sets and set_name(m.group(1)) not in f.reads:
            # the Souffle determination, and not the pick that reads it
            f.name = set_name(f.name)
            f.marks = [x for x in f.marks if x != "(ONE)"]
            by = BY_PROPOSER.fullmatch(f.lines[0]) if f.body is None else None
            if by and by.group(1) in MEMBERS:
                n = next(n for n in self.c.open_params if self.c.rel_name(("Params",), n) == m.group(1))
                label = pascal(self.c.rels[(("Params",), n)].columns[0].name)
                f.body = [f"({MEMBERS[by.group(1)]} *{label})"]
                f.cols = [label]
                f.side = "DET"
                f.lines = [f"(DET {f.name}", f"  {f.body[0]})"]
            elif f.body is None:
                f.lines[0] = f.lines[0].replace(m.group(1), f.name, 1)
            else:
                f.lines = [f.lines[0].replace(m.group(1), f.name, 1)] + ["  " + l for l in f.body + f.marks]
                close(f.lines, ")")
        return f

    def plain_comments(self, line: int) -> list[str]:
        out = []
        for d, rest, _ in directives(self.comments_above(line)):
            if d == "" and rest and not rest.startswith("---"):
                out.append(params_to_amp(rest))
        return out

    # ---- instances

    def instance(self, inst, us: list[Unit], side: str, empty: frozenset[str] = frozenset(),
                 split: frozenset[str] = frozenset()) -> list[Form]:
        """The forms of an instance of the lib component, from its input clauses
        `us`. Input clauses that fix branches of one point make one instance per
        branch, which holds that branch's clauses and the clauses that fix no
        branch of the point. The form at the branches no clause fixes holds the
        clauses that fix no branch of the point and, for each input that none
        of those writes, the clauses of that input that fix the point's first
        constructor through a constructor of a column and through no
        `impl_choice` atom, as an alt reads from the concept an input that it
        does not write. No such form stands where those clauses make no row
        alone. A clause fixes a branch through a constructor of its
        head, or through the constructors its body fixes as the clause writer
        records the branches of any clause, and it fixes the branch of each
        point that the branch's point is nested under. Where clauses fix
        branches of two points, a form stands at the branches of both points,
        each its own or the branches no clause fixes."""
        c = self.c
        points = list(c.point_fields())
        point_of = {k.name: f_ for f_, adt_ in points for k in adt_.constructors}
        scope = inst.scope.components
        sub = c.parse_sub if scope == ("Parse",) else {}

        def fixed(u: Unit) -> set[str]:
            """The constructors of a point that the clause `u` fixes: those the
            clause writer records for its body and those of its head, each with
            the constructors of the points that the constructor's point stands
            under."""
            saved = list(self.todo.pending), Counter(self.todo.kinds)
            w = ClauseWriter(c, scope, sub, {})
            w.lits(list(u.body or []), set())
            self.todo.pending, self.todo.kinds = saved
            ctors = (w.branches | {k for a in u.head.args for k in ctor_names(a)}) & point_of.keys()
            return ctors | {k for x in ctors for _, k in self.ancestors(point_of[x])}

        def gated_on(u: Unit, ctor: str) -> bool:
            """Whether a positive `impl_choice` atom in the body of the clause `u` fixes
            the constructor `ctor`."""
            saved = list(self.todo.pending), Counter(self.todo.kinds)
            w = ClauseWriter(c, scope, sub, {})
            gated = any(isinstance(l, AtomLiteral) and not l.negated and w.is_gate(l) and ctor in (w.gate_ctors(l) or ())
                        for l in u.body or [])
            self.todo.pending, self.todo.kinds = saved
            return gated
        named = [fixed(u) for u in us]
        for f_, adt_ in points:
            if f_ in split:
                continue   # split already
            ks = [k.name for k in adt_.constructors if any(k.name in ns for ns in named)]
            free = [u for u, ns in zip(us, named) if not any(point_of[x] == f_ for x in ns)]
            if not ks or (len(ks) == 1 and not free):
                continue
            out: list[Form] = []
            for k in ks:
                part = [u for u, ns in zip(us, named) if not any(point_of[x] == f_ and x != k for x in ns)]
                # a form of the branch's instance holds in that branch alone,
                # also where none of its clauses names the branch
                for g in self.instance(inst, part, side, empty, split | {f_}):
                    g.branches = tuple(sorted(set(g.branches) | {k}))
                    out.append(g)
            c0 = adt_.constructors[0].name
            rest = {k.name for k in adt_.constructors} - set(ks)
            # an input that reads the instance's outputs, or that no output copies, makes no row alone
            ren_ = libmap.COMP.get(inst.component)
            copied = COPIED_INPUTS.get(ren_.name if ren_ else inst.component)
            gen = [u for u in free if (copied is None or (
                ren_.parts.get(u.head.relation.name, u.head.relation.name) if ren_ else u.head.relation.name) in copied)
                and (u.body is None or not any(
                    isinstance(l, AtomLiteral) and l.atom.relation.instances[:1] == (inst.name,) for l in u.body))]
            if gen and rest:
                # an alt reads a relation that it does not derive from the concept,
                # and so an input that no clause of `free` writes: the form at
                # `rest` holds the clauses of that input that fix the first
                # constructor through a column and through no `impl_choice` atom
                written = {u.head.relation.name for u in free}
                inherited = [u for u, ns in zip(us, named)
                             if c0 in ns and not any(point_of[x] == f_ and x != c0 for x in ns)
                             and u.head.relation.name not in written and not gated_on(u, c0)]
                gs = self.instance(inst, free + inherited, side, empty, split | {f_})
                # where another point is also fixed, the forms of the clauses that fix
                # nothing at this point stand at the point's other branches, so that
                # a case that takes a branch of both points has one form of the relation
                fixes_other = bool(split) or any(point_of[x] != f_ for ns in named for x in ns)
                if c0 in ks or fixes_other:
                    for g in gs:
                        g.branches = tuple(sorted(set(g.branches) | rest))
                out.extend(gs)
            # a form that writes what a form of fewer branches writes repeats
            # it: the latter holds wherever the former does
            def holds_where(h: Form, g: Form) -> bool:
                """Whether `h` holds in each case `g` holds: at each point, `h` names
                no constructor of the point or each one that `g` names."""
                return all(not (hs := {b for b in h.branches if point_of.get(b) == p})
                           or {b for b in g.branches if point_of.get(b) == p} <= hs
                           for p, _ in points)
            concept = {adt.constructors[0].name for _, adt in points}
            kept: list[Form] = []
            for g in sorted(out, key=lambda g: len(set(g.branches) - concept)):
                if not any(h.lines == g.lines and holds_where(h, g) for h in kept):
                    kept.append(g)
            return [g for g in out if any(g is h for h in kept)]
        c.cur_empty = empty
        try:
            return self._instance(inst, us, side, empty)
        finally:
            c.cur_empty = frozenset()

    def _instance(self, inst, us: list[Unit], side: str, empty: frozenset[str]) -> list[Form]:
        c = self.c
        if empty:
            scope0 = inst.scope.components
            lsub0 = c.parse_sub if scope0 == ("Parse",) else {}
            live = []
            saved = list(self.todo.pending), Counter(self.todo.kinds)
            for u in us:
                if u.body is None:
                    live.append(u)
                    continue
                try:
                    ClauseWriter(c, scope0, lsub0, {}).lits(list(u.body), set())
                    live.append(u)
                except Dead:
                    pass
            self.todo.pending, self.todo.kinds = saved
            # an instance whose every input is empty, or reads its own
            # outputs alone, holds no row
            if us and not any(u.body is not None and not all(
                    isinstance(l, AtomLiteral) and l.atom.relation.instances[:1] == (inst.name,)
                    for l in u.body if isinstance(l, AtomLiteral) and not l.negated) for u in live):
                return []
            us = live
        # an instance with no clause of an input its component requires, or of
        # any input of its one-of group, holds no row
        if leaves_a_need(inst.component, us):
            return []
        if (inst.scope.components, inst.name) in c.demo_insts and any(
                u.head.relation.name == "prediction" for u in us):
            return self.demonstrated_form(inst, us, side)
        orig_us = us
        scope = inst.scope.components
        key = (scope, inst.name)
        amp = c.rel_name(scope, inst.name)
        tparams, rels = c.lib.relations(inst.component)
        written = {u.head.relation.name for u in us}
        us = us + [dc_replace(u, scope=inst.scope,
                              head=dc_replace(u.head, relation=RelationName((inst.name,), u.head.relation.name)))
                   for u in c.lib.input_clauses(inst.component) if u.head.relation.name in written]
        sub = {p: a.name for p, a in zip(tparams, inst.type_args)}
        if scope == ("Parse",):
            sub = {p: c.parse_sub.get(a.name, a.name) for p, a in zip(tparams, inst.type_args)}
        lsub = c.parse_sub if scope == ("Parse",) else {}
        knames = c.key_names.get(key, [])
        # the inputs the lib declares with no key column: broadcasts, which
        # read no key label and add no branch to the key clause
        unkeyed = {lr.name for lr in rels if lr.is_input and not (lr.cols and lr.cols[0].name == "key")}
        kn = knames   # the key labels in scope in the input at hand

        def kren(u):
            return {} if u.head.relation.name in unkeyed else self.key_rename(u, key_leaves, knames)
        by_rel: dict[str, list[Unit]] = defaultdict(list)
        for u in us:
            by_rel[u.head.relation.name].append(u)
        lines = [f"(INIT {amp} {inst.component}"]
        reads: set[str] = set()
        branches: set[str] = set()
        # the branches the key columns of the input heads name
        case_ctors = {k.name for _, adt_ in c.point_fields() for k in adt_.constructors}
        for u in us:
            if u.head.relation.name not in unkeyed and u.head.args:
                branches.update(x for x in ctor_names(u.head.args[0]) if x in case_ctors)
        key_leaves = c.leaves("key", "Key", True, scope, sub, outer=lsub)
        has_key = any(l.kind in ("keep", "example") for l in key_leaves)
        # the key clause: the atoms over key labels alone, where every input
        # clause shares them; else the union of the generators' bodies, which is
        # also the key clause of a Cardinality with no domain clause. A Frame2D
        # holds the keys that `extent` gives on each of two perpendicular axes:
        # the join of the generators' union with a copy of itself at a
        # perpendicular axis, in place of the union
        residual: dict[int, list] = {}
        key_body: list[str] | None = None
        counts_members_only = False
        blocks: list[list[str]] = []
        if has_key:
            kset = set(knames)

            def key_atoms(u):
                ren = kren(u)
                idx = []
                for i, l in enumerate(u.body or []):
                    if not isinstance(l, AtomLiteral) or l.negated:
                        continue
                    if l.atom.relation.instances[:1] == (inst.name,):
                        continue
                    probe = ClauseWriter(c, scope, lsub, ren, own_inst=key)
                    saved = list(self.todo.pending), Counter(self.todo.kinds)
                    text = " ".join(probe.lits([l], set()))
                    self.todo.pending, self.todo.kinds = saved
                    vs = set(LABEL.findall(text))
                    if vs and vs <= kset:
                        idx.append(i)
                # an algebra atom whose labels the other key atoms do not all
                # bind stays with the member atoms
                texts = {}
                for i in idx:
                    probe = ClauseWriter(c, scope, lsub, ren, own_inst=key)
                    saved = list(self.todo.pending), Counter(self.todo.kinds)
                    texts[i] = " ".join(probe.lits([u.body[i]], set()))
                    self.todo.pending, self.todo.kinds = saved

                def labels(t: str) -> set[str]:
                    return set(LABEL.findall(t))
                algebra = {i for i in idx if (m := re.match(r"\((\w+)", texts[i])) and m.group(1) in ALGEBRA_MODES}
                bound_by_members = set().union(set(), *(labels(texts[i]) for i in idx if i not in algebra))
                idx = [i for i in idx if i not in algebra or labels(texts[i]) <= bound_by_members]
                return ren, idx

            groups = {}
            for u in us:
                if u.body is None or u.head.relation.name in unkeyed:
                    continue
                ren, idx = key_atoms(u)
                if not idx:
                    continue
                w = ClauseWriter(c, scope, lsub, ren, own_inst=key)
                ls = mark_key(w.lits([u.body[i] for i in idx], set()), knames)
                groups[id(u)] = (ls, idx, w)
            gens = [u for u in us if u.body is not None and u.head.relation.name not in unkeyed and not any(
                isinstance(l, AtomLiteral) and l.atom.relation.instances[:1] == (inst.name,) for l in u.body)]
            shared = None
            # a Cardinality with no domain clause gets its domain from the key,
            # which then holds only the keys that some member has
            renamed = libmap.COMP.get(inst.component)
            counts_members_only = renamed is not None and renamed.name == "Cardinality" and "domain" not in written
            two_axes = inst.component == FRAME_2D
            if gens and not counts_members_only and not two_axes and all(id(u) in groups for u in gens):
                cands = {tuple(groups[id(u)][0]) for u in gens}
                if len(cands) == 1:
                    shared = list(next(iter(cands)))
            if shared is not None and all(set(knames) <= {x.lstrip("^") for x in re.findall(r"\^\w+", " ".join(shared))} for _ in [0]):
                key_body = list(shared)
                for u in us:
                    g = groups.get(id(u))
                    if g and g[0] == shared:
                        residual[id(u)] = [l for i, l in enumerate(u.body) if i not in g[1]]
                        reads |= g[2].reads
                        branches |= g[2].branches
            elif gens:
                axis = extent_axis(gens, kren, knames) if two_axes else None
                uniq = []
                for u in gens:
                    ren = kren(u)
                    key_axis = None
                    if axis is not None:
                        # a generator whose axis is a key label makes the axis label equal to it
                        v = u.head.args[1].name
                        if ren.get(v, v) in knames:
                            key_axis = ren.get(v, v)
                        else:
                            ren = {**ren, v: axis}
                    w = ClauseWriter(c, scope, lsub, ren, own_inst=key)
                    ls = mark_key(w.lits(list(u.body), set()), knames)
                    if key_axis is not None:
                        ls.append(f"(= *{axis} {key_axis})")
                    reads |= w.reads
                    branches |= w.branches
                    if ls not in uniq:
                        uniq.append(ls)
                uniq = drop_implied(uniq)
                key_body = list(uniq[0] if len(uniq) == 1 else wrap("(OR ", share_labels(uniq)))
                if axis is not None:
                    key_body = perpendicular_join(key_body, axis, knames)
        def column_leaves(lr):
            """Each non-key column of the input, with its leaves."""
            return [(col, c.leaves(col.name, col.type, col.tparam, scope, sub, outer=lsub))
                    for i, col in enumerate(lr.cols) if not (i == 0 and col.name == "key")]

        def head_terms(u, lr, ren):
            """Each non-key column of the input's head: (col, [(leaf, term)])."""
            out = []
            keyed = bool(lr.cols) and lr.cols[0].name == "key"
            for (col, leaves), arg in zip(column_leaves(lr), u.head.args[int(keyed):]):
                terms = ClauseWriter(c, scope, lsub, ren).split(arg, leaves)
                for l, t in zip(leaves, terms):
                    if l.kind == "case":
                        branches.update(ctor_names(t))
                kept = [(l, t) for l, t in zip(leaves, terms) if l.kind in ("keep", "example")]
                if kept:
                    out.append((col, kept))
            return out

        def is_zero(t) -> bool:
            return (isinstance(t, NumberTerm) and t.value == 0) or (isinstance(t, DefinedName) and t.name == "ZERO")

        def lab_of(t, ren) -> str:
            if isinstance(t, Variable):
                return ren.get(t.name, t.name)
            if is_zero(t):
                return "0"
            if isinstance(t, DefinedName):
                self.todo.add("literal", t.name)
                return t.name
            if not set(ctor_names(t)) & c.select_ctors:
                self.todo.add("head-term", souffle_term(t))
            return souffle_term(t)

        def site_text(col, labs: list[str], leaves) -> str:
            if col.tparam and len(labs) > 1:
                return f"(:{col.name} {' '.join(field_sites(field_names(leaves), labs))})"
            if col.tparam:
                return f"(:{col.name} {' '.join(labs)})"
            if labs[0] == col.name and len(labs) == 1:
                return labs[0]
            return f"(:{col.name} {' '.join(labs)})"

        def zero_sites(hts, ren, taken: set[str]) -> tuple[list[str], list[str]]:
            """The head sites, each zero term a label named after its leaf,
            and the `(= *X 0)` that makes each such label."""
            sites_, eqs = [], []
            for col, kept in hts:
                labs = []
                for leaf, t in kept:
                    if is_zero(t):
                        lab = fresh(pascal(leaf.name), taken)
                        eqs.append(f"(= *{lab} 0)")
                        labs.append(lab)
                    else:
                        labs.append(lab_of(t, ren))
                sites_.append(site_text(col, labs, [l for l, _ in kept]))
            return sites_, eqs

        def fact_block(u, lr):
            key_arg = u.head.args[0] if u.head.args and lr.cols and lr.cols[0].name == "key" else None
            hts = head_terms(u, lr, {})
            if (key_arg is None or (isinstance(key_arg, ConstructorTerm) and key_arg.name == "U")) \
                    and all(is_zero(t) for _, kept in hts for _, t in kept):
                sites_, eqs = zero_sites(hts, {}, set(kn))
                block = [f"  ({lr.name} ({' '.join(sites_)})"] + ["    " + e for e in eqs]
                close(block, ")")
                return block
            self.todo.add("input-fact", souffle_term(u.head))
            return [f"  ;; TODO input-fact: {souffle_term(u.head)}"]

        key_ls = [l for l in key_leaves if l.kind in ("keep", "example")]
        key_typed = len(key_ls) == len(knames) and all(l.type for l in key_ls)

        def key_label(leaf) -> str | None:
            """The key's one label of the leaf's type (the engine's `key_fill`), or
            None where the key has none or several of that type. Two type names are
            one type where each alias and subtype they name, followed to its end,
            gives one name. A leaf or a key label with no type gives None."""
            if not (key_typed and leaf.type):
                return None
            labs = [n for n, k in zip(knames, key_ls) if c.type_root(k.type, scope) == c.type_root(leaf.type, scope)]
            return labs[0] if len(labs) == 1 else None

        def from_key(lr) -> bool:
            """Whether the registry marks the input `from-key`."""
            ren_ = libmap.COMP.get(inst.component)
            target = ren_.name if ren_ else inst.component
            port = ren_.parts.get(lr.name, lr.name) if ren_ else lr.name
            return port in FROM_KEY.get(target, ())

        def skipped(u, lr) -> bool:
            """An input clause the engine fills from the key whatever the types: the
            registry marks the input `from-key`, the input has no kept leaf beside
            the key, and the clause only reads the instance's own key. A written
            input gets no fill from the engine, so the clauses of an input are left
            out only where this holds for each of them. The converse is `unfilled`."""
            own_read = any(isinstance(l, AtomLiteral) and l.atom.relation.instances[:1] == (inst.name,)
                           for l in u.body)
            beside_key = any(l.kind in ("keep", "example") for _, leaves in column_leaves(lr) for l in leaves)
            return from_key(lr) and not beside_key and (
                (own_read and len(u.body) == 1) or not residual.get(id(u), list(u.body)))

        def unfilled(lr) -> list[str] | None:
            """A TODO for an input that no solver clause writes, where the engine
            would fill the input from the key: the registry marks the input
            `from-key`, it has a kept leaf beside the key, and for each such leaf
            the key has exactly one label of its type. None elsewhere. The Souffle
            input holds no row, and the fill would add one per key. No clause keeps
            the input empty, since a body that holds nowhere is a self comparison,
            which the grammar refuses. A solver keeps such an input empty by a key
            or a body type that the fill does not take, as a `Unit` body does where
            each key holds one body."""
            hts = [(col, [l for l in leaves if l.kind in ("keep", "example")]) for col, leaves in column_leaves(lr)]
            hts = [(col, kept) for col, kept in hts if kept]
            labs = [[key_label(l) for l in kept] for _, kept in hts]
            if not (hts and from_key(lr) and all(lab for ls in labs for lab in ls)):
                return None
            detail = f"{lr.name}: the key fills the input, whose Souffle relation holds no row"
            self.todo.add("unfilled-input", detail)
            return [f"  ;; TODO unfilled-input: {detail}"]

        def without_grounding(u, lr, ren) -> list:
            """The clause's body, less each positive atom that shares no variable
            but the key's with the head's non-key columns or another literal, and
            is no read of the instance, where the shape wrote the input to bind
            the key and the body reads no key label. Such an atom restricts no
            output."""
            lits = residual.get(id(u), list(u.body))
            if (scope, inst.name, lr.name) not in GROUNDED:
                return lits
            keyed = bool(lr.cols) and lr.cols[0].name == "key"
            key_vars = set(term_vars(u.head.args[:1], [])) if keyed else set()
            head_vars = term_vars(u.head.args[1:] if keyed else u.head.args, [])
            drop = set()
            for i, l in enumerate(lits):
                if not isinstance(l, AtomLiteral) or l.negated or l.atom.relation.instances[:1] == (inst.name,):
                    continue
                vs = set(term_vars(l.atom.args, [])) - key_vars
                others: set[str] = set(head_vars)
                collect_vars(lits[:i] + lits[i + 1:], others)
                if not vs & (others - key_vars):
                    drop.add(i)
            if not drop:
                return lits
            probe = ClauseWriter(c, scope, lsub, dict(ren), own_inst=key)
            saved = list(self.todo.pending), Counter(self.todo.kinds)
            text = " ".join(probe.lits(lits, set()))
            self.todo.pending, self.todo.kinds = saved
            if set(kn) & set(LABEL.findall(text)):
                return lits
            return [l for i, l in enumerate(lits) if i not in drop]

        def single(u, lr) -> list[str]:
            ren = kren(u)
            hts = head_terms(u, lr, ren)
            w = ClauseWriter(c, scope, lsub, ren, own_inst=key)
            body = w.lits(without_grounding(u, lr, ren), set(kn))
            taken = set(kn) | label_names(body) | {
                ren.get(t.name, t.name) for _, kept in hts for _, t in kept if isinstance(t, Variable)}
            head_sites, eqs = zero_sites(hts, ren, taken)
            body = body + eqs
            reads.update(w.reads)
            branches.update(w.branches)
            block = ["  " + p for p in self.todo.take()]
            block.append(f"  ({lr.name} ({' '.join(head_sites)})")
            block.extend("    " + l for l in body)
            close(block, ")")
            return block

        def merged(us_, lr) -> list[str] | None:
            """The input's clauses as one input whose body is an OR, one
            branch per clause; None where the heads do not line up."""
            rens = [kren(u) for u in us_]
            saved = list(self.todo.pending), Counter(self.todo.kinds)
            hts = [head_terms(u, lr, r) for u, r in zip(us_, rens)]
            self.todo.pending, self.todo.kinds = saved
            shape = [(col.name, len(kept)) for col, kept in hts[0]]
            if any([(col.name, len(kept)) for col, kept in h] != shape for h in hts):
                return None
            terms = [[t for _, kept in h for _, t in kept] for h in hts]
            if any(not isinstance(t, Variable) and not is_zero(t) for ts in terms for t in ts):
                return None
            for u in us_:
                if u.body is None and u.head.args and lr.cols[0].name == "key" and \
                        not (isinstance(u.head.args[0], ConstructorTerm) and u.head.args[0].name == "U"):
                    return None
            taken: set[str] = set(kn)
            for u, r in zip(us_, rens):
                vs: set[str] = set()
                collect_vars(list(u.body or []), vs)
                collect_vars([AtomLiteral(u.head, False)], vs)
                taken |= {r.get(v, v) for v in vs}
            leaf_names = [l.name for _, kept in hts[0] for l, _ in kept]
            common: list[str] = []
            for p in range(len(terms[0])):
                cands: list[str] = [str(r.get(ts[p].name, ts[p].name)) for ts, r in zip(terms, rens) if isinstance(ts[p], Variable)]
                if not cands:
                    base, n = pascal(leaf_names[p]), 2
                    lab = base
                    while lab in taken or lab in common:
                        lab, n = f"{base}{n}", n + 1
                    taken.add(lab)
                    common.append(lab)
                    continue
                lab = cands[0]
                if lab in common:
                    q = common.index(lab)
                    if all(isinstance(ts[p], Variable) and isinstance(ts[q], Variable) and ts[p].name == ts[q].name
                           for ts in terms):
                        common.append(lab)   # every clause repeats the label in its head
                        continue
                if lab in common or (lab in kn and any(x != lab for x in cands)):
                    base = pascal(leaf_names[p])
                    lab, n = base, 2
                    while lab in taken or lab in common:
                        lab, n = f"{base}{n}", n + 1
                    taken.add(lab)
                common.append(lab)
            cols_ = {x for x in common if x != "0" and x not in kn}
            bodies = []
            for u, r, ts in zip(us_, rens, terms):
                ren = dict(r)
                assigned: dict[str, str] = {}
                extras: list[str] = []
                for p, t in enumerate(ts):
                    if isinstance(t, Variable):
                        lab = ren.get(t.name, t.name)
                        if t.name in assigned:
                            if assigned[t.name] != common[p]:
                                extras.append(f"(= *{common[p]} {assigned[t.name]})")
                        elif lab == common[p]:
                            assigned[t.name] = lab
                        elif lab in kn or common[p] in kn:
                            extras.append(f"(= *{common[p]} {lab})")
                        else:
                            ren[t.name] = common[p]
                            assigned[t.name] = common[p]
                    elif common[p] != "0":
                        extras.append(f"(= *{common[p]} 0)")
                vs = set()
                collect_vars(list(u.body or []), vs)
                for v in sorted(vs):
                    if v not in assigned and ren.get(v, v) in cols_:
                        base, n = ren.get(v, v), 2
                        while f"{base}{n}" in taken:
                            n += 1
                        ren[v] = f"{base}{n}"
                        taken.add(ren[v])
                lines_ = []
                if u.body is not None:
                    w = ClauseWriter(c, scope, lsub, ren, own_inst=key)
                    lines_ = w.lits(without_grounding(u, lr, ren), set(kn))
                    reads.update(w.reads)
                    branches.update(w.branches)
                bodies.append((self.todo.take(), lines_ + extras))
            head_sites, p = [], 0
            for col, kept in hts[0]:
                head_sites.append(site_text(col, common[p:p + len(kept)], [l for l, _ in kept]))
                p += len(kept)
            MERGES["input"] += 1
            block = [f"  ({lr.name} ({' '.join(head_sites)})"]
            block.extend("    " + l for l in or_body(bodies, cols_, set(kn)))
            close(block, ")")
            return block

        broadcast: set[int] = set()
        for lr in rels:
            if lr.is_input and lr.name not in by_rel and lr.name not in unkeyed and (block := unfilled(lr)):
                blocks.append(block)
            if not lr.is_input or lr.name not in by_rel:
                continue
            kn = [] if lr.name in unkeyed else knames
            first = len(blocks)
            filled = all(u.body is not None and skipped(u, lr) for u in by_rel[lr.name])
            us_ = [] if filled else list(by_rel[lr.name])
            facts = [u for u in us_ if u.body is None]
            if len(us_) > 1:
                block = merged(us_, lr)
                if block is not None:
                    blocks.append(block)
                    if lr.name in unkeyed:
                        broadcast.add(first)
                    continue
                MERGES["input-unmerged"] += 1
                if key not in c.demo_select:
                    self.todo.add("input-unmerged", f"{lr.name}: the clauses' heads do not line up")
            for u in us_:
                blocks.append(fact_block(u, lr) if u.body is None else single(u, lr))
            if lr.name in unkeyed:
                broadcast.update(range(first, len(blocks)))
        with_domain = None
        if key_body is not None and counts_members_only:
            domain = ["  (domain ()"] + ["    " + l.replace("^", "") for l in key_body]
            close(domain, ")")
            with_domain = lines + nest_keyed(key_body, [*blocks, domain], knames, "key", amp, broadcast=broadcast)
            close(with_domain, ")")
        lines.extend(nest_keyed(key_body, blocks, knames, "key", amp, broadcast=broadcast))
        close(lines, ")")
        reads.discard(amp)
        f = Form(lines, amp, reads, line=inst.span.first if inst.span else 0, with_domain=with_domain)
        f.branches = tuple(sorted(branches))
        f.comments = [";; " + t for t in self.plain_comments(f.line)]
        f.src_inst = (inst, orig_us, side)
        cm = directives(self.comments_above(f.line))
        for d, rest, _ in cm:
            if d == "claim":
                f.claim_slugs = rest.split()
        return [f]

    def demonstrated_form(self, inst, us: list[Unit], side: str) -> list[Form]:
        """A DemonstrationConsistency instance as a DEMONSTRATED form: its
        `value` and `demonstration` inputs as an instance's, then a DEMO_RULE
        per rule, whose `&prediction` clause has the columns the `value`
        head names. It records on the converter (`demo_value_labels`), by the
        instance's key, the labels of each leaf of each `value` head site, which
        `site_columns` gives the leaves of the instance's `prediction`."""
        c = self.c
        preds = [u for u in us if u.head.relation.name == "prediction"]
        gs = self._instance(inst, [u for u in us if u not in preds], side, frozenset())
        if not gs:
            return gs
        f = gs[0]
        scope = inst.scope.components
        key = (scope, inst.name)
        tparams, _ = c.lib.relations(inst.component)
        sub = {p: a.name for p, a in zip(tparams, inst.type_args)}
        if scope == ("Parse",):
            sub = {p: c.parse_sub.get(a.name, a.name) for p, a in zip(tparams, inst.type_args)}
        lsub = c.parse_sub if scope == ("Parse",) else {}
        knames = c.key_names.get(key, [])
        key_leaves = c.leaves("key", "Key", True, scope, sub, outer=lsub)

        def head_labels(input_name: str) -> list[list[str]]:
            """The labels of each head site of the input, as the lines give them: at a
            site of fields, the name of each field, and at another, each label."""
            for line in f.lines:
                s = line.strip()
                if s.startswith(f"({input_name} (("):
                    inner = s[len(input_name) + 3:]
                    out, depth, cur = [], 0, ""
                    for ch in inner:
                        if ch == "(":
                            depth += 1
                            if depth == 1:
                                cur = ""
                                continue
                        elif ch == ")":
                            depth -= 1
                            if depth == 0:
                                _, _, args = cur.partition(" ")
                                out.append([m[1] or m[2] for m in re.finditer(r"\(:([^\s()]+)[^()]*\)|([^\s()]+)", args)])
                                continue
                            if depth < 0:
                                break
                        if depth >= 1:
                            cur += ch
                    return out
            return []
        vlabs = head_labels("value")
        c.demo_value_labels = {**getattr(c, "demo_value_labels", {}), key: vlabs}
        flat_v = [x for ls in vlabs for x in ls]
        # the rules, in the order the type declares them
        order = []
        dem = c.find_type(inst.type_args[1].name, ())
        if isinstance(dem, AdtType):
            order = [k.name for k in dem.constructors]
        groups: dict[str, list[Unit]] = defaultdict(list)
        for u in preds:
            groups[u.head.args[1].name].append(u)
        reads: set[str] = set(f.reads)
        rules = []
        case_ctors = {k.name for _, adt_ in c.point_fields() for k in adt_.constructors}
        pred_branches: set[str] = set()
        fields_of: dict[str, list[str]] = {}
        for rule in sorted(groups, key=lambda r: order.index(r) if r in order else len(order)):
            rule_reads: set[str] = set()
            bodies = []
            texts: list[str] = []
            for u in groups[rule]:
                ren = self.key_rename(u, key_leaves, knames)
                targets = []
                for t, labs in zip(u.head.args[2:], vlabs):
                    leaves = t.args if isinstance(t, RecordTerm) else (t,)
                    if len(leaves) == len(labs) and all(isinstance(x, Variable) for x in leaves):
                        targets.extend((x.name, lab) for x, lab in zip(leaves, labs))
                vs: set[str] = set()
                collect_vars(list(u.body or ()), vs)
                given = {tl for _, tl in targets}
                for v, tl in targets:
                    ren[v] = tl
                for v in sorted(vs):
                    if v not in dict(targets) and ren.get(v, v) in given:
                        n = 2
                        while f"{ren.get(v, v)}{n}" in vs or f"{ren.get(v, v)}{n}" in given:
                            n += 1
                        ren[v] = f"{ren.get(v, v)}{n}"
                # the rule's fields, under the labels its first clause gives them
                fv = [a.name for a in u.head.args[1].args]
                if rule not in fields_of:
                    fields_of[rule] = [ren.get(v, v) for v in fv]
                ren.update(zip(fv, fields_of[rule]))
                w = ClauseWriter(c, scope, c.parse_sub if scope == ("Parse",) else {}, ren, own_inst=key)
                body = w.lits(list(u.body or ()), set())
                reads |= w.reads
                rule_reads |= w.reads
                pred_branches |= w.branches | {x for x in ctor_names(u.head.args[0]) if x in case_ctors}
                todos = self.todo.take()
                if len(targets) != len(flat_v):
                    self.todo.add("head-term", f"{rule}: a prediction head site that is no label")
                    todos += self.todo.take()
                texts += self.plain_comments(u.span.first if u.span else 0)
                bodies.append((todos, body))
            if not texts and isinstance(dem, AdtType):
                # the rule's text: the comments above its constructor
                ks = list(dem.constructors)
                at = next((n for n, k in enumerate(ks) if k.name == rule), None)
                if at is not None:
                    lo = ks[at - 1].span.first if at else dem.span.first
                    cm = [comment_text(self.lines[ln]) for ln in range(lo, ks[at].span.first - 1)]
                    texts = [params_to_amp(t) for d, t, _ in directives([x for x in cm if x is not None])
                             if d == "" and t]
            cols = set(flat_v) | set(knames) | set(fields_of[rule])
            lines = or_body(bodies, cols, set()) if len(bodies) > 1 else [*bodies[0][0], *bodies[0][1]]
            # the header makes each field's label, so the body joins it
            for x in fields_of[rule]:
                lines = [re.sub(rf"\*{re.escape(x)}(?!\w)", x, l) for l in lines]
            pred = c.wrote("&prediction", Written(scope, f"{inst.name}.prediction", False))
            rule_lines = [f"({side} {pred}"] + ["  " + l for l in lines]
            close(rule_lines, ")")
            head = f"(${rule} {' '.join('*' + x for x in fields_of[rule])})" if fields_of[rule] else f"${rule}"
            rules.append((rule, " ".join(texts), rule_lines, rule_reads, head))
        lines = list(f.lines)
        lines[0] = f"(DEMONSTRATED {c.rel_name(scope, inst.name)}"
        last = max(i for i, l in enumerate(lines) if not l.lstrip().startswith(";;"))
        assert lines[last].endswith(")")
        lines[last] = lines[last][:-1]
        if c.demo_mode.get(key) == "pair":
            lines = [lines[0], *self.pair_key(lines[1:], head_labels("demonstration"))]
        f.branches = tuple(sorted(set(f.branches) | pred_branches))
        f.demo = rules
        f.demo_head = lines
        f.demo_input_reads = set(f.reads)
        f.lines = lines + demo_lines(rules, {})
        f.reads = reads - {f.name}
        f.src_inst = (inst, us, side)
        return [f]

    def pair_key(self, lines: list[str], dlabs: list[list[str]]) -> list[str]:
        """A DEMONSTRATED form's inputs keyed by the demonstrated pair: the
        demonstration's body as the key clause, with the demonstration
        inside it, then the other inputs."""
        blocks: list[list[str]] = []
        pending: list[str] = []
        for l in lines:
            if l.startswith("  ;;"):
                pending.append(l)
            elif l.startswith("  (") or not blocks:
                blocks.append(pending + [l])
                pending = []
            else:
                blocks[-1].append(l)
        dem = next((b for b in blocks if any(x.startswith("  (demonstration (") for x in b)), None)
        knames = [ls[0] for ls in dlabs[:2] if ls]
        if dem is None or len(knames) != 2:
            self.todo.add("demonstrated-pair", "the demonstration's head")
            return [*self.todo.take(), *lines]
        i = next(k for k, x in enumerate(dem) if x.startswith("  (demonstration ("))
        head = dem[i].strip()
        body = [x[4:] for x in dem[i + 1:]]
        if not body:
            self.todo.add("demonstrated-pair", "the demonstration has no body")
            return [*self.todo.take(), *lines]
        assert body[-1].endswith(")")
        body[-1] = body[-1][:-1]
        body = mark_key(body, knames)
        lead = "  (key ("
        out = dem[:i] + [lead + body[0]] + [" " * len(lead) + x for x in body[1:]]
        close(out, ")")
        out.append(f"    {head})")
        close(out, ")")
        return out + [x for b in blocks if b is not dem for x in b]

    def pick_form(self, p) -> Form | None:
        c = self.c
        if p.ones is not None and p.fold:
            return None
        amp = c.rel_name(p.scope, p.name)
        sub = c.parse_sub if p.scope == ("Parse",) else {}
        lines = [f"(CHOOSE {amp}"]
        reads: set[str] = set()
        for note in p.notes:
            self.todo.add("pick-read", note)
        lines.extend("  " + t for t in self.todo.take())
        if p.ones is not None:
            # a clause of the item atom, with the pick's marks
            w = ClauseWriter(c, p.scope, sub, {})
            body = w.lits([AtomLiteral(p.item, False)], set())
            lines[0] = f"(RULE {amp}"
            lines.extend("  " + l for l in body)
            item_vars = set(term_vars(p.item.args, []))

            def key_labels(v: str) -> list[str]:
                """The labels the item atom writes for the column variable `v`: its own where it is a scalar, those
                of its fields where it is a record. A case's or a lifted key is not written."""
                keep = set(term_vars(p.spread.get(v, Variable(v)), []))
                only = {n: Wildcard() for n in item_vars - keep}
                saved = list(self.todo.pending), Counter(self.todo.kinds)
                text = ClauseWriter(c, p.scope, sub, {}).lits([AtomLiteral(subst_terms(p.item, only), False)], set())
                self.todo.pending, self.todo.kinds = saved
                return list(dict.fromkeys(re.findall(r"\*(\w+)", " ".join(text))))
            lines.extend("  (" + " ".join(["ONE"] + [x for v in key for x in key_labels(v)]) + ")" for key in p.ones)
            close(lines, ")")
            f = Form(lines, amp, w.reads - {amp}, line=p.line)
            f.comments = [";; " + t for t in self.plain_comments(f.line)]
            for d, rest, _ in directives(self.comments_above(f.line)):
                if d == "claim":
                    f.claim_slugs = rest.split()
            return f
        drop = {n: Wildcard() for n in p.items}
        w = ClauseWriter(c, p.scope, sub, {})
        slot = [l.replace("*", "^") for l in w.lits([AtomLiteral(subst_terms(p.item, drop), False)], set())]
        reads |= w.reads
        heads = set(re.findall(r"\^(\w+)", " ".join(slot)))
        w = ClauseWriter(c, p.scope, sub, {})
        item = w.lits([AtomLiteral(p.item, False)], set(heads))
        reads |= w.reads
        nevers: list[tuple[list[str], list[str]]] = []
        for body in p.aparts:
            wn = ClauseWriter(c, p.scope, sub, {})
            ls = wn.lits(list(body), set())
            reads |= wn.reads
            nevers.append((self.todo.take(), ls))
        # the labels of the candidate and of the row named as the chosen relation's columns
        _, pcols, _, _ = c.resolve(RelationName((), p.name), p.scope, sub)
        vars_ = p.fold or p.cvars
        if pcols is not None and len(pcols) == len(vars_):
            ren: dict[str, str] = {}
            for (col, leaves), v in zip(pcols, vars_):
                if v is None:
                    continue
                terms = w.split(Variable(v), leaves)
                nkeep = sum(1 for l in leaves if l.kind == "keep")
                for l, t in zip(leaves, terms):
                    if l.kind == "keep" and isinstance(t, Variable):
                        ren[w.label(t.name)] = l.name if nkeep > 1 else col.name
            made = label_names(item) | label_names(slot) | set().union(set(), *(label_names(ls) for _, ls in nevers))
            ren = {a: b for a, b in ren.items() if a != b and b not in made and list(ren.values()).count(b) == 1}
            if ren:
                def rename(mark, x):
                    return mark + ren.get(x, x)
                item = relabel(item, rename)
                slot = relabel(slot, rename)
                nevers = [(todos, relabel(ls, rename)) for todos, ls in nevers]
                heads = {ren.get(x, x) for x in heads}
        lines.extend(nest_keyed(slot if heads else None, [["  (@@in " + " ".join(item) + ")"]],
                                sorted(heads), "for"))
        for todos, ls in nevers:
            lines.extend("  " + t for t in todos)
            lines.append("  (never")
            lines.extend("    " + l for l in ls)
            close(lines, ")")
        close(lines, ")")
        reads.discard(amp)
        f = Form(lines, amp, reads, line=p.line)
        f.comments = [";; " + t for t in self.plain_comments(f.line)]
        for d, rest, _ in directives(self.comments_above(f.line)):
            if d == "claim":
                f.claim_slugs = rest.split()
        return f

    def key_rename(self, u: Unit, key_leaves, knames) -> dict[str, str]:
        if not u.head.args:
            return {}
        w = ClauseWriter(self.c, (), {}, {})
        terms = w.split(u.head.args[0], key_leaves)
        kept = [t for l, t in zip(key_leaves, terms) if l.kind in ("keep", "example")]
        ren = {}
        for t, n in zip(kept, knames):
            if isinstance(t, Variable) and t.name != n:
                ren[t.name] = n
        vars_: set[str] = set()
        collect_vars(list(u.body or []), vars_)
        for t in u.head.args[1:]:
            collect_vars([AtomLiteral(Atom(u.head.relation, (t,), 0), False)], vars_)
        taken = set(ren.values())
        for v in sorted(vars_):
            if v in taken and v not in ren:
                n = 2
                while f"{v}{n}" in vars_ or f"{v}{n}" in taken:
                    n += 1
                ren[v] = f"{v}{n}"
                taken.add(ren[v])
        return ren

