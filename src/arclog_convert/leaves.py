"""A column's term split into the parts arclog keeps (`Leaf`, `Written`), and the
`Converter`, which reads one solver's program and gives its relations, columns
and clauses their arclog forms."""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass, field as dc_field, fields as dc_fields, is_dataclass, replace as dc_replace
from engine.program import (
    AdtType,
    Aggregate,
    AliasType,
    Atom,
    AtomLiteral,
    Comparison,
    ConstructorTerm,
    Disjunction,
    Instance,
    RigidCall,
    RecordTerm,
    RecordType,
    RelationName,
    UnionType,
    Unit,
    Variable,
    Wildcard,
    ComparisonOperator,
)
from souffle.parser import parse
from souffle.printer import unit as souffle_unit
from arclog_convert.literals import collect_vars
from arclog_convert.open_orders import keys_retyped as order_keys_retyped, orders as open_orders
from arclog_convert.picks import rewrite as rewrite_picks
from arclog_convert.libmap import box as libmap_box, rewrite as libmap_rewrite
from arclog_convert.libmap.instances import LIB_PATH, Placement
from arclog_convert import paths

from arclog_convert.checks import Fold, with_checks
from arclog_convert.clauses import ClauseWriter
from arclog_convert.forms import Form, Source, Todo, comment_text, label_sources, tile_frames_split
from arclog_convert.lib import Col, ColMismatch, Lib, pascal
from arclog_convert.terms import (
    MOVED_RELS,
    ctor_names,
    inlined,
    record_eqs,
    rename_rel,
    subst,
    subst_terms,
    walk_lits,
)


FACTS = {"in", "ex_in", "ex_out"}

type ScopedName = tuple[tuple[str, ...], str]
"""A relation or an instance of the solver's program: the component path it is declared under, and its name there."""


# --------------------------------------------------------------------------
# Leaves: a column's term split into the parts arclog keeps


@dataclass
class Leaf:
    name: str     # the column or field name
    kind: str     # keep | case | drop | example
    tparam: bool
    path: tuple[int, ...] = ()
    field: tuple[str, ...] = ()   # the record field names along the path
    type: str = dc_field(default="", compare=False)   # the Souffle type of a keep leaf, `Example` for an example leaf; "" if unknown


@dataclass(frozen=True)
class Written:
    """The Souffle relation, or instance, an arclog name was written from:
    the solver component path it is declared under, and its name there; and,
    where the converter holds how the arclog relation's columns stand for
    the Souffle relation's, the `Placement` of each arclog column in it."""

    scope: tuple[str, ...]
    relation: str
    instance: bool
    columns: tuple[Placement, ...] | None = None


def rel_map(x, fn):
    """`x`, a term, literal or clause, with each relation name inside it replaced by `fn` of it."""
    if isinstance(x, RelationName):
        return fn(x)
    if isinstance(x, tuple):
        return tuple(rel_map(y, fn) for y in x)
    if is_dataclass(x) and not isinstance(x, type):
        ch = {f_.name: rel_map(getattr(x, f_.name), fn) for f_ in dc_fields(x)
              if isinstance(getattr(x, f_.name), (tuple, RelationName))
              or (is_dataclass(getattr(x, f_.name)) and not isinstance(getattr(x, f_.name), type))}
        return dc_replace(x, **ch) if ch else x
    return x


def walk_vars(x, out: list[str]) -> None:
    """Append to `out` each variable name inside the term, literal or clause `x`, once, in order."""
    if isinstance(x, Variable):
        if x.name not in out:
            out.append(x.name)
    elif isinstance(x, tuple):
        for y in x:
            walk_vars(y, out)
    elif is_dataclass(x) and not isinstance(x, type):
        for f_ in dc_fields(x):
            walk_vars(getattr(x, f_.name), out)


class ParseNodes:
    """The relations, the instances and the clauses of the solver's `Parse` component in `prog`. A
    node is a relation or an instance of the component, named as the component declares it."""

    def __init__(self, prog, lib: Lib) -> None:
        self.lib = lib
        self.rels = {r.name: r for r in prog.relations if r.scope.components == ("Parse",)}
        self.insts = {i.name: i for i in prog.instances if i.scope.components == ("Parse",)}
        self.units = [u for u in prog.units if u.scope.components == ("Parse",)]
        self.deps: dict[str, set[str]] = defaultdict(set)
        """The nodes whose relations the clauses of each node read."""
        for u in self.units:
            h = self.node(u.head.relation)
            if h is not None:
                self.deps[h] |= {x for a in Converter._atoms(u.body or ()) if (x := self.node(a.relation)) is not None}

    def node(self, rn: RelationName) -> str | None:
        """The node that `rn`, read in the component, names: the relation, or the instance its path starts with."""
        if rn.instances:
            return rn.instances[0] if rn.instances[0] in self.insts else None
        return rn.name if rn.name in self.rels else None

    def key_at(self, rn: RelationName) -> int | None:
        """The column of the relation `rn` of the component whose type is its `Key`."""
        r = self.rels.get(rn.name) if not rn.instances else None
        return next((i for i, c_ in enumerate(r.columns) if c_.type.name == "Key"), None) if r else None

    def instance_key_at(self, rn: RelationName) -> int | None:
        """The key column of a relation of an instance of the component: for an
        instance of a lib component, the first column typed by the parameter
        that the component's Key stands for (an input such as `dir(D)` has
        none); for another, the first column."""
        inst = self.insts.get(rn.instances[0])
        if inst is None or len(rn.instances) > 1 or inst.component not in self.lib.comps:
            return 0
        tparams, rels = self.lib.relations(inst.component)
        lr = next((r for r in rels if r.name == rn.name), None)
        keyed = {p for p, a in zip(tparams, inst.type_args) if a.name == "Key"}
        return next((i for i, c_ in enumerate(lr.cols) if c_.type in keyed), None) if lr else None

    def read_through(self, units: Iterable[Unit], instance: str) -> Iterator[str]:
        """The node of each relation that a body of `units` reads through the
        instance `instance` of the component."""
        for u in units:
            for a in Converter._atoms(u.body or ()):
                if a.relation.instances[:1] == (instance,) and (
                        x := self.node(RelationName(a.relation.instances[1:], a.relation.name))) is not None:
                    yield x

    def closure(self, roots: Iterable[str]) -> set[str]:
        """`roots` and each node whose relation a clause of a node in the set reads."""
        read: set[str] = set()
        todo = list(roots)
        while todo:
            x = todo.pop()
            if x not in read:
                read.add(x)
                todo += self.deps.get(x, ())
        return read


