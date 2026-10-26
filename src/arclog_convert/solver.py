"""`Claim` and `Solver`, which converts one solver. `Solver` composes the mixins
of `solver_params`, `solver_instances`, `solver_render` and `solver_cases`,
each holding one group of its methods; this module holds its construction,
its header reading and `run`."""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass, fields as dc_fields, is_dataclass, replace as dc_replace
from engine.program import (
    Aggregate,
    AtomLiteral,
    Comparison,
    ConstructorTerm,
    Disjunction,
    GridCall,
    RecordTerm,
    Unit,
    Variable,
    Wildcard,
)
from arclog_convert.frame_reads import FieldPlan, field_plan
from arclog_convert import libmap
from arclog_convert.helper_rows import helper_rels, rows as helper_rows_of

from arclog_convert.clauses import ClauseWriter
from arclog_convert.forms import (
    Form,
    Todo,
    comment_text,
    directives,
    grid_param,
    mask_param,
    or_gloss,
    params_to_amp,
    unplaced_rows,
    wrap_param,
)
from arclog_convert.leaves import Converter, Written
from arclog_convert.lib import (
    DET_COLS,
    KeyedTable,
    Lib,
    PROPOSER_COLS,
    covered_proposer,
    derive_proposer,
    domain_proposer,
    keyed_row,
    keyed_tables,
    pascal,
    plan_proposer,
)
from arclog_convert.solver_cases import CasesMixin
from arclog_convert.solver_instances import InstancesMixin
from arclog_convert.solver_params import ParamsMixin
from arclog_convert.solver_render import RenderMixin
from arclog_convert.terms import MOVED_RELS, NEG_OP, ctor_names, subst, subst_terms, var_uses


# the lib relations that list the members of a closed set: a literal of one
# of them has a member at each binding
ELEM_RELATIONS = frozenset({
    "dir_elem", "axis_elem", "diag_dir_elem", "diag_axis_elem", "d4_elem",
    "c4_elem", "sense_elem", "sym_elem", "dir8_elem", "axis4_elem"})


def negative_reads(lits, outer: tuple, scope: tuple[str, ...], out: dict) -> None:
    """Add to `out`, for each relation, the negated reads in `lits`, each with
    the literals of its reading clause that hold at the read: those of the
    conjunction it stands in and of each conjunction around it."""
    here = outer + tuple(lits)
    for l in lits:
        if isinstance(l, AtomLiteral) and l.negated and not l.atom.relation.instances:
            out[l.atom.relation.name].append((l.atom, here, scope))
        elif isinstance(l, Disjunction):
            for b in l.branches:
                negative_reads(b, here, scope, out)
        elif isinstance(l, Comparison):
            for t in (l.lhs, l.rhs):
                if isinstance(t, Aggregate):
                    negative_reads(t.body, here, scope, out)


def term_matches(t, s, free: set[str], once: set[str], sigma: dict) -> bool:
    """The domain term `t` stands for the term `s` of the reading clause, under
    `sigma`, which it extends: a variable of `free` takes the term it meets,
    and takes a `_` only where it stands once in the defect clause."""
    if isinstance(t, Variable) and t.name in free:
        if t.name in sigma:
            return sigma[t.name] == s and not isinstance(s, Wildcard)
        if isinstance(s, Wildcard) and t.name not in once:
            return False
        sigma[t.name] = s
        return True
    if isinstance(t, Wildcard):
        return True
    if isinstance(t, (ConstructorTerm, RecordTerm)):
        return (type(s) is type(t) and getattr(s, "name", None) == getattr(t, "name", None)
                and len(s.args) == len(t.args)
                and all(term_matches(a, b, free, once, sigma) for a, b in zip(t.args, s.args)))
    return t == s


def domain_has_member(u: Unit, test_i: int, atom, context: tuple) -> bool:
    """The clause `u` of a defect relation, read as `!R(args)` with `atom` in a
    clause whose literals at the read are `context`, has a member of its domain
    at each binding of the reading clause: each literal of `u` but its test
    maps onto a positive atom of `context`, or onto an equal literal of it,
    under one substitution of the variables that `u` does not take from the
    head, or is a literal of a lib element relation."""
    heads = [h.name for h in u.head.args]
    if len(set(heads)) != len(heads) or len(heads) != len(atom.args):
        return False
    if not all(isinstance(a, Variable) for a in atom.args):
        return False
    uses: Counter = Counter()
    var_uses(u.body, uses)
    once = {v for v, n in uses.items() if n == 1}
    free = {v for v in uses if v not in heads}
    key = {h: a for h, a in zip(heads, atom.args)}
    dom = [subst_terms(l, key) for i, l in enumerate(u.body) if i != test_i]
    # the variables of `u` that its head does not name get names no reading clause holds
    rename = {v: "?" + v for v in free}
    dom = [subst(l, rename) for l in dom]
    free = set(rename.values())
    once = {rename.get(v, v) for v in once}
    atoms = [l for l in dom if isinstance(l, AtomLiteral) and not l.negated
             and l.atom.relation.name not in ELEM_RELATIONS]
    others = [l for l in dom if not (isinstance(l, AtomLiteral) and not l.negated)]
    elems = [l for l in dom if isinstance(l, AtomLiteral) and not l.negated
             and l.atom.relation.name in ELEM_RELATIONS]
    if any(not all(isinstance(a, Variable) for a in l.atom.args) for l in elems):
        return False
    partners = [l.atom for l in context if isinstance(l, AtomLiteral) and not l.negated]

    def place(i: int, sigma: dict) -> bool:
        if i == len(atoms):
            held = [unlined(l) for l in context]
            return all(unlined(subst_terms(l, sigma)) in held for l in others)
        a = atoms[i].atom
        for p in partners:
            if p.relation != a.relation or len(p.args) != len(a.args):
                continue
            trial = dict(sigma)
            if all(term_matches(x, y, free, once, trial) for x, y in zip(a.args, p.args)) \
                    and place(i + 1, trial):
                return True
        return False
    return place(0, {})


def unlined(x):
    """`x` with the line number of each atom and comparison in it set to 0."""
    if isinstance(x, tuple):
        return tuple(unlined(y) for y in x)
    if is_dataclass(x) and not isinstance(x, type):
        return dc_replace(x, **{f.name: (0 if f.name == "line" else unlined(getattr(x, f.name)))
                                for f in dc_fields(x)})
    return x


@dataclass
class Claim:
    kind: str     # INPUT | OUTPUT
    slug: str
    text: str
    approx: str | None = None



class Solver(ParamsMixin, InstancesMixin, RenderMixin, CasesMixin):
    def __init__(self, stem: str, lib: Lib, sig: Lib, todo: Todo, inline: frozenset[str] = frozenset()) -> None:
        self.stem = stem
        self.todo = todo
        self.c = Converter(stem, lib, sig, todo, inline)
        self.lines = self.c.src_lines
        self.c.skip_rels = {"impl_choice"}

    # ---- header

    def header(self):
        lines = []
        for raw in self.lines:
            t = comment_text(raw)
            if t is None:
                if raw.strip():
                    break
                continue
            lines.append(t)
        claims: list[Claim] = []
        rep = None
        approx_witness: dict[str, list[str]] = defaultdict(list)
        for d, rest, ind in directives(lines[1:]):
            if d in ("scene", "rule"):
                m = re.match(r"([\w-]+):\s*(.*)", rest)
                if m:
                    claims.append(Claim("INPUT" if d == "scene" else "OUTPUT", m.group(1), params_to_amp(m.group(2))))
            elif d == "approximated" and claims:
                claims[-1].approx = params_to_amp(rest)
            elif d == "witness" and claims:
                approx_witness[claims[-1].slug].append(rest)
            elif d == "representative":
                rep = rest
        return claims, rep, approx_witness

    # ---- comments above a line

    def derives_from_params(self, u: Unit) -> bool:
        """A Params clause that reads only parameters and the lib, and no
        evidence: derived data, a RULE."""
        params = {r.name for r in self.c.prog.relations if r.scope.components == ("Params",)}

        def ok(lits) -> bool:
            for l in lits:
                if isinstance(l, AtomLiteral):
                    rn = l.atom.relation
                    if rn.instances or not (rn.name in params or rn.name in self.c.lib.top
                                            or rn.name in self.c.sig.top):
                        return False
                elif isinstance(l, Disjunction):
                    if not all(ok(b) for b in l.branches):
                        return False
                elif isinstance(l, Comparison) and any(isinstance(t, Aggregate) for t in (l.lhs, l.rhs)):
                    return False
            return True
        return ok(u.body or ())

    def open_amps(self) -> set[str]:
        return {self.c.rel_name(("Params",), n) for n in self.c.open_params}

    def comments_above(self, line: int) -> list[str]:
        out = []
        i = line - 2
        while i >= 0:
            t = comment_text(self.lines[i])
            if t is None:
                break
            out.append(t)
            i -= 1
        return list(reversed(out))

    def gloss_at(self, line: int) -> str:
        """The gloss of the declaration at `line`: its comment lines that
        are no directive."""
        return " ".join(rest for d, rest, _ in directives(self.comments_above(line)) if d == "")

    # ---- main

    def run(self) -> tuple[str, str]:
        c = self.c
        prog = c.prog
        claims, rep, approx_w = self.header()
        points = c.point_fields()
        concept = {adt.constructors[0].name for _, adt in points}
        all_ctors = {k.name: f for f, adt in points for k in adt.constructors}

        self.case_sets = c.case_sets = set()
        self.case_set_rows: dict[str, list[dict[str, str]]] = {}
        self.case_set_types: dict[str, set[str]] = {}
        c.case_set_unread = set()
        for r in prog.relations:
            own = [u for u in prog.units if u.head.relation.name == r.name and u.scope == r.scope
                   and not u.head.relation.instances]
            if r.scope.components in ((), ("Parse",), ("Determine",), ("Params",)) and r.columns \
                    and all(col.type.name in c.case_types for col in r.columns) \
                    and (r.name == "impl_choice" or not [u for u in prog.units if u.head.relation.name == r.name
                                                         and u.body is not None and u.scope.components == r.scope.components]) \
                    and (r.scope.components in ((), ("Parse",)) or own):
                c.skip_rels.add(r.name)
                facts = [u for u in prog.units if u.head.relation.name == r.name and u.body is None]
                full = len(r.columns) == 1 and not [u for u in prog.units if u.head.relation.name == r.name
                                                     and u.body is not None] and \
                    {frozenset(ctor_names(u.head.args[0])) for u in facts} == \
                    {frozenset(v) for v in self.type_values(r.columns[0].type.name)}
                if not full and r.name != "impl_choice":
                    self.case_sets.add(r.name)
                    rows = []
                    for u in facts:
                        row = {}
                        def walk(t):
                            if isinstance(t, ConstructorTerm):
                                for f_, adt_ in self.c.point_fields():
                                    if any(k.name == t.name for k in adt_.constructors):
                                        row[f_] = t.name
                                for a in t.args:
                                    walk(a)
                            elif isinstance(t, RecordTerm):
                                for a in t.args:
                                    walk(a)
                        for a in u.head.args:
                            walk(a)
                        rows.append(row)
                    self.case_set_rows[r.name] = rows
                    self.case_set_types[r.name] = set().union(*(self.reached_types(col.type.name) for col in r.columns))
        c.skip_rels.discard("out")
        concept_of = c.concept_of()
        for name, rows in self.case_set_rows.items():
            if not any(all(row.get(f_, k) == k for f_, k in concept_of.items()) for row in rows):
                c.case_set_unread.add(name)
        self.concept_of = concept_of
        # enumerators feeding impl_choice
        for u in prog.units:
            if not u.scope.components and u.head.relation.name == "impl_choice" and u.body:
                for l in u.body:
                    if isinstance(l, AtomLiteral):
                        c.skip_rels.add(l.atom.relation.name)

        # instance key names from the first input clause of each instance
        for u in prog.units:
            if u.head.relation.instances and u.body is not None:
                inst_path = u.head.relation.instances
                scope = u.scope.components
                key = None
                for i in range(len(scope), -1, -1):
                    if (scope[:i], inst_path[0]) in c.insts:
                        key = (scope[:i], inst_path[0])
                        break
                if key is None or len(inst_path) != 1 or key in c.key_names:
                    continue
                inst = c.insts[key]
                if inst.component not in c.lib.comps or not u.head.args:
                    continue
                tparams, lrels = c.lib.relations(inst.component)
                lr0 = next((r for r in lrels if r.name == u.head.relation.name), None)
                if lr0 is None or not lr0.cols or lr0.cols[0].name != "key":
                    continue
                sub = {p: a.name for p, a in zip(tparams, inst.type_args)}
                leaves = c.leaves("key", "Key", True, key[0], sub,
                                  outer=c.parse_sub if key[0] == ("Parse",) else {})
                ws = ClauseWriter(c, scope, {}, {})
                saved = list(self.todo.pending), Counter(self.todo.kinds)
                terms = ws.split(u.head.args[0], leaves)
                self.todo.pending, self.todo.kinds = saved
                spans = isinstance(u.head.args[0], Variable) and len(leaves) > 1
                names = [t.name if isinstance(t, Variable) and not spans else pascal(l.name)
                         for l, t in zip(leaves, terms) if l.kind in ("keep", "example")]
                c.key_names[key] = names
                c.key_paths[key] = [l.path for l in leaves if l.kind in ("keep", "example")]

        forms: list[Form] = []
        # a Parse relation the program fills from `in` is `in`, in every
        # form that reads it, the determination's included
        # (a relation with a clause that is no copy of `in` is no alias of it)
        not_copy: set[str] = set()
        for u in prog.units:
            path = u.head.relation.instances
            inst = c.insts.get(((), path[0])) if path and u.scope.components == () else None
            if inst is not None and inst.component in c.comps and len(path) == 1 and not (
                    u.body and len(u.body) == 1 and isinstance(u.body[0], AtomLiteral)
                    and u.body[0].atom.relation.name == "in"):
                not_copy.add(u.head.relation.name)
        for u in prog.units:
            path = u.head.relation.instances
            inst = c.insts.get(((), path[0])) if path and u.scope.components == () else None
            if inst is not None and inst.component in c.comps and len(path) == 1 and u.body \
                    and len(u.body) == 1 and isinstance(u.body[0], AtomLiteral) \
                    and u.body[0].atom.relation.name == "in" and u.head.relation.name not in not_copy:
                c.names[(("Parse",), u.head.relation.name)] = "__in__"
        # a copy of the program's parse in the determination takes the name
        # of what it copies, after the program's parse
        for key, x in c.det_parse_copies.items():
            c.rel_name(("Parse",), x)
            cand, k = x, 2
            while cand in c.used_names:
                cand, k = f"{x}{k}", k + 1
            c.used_names.add(cand)
            c.names[key] = cand

        # defect relations: read only under negation, one clause, one test
        reads_pos: Counter[str] = Counter()
        reads_neg: Counter[str] = Counter()
        reads_inst: Counter[str] = Counter()   # a read through an instance path

        def scan_reads(lits):
            for l in lits:
                if isinstance(l, AtomLiteral) and not l.atom.relation.instances:
                    (reads_neg if l.negated else reads_pos)[l.atom.relation.name] += 1
                elif isinstance(l, AtomLiteral):
                    reads_inst[l.atom.relation.name] += 1
                elif isinstance(l, Disjunction):
                    for b in l.branches:
                        scan_reads(b)
                elif isinstance(l, Comparison):
                    for t in (l.lhs, l.rhs):
                        if isinstance(t, Aggregate):
                            scan_reads(t.body)
        for u in prog.units:
            scan_reads(u.body or [])
        defs: dict[str, list[Unit]] = defaultdict(list)
        for u in prog.units:
            if not u.head.relation.instances and u.scope.components in ((), ("Parse",)):
                defs[u.head.relation.name].append(u)
        c.all_inline = {}
        for name, us in defs.items():
            if len(us) != 1 or reads_pos[name] or reads_inst[name] or not reads_neg[name] or name in c.skip_rels:
                continue
            u = us[0]
            if not u.body or any(isinstance(l, Disjunction) for l in u.body):
                continue
            if not all(isinstance(a, Variable) for a in u.head.args):
                continue
            r = c.rels.get((u.scope.components, name))
            if r is None or any(col.type.name in c.case_types for col in r.columns):
                continue
            negs = [i for i, l in enumerate(u.body) if isinstance(l, AtomLiteral) and l.negated]
            cmps = [i for i, l in enumerate(u.body) if isinstance(l, Comparison) and l.op in NEG_OP
                    and not isinstance(l.lhs, Aggregate) and not isinstance(l.rhs, Aggregate)]
            if len(negs) == 1:
                c.all_inline[name] = (u, negs[0])
            elif not negs and cmps:
                c.all_inline[name] = (u, cmps[-1])
        # a defect relation whose test negates another: the universal reads
        # that other relation positively, so it is declared
        for name, (u, i) in list(c.all_inline.items()):
            t = u.body[i]
            if isinstance(t, AtomLiteral) and not t.atom.relation.instances:
                c.all_inline.pop(t.atom.relation.name, None)
        # an `ALL` with no member fails where the negation of the relation holds,
        # so a relation stays inlined only where each read gives its domain a member
        sites: dict[str, list] = defaultdict(list)
        for u in prog.units:
            negative_reads(u.body or (), (), u.scope.components, sites)
        for name, (u, i) in list(c.all_inline.items()):
            if not all(scope == u.scope.components and domain_has_member(u, i, atom, ctx)
                       for atom, ctx, scope in sites[name]):
                del c.all_inline[name]
        self.all_count = len(c.all_inline)

        # params and determine
        params_decls = [r for r in prog.relations if r.scope.components == ("Params",)]
        # the proposers of each parameter's @derive lines
        self.derive_props = {r.name: list(dict.fromkeys(
            derive_proposer(rest) for d, rest, _ in directives(self.comments_above(r.span.first)) if d == "derive"))
            for r in params_decls if r.span}
        self.many = {n for n, ps in self.derive_props.items() if len(ps) > 1}

        det_units = defaultdict(list)
        for u in prog.units:
            if u.scope.components == ("Determine",) and not u.head.relation.instances:
                det_units[u.head.relation.name].append(u)
        det_units_all = {k: list(v) for k, v in det_units.items()}
        self.rigid_proposed: set[str] = set()   # the rigid parts a proposer's table gives
        param_facts: dict[str, list] = defaultdict(list)
        param_rules: dict[str, list] = defaultdict(list)
        for u in prog.units:
            if u.scope.components == ("Params",):
                if u.body is None:
                    param_facts[u.head.relation.name].append(u)
                else:
                    param_rules[u.head.relation.name].append(u)
        grid_params = defaultdict(list)
        for m in prog.macros:
            if isinstance(m, GridCall) and m.scope.components == ("Params",):
                grid_params[m.relation.name].append(m)

        arcdata_params: list[str] = []
        arcdata_excludes: list[str] = []
        derive_points: list[tuple[str, list]] = []
        # A Params relation the helpers derive is a parameter, its rows a
        # run's; a stored relation only those clauses read drops out.
        helper_derived = set(helper_rels(prog))
        helper_rows = helper_rows_of(c.stem) if helper_derived else {}
        for tiles, table in c.tile_frames.items():
            helper_rows[tiles] = unplaced_rows(helper_rows.get(table, []))
        param_names = {r.name for r in params_decls}
        read_elsewhere: set[str] = set()

        def collect(lits, in_params):
            for l in lits:
                if isinstance(l, AtomLiteral):
                    rn = l.atom.relation
                    if (in_params and not rn.instances) or rn.instances == ("params",):
                        read_elsewhere.add(rn.name)
                elif isinstance(l, Disjunction):
                    for b in l.branches:
                        collect(b, in_params)
                elif isinstance(l, Comparison):
                    for t in (l.lhs, l.rhs):
                        if isinstance(t, Aggregate):
                            collect(t.body, in_params)
        for u in prog.units:
            if u.scope.components == ("Params",) and u.head.relation.name in helper_derived:
                continue
            collect(u.body or (), u.scope.components == ("Params",))
        # a table whose clauses `field_plan` takes, a frame or a tiled frame of extents
        # that parameters give: instances over those parameters' DETs; else
        # one whose clauses read a frame of a stored extent: a Frame2D or
        # AxisFrame instance; and the sources of each stay
        fielded: dict[str, FieldPlan] = {}
        framed: dict[str, tuple[str, list, list]] = {}
        for name in helper_derived:
            fields = field_plan(param_rules.get(name, []), param_names)
            if fields is not None:
                fielded[name] = fields
                continue
            got = self.frame_plan(param_rules.get(name, []))
            if got is not None:
                framed[name] = got
        instanced = framed.keys() | fielded.keys()
        helper_inputs: set[str] = set()
        for u in prog.units:
            if u.scope.components == ("Params",) and u.head.relation.name in helper_derived \
                    and u.head.relation.name not in instanced:
                collect_into = set()
                for l in u.body or ():
                    if isinstance(l, AtomLiteral) and not l.atom.relation.instances:
                        collect_into.add(l.atom.relation.name)
                helper_inputs |= collect_into & param_names
        dropped = helper_inputs - read_elsewhere - helper_derived
        # the name a parameter's DET writes, where no stored side stands: the
        # derivation of a table the helpers derive, the proposer the plan
        # covers the parameter with, or the one whose domain the DET tests
        c.proposer_cols = {}
        covered: dict[str, str] = {}   # each parameter the plan covers with a proposer, its proposer
        helper_det: dict[str, tuple[str | None, str | None]] = {}   # each helper table: its derivation and its param
        for r in params_decls:
            ds = directives(self.comments_above(r.span.first)) if r.span else []
            types = [col.type.name for col in r.columns]
            if r.name in helper_derived and r.name not in dropped and r.name not in instanced:
                helper_det[r.name] = self.helper_derivation(
                    c.rel_name(("Params",), r.name), param_rules.get(r.name, []), helper_rows.get(r.name, []))
                prop = helper_det[r.name][0]
                name = libmap.DERIVATIONS[prop] if prop else None
            elif any(d == "derive" for d, _, _ in ds):
                if r.name in c.cand_params:
                    continue   # a DET_OR_RULE with a body: the columns its body's labels give
                # a DET_OR_RULE with no body: its first proposer's columns
                name = self.derive_props[r.name][0]
            elif r.name in c.cand_params:
                name = domain_proposer(types)
            else:
                name = plan_proposer(self.plan().get(r.name), types, r.name in c.open_params)
                if name in PROPOSER_COLS:
                    covered[r.name] = name
            if name in DET_COLS:
                c.proposer_cols[r.name] = DET_COLS[name]
        # each set-keyed table: its two parameters, one relation of its name
        decls = {r.name: r for r in params_decls}
        keyed: dict[str, KeyedTable] = {}
        for kt in keyed_tables({n: [col.type.name for col in r.columns] for n, r in decls.items()}, covered):
            if kt.name in c.used_names or any((("Params",), n) in c.names for n in (kt.child, kt.parent)):
                raise ValueError(f"{kt.child}, {kt.parent}: the name {kt.name} of their table is taken")
            c.used_names.add(kt.name)
            for n, cols in ((kt.child, kt.child_cols()), (kt.parent, kt.parent_cols())):
                c.names[(("Params",), n)] = kt.name
                c.proposer_cols[n] = cols
                keyed[n] = kt
        self.param_order: dict[str, list[int]] = {}
        for r in params_decls:
            if r.name in dropped:
                det_units.pop(r.name, None)
                continue
            if r.name in c.skip_rels:
                continue
            if r.name in fielded:
                forms.extend(self.field_forms(r, fielded[r.name]))
                continue
            if r.name in framed:
                forms.extend(self.frame_forms(r, framed[r.name]))
                continue
            if r.name in helper_derived:
                amp = c.rel_name(("Params",), r.name)
                cm = self.comments_above(r.span.first) if r.span else []
                gloss = " ".join(rest for d, rest, _ in directives(cm) if d == "")
                prop, record = helper_det[r.name]
                rows = helper_rows.get(r.name, [])
                f = Form([f"(DET {amp}{' ' + prop if prop else ''})"], amp, set(), line=r.span.first if r.span else 0)
                if prop is None:
                    self.todo.add("no-det-proposer", f"{amp}: no proposer gives the table")
                else:
                    self.todo.add("stored-fields", f"{amp}: the {libmap.DERIVATIONS[prop]} fields are stored")
                f.comments = [*(f";; {params_to_amp(g)}" for g in [gloss] if g), *self.todo.take()]
                forms.append(f)
                arcdata_params.append(record or mask_param(amp, rows) or
                                      "\n".join([f"(param {amp}"] + ["  (" + " ".join(row) + ")" for row in rows]) + ")")
                continue
            if r.name.startswith("_rigid_"):
                placed = r.name[len("_rigid_"):]
                if placed in c.rigid and (r.name in param_facts or r.name in grid_params):
                    arcdata_params.append(self.param_line(c.rel_name(("Params",), placed), r,
                                                          param_facts.get(r.name, []), grid_params.get(r.name, [])))
                continue
            if r.name in c.rigid:
                us = det_units.pop(r.name, [])
                for u in us:
                    forms.append(self.clause(u, "DET", ("Determine",), {}))
                verdict = self.plan().get(r.name)
                prop = covered_proposer(verdict, [col.type.name for col in r.columns[1:]])
                if not us and prop:
                    # a part whose value a proposer covers: its table is the proposer's
                    part = c.rel_name(("Determine",), r.name)
                    stored = decls.get("_rigid_" + r.name)   # the declaration of the part's `param` record
                    mark = "" if stored is None else self.set_mark(
                        c.rel_name(("Params",), r.name), stored, [prop], param_facts.get("_rigid_" + r.name, []),
                        grid_params.get("_rigid_" + r.name, []))
                    forms.append(Form([f"(DET {part} {prop}{mark})"], part, set(), line=r.span.first if r.span else 0))
                    self.rigid_proposed.add(r.name)
                continue
            cm = self.comments_above(r.span.first) if r.span else []
            ds = directives(cm)
            gloss = " ".join(rest for d, rest, _ in ds if d == "")
            derives = [rest for d, rest, _ in ds if d == "derive"]
            under = None   # the proposer of the @derive line an @ignore line stands under
            for d, rest, _ in ds:
                if d == "derive":
                    under = derive_proposer(rest)
                elif d == "ignore":
                    arcdata_excludes.extend(self.ignore_line(r.name, rest, concept, under))
                else:
                    under = None
            amp = c.rel_name(("Params",), r.name)
            kt = keyed.get(r.name)
            if kt is not None:
                # a set-keyed table: one DET and one param, at its child
                if r.name == kt.child:
                    f = Form([f"(DET {amp} {kt.proposer})"], amp, set(), line=r.span.first if r.span else 0)
                    parent = decls[kt.parent]
                    glosses = (gloss, self.gloss_at(parent.span.first) if parent.span else "")
                    f.comments = [f";; {params_to_amp(g)}" for g in glosses if g]
                    forms.append(f)
                    arcdata_params.append(self.keyed_param_line(amp, kt, param_facts, grid_params))
                continue
            if derives:
                props = self.derive_props[r.name]
                if r.name in c.cand_params:
                    # the stored reading: the candidates the examples show, kept by the program's fit
                    lab = pascal(r.columns[0].name)
                    f = Form([f"(DET_OR_RULE {amp}{or_gloss(gloss)} {' '.join(props)}", f"  (ex_input (:Col *{lab})))"],
                             amp, set(), line=r.span.first)
                else:
                    mark = self.set_mark(amp, r, props, param_facts.get(r.name, []), grid_params.get(r.name, []))
                    f = Form([f"(DET_OR_RULE {amp}{or_gloss(gloss)} {' '.join(props)}{mark})"], amp, set(),
                             line=r.span.first)
                forms.append(f)
                derive_points.append((amp, derives, "Derived", r.name))
            elif r.name in c.cand_params:
                # the candidates the determination tested: every value, kept by the fit
                types = [col.type.name for col in r.columns]
                f = Form([f"(DET {amp} {domain_proposer(types)})"], amp, set(),
                         line=r.span.first if r.span else 0)
                f.comments = [f";; {params_to_amp(gloss)}"] if gloss else []
                forms.append(f)
            elif r.name in param_rules:
                made = [self.clause(u, "RULE" if self.derives_from_params(u) else "DET", ("Params",), {})
                        for u in param_rules[r.name]]
                forms.extend(made)
                self.set_param_order(amp, r, made)
            elif r.name in det_units:
                made = [self.clause(u, "DET", ("Determine",), {}, name_scope=("Params",))
                        for u in det_units.pop(r.name)]
                forms.extend(made)
                self.set_param_order(amp, r, made)
            elif r.name in c.orders:
                forms.append(self.order_form(r, amp, gloss))
            else:
                verdict = self.plan().get(r.name)
                types = [col.type.name for col in r.columns]
                prop = plan_proposer(verdict, types, r.name in c.open_params)
                if prop:
                    mark = self.set_mark(amp, r, [prop], param_facts.get(r.name, []), grid_params.get(r.name, []))
                    f = Form([f"(DET {amp} {prop}{mark})"], amp, set(), line=r.span.first if r.span else 0)
                    f.comments = [f";; {params_to_amp(gloss)}"] if gloss else []
                else:
                    f = Form([f"(DET {amp})"], amp, set(), line=r.span.first if r.span else 0)
                    kind = "no-det-rigid" if r.name.startswith("_rigid_") else \
                        "no-det-relation" if verdict and verdict[0] == "write" else \
                        "no-det-plan" if verdict is None or verdict[0] == "undecided" else "no-det-" + verdict[0]
                    why = "the plan gives no verdict" if verdict is None else \
                        "the plan leaves it undecided, and no type-domain proposer gives its value" \
                        if verdict[0] == "undecided" else " ".join(verdict[1:])
                    self.todo.add(kind, f"{amp}: {why}")
                    f.comments = [*(f";; {params_to_amp(g)}" for g in [gloss] if g), *self.todo.take()]
                forms.append(f)
            if r.name in param_facts or r.name in grid_params:
                arcdata_params.append(self.param_line(amp, r, param_facts.get(r.name, []), grid_params.get(r.name, [])))

        # each parameter's types, after its name
        self.param_types: dict[str, list[str]] = {}
        self.type_order: dict[str, list[int]] = {}   # per reordered parameter, its types' indices in the order of its record
        decl_of = {c.rel_name(("Params",), r.name): r for r in params_decls}
        for r in params_decls:
            if r.name.startswith("_rigid_") and r.name[len("_rigid_"):] in c.rigid:
                decl_of[c.rel_name(("Params",), r.name[len("_rigid_"):])] = r
        for i, text in enumerate(arcdata_params):
            m = re.match(r"\(param (\S+)", text)
            r = decl_of.get(m.group(1)) if m else None
            if r is None:
                continue
            kt = keyed.get(r.name)
            columns = self.ordered(m.group(1), r.columns) if kt is None else \
                keyed_row(decls[kt.parent].columns, decls[kt.child].columns)
            ts = [self.type_text(col.type.name) for col in columns
                  if col.type.name not in c.case_types and col.type.name not in c.open_types]
            self.param_types[m.group(1)] = ts
            if m.group(1) in self.param_order:
                kept = [i for i, col in enumerate(r.columns)
                        if col.type.name not in c.case_types and col.type.name not in c.open_types]
                self.type_order[m.group(1)] = [kept.index(i) for i in self.param_order[m.group(1)] if i in kept]
            types = ts[0] if len(ts) == 1 else "(" + " ".join(ts) + ")"
            arcdata_params[i] = grid_param(text[:m.end()] + " " + types, ts, text[m.end():]) or \
                wrap_param(text[:m.end()] + " " + types, text[m.end():])

        forms.extend(self.rigid_forms(det_units_all))

        for name, us in det_units.items():
            for u in us:
                if u.head.relation.instances and u.head.relation.instances[0] in ("ex",) and \
                        c.insts.get((("Determine",), u.head.relation.instances[0])) and \
                        c.insts[(("Determine",), u.head.relation.instances[0])].component in c.comps:
                    continue
        det_inst_units = defaultdict(list)
        for u in prog.units:
            if u.scope.components == ("Determine",):
                if u.head.relation.instances:
                    det_inst_units[u.head.relation.instances].append(u)
                elif u.head.relation.name in det_units and u.head.relation.name not in c.skip_rels:
                    forms.append(self.clause(u, "DET", ("Determine",), {}))

        # instances and clauses, in program order
        inst_units = defaultdict(list)
        for u in prog.units:
            sc = u.scope.components
            if sc in (("Params",), ("Determine",)):
                continue
            if u.head.relation.instances and sc == ():
                inst_units[u.head.relation.instances].append(u)
            elif u.head.relation.instances and sc == ("Parse",):
                inst_units[("Parse",) + u.head.relation.instances].append(u)

        # Parse inputs fed from `in`: alias
        parse_alias: dict[str, str] = {}
        for path, us in list(inst_units.items()):
            inst = c.insts.get(((), path[0]))
            if inst is not None and inst.component in c.comps and len(path) == 1:
                for u in us:
                    if u.body and len(u.body) == 1 and isinstance(u.body[0], AtomLiteral) \
                            and u.body[0].atom.relation.name == "in" and u.head.relation.name not in not_copy:
                        parse_alias[u.head.relation.name] = "in"
                    else:
                        forms.append(self.clause(u, "RULE", (), {}))
                del inst_units[path]
        for k in [k for k in det_inst_units if c.insts.get((("Determine",), k[0])) and
                  c.insts[(("Determine",), k[0])].component in c.comps]:
            del det_inst_units[k]
        self.parse_alias = parse_alias
        for n in parse_alias:
            c.names[(("Parse",), n)] = "__in__"


        # local clauses
        for u in prog.units:
            sc = u.scope.components
            if u.head.relation.instances:
                continue
            if sc not in ((), ("Parse",)):
                continue
            hn = u.head.relation.name
            if hn in c.skip_rels or hn in parse_alias and sc == ("Parse",):
                continue
            if hn == "impl_choice" or hn in c.all_inline or hn in c.demo_dropped:
                continue
            forms.append(self.clause(u, "RULE", sc, c.parse_sub if sc == ("Parse",) else {}))

        # instances
        for (sc, name), inst in c.insts.items():
            if inst.component not in c.lib.comps:
                continue
            if sc == ("Parse",):
                us = inst_units.get(("Parse", name), [])
                side = "RULE"
            elif sc == ("Determine",):
                us = det_inst_units.get((name,), [])
                side = "DET"
            elif sc == ():
                us = inst_units.get((name,), [])
                side = "RULE"
            elif sc == ("Params",) and inst.component != "ParamsHelpers":
                us = [u for u in prog.units if u.scope.components == sc and u.head.relation.instances == (name,)]
                side = "DET"
            else:
                continue
            forms.extend(self.instance(inst, us, side))
        for p in c.picks.values():
            pf = self.pick_form(p)
            if pf is not None:
                forms.append(pf)

        self.store_points = []
        decl_lines = [(r.span.first, r.name, None, r.scope.components) for r in prog.relations
                      if r.span and r.span.file is None and r.scope.components in ((), ("Parse",))]
        decl_lines += [(i.span.first, None, i, i.scope.components) for i in prog.instances
                       if i.span and i.span.file is None and i.scope.components in ((), ("Parse",))]
        for line, rname, inst, rscope in decl_lines:
            ds = directives(self.comments_above(line))
            gloss = " ".join(rest for d, rest, _ in ds if d == "")
            for d, rest, _ in ds:
                if d == "store":
                    m = re.match(r"(?:(\w+)\s*:)?\s*(.*)", rest)
                    sub_rel, more = m.groups()
                    sub_rel = sub_rel or ""
                    if inst is not None and inst.name in c.lib_moved:
                        # an expanded instance's directive: the relation of the shape that stands for its relation
                        was, moves = c.lib_moved[inst.name]
                        to = moves.get(sub_rel, inst.name).split(".")
                        amp = ".".join([c.rel_name(inst.scope.components, to[0]), *to[1:]])
                        wid = was + ("." + sub_rel if sub_rel else "")
                    elif inst is not None and inst.component == "Parse":
                        # the solver's own Parse: its relations are written as relations of their own
                        amp = c.rel_name(("Parse",), sub_rel)
                        MOVED_RELS[f"{inst.name}.{sub_rel}"] = amp[1:]   # the witness names spell it `parse.<rel>`
                        wid = inst.name + ("." + sub_rel if sub_rel else "")
                    elif inst is not None:
                        amp = c.rel_name(inst.scope.components, inst.name) + ("." + sub_rel if sub_rel else "")
                        wid = inst.name + ("." + sub_rel if sub_rel else "")
                    else:
                        amp = c.rel_name(rscope, rname)
                        wid = rname
                    if inst is not None and inst.component != "Parse":
                        c.wrote(amp, Written(inst.scope.components, wid, False))
                    self.store_points.append((amp, [":" + more], "Stored", wid))
                    forms.append(Form([f"(RULE_OR_DET {amp}{or_gloss(gloss)})"],
                                      amp.split(".")[0] if inst else amp, set(), line=line))
                elif d == "ignore" and re.match(r"\w*\s*:?\s*(store|derive)\b", rest):
                    m = re.match(r"(?:(\w+)\s*:)?\s*(.*)", rest)
                    sub_rel, more = m.groups()
                    sub_rel = sub_rel or ""
                    target = (inst.name + ("." + sub_rel if sub_rel else "")) if inst is not None else rname
                    stored = any(d_ == "store" and (re.match(r"(?:(\w+)\s*:)?", r_).group(1) or "") == sub_rel
                                 for d_, r_, _ in ds)
                    arcdata_excludes.extend(self.ignore_line(target, more, concept, "store" if stored else None))

        for f in forms:
            if not f.claim_slugs and f.line:
                for d, rest, _ in directives(self.comments_above(f.line)):
                    if d == "claim":
                        f.claim_slugs = rest.split()

        forms = [f for f in forms if f is not None]
        # an open parameter's determination by a proposer, or with no body,
        # and its DET_OR_RULE line end in `(ONE)`, as its clauses do
        for f in forms:
            m = re.match(r"\((DET|DET_OR_RULE) (&[^\s)]+)", f.lines[0]) if len(f.lines) == 1 else None
            if not m or m.group(2) not in self.open_amps() or "(ONE)" in f.marks:
                continue
            f.marks.append("(ONE)")
            f.lines[0] = f.lines[0][:-1] + " (ONE))"
        arclog = self.render(forms, claims, points, concept, all_ctors)
        arcdata = self.arcdata(rep, arcdata_params, arcdata_excludes, points, concept, derive_points, approx_w)
        return arclog, arcdata