class Converter:
    def __init__(self, stem: str, lib: Lib, sig: Lib, todo: Todo, inline: frozenset[str] = frozenset(),
                 own_copies: frozenset[ScopedName] = frozenset(), checks: Sequence[Fold] = ()) -> None:
        self.stem = stem
        # the relations of the solver's parse and of its program that an alt
        # rederives, in clauses keyed by a constructor outside the concept
        # case, as `split_det_parse` finds them, and those of them that the
        # determination gets copies of
        self.rederived: set[ScopedName] = set()
        self.own_copies = own_copies
        # each relation or instance this pass makes that the Souffle program
        # does not declare, by its scope and name, with each thing it stands
        # for: none for a relation of an expansion's shape that no Souffle
        # relation stands behind
        self.made: dict[tuple[tuple[str, ...], str], tuple[Written, ...]] = {}
        # each arclog name this pass writes, with each thing it was written from
        self.written: dict[str, list[Written]] = {}
        # for each arclog name whose clauses this pass writes, for each set of
        # ALT constructors it writes them under (none: the top level), the
        # `label_sources` of those clauses
        self.writings: dict[str, dict[frozenset[str], tuple[tuple[Source, ...], ...]]] = {}
        self.unsafe: set[str] = set()   # the relations with a clause whose body no order makes safe
        self.col_mismatch: ColMismatch = {}
        self.lib = lib
        self.sig = sig   # the lib the output is written in: a name the expansions write that `lib` lacks
        self.todo = todo
        path = paths.SOLVERS / f"{stem}.dl"
        self.text = path.read_text()
        self.src_lines = self.text.splitlines()
        prog = parse(f'#include "lib.dl"\n#line 1\n{self.text}', path.parent.parent)
        if not hasattr(prog, "units"):
            raise ValueError(f"parse failed: {prog}")
        own = lambda x: x.span is None or x.span.file is None  # noqa: E731
        prog = dc_replace(prog, types=tuple(filter(own, prog.types)),
                          relations=tuple(filter(own, prog.relations)),
                          components=tuple(filter(own, prog.components)),
                          instances=tuple(filter(own, prog.instances)),
                          functors=tuple(filter(own, prog.functors)),
                          units=tuple(filter(own, prog.units)),
                          macros=tuple(filter(own, prog.macros)))
        # the column count of each relation and the component of each instance the solver file declares
        self.souffle_columns = {(r.scope.components, r.name): len(r.columns) for r in prog.relations}
        self.souffle_components = {(i.scope.components, i.name): i.component for i in prog.instances}
        self.source = prog   # the solver's own program, as the file gives it
        prog, self.checks = with_checks(prog, checks, lib)
        prog = inlined(prog, inline, lib)
        prog, self.tile_frames = tile_frames_split(prog)
        prog, self.picks, self.dropped = rewrite_picks(prog)
        prog, self.lib_judgment = libmap_box.typed(prog, lib)
        # the rewrite in its ground form, whose clauses the Souffle engine can run, which
        # `parity_text` reads; it runs first, as `instances.GROUNDED` holds the latest run's inputs
        self.ground_prog = libmap_rewrite(prog, lib, ground=True)[0]
        # the instances in `Params` that a frame-read plan makes (`FieldPlan.souffle`), and their
        # clauses, as the ground program's units are, which `parity_text` reads beside it
        self.plan_instances: dict[ScopedName, Instance] = {}
        self.plan_units: list[Unit] = []
        # for each arclog name, the label and field of each site that a read of it writes, since a
        # label of a `DET` that no read names is existential and the relation holds no column for it
        self.read_sites: dict[str, set[tuple[str, str | None]]] = {}
        prog, judgment, self.lib_moved, lib_held = libmap_rewrite(prog, lib)
        MOVED_RELS.clear()
        MOVED_RELS.update({f"{was}.{r}": new for was, moves in self.lib_moved.values() for r, new in moves.items()})
        self.lib_judgment |= judgment
        # a folded ONE pick: its relation's clauses end in its marks
        self.one_marks = {(p.scope, p.name): p for p in self.picks.values() if p.ones is not None and p.fold}
        self.prog = prog
        self.types: dict[tuple[tuple[str, ...], str], object] = {
            (t.scope.components, t.name): t for t in prog.types}
        self.rels = {(r.scope.components, r.name): r for r in prog.relations}
        self.insts = {(i.scope.components, i.name): i for i in prog.instances}
        # each relation of a shape the lib rewrite makes, with each Souffle
        # relation it holds
        for (sc, rel), helds in lib_held.items():
            if (sc, rel) not in self.souffle_columns:
                self.made[(sc, rel)] = tuple(Written(sc, f"{h.instance}.{h.relation}", False, h.columns) for h in helds)
        for (sc, _), (_, moves) in self.lib_moved.items():
            for new in moves.values():
                if (sc, new) not in self.souffle_columns:
                    self.made.setdefault((sc, new), ())
        self.comps = {c.name: c for c in prog.components}
        self.case_types = self._case_types()
        self.open_params = self._open_params()
        self.open_types = self._open_types()
        self.orders = open_orders(prog, self.open_params, self.types)
        self.prog = prog = order_keys_retyped(prog, self.orders)
        self.rels = {(r.scope.components, r.name): r for r in prog.relations}
        self.prog = prog = dc_replace(prog, units=tuple(self.open_eqs_dropped(u) for u in prog.units))
        self.prog = prog = self.open_carriers_dropped(prog)
        self.prog = prog = dc_replace(prog, units=tuple(u2 for u in prog.units for u2 in self.case_tested(u)))
        self.prog = prog = dc_replace(prog, units=tuple(record_eqs(u, self.record_fields) for u in prog.units))
        self.prog = prog = self.split_read_inputs(prog)
        self.det_copies: dict[ScopedName, ScopedName] = {}   # a copy -> the relation it is a copy of
        self.det_copy_via: dict[ScopedName, str] = {}   # a copy of a relation of the parse -> the instance of the parse, in the copy's scope, that holds the relation
        self.prog = prog = self.parse_instance_copies(prog)
        self.prog = prog = self.split_det_parse(prog)
        self.prog = prog = self.det_program_copies(prog)
        self.rels = {(r.scope.components, r.name): r for r in prog.relations}
        self.prog = prog = self.candidate_parse(prog)
        self.prog = prog = self.demonstrated(prog)
        self.alias: dict[tuple[tuple[str, ...], str], dict[int, int]] = {}
        self.prog = prog = self.same_columns(prog)
        self.names: dict[tuple[tuple[str, ...], str], str] = {}
        self.used_names: set[str] = {"output"}   # `out` becomes `&output`
        self.key_names: dict[tuple[tuple[str, ...], str], list[str]] = {}
        self.key_paths: dict[tuple[tuple[str, ...], str], list[tuple[int, ...]]] = {}   # each key name's leaf path
        # Souffle RIGID blocks: each placed relation is read as a part of its block,
        # `&<block>.<part>`, with a Pose column; the determination's relation
        # of the same name is the part's table, `&<part>`. The program reads a
        # part under its table's name, so the table takes the part's name, and
        # another relation of that name takes a digit when it is named.
        self.rigid: dict[str, tuple[str, str]] = {}
        for m in prog.macros:
            if isinstance(m, RigidCall) and m.scope.components == ("Params",):
                for n in m.names:
                    self.rigid[n] = (m.block, n[len(m.block) + 1:])
        for n, (block, part) in self.rigid.items():
            self.used_names.add(block)
            self.used_names.add("pose")   # `&<block>.pose` is the form's own output
        for n, (block, part) in self.rigid.items():
            cand, k = part, 2
            while cand in self.used_names:
                cand, k = f"{part}{k}", k + 1
            self.used_names.add(cand)
            self.names[(("Determine",), n)] = cand
            self.names[(("Params",), n)] = f"{block}.{cand}"

    # ---- types

    @property
    def parse_sub(self) -> dict[str, str]:
        """The type parameters of a clause inside `.comp Parse`: `Key` lifted,
        each other parameter the type the program's instance gives it."""
        out = {"Key": "@lift"}
        comp = self.comps.get("Parse")
        inst = next((i for (sc, _), i in self.insts.items() if sc == () and i.component == "Parse"), None)
        if comp is not None and inst is not None:
            for p_, a in zip(comp.type_params, inst.type_args):
                if p_ != "Key" or a.name not in ("Unit", "Example"):
                    out[p_] = a.name
        return out

    def record_fields(self, u: Unit, v: str) -> list[str] | None:
        """The field names of the record type of variable v, from a column
        of the clause's head or of an atom of its body that v fills."""
        def col_type(rn: RelationName, i: int, scope) -> str | None:
            if not rn.instances:
                for k in range(len(scope), -1, -1):
                    r = self.rels.get((scope[:k], rn.name))
                    if r is not None:
                        return r.columns[i].type.name if i < len(r.columns) else None
                return None
            if rn.instances == ("params",):
                r = self.rels.get((("Params",), rn.name))
                return r.columns[i].type.name if r and i < len(r.columns) else None
            inst = None
            for k in range(len(scope), -1, -1):
                inst = self.insts.get((scope[:k], rn.instances[0]))
                if inst is not None:
                    break
            if inst is None or len(rn.instances) != 1 or inst.component not in self.lib.comps:
                return None
            tps, rels = self.lib.relations(inst.component)
            lr = next((r for r in rels if r.name == rn.name), None)
            if lr is None or i >= len(lr.cols):
                return None
            t = lr.cols[i].type
            return dict(zip(tps, (a.name for a in inst.type_args))).get(t, t)

        atoms = [u.head]

        def walk(lits):
            for l in lits:
                if isinstance(l, AtomLiteral):
                    atoms.append(l.atom)
                elif isinstance(l, Disjunction):
                    for b in l.branches:
                        walk(b)
        walk(u.body or ())
        for a in atoms:
            for i, x in enumerate(a.args):
                if x == Variable(v):
                    t = col_type(a.relation, i, u.scope.components)
                    decl = self.find_type(t, u.scope.components) if t else None
                    if isinstance(decl, RecordType):
                        return [f.name for f in decl.fields]
        return None

    def alias_base(self, name: str, scope: tuple[str, ...]) -> str:
        """The type `name` stands for once each alias `.type A = B` it
        names is followed to its target."""
        t = self.find_type(name, scope)
        while isinstance(t, AliasType):
            name = t.target.name
            t = self.find_type(name, scope)
        return name

    def type_root(self, name: str, scope: tuple[str, ...]) -> str:
        """The type `name` stands for once each alias `.type A = B` and each
        union `.type A = B | C` it names is followed to its end (a union to
        its first member), so that a type and the union over it, such as
        `Dir` and `Dir8`, are one type. A subtype `.type A <: B` stays
        apart from `B`: `Ident` and `Dir` are both subtypes of `number`."""
        t = self.find_type(name, scope) or self.lib.types.get(name)
        while isinstance(t, (AliasType, UnionType)):
            name = (t.target if isinstance(t, AliasType) else t.members[0]).name
            t = self.find_type(name, scope) or self.lib.types.get(name)
        return name

    def find_type(self, name: str, scope: tuple[str, ...]):
        for i in range(len(scope), -1, -1):
            t = self.types.get((scope[:i], name))
            if t is not None:
                return t
        return None

    def _case_types(self) -> set[str]:
        choice = self.find_type("Choice", ())
        out: set[str] = set()
        if choice is None:
            return out
        out.add("Choice")
        todo = [f.type.name for f in choice.fields] if isinstance(choice, RecordType) else []
        if isinstance(choice, AdtType):
            todo += [f.type.name for k in choice.constructors for f in k.fields]
        while todo:
            t = todo.pop()
            if t in out:
                continue
            decl = self.find_type(t, ())
            if isinstance(decl, AdtType):
                out.add(t)
                todo += [f.type.name for k in decl.constructors for f in k.fields]
        return out

    def case_adt(self, ctor: str) -> AdtType | None:
        """The case type a constructor belongs to."""
        for t in self.prog.types:
            if isinstance(t, AdtType) and t.name in self.case_types and any(k.name == ctor for k in t.constructors):
                return t
        return None

    def case_complement(self, adt: AdtType, pat) -> list | None:
        """The values of `adt` that `pat` does not match, as patterns: each
        other constructor whole, and the matched constructor with its one
        case field's complement; None where the pattern tests several
        fields."""
        if not isinstance(pat, ConstructorTerm):
            return []
        out = []
        for k in adt.constructors:
            if k.name != pat.name:
                out.append(ConstructorTerm(k.name, tuple(Wildcard() for _ in k.fields)))
                continue
            tested = [i for i, a in enumerate(pat.args) if not isinstance(a, Wildcard)]
            if not tested:
                continue
            if len(tested) > 1:
                return None
            i = tested[0]
            sub = self.find_type(k.fields[i].type.name, ())
            if not isinstance(sub, AdtType) or sub.name not in self.case_types:
                return None
            rest = self.case_complement(sub, pat.args[i])
            if rest is None:
                return None
            for r in rest:
                out.append(ConstructorTerm(k.name, tuple(r if j == i else Wildcard() for j in range(len(k.fields)))))
        return out

    def case_tested(self, u: Unit) -> list[Unit]:
        """A clause whose body tests a case variable against a constructor,
        `X = $K(..)` or `X != $K(..)`, as one clause per value the test
        admits, with the value in place of the variable and the test gone:
        each is then a clause of its case, as one whose head names the
        constructor."""
        if u.body is None or u.head.relation.name == "impl_choice":
            return [u]
        for i, l in enumerate(u.body):
            if not (isinstance(l, Comparison) and l.op.value in ("=", "!=")):
                continue
            var, pat = (l.lhs, l.rhs) if isinstance(l.rhs, ConstructorTerm) else (l.rhs, l.lhs)
            if not (isinstance(var, Variable) and isinstance(pat, ConstructorTerm)):
                continue
            adt = self.case_adt(pat.name)
            if adt is None:
                continue
            vals = [pat] if l.op.value == "=" else self.case_complement(adt, pat)
            if vals is None:
                continue
            rest = u.body[:i] + u.body[i + 1:]
            out = []
            for v in vals:
                head = subst_terms(u.head, {var.name: v})
                body = tuple(subst_terms(x, {var.name: v}) for x in rest)
                out.extend(self.case_tested(dc_replace(u, head=head, body=body)))
            return out
        return [u]

    def _open_params(self) -> set[str]:
        """The Params relations under an `// @open` line."""
        out = set()
        for r in self.prog.relations:
            if r.scope.components != ("Params",) or not r.span:
                continue
            i = r.span.first - 2
            while i >= 0 and (t := comment_text(self.src_lines[i])) is not None:
                if t.strip() == "@open":
                    out.add(r.name)
                i -= 1
        return out

    def open_eqs_dropped(self, u: Unit) -> Unit:
        """The unit without its comparisons on an open value: a variable at a
        column or field of an open type is dropped with it, so a comparison
        that names one goes too."""
        if not self.open_types or u.body is None:
            return u
        open_vars: set[str] = set()

        def typed(term, tname: str) -> None:
            if tname in self.open_types:
                collect_vars([Comparison(ComparisonOperator.EQ, term, term, 0)], open_vars)
                return
            t = self.types.get(((), tname)) or self.types.get((u.scope.components, tname))
            if isinstance(t, RecordType) and isinstance(term, RecordTerm) and len(term.args) == len(t.fields):
                for a, f in zip(term.args, t.fields):
                    typed(a, f.type.name)

        def atom(a: Atom) -> None:
            if a.relation.instances:
                return
            r = self.rels.get((u.scope.components, a.relation.name)) or self.rels.get(((), a.relation.name))
            if r is not None and len(r.columns) == len(a.args):
                for arg, col in zip(a.args, r.columns):
                    typed(arg, col.type.name)

        def scan(lits) -> None:
            for l in lits:
                if isinstance(l, AtomLiteral):
                    atom(l.atom)
                elif isinstance(l, Disjunction):
                    for b in l.branches:
                        scan(b)

        atom(u.head)
        scan(u.body)
        if not open_vars:
            return u

        def names(l) -> bool:
            vs: set[str] = set()
            collect_vars([l], vs)
            return bool(vs & open_vars)

        def drop(lits):
            out = []
            for l in lits:
                if isinstance(l, Comparison) and names(l):
                    continue
                if isinstance(l, Disjunction):
                    l = dc_replace(l, branches=tuple(tuple(drop(b)) for b in l.branches))
                out.append(l)
            return out
        return dc_replace(u, body=tuple(drop(u.body)))

    def open_carriers_dropped(self, prog):
        """A relation whose columns are a case's and an open value's, with
        at least one of the latter, dropped with its positive reads: in a
        model it holds the one open value, so a read of it tells nothing. A
        check relation (`checks`) stays: it is read by no clause, and its
        clauses are what the row-parity check compares."""
        if not self.open_types:
            return prog
        gone = set()
        cases = {"impl_choice"}   # the relations of a case's columns alone
        checks = set(self.checks.values())
        for r in prog.relations:
            if r.scope.components or not r.columns or r.name in checks:
                continue
            kinds = {lf.kind for col in r.columns for lf in self.leaves(col.name, col.type.name, False, (), {})}
            if not any(col.type.name in self.open_types for col in r.columns):
                if kinds == {"case"}:
                    cases.add(r.name)
            elif kinds <= {"case", "drop"}:
                gone.add(r.name)

        # it reads only the case, a parameter, and other such relations
        def plain(lits) -> bool:
            for l in lits:
                if isinstance(l, AtomLiteral):
                    rn = l.atom.relation
                    if l.negated or not (rn.instances == ("params",) or not rn.instances
                                         and (rn.name in cases or rn.name in gone)):
                        return False
                elif isinstance(l, Disjunction):
                    if not all(plain(b) for b in l.branches):
                        return False
                elif not isinstance(l, Comparison):
                    return False
            return True
        while True:
            bad = {u.head.relation.name for u in prog.units
                   if not u.scope.components and not u.head.relation.instances
                   and u.head.relation.name in gone and not plain(u.body or ())}
            if not bad:
                break
            gone -= bad

        def negated(lits) -> set[str]:
            out = set()
            for l in lits:
                if isinstance(l, AtomLiteral) and l.negated and not l.atom.relation.instances:
                    out.add(l.atom.relation.name)
                elif isinstance(l, Disjunction):
                    for b in l.branches:
                        out |= negated(b)
            return out
        for u in prog.units:
            if u.body:
                gone -= negated(u.body)
        if not gone:
            return prog

        def drop(lits):
            out = []
            for l in lits:
                if isinstance(l, AtomLiteral) and not l.atom.relation.instances and l.atom.relation.name in gone:
                    continue
                if isinstance(l, Disjunction):
                    l = dc_replace(l, branches=tuple(tuple(drop(b)) for b in l.branches))
                out.append(l)
            return out
        units = tuple(u if u.body is None else dc_replace(u, body=tuple(drop(u.body)))
                      for u in prog.units
                      if not (not u.scope.components and not u.head.relation.instances and u.head.relation.name in gone))
        self.open_carriers = gone
        return dc_replace(prog, units=units,
                          relations=tuple(r for r in prog.relations if r.scope.components or r.name not in gone))

    def _open_types(self) -> set[str]:
        """The types that tell one open value from another: `OpenValue`, and
        the record type of each of its fields. A column or field of one of
        them is dropped, since a model of an open relation's `ONE` mark holds
        one value."""
        t = self.types.get(((), "OpenValue"))
        if not isinstance(t, RecordType):
            return set()
        return {"OpenValue"} | {f.type.name for f in t.fields}

    def demonstrated(self, prog):
        """Each DemonstrationConsistency instance that a DEMONSTRATED form
        states, with its reads rewritten as reads of the form's relation.

        A prediction clause that names its rule by a variable is written once
        per rule, with the rule's constructor in place of the variable. The
        reads the form states are `consistent(K, R, A, B), prediction(K, R,
        O, I, V)` with a Unit key, a rule consistent on the one pair A, B,
        which the form keys by the pair, and `prediction(K, R, O, I, V),
        !refuted(.., R)`, where `refuted` holds the rules some demonstration
        of K does not confirm. An instance whose program reads a rule, or
        reads the instance otherwise, is no DEMONSTRATED form."""
        self.demo_insts: set[tuple[tuple[str, ...], str]] = set()
        self.demo_mode: dict[tuple[tuple[str, ...], str], str] = {}
        self.demo_pair: dict[tuple[tuple[str, ...], str], list[str]] = {}
        self.demo_rule_types: set[str] = set()
        self.demo_rule_records: set[str] = set()
        self.demo_dropped: set[str] = set()
        self.demo_select: set[tuple[tuple[str, ...], str]] = set()
        for key, inst in list(self.insts.items()):
            if inst.component != "DemonstrationConsistency":
                continue
            got = self._demonstrated(prog, key, inst)
            if got is None:
                self.demo_select.add(key)
                continue
            prog = got
            self.demo_insts.add(key)
            self.demo_rule_types.add(inst.type_args[1].name)
            pair = [a.name for a in inst.type_args[:2]]
            self.demo_rule_records |= {t.name for t in prog.types if isinstance(t, RecordType)
                                       and [f.type.name for f in t.fields] == pair}
        self.select_ctors = {k.name for sc_, n in self.demo_select
                             for t in [self.find_type(self.insts[(sc_, n)].type_args[1].name, ())]
                             if isinstance(t, AdtType) for k in t.constructors}
        return prog

    def _demonstrated(self, prog, key, inst):
        sc, name = key
        rn = lambda r: RelationName((name,), r)  # noqa: E731
        adt = self.find_type(inst.type_args[1].name, ())
        if not isinstance(adt, AdtType):
            return None
        # an input that a prediction reads is a relation of its own, which
        # the form's DEMO_RULE bodies read
        if sc == ():
            _, lrels = self.lib.relations(inst.component)
            for lr in lrels:
                if not lr.is_input or not any(
                        u.scope.components == sc and u.head.relation == rn("prediction")
                        and any(isinstance(l, AtomLiteral) and l.atom.relation == rn(lr.name)
                                for l in walk_lits(u.body or ())) for u in prog.units):
                    continue
                own = [u for u in prog.units if u.scope.components == sc and u.head.relation == rn(lr.name)]
                bridge = own[0].body if len(own) == 1 and own[0].body and len(own[0].body) == 1 else None
                if bridge and isinstance(bridge[0], AtomLiteral) and not bridge[0].negated \
                        and not bridge[0].atom.relation.instances and bridge[0].atom.args == own[0].head.args:
                    new = bridge[0].atom.relation.name   # split already
                else:
                    prog = self._split_input(prog, inst, lr)
                    new = prog.relations[-1].name
                    self.rels[((), new)] = prog.relations[-1]
                prog = dc_replace(prog, units=tuple(
                    rename_rel(u, rn(lr.name), RelationName((), new))
                    if u.scope.components == sc and u.head.relation == rn("prediction") else u
                    for u in prog.units))
        units = []
        for u in prog.units:
            if u.scope.components == sc and u.head.relation == rn("prediction") and len(u.head.args) == 5 \
                    and isinstance(u.head.args[1], Variable):
                if any(k.fields for k in adt.constructors):
                    return None
                r = u.head.args[1].name
                for k in adt.constructors:
                    m = {r: ConstructorTerm(k.name, ())}
                    units.append(dc_replace(u, head=subst_terms(u.head, m),
                                            body=tuple(subst_terms(x, m) for x in u.body or ())))
            else:
                units.append(u)
        preds = [u for u in units if u.scope.components == sc and u.head.relation == rn("prediction")]
        if not preds or not all(len(u.head.args) == 5 and isinstance(u.head.args[1], ConstructorTerm)
                                and all(isinstance(a, Variable) for a in u.head.args[1].args) for u in preds):
            return None
        # the relations that hold the rules some demonstration refutes
        refuted: dict[str, Unit] = {}
        for u in units:
            b = u.body or ()
            if u.head.relation.instances or len(b) != 3 or not all(isinstance(a, Variable) for a in u.head.args):
                continue
            p_, d_, c_ = (next((l for l in b if isinstance(l, AtomLiteral) and l.atom.relation == rn(x)), None)
                          for x in ("prediction", "demonstration", "consistent"))
            if p_ is None or d_ is None or c_ is None or p_.negated or d_.negated or not c_.negated:
                continue
            k_, r_, o_ = p_.atom.args[:3]
            if d_.atom.args[0] == k_ and (isinstance(o_, Wildcard) or d_.atom.args[1] == o_) \
                    and c_.atom.args == (k_, r_, *d_.atom.args[1:]) and isinstance(r_, Variable):
                refuted[u.head.relation.name] = u
        pair_names = []
        dems = [u for u in units if u.scope.components == sc and u.head.relation == rn("demonstration")]
        if dems:
            pair_names = [a.name if isinstance(a, Variable) else n for a, n in zip(dems[0].head.args[1:], ("O", "O2"))]
            if pair_names[0] == pair_names[1]:
                pair_names = ["O", "O2"]
        modes: set[str] = set()
        # the records that pair a key with a rule: a column of one names the
        # rule a row is derived at, which the form's relation leaves out
        rule_records = {adt.name} | {t.name for t in self.prog.types if isinstance(t, RecordType)
                                     and any(f.type.name == adt.name for f in t.fields)}

        def read(u: Unit) -> Unit:
            if u.body is None or u.head.relation.instances[:1] == (name,) or u.head.relation.name in refuted:
                return u
            body = list(u.body)
            changed = True
            while changed:
                changed = False
                for j, m in enumerate(body):
                    if not (isinstance(m, AtomLiteral) and not m.negated and m.atom.relation == rn("prediction")
                            and isinstance(m.atom.args[1], Variable)):
                        continue
                    k, r = m.atom.args[:2]
                    o, i_, v = m.atom.args[2:]
                    for i, l in enumerate(body):
                        if i == j or not isinstance(l, AtomLiteral):
                            continue
                        if not l.negated and l.atom.relation == rn("confirmed") and l.atom.args == (k, r):
                            mode, args = "all", (k, o, i_, v)
                        elif not l.negated and l.atom.relation == rn("consistent") and l.atom.args[:2] == (k, r) \
                                and inst.type_args[0].name == "Unit":
                            mode, args = "pair", (RecordTerm(l.atom.args[2:]), o, i_, v)
                        elif l.negated and not l.atom.relation.instances and l.atom.relation.name in refuted:
                            ru = refuted[l.atom.relation.name]
                            mp = {h.name: a for h, a in zip(ru.head.args, l.atom.args)}
                            rp = next(x for x in ru.body if isinstance(x, AtomLiteral)
                                      and x.atom.relation == rn("prediction"))
                            if subst_terms(rp.atom.args[0], mp) != k or subst_terms(rp.atom.args[1], mp) != r:
                                continue
                            mode, args = "all", (k, o, i_, v)
                        else:
                            continue
                        rest = [x for n_, x in enumerate(body) if n_ not in (i, j)]
                        vs: set[str] = set()
                        collect_vars(rest, vs)
                        hr = self.rels.get((u.scope.components, u.head.relation.name))
                        collect_vars([AtomLiteral(dc_replace(u.head, args=tuple(
                            a for n_, a in enumerate(u.head.args)
                            if hr is None or n_ >= len(hr.columns)
                            or hr.columns[n_].type.name not in rule_records)), False)], vs)
                        if r.name in vs:
                            continue
                        modes.add(mode)
                        atom = Atom(rn("@demonstrated"), args, m.atom.line)
                        lo, hi = sorted((i, j))
                        body = body[:lo] + [AtomLiteral(atom, False)] + body[lo + 1:hi] + body[hi + 1:]
                        changed = True
                        break
                    if changed:
                        break
            return dc_replace(u, body=tuple(body)) if changed or body != list(u.body) else u

        units = [read(u) for u in units]
        if len(modes) != 1:
            return None
        # the refuted relations no rewritten unit reads drop out
        def reads(lits):
            for l in lits:
                if isinstance(l, AtomLiteral):
                    yield l.atom.relation
                elif isinstance(l, Disjunction):
                    for b in l.branches:
                        yield from reads(b)
                elif isinstance(l, Comparison):
                    for t in (l.lhs, l.rhs):
                        if isinstance(t, Aggregate):
                            yield from reads(t.body)
        read_rels = {x for u in units if u.head.relation.name not in refuted for x in reads(u.body or ())}
        dropped = {n for n in refuted if RelationName((), n) not in read_rels}
        for u in units:
            if u.head.relation.instances[:1] == (name,) or u.head.relation.name in dropped:
                continue
            if any(x.instances[:1] == (name,) and x.name != "@demonstrated" for x in reads(u.body or ())):
                return None   # the program reads a rule or an input of the instance
        self.demo_mode[key] = modes.pop()
        if self.demo_mode[key] == "pair":
            self.demo_pair[key] = [pascal(n) for n in pair_names]
        self.demo_dropped |= dropped
        return dc_replace(prog, units=tuple(u for u in units if u.head.relation.name not in dropped
                                            or u.head.relation.instances))

    def candidate_parse(self, prog):
        """A determination that runs the program's parse at each candidate
        value of a parameter and keeps the values a test of its own passes:
        the parameter's DET offers the candidates, the engine keeps those
        that the program's fit passes, and the determination's clauses that
        only that test reads drop out. A determination clause that reads the
        parse at the kept value reads the program's parse, lifted, with the
        parameter in place of the candidate."""
        self.cand_params: set[str] = set()
        self.cand_insts: dict[str, str] = {}   # a Determine parse instance -> its key type
        self.cand_key_fields: dict[str, set[int]] = {}   # its key type -> the fields that hold a candidate
        det = ("Determine",)
        comp_insts = {n: i for (sc, n), i in self.insts.items() if sc == det and i.component in self.comps}
        if not comp_insts:
            return prog
        prog_inst = {i.component: n for (sc, n), i in self.insts.items() if sc == () and i.component in self.comps}

        def atoms(lits):
            for l in lits:
                if isinstance(l, AtomLiteral):
                    yield l.atom
                elif isinstance(l, Disjunction):
                    for b in l.branches:
                        yield from atoms(b)
                elif isinstance(l, Comparison):
                    for t in (l.lhs, l.rhs):
                        if isinstance(t, Aggregate):
                            yield from atoms(t.body)
        params = {r.name for r in prog.relations if r.scope.components == ("Params",)}
        # each Parse input the program fills from a parameter: name -> params
        fed: dict[tuple[str, str], set[str]] = defaultdict(set)
        for u in prog.units:
            rn = u.head.relation
            if u.scope.components == () and len(rn.instances) == 1 and rn.instances[0] in prog_inst.values():
                comp = self.insts[((), rn.instances[0])].component
                for a in atoms(u.body or ()):
                    if a.relation.instances == ("params",):
                        fed[(comp, rn.name)].add(a.relation.name)
        cand_fields: dict[str, dict[int, str]] = {}   # instance -> key field index -> parameter
        for n, inst in comp_insts.items():
            for u in prog.units:
                rn = u.head.relation
                if u.scope.components != det or rn.instances != (n,) or (inst.component, rn.name) not in fed:
                    continue
                read = {a.relation.name for a in atoms(u.body or ())
                        if not a.relation.instances or a.relation.instances == ("params",)}
                for p_ in fed[(inst.component, rn.name)]:
                    if p_ not in read:
                        self.cand_params.add(p_)
                        # the key field that holds the candidate
                        k = u.head.args[0] if u.head.args else None
                        if isinstance(k, RecordTerm):
                            pu = next((x for x in prog.units if x.scope.components == () and
                                       x.head.relation == RelationName((prog_inst[inst.component],), rn.name)), None)
                            for j, (hk, ha) in enumerate(zip(u.head.args[1:], pu.head.args[1:] if pu else ())):
                                if isinstance(hk, Variable):
                                    for fi, f_ in enumerate(k.args):
                                        if f_ == hk and isinstance(ha, Variable):
                                            cand_fields.setdefault(n, {})[fi] = p_
        if not self.cand_params:
            return prog
        # a candidate stands where the parameter's determination refutes it:
        # a clause of it negates, at its own value, a relation that reads
        # the parse it runs per candidate
        dheads: dict[str, list] = defaultdict(list)
        for u in prog.units:
            if u.scope.components == det and not u.head.relation.instances:
                dheads[u.head.relation.name].append(u)
        reads_parse: dict[str, bool] = {}

        def reads(x: str, seen=frozenset()) -> bool:
            if x in reads_parse:
                return reads_parse[x]
            if x in seen:
                return False
            got = any(a.relation.instances[:1] and a.relation.instances[0] in comp_insts
                      or (not a.relation.instances and a.relation.name in dheads
                          and reads(a.relation.name, seen | {x}))
                      for u in dheads.get(x, ()) for a in atoms(u.body or ()))
            reads_parse[x] = got
            return got

        def refuted(x: str, seen=frozenset()) -> bool:
            for u in dheads.get(x, ()):
                hv = {a.name for a in u.head.args if isinstance(a, Variable)}
                for l in u.body or ():
                    if isinstance(l, AtomLiteral) and not l.atom.relation.instances:
                        n = l.atom.relation.name
                        av = {a.name for a in l.atom.args if isinstance(a, Variable)}
                        if l.negated and av & hv and reads(n):
                            return True
                        if not l.negated and n in dheads and n not in seen and n != x and refuted(n, seen | {x}):
                            return True
            return False
        # a parameter a Params clause derives: the stored ones it reads
        rules = defaultdict(set)
        for u in prog.units:
            if u.scope.components == ("Params",) and u.body:
                rules[u.head.relation.name] |= {a.relation.name for a in atoms(u.body)
                                                if not a.relation.instances and a.relation.name in params}
        todo = list(self.cand_params)
        self.cand_params = set()
        while todo:
            x = todo.pop()
            if rules.get(x):
                todo += [y for y in rules[x] if y not in self.cand_params]
            else:
                self.cand_params.add(x)
        rigid = {n for m in prog.macros if isinstance(m, RigidCall) for n in m.names}
        # a parameter the program also derives (@derive) keeps its determination
        derived = set()
        for r in prog.relations:
            if r.scope.components == ("Params",) and r.span:
                i = r.span.first - 2
                while i >= 0 and self.src_lines[i].strip().startswith("//"):
                    if "@derive" in self.src_lines[i]:
                        derived.add(r.name)
                    i -= 1
        one_color = {r.name for r in prog.relations if r.scope.components == ("Params",)
                     and [c.type.name for c in r.columns] == ["Color"]}
        # (a derived parameter's stored reading lists the candidates, where they are the task's colors)
        self.cand_params = {x for x in self.cand_params if refuted(x) and x not in rigid
                            and (x not in derived or x in one_color)}
        if not self.cand_params:
            return prog
        for n, inst in comp_insts.items():
            k = inst.type_args[0].name
            if k not in ("Unit", "Example"):
                self.cand_insts[n] = k
                self.cand_key_fields[k] = set(cand_fields.get(n, {}))
        # the determination clauses the other parameters read
        dunits = [u for u in prog.units if u.scope.components == det]
        heads: dict[str, list] = defaultdict(list)
        for u in dunits:
            rn = u.head.relation
            heads[rn.instances[0] if rn.instances else rn.name].append(u)
        need: set[str] = set()
        rigid = {n for m in prog.macros if isinstance(m, RigidCall) for n in m.names}
        todo = [x for x in heads if (x in params and x not in self.cand_params) or x in rigid]
        while todo:
            x = todo.pop()
            if x in need:
                continue
            need.add(x)
            for u in heads.get(x, ()):
                for a in atoms(u.body or ()):
                    rn = a.relation
                    y = rn.instances[0] if rn.instances else rn.name
                    if y in heads and y not in need and not (y in params and y in self.cand_params):
                        todo.append(y)
        drop = {x for x in heads if x not in need}
        for x in drop:
            self.insts.pop((det, x), None)
        units = []
        for u in prog.units:
            if u.scope.components == det:
                rn = u.head.relation
                x = rn.instances[0] if rn.instances else rn.name
                if x in drop or (rn.instances and rn.instances[0] in comp_insts):
                    continue
                # a read of the candidate parse binds its candidate to the parameter
                extra = []
                for a in atoms(u.body or ()):
                    fs = cand_fields.get(a.relation.instances[0] if a.relation.instances else "")
                    key = a.args[0] if a.args else None
                    while isinstance(key, RecordTerm) and fs and len(key.args) and isinstance(key.args[0], RecordTerm):
                        key = key.args[0]
                    if fs and isinstance(key, RecordTerm):
                        for fi, p_ in fs.items():
                            v = key.args[fi] if fi < len(key.args) else None
                            if isinstance(v, Variable):
                                lit = AtomLiteral(Atom(RelationName(("params",), p_), (v,), a.line), False)
                                own = AtomLiteral(Atom(RelationName((), p_), (v,), a.line), False)
                                if lit not in extra and not any(isinstance(b, AtomLiteral) and not b.negated
                                                                and b.atom.relation in (lit.atom.relation, own.atom.relation)
                                                                and b.atom.args == (v,) for b in u.body or ()):
                                    extra.append(lit)
                if extra:
                    u = dc_replace(u, body=tuple(u.body) + tuple(extra))
            units.append(u)
        return dc_replace(prog, units=tuple(units),
                          relations=tuple(r for r in prog.relations
                                          if not (r.scope.components == det and r.name in drop)),
                          instances=tuple(i for i in prog.instances
                                          if not (i.scope.components == det and i.name in drop | set(comp_insts))))

    def same_columns(self, prog):
        """A column that every clause of its relation fills with the variable
        of another column, dropped: the relation keeps the other column, and
        each read of it reads the dropped column's variable as the other's."""
        def leaves_of(scope, rel):
            sub = self.parse_sub if scope == ("Parse",) else {}
            out = []
            for i, c_ in enumerate(rel.columns):
                for l in self.leaves(pascal(c_.name), c_.type.name, False, scope, sub):
                    out.append((i, l))
            return out

        def flat(a: Atom, scope, rel):
            sub = self.parse_sub if scope == ("Parse",) else {}
            w = ClauseWriter(self, scope, sub, {})
            out = []
            for c_, t in zip(rel.columns, a.args):
                ls = self.leaves(pascal(c_.name), c_.type.name, False, scope, sub)
                saved = list(self.todo.pending), Counter(self.todo.kinds)
                ts = w.split(t, ls)
                self.todo.pending, self.todo.kinds = saved
                out += [t_ if l.kind == "keep" else None for l, t_ in zip(ls, ts)]
            return out

        def find(rn: RelationName, scope):
            if rn.instances or rn.name in FACTS:
                return None
            for k in range(len(scope), -1, -1):
                if (scope[:k], rn.name) in self.rels:
                    return (scope[:k], rn.name)
            return None

        def put(t, path, x):
            if not path:
                return x
            if isinstance(t, RecordTerm):
                args = list(t.args)
                args[path[0]] = put(args[path[0]], path[1:], x)
                return RecordTerm(tuple(args))
            return t

        def fix(a: Atom, scope, m: dict, shared: set[str]) -> Atom:
            """The read with each dropped column's variable at the column it
            repeats, where the read leaves that column out; the renames of
            the variables it names at both columns go to `m`. `shared` holds
            the variables that stand at more than one site of atoms."""
            key = find(a.relation, scope)
            if key is None or key not in self.alias:
                return a
            rel = self.rels[key]
            r = flat(a, key[0], rel)
            pos = leaves_of(key[0], rel)
            args = list(a.args)
            for k, j in self.alias[key].items():
                tk, tj = r[k], r[j]
                ck, lk = pos[k]
                if not isinstance(tk, Variable) or not isinstance(tj, (Variable, Wildcard)) or tk == tj:
                    continue
                whole, depth = a.args[ck], 0
                while isinstance(whole, RecordTerm) and depth < len(lk.path):
                    whole, depth = whole.args[lk.path[depth]], depth + 1
                one_kept = sum(1 for n_, (i_, l) in enumerate(pos) if i_ == ck and l.path[:depth] == lk.path[:depth]
                               and l.kind == "keep" and n_ not in self.alias[key]) == 1
                if isinstance(whole, Variable) and depth < len(lk.path) and (
                        depth == 0 and isinstance(tj, Variable) or one_kept and whole.name in shared):
                    # the record variable, which stands whole at the dropped
                    # leaf's record, spelled out: the repeated column's
                    # variable is at the dropped leaf, so each other read of
                    # the variable reads the same leaves; the read here keeps
                    # one leaf of a record variable, which a clause's other
                    # read would give a name per leaf
                    prefix = lk.path[:depth]
                    cls = [dc_replace(l, path=l.path[depth:]) for i_, l in pos if i_ == ck and l.path[:depth] == prefix]
                    ts = [t_ if t_ is not None else Wildcard()
                          for (i_, l), t_ in zip(pos, r) if i_ == ck and l.path[:depth] == prefix]
                    rec = None
                    for l, t_ in zip(cls, ts):
                        rec = put(rec if rec is not None else build(cls), l.path,
                                  tj if l.path == lk.path[depth:] and isinstance(tj, Variable) else t_)
                    m.setdefault(whole.name, rec)
                elif isinstance(tj, Variable):
                    m.setdefault(tk.name, tj)
                if isinstance(tj, Wildcard):
                    ci, leaf = pos[j]
                    args[ci] = put(args[ci], leaf.path, tk)
            return dc_replace(a, args=tuple(args))

        def build(cls):
            """A record term of wildcards with the leaves' structure."""
            def node(depth, ls):
                if len(ls) == 1 and len(ls[0].path) == depth:
                    return Wildcard()
                groups: dict[int, list] = defaultdict(list)
                for l in ls:
                    groups[l.path[depth]].append(l)
                return RecordTerm(tuple(node(depth + 1, groups[i]) for i in sorted(groups)))
            return node(0, cls)

        def same_of(rows) -> dict[int, int]:
            same: dict[int, int] = {}
            for k in range(len(rows[0])):
                for j in range(k):
                    if j not in same and k not in same and \
                            all(isinstance(r[k], Variable) and r[k] == r[j] for r in rows):
                        same[k] = j
            return same

        for (scope, name), rel in self.rels.items():
            if scope not in ((), ("Parse",)):
                continue
            us = [u for u in prog.units if u.scope.components == scope and u.head.relation == RelationName((), name)]
            if not us or any(u.body is None for u in us):
                continue
            same = same_of([flat(u.head, scope, rel) for u in us])
            if same:
                self.alias[(scope, name)] = same
        if not self.alias:
            return prog
        # a chosen relation whose candidate repeats a column repeats it too
        for p_ in self.picks.values():
            key = (p_.scope, p_.name)
            rel = self.rels.get(key)
            vars_ = p_.fold or p_.cvars
            if rel is None or p_.ones is not None or len(vars_) != len(rel.columns):
                continue
            ck = find(p_.item.relation, p_.scope)
            if ck in self.alias and p_.item.args == tuple(Variable(v) for v in vars_ if v) \
                    and [c_.type for c_ in self.rels[ck].columns] == [c_.type for c_ in rel.columns]:
                self.alias[key] = dict(self.alias[ck])

        def shared_vars(lits, head=None) -> set[str]:
            """The variables that stand at more than one site of the atoms of
            `lits` and `head`."""
            seen: Counter = Counter()

            def walk(t) -> None:
                if isinstance(t, Variable):
                    seen[t.name] += 1
                for x in getattr(t, "args", ()) or ():
                    walk(x)

            def scan(ls) -> None:
                for l in ls:
                    if isinstance(l, AtomLiteral):
                        walk(l.atom)
                    elif isinstance(l, Disjunction):
                        for b in l.branches:
                            scan(b)
            scan(lits)
            if head is not None:
                walk(head)
            return {v for v, n in seen.items() if n > 1}

        def lits_fix(lits, scope, m, shared):
            out = []
            for l in lits:
                if isinstance(l, AtomLiteral):
                    out.append(dc_replace(l, atom=fix(l.atom, scope, m, shared)))
                elif isinstance(l, Disjunction):
                    out.append(dc_replace(l, branches=tuple(tuple(lits_fix(b, scope, m, shared)) for b in l.branches)))
                else:
                    out.append(l)
            return out
        units = []
        for u in prog.units:
            if u.body is None:
                units.append(u)
                continue
            m: dict[str, object] = {}
            body = lits_fix(list(u.body), u.scope.components, m, shared_vars(u.body, u.head))
            head = u.head
            if m:
                head = subst_terms(head, m)
                body = [subst_terms(x, m) for x in body]
            units.append(dc_replace(u, head=head, body=tuple(body)) if m or body != list(u.body) else u)
        for p_ in self.picks.values():
            parts = []
            for b in p_.aparts:
                m = {}
                b2 = lits_fix(list(b), p_.scope, m, shared_vars(b))
                parts.append(tuple(subst_terms(x, m) for x in b2) if m else tuple(b2))
            p_.aparts = parts
        return dc_replace(prog, units=tuple(units))

    def split_read_inputs(self, prog):
        """An instance input that a clause the instance depends on reads, as
        a relation of its own that the input and its readers read. The
        arclog form of an instance is one node, so such a read would make
        the instance and its reader read each other, where the Souffle has
        no recursion: an input does not depend on the instance's outputs."""
        def node(rn: RelationName, scope):
            if rn.instances:
                if len(rn.instances) == 1 and ((), rn.instances[0]) in self.insts and scope == ():
                    return ("inst", rn.instances[0])
                return None
            if rn.name in FACTS:
                return None
            return ("rel", rn.name) if ((), rn.name) in self.rels else None

        def atoms(lits):
            for l in lits:
                if isinstance(l, AtomLiteral):
                    yield l.atom
                elif isinstance(l, Disjunction):
                    for b in l.branches:
                        yield from atoms(b)
                elif isinstance(l, Comparison):
                    for t in (l.lhs, l.rhs):
                        if isinstance(t, Aggregate):
                            yield from atoms(t.body)

        def input_rel(rn: RelationName):
            """(instance, LibRel) where `rn` names an input of a top-level
            lib instance."""
            if len(rn.instances) != 1:
                return None
            inst = self.insts.get(((), rn.instances[0]))
            if inst is None or inst.component not in self.lib.comps:
                return None
            _, rels = self.lib.relations(inst.component)
            lr = next((r for r in rels if r.name == rn.name), None)
            return (inst, lr) if lr is not None and lr.is_input else None

        done: set[tuple[str, str]] = set()
        while True:
            edges: dict[tuple, set] = defaultdict(set)
            for u in prog.units:
                if u.scope.components != ():
                    continue
                h = node(u.head.relation, ())
                if h is None:
                    continue
                for a in atoms(u.body or ()):
                    n = node(a.relation, ())
                    if n is not None:
                        edges[h].add(n)

            def reaches(a, b) -> bool:
                seen, todo = set(), [a]
                while todo:
                    x = todo.pop()
                    if x == b:
                        return True
                    if x in seen:
                        continue
                    seen.add(x)
                    todo.extend(edges.get(x, ()))
                return False

            target = None
            for u in prog.units:
                if u.scope.components != () or u.body is None:
                    continue
                h = node(u.head.relation, ())
                for a in atoms(u.body):
                    got = input_rel(a.relation)
                    if got is None or h is None or (a.relation.instances[0], a.relation.name) in done:
                        continue
                    x = ("inst", a.relation.instances[0])
                    # an input that another input of its instance reads
                    sibling = x == h and a.relation != u.head.relation and any(
                        v.scope.components == () and v.head.relation == a.relation for v in prog.units)
                    if sibling or (x != h and reaches(x, h)):
                        target = got
                        break
                if target:
                    break
            if target is None:
                # an input that a sibling input reads, in a component's scope
                for u in prog.units:
                    sc = u.scope.components
                    rn_ = u.head.relation
                    if sc == () or u.body is None or len(rn_.instances) != 1:
                        continue
                    inst_ = self.insts.get((sc, rn_.instances[0]))
                    if inst_ is None or inst_.component not in self.lib.comps:
                        continue
                    _, rels_ = self.lib.relations(inst_.component)
                    for a in atoms(u.body):
                        lr_ = next((r for r in rels_ if r.name == a.relation.name), None)
                        if a.relation.instances == rn_.instances and a.relation != rn_ and lr_ is not None \
                                and lr_.is_input and (sc, inst_.name, lr_.name) not in done \
                                and any(v.scope.components == sc and v.head.relation == a.relation
                                        for v in prog.units):
                            target = (inst_, lr_)
                            break
                    if target:
                        break
            if target is None:
                return prog
            inst, lr = target
            if inst.scope.components:
                done.add((inst.scope.components, inst.name, lr.name))
                prog = self._split_input(prog, inst, lr)
                self.rels = {(r.scope.components, r.name): r for r in prog.relations}
                continue
            done.add((inst.name, lr.name))
            prog = self._split_input(prog, inst, lr)

    def _split_input(self, prog, inst, lr):
        from engine.program import Column, DeclId, RelationDecl, Scope, TypeName, UnitId
        sc = inst.scope.components
        rn = RelationName((inst.name,), lr.name)
        own = [u for u in prog.units if u.scope.components == sc and u.head.relation == rn]
        tparams, _ = self.lib.relations(inst.component)
        isub = {p: a.name for p, a in zip(tparams, inst.type_args)}
        taken = {r.name for r in prog.relations}
        name, n = f"{inst.name}_{lr.name}", 2
        while name in taken:
            name, n = f"{inst.name}_{lr.name}{n}", n + 1
        # a column every clause's head repeats from an earlier one is that
        # column again, and the relation leaves it out, where every reader
        # reads it as the earlier one or not at all
        def reader_atoms(lits):
            for l in lits:
                if isinstance(l, AtomLiteral) and l.atom.relation == rn:
                    yield l.atom
                elif isinstance(l, Disjunction):
                    for b in l.branches:
                        yield from reader_atoms(b)
        readers = [a for u in prog.units if u.scope.components == sc and u.head.relation != rn
                   for a in reader_atoms(u.body or ())]
        dup: dict[int, int] = {}
        for i in range(1, len(lr.cols)):
            j = next((j for j in range(i) if j not in dup and own and all(
                len(u.head.args) > i and u.head.args[i] == u.head.args[j] for u in own)), None)
            if j is not None and all(isinstance(a.args[i], Wildcard) or a.args[i] == a.args[j] for a in readers):
                dup[i] = j
        first = own[0].head.args if own else ()
        cols, args = [], []
        for i, c in enumerate(lr.cols):
            if i in dup:
                continue
            a = first[i] if i < len(first) else None
            t = isub.get(c.type, c.type)
            cn = a.name if isinstance(a, Variable) else c.name
            decl_t = self.find_type(t, sc)
            if isinstance(a, RecordTerm) and isinstance(decl_t, RecordType):
                # a record with one field outside the cases: that field's name
                kept = [x for x, f_ in zip(a.args, decl_t.fields)
                        if isinstance(x, Variable) and f_.type.name not in self.case_types]
                if len(kept) == 1 and len(self.leaves("k", t, False, (), {})) - \
                        sum(1 for l in self.leaves("k", t, False, (), {}) if l.kind != "keep") == 1:
                    cn = kept[0].name
            if cn in [x.name for x in cols]:
                cn = f"{cn}{i}"
            cols.append(Column(cn, TypeName((), t)))
            args.append(Variable(pascal(cn)))
        decl = RelationDecl(DeclId(prog.next_decl_index()), name, Scope(sc), tuple(cols), (), (), None)
        new_rn = RelationName((), name)
        kept_idx = [i for i in range(len(lr.cols)) if i not in dup]
        self.made[(sc, name)] = (Written(sc, f"{inst.name}.{lr.name}", False, tuple(kept_idx)),)
        full = [args[kept_idx.index(dup.get(i, i))] for i in range(len(lr.cols))]

        def rename(x):
            if isinstance(x, Atom) and x.relation == rn and dup:
                return dc_replace(x, relation=new_rn, args=tuple(rename(x.args[i]) for i in kept_idx))
            if isinstance(x, RelationName):
                return new_rn if x == rn else x
            if isinstance(x, tuple):
                return tuple(rename(y) for y in x)
            if is_dataclass(x) and not isinstance(x, type):
                ch = {}
                for f_ in dc_fields(x):
                    v = getattr(x, f_.name)
                    if isinstance(v, (tuple, RelationName)) or (is_dataclass(v) and not isinstance(v, type)):
                        ch[f_.name] = rename(v)
                return dc_replace(x, **ch) if ch else x
            return x
        units = []
        bridged = False
        for u in prog.units:
            if u.scope.components != sc:
                units.append(u)
            elif u.head.relation == rn:
                if not bridged:
                    bridged = True
                    units.append(Unit(UnitId(prog.next_unit_index()), u.scope,
                                      Atom(rn, tuple(full), u.head.line),
                                      (AtomLiteral(Atom(new_rn, tuple(args), u.head.line), False),),
                                      None, u.span))
                units.append(dc_replace(u, head=dc_replace(u.head, relation=new_rn,
                                                           args=tuple(u.head.args[i] for i in kept_idx)),
                                        body=rename(u.body)))
            elif u.head.relation.instances[:1] == rn.instances:
                units.append(rename(u) if u.head.relation != rn else u)
            else:
                units.append(rename(u))
        return dc_replace(prog, relations=prog.relations + (decl,), units=tuple(units))

    def split_det_parse(self, prog):
        """A determination's parse keyed on Example is the program's parse,
        lifted, where the determination feeds each of its inputs as the
        program does in the concept case. A feed of the program is its
        clauses that hold in the concept case: a clause keyed by a constructor
        outside the concept case, in its head or by an equation, is an
        alternate of another case, and drops out where the program derives
        the relation in every case of its point: a clause has no constructor
        key, or each constructor of the point's ADT keys a clause. A feed of the
        determination drops the atoms that only test: the example's input
        or output exists, a relation of the determination that holds the
        trained examples, a read of the instance's input relation at the
        example with wildcards. A case relation of the parse, whose columns
        but its Key are case types, is the program's where the determination
        feeds it the concept fact alone. A read of a nested instance of the
        program's parse at the literal key of the concept case is a read at
        the example. A read of a relation that the concept case derives from
        one parameter alone, such as `wall` from `params.frame_color`, at the
        key variable of the program's parse is a read of that parameter, and
        the parameter's variable takes the key variable's other uses. An input the determination leaves
        unfed differs, and its dependents are copied only where the
        determination reads them. Each relation and instance of the parse
        that reads an input fed otherwise is the determination's own: a copy
        keyed on Example, which the determination's readers read. So is each
        relation or instance of the parse that an alt rederives, in clauses
        keyed by a constructor outside the concept case, where a `DET` of the
        concept program reads it (`own_copies`): the copy has the concept
        case's clauses alone, so that no alt rederives what such a `DET`
        reads. An input whose program feed reads a relation of the program
        that `det_program_copies` copies is fed otherwise too: the
        determination's feed of it reads no relation an alt rederives."""
        from engine.program import Column, DeclId, Scope, Span, TypeName, UnitId
        det = ("Determine",)
        concept = set(self.concept_of().values())
        other_ctors = self.other_ctors()
        concept_program, program_rederived = self.program_concept(prog)
        self.rederived |= {((), x) for x in program_rederived}
        # the relations of the program that an alt rederives and a `DET` of the concept program reads, and those that read them
        copied_program = self.tainted_program(concept_program, program_rederived)

        prog_inst = {i.component: i.name for i in prog.instances if i.scope.components == () and i.component in self.comps}
        nodes = ParseNodes(prog, self.lib)
        parse_rels, parse_insts, parse_units = nodes.rels, nodes.insts, nodes.units
        node, key_at, instance_key_at = nodes.node, nodes.key_at, nodes.instance_key_at
        E = Variable("@E")

        def canon(u: Unit) -> str:
            names: list[str] = []
            walk_vars((u.head, u.body), names)
            return souffle_unit(subst(dc_replace(u, scope=Scope(det)), {n: f"V{i}" for i, n in enumerate(names)}))

        case_rels = {r.name for r in prog.relations if r.scope.components == () and r.columns
                     and all(c_.type.name in self.case_types for c_ in r.columns)} | {"impl_choice"}

        # the relations of the parse that the program feeds from its input
        fed_by_in = {u.head.relation.name for u in prog.units if u.head.relation.instances
                     and any(a.relation == RelationName((), "in") for a in self._atoms(u.body or ()))}
        # the determination's relations that hold the trained examples
        det_heads = Counter(u.head.relation for u in prog.units if u.scope.components == det)
        trained_rels = {u.head.relation.name for u in prog.units
                        if u.scope.components == det and not u.head.relation.instances and len(u.head.args) == 1
                        and det_heads[u.head.relation] == 1 and u.body is not None and len(u.body) == 1
                        and isinstance(u.body[0], AtomLiteral) and not u.body[0].negated
                        and u.body[0].atom.relation == RelationName((), "ex_out")
                        and u.body[0].atom.args[:1] == u.head.args
                        and all(isinstance(t, Wildcard) for t in u.body[0].atom.args[1:])}

        def keyed_ctors(u: Unit) -> set[str]:
            # the constructors that key a program clause: in its head key, or
            # by an equation that binds the key variable
            hk = key_at(RelationName(u.head.relation.instances[1:], u.head.relation.name))
            k = u.head.args[hk] if hk is not None and hk < len(u.head.args) else None
            out = set(ctor_names(k)) if k is not None else set()
            for l in u.body or ():
                if isinstance(l, Comparison) and l.op == ComparisonOperator.EQ and isinstance(k, Variable):
                    for a, b in ((l.lhs, l.rhs), (l.rhs, l.lhs)):
                        if isinstance(a, Variable) and a.name == k.name:
                            out |= set(ctor_names(b))
            return out

        def alternates(clauses: list[Unit]) -> set[int]:
            # the clauses of one relation that are alternates of other cases,
            # where the program derives the relation in every case of their
            # point: each constructor of its ADT keys a clause, or a clause
            # has no constructor key
            keyed = [keyed_ctors(u) for u in clauses]
            if all(keyed) and any(
                    not all(any(k.name in ks2 for ks2 in keyed) for k in adt_.constructors)
                    for ks in keyed if ks & other_ctors for _, adt_ in self.point_fields()
                    if any(k.name in ks for k in adt_.constructors)):
                return set()
            return {i for i, ks in enumerate(keyed) if ks & other_ctors}

        def concept_key(t):
            # the literal key of the concept case, as the example; a record
            # that opens with it, with that key replaced
            def literal(t) -> bool:
                names: list[str] = []
                walk_vars(t, names)
                return not names and bool(ctor_names(t)) and set(ctor_names(t)) <= concept
            if literal(t):
                return E
            if isinstance(t, RecordTerm) and t.args and literal(t.args[0]):
                return RecordTerm((E,) + t.args[1:])
            return t

        def stands_for(x: str) -> tuple[RelationName, int] | None:
            # the parameter that the relation x holds at the concept case, and
            # the column it holds it in: its one clause of the concept case
            # reads a parameter and relations of case values alone, and puts
            # the parameter's value in one column of its head
            cs = [u for u in prog.units if u.scope.components == () and u.head.relation == RelationName((), x)
                  and not {m for t in u.head.args for m in ctor_names(t)} & other_ctors]
            if len(cs) != 1 or cs[0].body is None:
                return None
            u = cs[0]
            lits = u.body
            if not all(isinstance(l, AtomLiteral) and not l.negated for l in lits):
                return None
            atoms_ = [l.atom for l in lits if isinstance(l, AtomLiteral)]
            reads = [a for a in atoms_ if a.relation.instances == ("params",)]
            if len(reads) != 1 or len(reads[0].args) != 1 or not isinstance(reads[0].args[0], Variable) \
                    or any(a.relation.instances or a.relation.name not in case_rels for a in atoms_ if a is not reads[0]):
                return None
            at = [i for i, t in enumerate(u.head.args) if t == reads[0].args[0]]
            names: list[str] = []
            walk_vars(tuple(t for i, t in enumerate(u.head.args) if i not in at), names)
            return (reads[0].relation, at[0]) if len(at) == 1 and reads[0].args[0].name not in names else None

        standing = {x: sf for x in {u.head.relation.name for u in prog.units
                                    if u.scope.components == () and not u.head.relation.instances and u.head.args}
                    if (sf := stands_for(x)) is not None}

        def stand(u: Unit, kn: str) -> Unit:
            # a read of a relation that stands for a parameter, at the key
            # variable of the parse, reads the parameter instead, and the
            # parameter's variable takes the key variable's other uses: the
            # key variable is a value of the parameter where the concept case
            # is the parameter's stored value
            for l in u.body or ():
                if isinstance(l, AtomLiteral) and not l.negated and not l.atom.relation.instances \
                        and l.atom.relation.name in standing:
                    prel, j = standing[l.atom.relation.name]
                    a = l.atom
                    if j < len(a.args) and a.args[j] == Variable(kn) \
                            and all(isinstance(t, Wildcard) for i, t in enumerate(a.args) if i != j):
                        v = f"@{prel.name}"
                        body = tuple(dc_replace(m, atom=dc_replace(a, relation=prel, args=(Variable(v),))) if m is l else m
                                     for m in u.body)
                        return complement(subst(dc_replace(u, body=body), {kn: v}), v)
            return u

        def complement(u: Unit, v: str) -> Unit:
            # the parameter's variable v, read by one atom and compared by
            # one `!=` with a variable x, as the negated read of x: the
            # parameter holds one value, so `params.p(V), X != V` is
            # `!params.p(X)`
            count: Counter[str] = Counter()

            def tally(x) -> None:
                if isinstance(x, Variable):
                    count[x.name] += 1
                elif isinstance(x, tuple):
                    for y in x:
                        tally(y)
                elif is_dataclass(x) and not isinstance(x, type):
                    for f_ in dc_fields(x):
                        tally(getattr(x, f_.name))
            tally((u.head, u.body))
            read = next(l for l in u.body if isinstance(l, AtomLiteral) and l.atom.args == (Variable(v),))
            for l in u.body:
                if isinstance(l, Comparison) and l.op == ComparisonOperator.NE and count[v] == 2:
                    for a, b in ((l.lhs, l.rhs), (l.rhs, l.lhs)):
                        if b == Variable(v) and isinstance(a, Variable) and a.name != v:
                            neg = AtomLiteral(dc_replace(read.atom, args=(a,)), True)
                            return dc_replace(u, body=tuple(neg if m is l else m for m in u.body if m is not read))
            return u

        def feed(u: Unit, iname: str, det_side: bool, case_key: bool = False) -> tuple[str, Unit]:
            # the clause as the lifted parse reads it: the example at each
            # key column of the parse, `in` that example's input, and no atom
            # that only tests that the example or the case exists; in the
            # determination, a relation of a parameter's name is the
            # parameter's determination; and the clause with those atoms dropped
            def fix(x):
                if isinstance(x, Atom):
                    rn = x.relation
                    if rn == RelationName((), "in"):
                        return dc_replace(x, relation=RelationName((), "ex_in"), args=(E,) + x.args)
                    if rn.instances[:1] == (iname,):
                        i = key_at(RelationName(rn.instances[1:], rn.name))
                        args = x.args if i is None or i >= len(x.args) else x.args[:i] + (E,) + x.args[i + 1:]
                        if len(rn.instances) > 1 and not det_side:
                            # a nested instance's key is the example where the determination reads it
                            args = tuple(concept_key(t) for t in args)
                        return dc_replace(x, relation=RelationName(("@parse",) + rn.instances[1:], rn.name), args=args)
                    if det_side and not rn.instances and (det, rn.name) in self.rels and (("Params",), rn.name) in self.rels:
                        return dc_replace(x, relation=RelationName(("params",), rn.name))
                    return x
                if isinstance(x, tuple):
                    return tuple(fix(y) for y in x)
                if is_dataclass(x) and not isinstance(x, type):
                    ch = {f_.name: fix(getattr(x, f_.name)) for f_ in dc_fields(x)
                          if isinstance(getattr(x, f_.name), tuple) or
                          (is_dataclass(getattr(x, f_.name)) and not isinstance(getattr(x, f_.name), type))}
                    return dc_replace(x, **ch) if ch else x
                return x
            hk = key_at(RelationName(u.head.relation.instances[1:], u.head.relation.name))
            k = u.head.args[hk] if hk is not None and hk < len(u.head.args) else None
            kn = k.name if isinstance(k, Variable) else None
            u = dc_replace(u, head=fix(u.head), body=fix(u.body))
            if kn is not None and not det_side:
                u = stand(u, kn)
            uses: Counter[str] = Counter()

            def count(x) -> None:
                if isinstance(x, Variable):
                    uses[x.name] += 1
                elif isinstance(x, tuple):
                    for y in x:
                        count(y)
                elif is_dataclass(x) and not isinstance(x, type):
                    for f_ in dc_fields(x):
                        count(getattr(x, f_.name))
            count((u.head, u.body))

            def test_only(l) -> bool:
                if not isinstance(l, AtomLiteral) or l.negated:
                    return False
                a = l.atom
                if a.relation.instances == ("@parse",):
                    return a.relation.name in fed_by_in and bool(a.args) and (a.args[0] == E or a.args[0] == k) \
                        and all(isinstance(t, Wildcard) for t in a.args[1:])
                if a.relation.instances:
                    return False
                if a.relation.name in trained_rels and det_side:
                    return a.args == (E,) or a.args == (k,)
                if a.relation.name in ("ex_in", "ex_out"):
                    return bool(a.args) and (a.args[0] == E or a.args[0] == k) \
                        and all(isinstance(t, Wildcard) for t in a.args[1:])
                # a case the key holds is the case the lifted parse runs in
                return a.relation.name in case_rels and all(
                    isinstance(t, Wildcard) or isinstance(t, Variable) and (uses[t.name] == 1 or t.name == kn and case_key)
                    for t in a.args)
            u = dc_replace(u, body=tuple(l for l in u.body or () if not test_only(l)))
            return canon(subst(u, {kn: E.name}) if kn else u), u

        def concept_feed(x: str, clauses: list[Unit]) -> bool:
            # the determination feeds the case relation x the concept fact alone
            r = parse_rels[x]
            others = [c_ for c_ in r.columns if c_.type.name != "Key"]
            if len(clauses) != 1 or not others or any(c_.type.name not in self.case_types for c_ in others):
                return False
            u = clauses[0]
            if u.body is None or len(u.body) != 1 or not isinstance(u.body[0], AtomLiteral) or u.body[0].negated:
                return False
            a = u.body[0].atom
            hk = key_at(RelationName((), x))
            if a.relation.instances or (det, a.relation.name) not in self.rels or hk is None \
                    or tuple(t for i, t in enumerate(u.head.args) if i != hk) != a.args \
                    or not all(isinstance(t, Variable) for t in a.args):
                return False
            facts = [f_ for f_ in prog.units if f_.scope.components == det and f_.head.relation == a.relation]
            names = {m for f_ in facts for t in f_.head.args for m in ctor_names(t)}
            return len(facts) == 1 and facts[0].body is None and bool(names) and names <= concept

        for inst in [i for i in prog.instances if i.scope.components == det and i.component in prog_inst]:
            comp = self.comps[inst.component]
            tsub = {p: a.name for p, a in zip(comp.type_params, inst.type_args)}
            if tsub.get("Key") != "Example":
                continue
            n, pname = inst.name, prog_inst[inst.component]
            pinst = next(i for i in prog.instances if i.scope.components == () and i.name == pname)
            case_key = dict(zip(comp.type_params, (a.name for a in pinst.type_args))).get("Key") in self.case_types
            feeds: dict[str, tuple[list[str], list[str]]] = defaultdict(lambda: ([], []))
            det_feeds: dict[str, list[Unit]] = defaultdict(list)
            prog_clauses: dict[str, list[Unit]] = defaultdict(list)
            for u in prog.units:
                rn = u.head.relation
                if u.scope.components == () and rn.instances == (pname,) and u.head.args:
                    prog_clauses[rn.name].append(u)
                elif u.scope.components == det and rn.instances == (n,) and u.head.args:
                    fed = feed(u, n, True)
                    feeds[rn.name][1].append(fed[0])
                    det_feeds[rn.name].append(fed[1])
            rederived: set[str] = set()
            for x, clauses in prog_clauses.items():
                dropped = alternates(clauses)
                feeds[x][0].extend(feed(u, pname, False, case_key)[0] for i, u in enumerate(clauses) if i not in dropped)
                if dropped and det_feeds[x]:
                    rederived.add(x)
            # the parse's own clauses that a constructor outside the concept case keys
            alternate_ctors = {id(u): {m for t in u.head.args for m in ctor_names(t)} & other_ctors for u in parse_units}
            rederived |= {h for u in parse_units if alternate_ctors[id(u)] and (h := node(u.head.relation)) is not None}
            self.rederived |= {(("Parse",), x) for x in rederived}
            # an input whose program feed reads a relation that the determination copies, before the `stand` rewrite or not
            fed_from_copies = {x for x, clauses in prog_clauses.items()
                               if any(a.relation.name in copied_program and not a.relation.instances
                                      for i, u in enumerate(clauses) if i not in alternates(clauses)
                                      for a in self._atoms(u.body or ()))}
            differ = {x for x, (a, b) in feeds.items()
                      if sorted(a) != sorted(b) and not (a and concept_feed(x, det_feeds[x]))} \
                | {x for x in rederived if (("Parse",), x) in self.own_copies} | fed_from_copies
            if not differ:
                continue
            # the parse's nodes that read an input fed otherwise
            tainted = set(differ)
            grew = True
            while grew:
                grew = False
                for u in parse_units:
                    h = node(u.head.relation)
                    if h is not None and h not in tainted and any(
                            node(a.relation) in tainted for a in self._atoms(u.body or ())):
                        tainted.add(h)
                        grew = True
            # those the determination reads
            read = nodes.closure(nodes.read_through(
                (u for u in prog.units if u.scope.components == det
                 and not (u.head.relation.instances == (n,) and u.head.relation.name not in differ)), n))
            copy = tainted & read
            if not copy:
                continue
            prog = self.copy_parse(prog, nodes, det, n, tsub, copy,
                                   [u for u in parse_units if node(u.head.relation) in copy and not (
                                       alternate_ctors[id(u)] and (("Parse",), node(u.head.relation)) in self.own_copies)])
        return prog

    def parse_instance_copies(self, prog):
        """Each top-level instance of the solver's `Parse` after the first
        (the solver's own, which `parse_sub` takes) is written as copies of
        the nodes of the parse that the program reads through it
        (`copy_parse`), each keyed on the instance's key type, with the
        instance's input clauses (`chart.cell`) as the copies' input; the
        program's parse relations hold the clauses of the solver's own
        instance alone. The instance is dropped. An instance that a clause
        outside the top level names is not written so: the clause would
        still read it, and it gets a `TODO` line, with no clause of the
        instance in the parse relations."""
        top = [i for i in prog.instances if i.scope.components == () and i.component == "Parse"]
        nodes = ParseNodes(prog, self.lib)
        for inst in top[1:]:
            n = inst.name
            named_in = {u.scope.components for u in prog.units
                        for a in (u.head, *self._atoms(u.body or ())) if a.relation.instances[:1] == (n,)}
            if named_in <= {()}:
                copy = nodes.closure(nodes.read_through((u for u in prog.units if u.scope.components == ()), n))
                prog = self.copy_parse(prog, nodes, (), n, {p: a.name for p, a in zip(self.comps["Parse"].type_params, inst.type_args)},
                                       copy, [u for u in nodes.units if nodes.node(u.head.relation) in copy])
            else:
                self.todo.add("parse-instance", f"{n}: a clause outside the top level names the instance of the "
                              f"{inst.component} component, which is written as copies in the top level")
            prog = dc_replace(prog, instances=tuple(i for i in prog.instances if (i.scope.components, i.name) != ((), n)),
                              units=tuple(u for u in prog.units
                                          if not (u.scope.components == () and u.head.relation.instances[:1] == (n,))))
            self.insts.pop(((), n), None)
        return prog

    def copy_parse(self, prog, nodes: ParseNodes, scope: tuple[str, ...], n: str, tsub: dict[str, str],
                   copy: set[str], clauses: list[Unit]):
        """`prog` with a copy, in `scope`, of each node of `copy` of the
        solver's parse that the instance `n` of `scope` holds, and of each
        type the copies read, under names of their own (`<n>__<name>`).
        `tsub` gives the type each parameter of the parse has for `n`, and the
        copies are keyed on the type `Key` has there. The copies' clauses are
        `clauses`, those of the parse, and read the copies. The clauses of
        `scope` that head or read a copied node of `n` head or read the copy.
        A copy that no clause derives is dropped (`without_empty`). Each copy
        is a copy through `n` of its node (`det_copies`, `det_copy_via`). A
        parse keyed on Example has the key variable of each clause `E`, and
        its key column `e`."""
        from engine.program import Column, DeclId, Scope, Span, TypeName, UnitId
        example = tsub.get("Key") == "Example"
        taken = {r.name for r in prog.relations if r.scope.components == scope} | \
                {i.name for i in prog.instances if i.scope.components == scope}
        own: dict[str, str] = {}
        for x in sorted(copy):
            cand, k = f"{n}__{x}", 2
            while cand in taken:
                cand, k = f"{n}__{x}{k}", k + 1
            taken.add(cand)
            own[x] = cand
            self.det_copies[(scope, cand)] = (("Parse",), x)
            self.det_copy_via[(scope, cand)] = n

        def to_copy(rn: RelationName, from_parse: bool):
            if from_parse:
                if rn.instances and rn.instances[0] in nodes.insts:
                    i0 = rn.instances[0]
                    return RelationName((own[i0],) + rn.instances[1:], rn.name) if i0 in own \
                        else RelationName((n,) + rn.instances, rn.name)
                if not rn.instances and rn.name in nodes.rels:
                    return RelationName((), own[rn.name]) if rn.name in own else RelationName((n,), rn.name)
                return rn
            if rn.instances[:1] == (n,):
                return to_copy(RelationName(rn.instances[1:], rn.name), True)
            return rn
        # the parse's types the copies read, each a copy keyed as the instance is
        parse_types = {t.name: t for t in prog.types if t.scope.components == ("Parse",)}
        scope_types = {t.name for t in prog.types if t.scope.components == scope}

        def type_refs(x, out: set[str]) -> None:
            if isinstance(x, TypeName):
                if not x.instances and x.name in parse_types and x.name not in out:
                    out.add(x.name)
                    type_refs(parse_types[x.name], out)
            elif isinstance(x, tuple):
                for y in x:
                    type_refs(y, out)
            elif is_dataclass(x) and not isinstance(x, type):
                for f_ in dc_fields(x):
                    type_refs(getattr(x, f_.name), out)
        refs: set[str] = set()
        type_refs(tuple(nodes.rels[x] for x in copy if x in nodes.rels), refs)
        type_refs(tuple(nodes.insts[x] for x in copy if x in nodes.insts), refs)
        type_refs(tuple(u for u in nodes.units if nodes.node(u.head.relation) in copy), refs)
        tmap = dict(tsub)
        for t in sorted(refs):
            cand, k = f"{n}__{t}", 2
            while cand in scope_types:
                cand, k = f"{n}__{t}{k}", k + 1
            scope_types.add(cand)
            tmap[t] = cand

        def retype(x):
            if isinstance(x, TypeName):
                return TypeName((), tmap[x.name]) if not x.instances and x.name in tmap else x
            if isinstance(x, tuple):
                return tuple(retype(y) for y in x)
            if is_dataclass(x) and not isinstance(x, type) and not isinstance(x, (RelationName, Span)):
                ch = {f_.name: retype(getattr(x, f_.name)) for f_ in dc_fields(x)
                      if isinstance(getattr(x, f_.name), tuple) or
                      (is_dataclass(getattr(x, f_.name)) and not isinstance(getattr(x, f_.name), type))}
                return dc_replace(x, **ch) if ch else x
            return x
        new_rels, new_insts, new_types, new_units = [], [], [], []

        def next_id() -> DeclId:
            return DeclId(prog.next_decl_index() + len(new_rels) + len(new_insts) + len(new_types))
        for t in sorted(refs):
            new_types.append(dc_replace(retype(parse_types[t]), id=next_id(), name=tmap[t], scope=Scope(scope)))
        for x in sorted(copy):
            if x in nodes.rels:
                r = nodes.rels[x]
                names = [c_.name for c_ in r.columns]
                cols = tuple(Column("e" if example and c_.type.name == "Key" and "e" not in names else c_.name,
                                    retype(c_.type))
                             for c_ in r.columns)
                new_rels.append(dc_replace(r, id=next_id(), name=own[x], scope=Scope(scope), columns=cols))
            else:
                i = nodes.insts[x]
                new_insts.append(dc_replace(i, id=next_id(), name=own[x], scope=Scope(scope),
                                            type_args=retype(i.type_args)))
        base = prog.next_unit_index()
        for u in clauses:
            m: dict[str, str] = {}
            if example:
                # the key is the example, E
                hk = nodes.instance_key_at(u.head.relation) if u.head.relation.instances else nodes.key_at(u.head.relation)
                k0 = u.head.args[hk] if hk is not None and hk < len(u.head.args) else None
                used: list[str] = []
                walk_vars((u.head, u.body), used)
                if "E" in used and k0 != Variable("E"):
                    # another E: a lifted read's Example column takes that name
                    j = 1
                    while f"E{j}" in used:
                        j += 1
                    m["E"] = f"E{j}"
                if isinstance(k0, Variable) and k0.name != "E":
                    m[k0.name] = "E"
            new_units.append(subst(retype(Unit(UnitId(base + len(new_units)), Scope(scope),
                                               rel_map(u.head, lambda rn: to_copy(rn, True)),
                                               rel_map(u.body, lambda rn: to_copy(rn, True)), u.plan, u.span)), m))
        units = []
        for u in prog.units:
            if u.scope.components == scope:
                rn = u.head.relation
                if rn.instances == (n,) and rn.name in copy:
                    u = dc_replace(u, head=dc_replace(u.head, relation=RelationName((), own[rn.name])))
                u = dc_replace(u, body=rel_map(u.body, lambda rn: to_copy(rn, False)))
            units.append(u)
            if nodes.units and u is nodes.units[-1]:
                units += new_units
        if not nodes.units:
            units += new_units
        units, empty = self.without_empty(units, scope, {r.name for r in new_rels} | {i.name for i in new_insts})
        new_rels = [r for r in new_rels if r.name not in empty]
        new_insts = [i for i in new_insts if i.name not in empty]
        for key_ in [k_ for k_ in self.det_copies if k_[1] in empty]:
            del self.det_copies[key_]
            self.det_copy_via.pop(key_, None)
        prog = dc_replace(prog, types=prog.types + tuple(new_types), relations=prog.relations + tuple(new_rels),
                          instances=prog.instances + tuple(new_insts), units=tuple(units))
        for i in new_insts:
            self.insts[(scope, i.name)] = i
        for t in new_types:
            self.types[(scope, t.name)] = t
        self.rels = {(r.scope.components, r.name): r for r in prog.relations}
        return prog

    @staticmethod
    def without_empty(units, det: tuple[str, ...], copies: set[str]):
        """`units` and the `copies` that no clause of `det` derives, where a
        copy no clause derives is empty, and so is an instance copy no input
        clause feeds: a clause of `det` that reads an empty copy holds
        nowhere, and a negation of it holds everywhere."""
        def of(a: Atom) -> str:
            return a.relation.instances[0] if a.relation.instances else a.relation.name
        while True:
            heads = {of(u.head) for u in units if u.scope.components == det}
            empty = copies - heads
            kept = []
            for u in units:
                if u.scope.components == det and any(
                        isinstance(l, AtomLiteral) and of(l.atom) in empty and not l.negated for l in u.body or ()):
                    continue
                if u.scope.components == det and u.body:
                    u = dc_replace(u, body=tuple(l for l in u.body if not (
                        isinstance(l, AtomLiteral) and l.negated and of(l.atom) in empty)))
                kept.append(u)
            if len(kept) == len(units):
                return kept, empty
            units = kept

    def other_ctors(self) -> set[str]:
        """The constructors of the points' ADTs outside the concept case."""
        return {k.name for _, adt_ in self.point_fields() for k in adt_.constructors} - set(self.concept_of().values())

    def program_concept(self, prog) -> tuple[dict[str, list[Unit]], set[str]]:
        """Each relation of the program, with its clauses that hold in the
        concept case: those that no constructor outside the concept case
        keys, in the head, in a positive read of a relation, or by an
        equation. And the relations with a clause that such a constructor keys:
        an alt rederives them."""
        other = self.other_ctors()

        def keyed(u: Unit) -> bool:
            names = [m for t in u.head.args for m in ctor_names(t)]
            for l in u.body or ():
                if isinstance(l, AtomLiteral) and not l.negated:
                    names += [m for t in l.atom.args for m in ctor_names(t)]
                elif isinstance(l, Comparison) and l.op == ComparisonOperator.EQ:
                    names += ctor_names(l.lhs) + ctor_names(l.rhs)
            return bool(other.intersection(names))
        concept: dict[str, list[Unit]] = defaultdict(list)
        rederived: set[str] = set()
        for u in prog.units:
            if u.scope.components == () and not u.head.relation.instances:
                if keyed(u):
                    rederived.add(u.head.relation.name)
                else:
                    concept[u.head.relation.name].append(u)
        return concept, rederived

    def tainted_program(self, concept: dict[str, list[Unit]], rederived: set[str]) -> set[str]:
        """The relations of the program that the determination is to copy
        (`own_copies`) and an alt rederives, and each relation whose clauses
        of the concept case read one of them, directly or through another."""
        tainted = {x for x in rederived if ((), x) in self.own_copies}
        grew = True
        while grew:
            grew = False
            for x, us in concept.items():
                if x not in tainted and any(a.relation.name in tainted and not a.relation.instances
                                            for u in us for a in self._atoms(u.body or ())):
                    tainted.add(x)
                    grew = True
        return tainted

    def det_program_copies(self, prog):
        """Each relation of the program that `tainted_program` finds and the
        determination reads, directly or through another such relation, gets
        a copy in the determination under a name of its own, with its clauses
        of the concept case alone, which reads the copies of the relations it
        reads; the determination's clauses read the copies. So no alt
        rederives what a `DET` of the concept program reads. A relation that
        the determination declares under the same name, or that a clause
        reads, is left as it is."""
        from engine.program import DeclId, Scope, UnitId
        det = ("Determine",)
        concept, rederived = self.program_concept(prog)
        det_names = {r.name for r in prog.relations if r.scope.components == det} | \
                    {i.name for i in prog.instances if i.scope.components == det}

        def reads(us) -> set[str]:
            return {a.relation.name for u in us for a in self._atoms(u.body or ()) if not a.relation.instances}
        tainted = self.tainted_program(concept, rederived)
        tainted -= {x for x in tainted if x in det_names or reads(concept[x]) & det_names}
        todo = list(reads(u for u in prog.units if u.scope.components == det) & tainted)
        copy: set[str] = set()
        while todo:
            x = todo.pop()
            if x not in copy:
                copy.add(x)
                todo += reads(concept[x]) & tainted
        if not copy:
            return prog
        own: dict[str, str] = {}
        for x in sorted(copy):
            cand, k = f"own__{x}", 2
            while cand in det_names:
                cand, k = f"own__{x}{k}", k + 1
            det_names.add(cand)
            own[x] = cand
            self.det_copies[(det, cand)] = ((), x)

        def reread(body):
            for x, cand in own.items():
                body = rename_rel(body, RelationName((), x), RelationName((), cand))
            return body
        decls = {r.name: r for r in prog.relations if r.scope.components == ()}
        new_rels = [dc_replace(decls[x], id=DeclId(prog.next_decl_index() + i), name=own[x], scope=Scope(det))
                    for i, x in enumerate(sorted(copy))]
        base = prog.next_unit_index()
        new_units = [Unit(UnitId(base + j), Scope(det), dc_replace(u.head, relation=RelationName((), own[x])),
                          reread(u.body), u.plan, u.span)
                     for j, (x, u) in enumerate((x, u) for x in sorted(copy) for u in concept[x])]
        units = [dc_replace(u, body=reread(u.body)) if u.scope.components == det else u for u in prog.units]
        units, empty = self.without_empty(units + new_units, det, set(own.values()))
        for key_ in [k_ for k_ in self.det_copies if k_[1] in empty]:
            del self.det_copies[key_]
        return dc_replace(prog, relations=prog.relations + tuple(r for r in new_rels if r.name not in empty),
                          units=tuple(units))

    @staticmethod
    def _atoms(lits):
        for l in lits:
            if isinstance(l, AtomLiteral):
                yield l.atom
            elif isinstance(l, Disjunction):
                for b in l.branches:
                    yield from Converter._atoms(b)
            elif isinstance(l, Comparison):
                for t in (l.lhs, l.rhs):
                    if isinstance(t, Aggregate):
                        yield from Converter._atoms(t.body)

    def concept_of(self) -> dict[str, str]:
        """The concept case: each point's name and the first constructor of
        its ADT."""
        return {f_: adt_.constructors[0].name for f_, adt_ in self.point_fields()}

    def point_fields(self) -> list[tuple[str, AdtType]]:
        """Each point: its name and its ADT, the Choice's fields and every ADT
        a constructor's field reaches, in declaration order."""
        choice = self.find_type("Choice", ())
        if choice is None:
            return []
        named: dict[str, str] = {}
        if isinstance(choice, RecordType):
            for f in choice.fields:
                named.setdefault(f.type.name, f.name)
        else:
            named["Choice"] = "choice"
        for t in self.prog.types:
            if isinstance(t, AdtType) and t.name in self.case_types:
                for k in t.constructors:
                    for f in k.fields:
                        named.setdefault(f.type.name, f.name)
        out = []
        for t in sorted((t for t in self.prog.types if isinstance(t, AdtType) and t.name in self.case_types
                         and not t.scope.components), key=lambda t: t.span.first):
            out.append((named.get(t.name, t.name[:1].lower() + t.name[1:]), t))
        return out

    def leaves(self, name: str, type_name: str, tparam: bool, scope: tuple[str, ...],
               sub: dict[str, str], outer: dict[str, str] | None = None, lift_ex: bool = False) -> list[Leaf]:
        """The leaves of a column of `type_name`; a record expands only when
        it holds a case, a key-lift or a Unit leaf."""
        t = sub.get(type_name, type_name)
        if outer is not None and t in outer and isinstance(self.find_type(outer[t], ()), RecordType):
            t = outer[t]   # the Parse comp's key parameter, a record
        if t in self.case_types:
            return [Leaf(name, "case", tparam)]
        if t == "TiebreakResolution":
            return [Leaf(name, "drop", tparam)]   # the picks drop every such column
        if t in getattr(self, "demo_rule_types", ()):
            return [Leaf(name, "rule", tparam)]
        if t in getattr(self, "demo_rule_records", ()):
            return [Leaf(name, "drop", tparam)]
        if t == "Unit" or t in self.open_types:
            return [Leaf(name, "drop", tparam)]
        if t == "@lift":
            return [Leaf(name, "drop", tparam)]
        if t == "@example":
            return [Leaf("E", "example", False, type="Example")]
        if t.startswith("@cand:"):
            # a candidate parse's key: its example, and the candidate, which
            # the parameter the read binds stands for
            decl = self.find_type(t[len("@cand:"):], ("Determine",))
            cand = self.cand_key_fields.get(t[len("@cand:"):], set())
            if isinstance(decl, RecordType):
                return [Leaf("E", "example", False, (i,), (f.name,), "Example") if f.type.name == "Example"
                        else Leaf(f.name, "drop" if i in cand else "keep", tparam, (i,), (f.name,), f.type.name)
                        for i, f in enumerate(decl.fields)]
            return [Leaf("E", "example", False, type="Example")]
        decl = self.find_type(t, scope)
        if isinstance(decl, RecordType):
            fsub = sub if outer is None else outer
            # a record the Parse comp's key parameter stands for: its Example
            # field is the lifted read's Example column
            lifted = lift_ex or (scope == ("Parse",) and type_name in sub)
            out = []
            for i, f in enumerate(decl.fields):
                if lifted and f.type.name == "Example":
                    out.append(Leaf("E", "example", False, (i,), (f.name,), "Example"))
                    continue   # an example field: the lifted read's Example column
                for leaf in self.leaves(f.name, f.type.name, tparam, decl.scope.components, fsub, lift_ex=lifted):
                    out.append(Leaf(leaf.name, leaf.kind, leaf.tparam, (i,) + leaf.path,
                                    (f.name,) + leaf.field, leaf.type))
            return out
        return [Leaf(name, "keep", tparam, type=t)]

    # ---- names

    def rel_key(self, scope: tuple[str, ...], name: str) -> tuple[tuple[str, ...], str]:
        """The key of the arclog relation that the Souffle relation `name` of
        `scope` is written as: the parameter's, for a `Determine` relation that
        determines a parameter, and its own otherwise."""
        key = (scope, name)
        if scope == ("Determine",) and key not in self.names and (("Params",), name) in self.rels \
                and key not in self.insts:
            return (("Params",), name)   # the determination of the parameter
        return key

    def rel_name(self, scope: tuple[str, ...], name: str) -> str:
        key = self.rel_key(scope, name)
        if key not in self.names:
            base = name
            cand = base
            n = 2
            while cand in self.used_names:
                cand = f"{base}{n}"
                n += 1
            self.used_names.add(cand)
            self.names[key] = cand
        inst = self.insts.get(key)
        souffle = self.souffle_of(key[0], key[1], inst is not None and inst.component in self.lib.comps)
        return self.wrote("in" if self.names[key] == "__in__" else "&" + self.names[key], *souffle)

    def souffle_of(self, scope: tuple[str, ...], name: str, instance: bool) -> tuple[Written, ...]:
        """What the relation, or instance, `name` of `scope` in the program
        this pass converts stands for in the Souffle program: itself, where
        the pass did not make it, and what it made it for otherwise (none,
        where it made it for no Souffle relation)."""
        if (scope, name) in self.made:
            return self.made[(scope, name)]
        return (Written(scope, name, instance),)

    def souffle_arity(self, scope: tuple[str, ...], relation: str) -> int | None:
        """The number of columns of the Souffle relation `relation` declared
        in `scope`, as the solver file declares it, or, for `<instance>.<name>`
        of an instance of a component of the lib, as the present lib declares
        it; none for a relation neither declares."""
        instance, dot, name = relation.partition(".")
        if not dot:
            if (scope, relation) in self.souffle_columns:
                return self.souffle_columns[(scope, relation)]
            return len(self.lib.top[relation]) if not scope and relation in self.lib.top else None
        component = self.souffle_components.get((scope, instance))
        if component is None or component not in self.lib.comps:
            return None
        return next((len(r.cols) for r in self.lib.present(component)[1] if r.name == name), None)

    def note_writing(self, forms: list[Form], within: frozenset[str]) -> None:
        """Record, for each arclog name that `forms` derive by clauses, the
        arclog column at which each kept leaf of the clauses' heads stands
        in `forms`, the writing under the ALTs with the constructors
        `within` (none: at the top level): a leaf stands at its own column
        unless the clauses of the name all drop it to the same other."""
        by_name: dict[str, list[Form]] = {}
        for f in forms:
            if f.src is not None and f.col_labels:
                by_name.setdefault(f.name, []).append(f)
        for name, fs in by_name.items():
            records = [label_sources(f) for f in fs]
            first = records[0]
            if any(tuple(map(len, r)) != tuple(map(len, first)) for r in records):
                continue
            self.writings.setdefault(name, {})[within] = tuple(
                tuple(first[j][k] if all(r[j][k] == first[j][k] for r in records) else (j, k)
                      for k in range(len(first[j])))
                for j in range(len(first)))

    def wrote(self, arc: str, *souffle: Written) -> str:
        """`arc`, an arclog name this pass writes, recorded with what it was
        written from, once each (`name_map`); with none, recorded as written
        from no Souffle relation."""
        got = self.written.setdefault(arc, [])
        got.extend(w for w in dict.fromkeys(souffle) if w not in got)
        return arc

    # ---- resolving an atom's relation

    def resolve(self, rel, scope: tuple[str, ...], sub: dict[str, str]):
        """(arclog name, [(Col, leaves)], kind, instance key) for a relation
        name read in `scope`; kind is fact, lib, param, derived, inst."""
        parts = rel.instances
        name = rel.name
        if not parts:
            if name in FACTS:
                cols = self.lib.top[name]
                out = [(Col(pascal(n), t, False), [Leaf(pascal(n), "keep", False, type=t)]) for n, t in cols]
                if name != "in":
                    out[0] = (out[0][0], [Leaf("E", "example", False, type="Example")])
                return self.wrote(name, Written((), name, False)), out, "fact", None
            for i in range(len(scope), -1, -1):
                r = self.rels.get((scope[:i], name))
                if r is not None:
                    return self._derived(r, sub)
            if name in self.lib.top:
                self.wrote(name, Written((), name, False))
            if name in self.lib.top or name in self.sig.top:
                cols = self.lib.top.get(name) or self.sig.top[name]
                return name, [(Col(pascal(n), t, False), [Leaf(pascal(n), "keep", False, type=t)]) for n, t in cols], "lib", None
            return name, None, "unknown", None
        head, rest = parts[0], parts[1:]
        if head == LIB_PATH and not rest:   # a lib relation an expansion wrote, whose name the solver takes
            cols = self.lib.top.get(name) or self.sig.top.get(name)
            if cols is None:
                return name, None, "unknown", None
            return name, [(Col(pascal(n), t, False), [Leaf(pascal(n), "keep", False, type=t)]) for n, t in cols], "lib", None
        if head == "params" and not rest:
            r = self.rels.get((("Params",), name))
            if r is None:
                return self.wrote("&" + name, Written(("Params",), name, False)), None, "unknown", None
            name_out, cols, _, _ = self._derived(r, sub)
            return name_out, cols, "param", None
        if head == "helpers":
            _, hrels = self.lib.relations("ParamsHelpers")
            lr = next((r for r in hrels if r.name == name), None)
            if lr is None:
                return name, None, "unknown", None
            return name, [(Col(pascal(c.name), c.type, False), [Leaf(pascal(c.name), "keep", False, type=c.type)]) for c in lr.cols], "lib", None
        inst = None
        for i in range(len(scope), -1, -1):
            inst = self.insts.get((scope[:i], head)) or self.plan_instances.get((scope[:i], head))
            if inst is not None:
                break
        if inst is None:
            return ".".join(parts + (name,)), None, "unknown", None
        if inst.component in self.comps:   # a solver comp: Parse
            comp = self.comps[inst.component]
            inner_sub = dict(sub)
            for p, a in zip(comp.type_params, inst.type_args):
                inner_sub[p] = "@example" if a.name == "Example" else "@lift" if a.name in ("Unit",) else a.name
                if inst.scope.components == ("Determine",) and inst.name in getattr(self, "cand_insts", {}) \
                        and p == "Key":
                    inner_sub[p] = "@cand:" + a.name   # the program's parse, lifted
            from engine.program import RelationName
            return self.resolve(RelationName(rest, name), (inst.component,), inner_sub)
        if rest:
            return ".".join(parts + (name,)), None, "unknown", None
        if inst.component not in self.lib.comps:
            return ".".join(parts + (name,)), None, "unknown", None
        tparams, rels = self.lib.relations(inst.component)
        isub = dict(sub)
        for p, a in zip(tparams, inst.type_args):
            isub[p] = sub.get(a.name, a.name)
        if name == "@demonstrated" and inst.component == "DemonstrationConsistency":
            # the key, then the prediction's columns; a form keyed by its
            # demonstrated pair has the pair as its key
            ikey = (inst.scope.components, inst.name)
            con = next(r for r in rels if r.name == "consistent")
            pred = next(r for r in rels if r.name == "prediction")
            cols = [(c_, self.leaves(c_.name, c_.type, c_.tparam, inst.scope.components, isub, outer=sub))
                    for c_ in [con.cols[0], *pred.cols[2:]]]
            if self.demo_mode.get(ikey) == "pair":
                obj = con.cols[2]
                cols[0] = (Col("key", obj.type, True),
                           [Leaf(n, "keep", True, (i,), (n,)) for i, n in enumerate(self.demo_pair[ikey])])
            return self.rel_name(inst.scope.components, inst.name), cols, "inst", ikey
        lr = next((r for r in rels if r.name == name), None)
        if lr is None:
            return ".".join(parts + (name,)), None, "unknown", None
        cols = []
        for c in lr.cols:
            cols.append((c, self.leaves(c.name, c.type, c.tparam, inst.scope.components, isub, outer=sub)))
        iname = self.rel_name(inst.scope.components, inst.name)
        return (self.wrote(f"{iname}.{name}", *self.souffle_of(inst.scope.components, f"{inst.name}.{name}", False)),
                cols, "inst", (inst.scope.components, inst.name))

    def leaf_type(self, type_name: str, path: tuple[int, ...], scope: tuple[str, ...], sub: dict[str, str]) -> str:
        """The type of the leaf at `path` of a column of `type_name`, as
        `leaves` gives the path, with each alias followed to its target."""
        t = sub.get(type_name, type_name)
        for i in path:
            decl = self.find_type(t, scope)
            assert isinstance(decl, RecordType), (t, path)
            scope, t = decl.scope.components, sub.get(decl.fields[i].type.name, decl.fields[i].type.name)
        return self.alias_base(t, scope)

    def _derived(self, r, sub):
        cols = []
        placed = r.scope.components == ("Params",) and r.name in self.rigid
        same = getattr(self, "alias", {}).get((r.scope.components, r.name), {})
        n = 0
        for i, c in enumerate(r.columns):
            col = Col("Pose" if placed and i == 0 else pascal(c.name), c.type.name, False)
            ls = self.leaves(col.name, c.type.name, False, r.scope.components, sub)
            if len(ls) > 1:
                ls = [dc_replace(l, name=pascal(l.name)) if l.kind == "keep" else l for l in ls]
            out_ls = []
            for l in ls:
                if l.kind == "keep" and n in same:
                    l = dc_replace(l, kind="drop")   # the same as another column
                out_ls.append(l)
                n += 1
            cols.append((col, out_ls))
        key = self.rel_key(r.scope.components, r.name)
        pcols = getattr(self, "proposer_cols", {}).get(r.name) if key[0] == ("Params",) else None
        mismatch = None
        if pcols is not None:
            # a parameter a proposer gives has the proposer's columns, where
            # its kept columns map onto them by count and by type
            kept = [(i, dc_replace(col, type=sub.get(col.type, col.type)))
                    for i, (col, ls) in enumerate(cols) if any(l.kind == "keep" for l in ls)]
            if len(kept) == len(pcols) and all(
                    [l.path for l in cols[i][1] if l.kind == "keep"] == [()]
                    and self.alias_base(col.type, r.scope.components) == self.alias_base(pc.type, ())
                    for (i, col), pc in zip(kept, pcols)):
                for (i, _), pc in zip(kept, pcols):
                    cols[i] = (dc_replace(cols[i][0], name=pc.name),
                               [dc_replace(l, name=pc.name) if l.kind == "keep" else l for l in cols[i][1]])
            else:
                mismatch = ([col for _, col in kept], pcols)
        def own_e(col, l):
            """Whether `l` of `col` is a column E that holds no Example."""
            return l.name == "E" and l.kind == "keep" \
                and self.leaf_type(col.type, l.path, r.scope.components, sub) != "Example"

        if any(own_e(col, l) for col, ls in cols for l in ls):
            # a lifted read's Example column is E, so the relation's own E takes a digit
            names = {l.name for _, ls in cols for l in ls}
            e = next(f"E{j}" for j in range(1, len(names) + 2) if f"E{j}" not in names)
            cols = [(dc_replace(col, name=e) if col.name == "E" and any(own_e(col, l) for l in ls) else col,
                     [dc_replace(l, name=e) if own_e(col, l) else l for l in ls])
                    for col, ls in cols]
        seen = Counter(l.name for _, ls in cols for l in ls if l.kind == "keep")
        if any(n > 1 for n in seen.values()):
            cols = [(col, [dc_replace(l, name=f"{col.name}_{l.name.lower()}") if len(ls) > 1 and l.kind == "keep" and seen[l.name] > 1 else l for l in ls]) for col, ls in cols]
            # leaves that still share a name take their path of fields
            seen = Counter(l.name for _, ls in cols for l in ls if l.kind == "keep")
            if any(n > 1 for n in seen.values()):
                cols = [(col, [dc_replace(l, name="_".join([col.name, *(f.lower() for f in l.field)]))
                               if l.kind == "keep" and seen[l.name] > 1 and l.field else l for l in ls])
                        for col, ls in cols]
        name = self.rel_name(r.scope.components, r.name)
        if mismatch is not None:
            self.col_mismatch[name] = mismatch
        if name == "in" and sum(l.kind == "keep" for _, ls in cols for l in ls) > len(self.lib.top["in"]):
            # a read of the parse at a key that holds more than the example is no read of `in`
            self.todo.add("parse-key", f"{r.name}: the program's parse is `in`, and this read's key holds a column "
                          "beyond the example")
            name = self.wrote("&" + r.name, Written(r.scope.components, r.name, False))
        if name == "in":
            in_cols = iter(pascal(n) for n, _ in self.lib.top["in"])
            out = []
            for col, ls in cols:
                ls = [dc_replace(l, name=next(in_cols)) if l.kind == "keep" else l for l in ls]
                kept = [l for l in ls if l.kind == "keep"]
                out.append((dc_replace(col, name=kept[0].name) if len(kept) == 1 else col, ls))
            cols = out
            if any(l.kind == "example" for _, ls in cols for l in ls):
                name = "ex_in"   # the parse at each example reads that example's input
        return name, cols, "derived", None


