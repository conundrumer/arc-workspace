"""Rewrite the constraint components of a parsed solver into picks.

A `CoverForcing`, `PlacementPruning` or `TiebreakResolutions` instance
becomes a `Pick`: an item relation, whose rows are a slot's candidates, a
picked relation named as the instance was, and the `apart` bodies. Reads of
the instance's outputs become reads of the picked relation, a read of its
generator relation outside the instance becomes a read of the item relation,
and every column of type `TiebreakResolution` is dropped.

A pick whose every apart says that one candidate stands in two slots gets
`ones`, the key columns of its `ONE` marks: the slot's columns, then the
joined columns of each such apart. A `TiebreakResolutions` pick gets no
`ones` where an apart joins on a column that is not the slot's, as its
items may stay unused, and a relation that gates its models adds aparts
(`gated_aparts`). A `TiebreakResolutions` pick of a key that no case fixes
reads an item relation of one key: its generator's clauses derive a pool of the
candidates at every key, and a relation of one key of the pool has a `ONE` mark
(`key_pick`). Where the pick is the item relation's
only reader, the item relation's clauses become the picked relation's
(`fold`). A head term `$Ctor(V..)` of type `TiebreakResolution` with no
`TiebreakResolutions` instance, or a record `[V..]` of that type, is a pick of
one row of the atoms that bind `V..`, over the case columns of the head's
relation; a head term the converter makes no pick of is listed in `unpicked`.
"""

from dataclasses import dataclass, field, fields as dc_fields, is_dataclass, replace as dc_replace
from typing import NamedTuple

from engine.program import (
    AdtType,
    Aggregate,
    Atom,
    AtomLiteral,
    Column,
    Comparison,
    ComparisonOperator,
    ConstructorTerm,
    DeclId,
    Disjunction,
    RecordTerm,
    RecordType,
    RelationDecl,
    RelationName,
    Scope,
    TypeName,
    Unit,
    UnitId,
    Variable,
    Wildcard,
)

COMPS = {"CoverForcing", "PlacementPruning", "TiebreakResolutions"}
RES = "TiebreakResolution"
CASE_TYPES = ("Choice", "OpenValue")


class Generator(NamedTuple):
    """A component's generator relation: the head positions of its (key,
    slot, item) terms, and the index in the instance's type arguments of the
    slot's and the item's types (`None`: the slot is a `Position`)."""

    relation: str
    order: tuple[int, int, int]
    types: tuple[int | None, int]


GENERATORS = {
    "CoverForcing": Generator("covers", (0, 2, 1), (None, 1)),
    "PlacementPruning": Generator("cand", (0, 2, 1), (2, 1)),
    "TiebreakResolutions": Generator("cand", (0, 1, 2), (1, 2)),
}


@dataclass
class Pick:
    name: str
    comp: str
    line: int
    item: Atom                 # over the template variables
    key: list[str]             # template key variables
    slot: list[str]
    items: list[str]
    scope: tuple[str, ...] = ()
    aparts: list[tuple] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    cvars: list[str] = field(default_factory=list)
    ones: list[list[str]] | None = None   # the ONE keys; None for a CHOOSE
    spread: dict = field(default_factory=dict)   # per column variable, the term of its item atom: a variable or a record of variables
    fold: list[str | None] | None = None  # per column of the folded relation, its cvar
    pool: Atom | None = None   # the candidates of every key, where the item atom holds those of the picked key


def tsubst(x, m: dict):
    """`x` with each variable named in `m` replaced by its term."""
    if isinstance(x, Variable):
        return m.get(x.name, x)
    if isinstance(x, tuple):
        return tuple(tsubst(y, m) for y in x)
    if is_dataclass(x) and not isinstance(x, type):
        changes = {}
        for f in dc_fields(x):
            v = getattr(x, f.name)
            if isinstance(v, (tuple, Variable)) or (is_dataclass(v) and not isinstance(v, type)):
                changes[f.name] = tsubst(v, m)
        return dc_replace(x, **changes) if changes else x
    return x


def unlined(x):
    """`x` with the line of each atom and comparison in it set to 0."""
    if isinstance(x, tuple):
        return tuple(unlined(y) for y in x)
    if is_dataclass(x) and not isinstance(x, type):
        return dc_replace(x, **{f.name: 0 if f.name == "line" else unlined(getattr(x, f.name)) for f in dc_fields(x)})
    return x


def term_vars(x, out: set[str]) -> set[str]:
    if isinstance(x, Variable):
        out.add(x.name)
    elif isinstance(x, tuple):
        for y in x:
            term_vars(y, out)
    elif is_dataclass(x) and not isinstance(x, type):
        for f in dc_fields(x):
            term_vars(getattr(x, f.name), out)
    return out


def first_vars(x) -> list[str]:
    """The distinct variables of a term, a literal or a tuple of them, in the order of their first occurrence."""
    return list(dict.fromkeys(_vars_in_order(x)))


def _vars_in_order(x) -> list[str]:
    if isinstance(x, Variable):
        return [x.name]
    if isinstance(x, tuple):
        return [v for y in x for v in _vars_in_order(y)]
    if is_dataclass(x) and not isinstance(x, type):
        return [v for f in dc_fields(x) for v in _vars_in_order(getattr(x, f.name))]
    return []


def map_lits(lits, fn):
    """Each literal through `fn`, which sees one conjunction at a time and
    returns its replacement list."""
    out = []
    for l in lits:
        if isinstance(l, Disjunction):
            l = dc_replace(l, branches=tuple(tuple(map_lits(b, fn)) for b in l.branches))
        elif isinstance(l, Comparison):
            l = dc_replace(l, lhs=_agg(l.lhs, fn), rhs=_agg(l.rhs, fn))
        out.append(l)
    return fn(out)


def _agg(t, fn):
    if isinstance(t, Aggregate):
        return dc_replace(t, body=tuple(map_lits(t.body, fn)))
    return t


def ne(a, b):
    """a and b differ: one comparison, or a disjunction over record fields."""
    if isinstance(a, RecordTerm) and isinstance(b, RecordTerm):
        pairs = []

        def walk(x, y):
            if isinstance(x, RecordTerm) and isinstance(y, RecordTerm):
                for p, q in zip(x.args, y.args):
                    walk(p, q)
            else:
                pairs.append((x, y))
        walk(a, b)
        pairs = [(x, y) for x, y in pairs if x != y]
        if not pairs:
            return Comparison(ComparisonOperator.NE, a, b, 0)
        if len(pairs) > 1:
            return Disjunction(tuple((Comparison(ComparisonOperator.NE, x, y, 0),) for x, y in pairs), 0)
        a, b = pairs[0]
    return Comparison(ComparisonOperator.NE, a, b, 0)


def fix_cmps(lits):
    """Comparisons of two records, written field by field."""
    def fn(ls):
        out = []
        for l in ls:
            if isinstance(l, Comparison) and isinstance(l.lhs, RecordTerm) and isinstance(l.rhs, RecordTerm):
                if l.op == ComparisonOperator.NE:
                    out.append(ne(l.lhs, l.rhs))
                    continue
                if l.op == ComparisonOperator.EQ:
                    out.extend(Comparison(ComparisonOperator.EQ, x, y, l.line)
                               for x, y in zip(l.lhs.args, l.rhs.args))
                    continue
            out.append(l)
        return out
    return tuple(map_lits(lits, fn))


def prune_disj(lits):
    """Drop a disjunction one of whose branches is empty: it always holds."""
    def fn(ls):
        return [l for l in ls if not (isinstance(l, Disjunction) and any(not b for b in l.branches))]
    return tuple(map_lits(lits, fn))


def ordered_vars(t) -> list[str]:
    """The distinct variables of a term, in order."""
    out: list[str] = []
    for v in ordered_vars_all(t):
        if v not in out:
            out.append(v)
    return out


def ordered_vars_all(t) -> list[str]:
    if isinstance(t, Variable):
        return [t.name]
    if isinstance(t, RecordTerm):
        return [v for a in t.args for v in ordered_vars_all(a)]
    if isinstance(t, tuple):
        return [v for a in t for v in ordered_vars_all(a)]
    return []


def canon(h) -> tuple:
    """A head's shape with its variables numbered by first appearance."""
    seen: dict[str, int] = {}

    def go(t):
        if isinstance(t, Variable):
            return seen.setdefault(t.name, len(seen))
        return tuple(go(a) for a in t.args)
    return tuple(go(t) for t in h)


def rebuild(p, names):
    """Pattern `p` with fresh variables from `names` in its variables' order."""
    m: dict[str, Variable] = {}

    def go(t):
        if isinstance(t, Variable):
            if t.name not in m:
                m[t.name] = Variable(next(names))
            return m[t.name]
        return RecordTerm(tuple(go(a) for a in t.args))
    return go(p)


def fill(m: dict, pat) -> dict:
    """`m` with every variable of `pat` it leaves unbound read as a wildcard."""
    out = dict(m)
    for v in term_vars(pat, set()):
        out.setdefault(v, Wildcard())
    return out


def is_unit_term(t) -> bool:
    return isinstance(t, ConstructorTerm) and t.name == "U"


class Rewriter:
    def __init__(self, prog) -> None:
        self.prog = prog
        self.types = {(t.scope.components, t.name): t for t in prog.types}
        self.next_decl = 1 + max((d.id.index for d in prog.declarations), default=0)
        self.next_unit = 1 + max((u.id.index for u in prog.units), default=0)
        self.picks: dict[str, Pick] = {}
        self.dropped: dict[tuple[tuple[str, ...], str], tuple[int, ...]] = {}   # each relation's dropped resolution columns, by index
        self.fresh_n = 0
        self.unpicked: dict[tuple[str, int], str] = {}   # a head term of type `TiebreakResolution` that no pick replaces, by its relation and line

    def fresh(self, base: str) -> Variable:
        self.fresh_n += 1
        return Variable(f"{base}_{self.fresh_n}")

    def spread(self, tname: str, base: str, taken: set[str], prefix: str = ""):
        """A template term for a column of `tname`: a record of plain fields
        becomes a record of field variables; anything else one variable."""
        rec = self.record(tname)
        if rec is None or not self.plain(rec):
            v = base
            if v in taken and prefix:
                v = f"{prefix}_{base.lower()}"
            while v in taken:
                v += "_"
            taken.add(v)
            return Variable(v), [v]
        args, names = [], []
        for f in rec.fields:
            t, ns = self.spread(f.type.name, f.name[:1].upper() + f.name[1:], taken, prefix or base)
            args.append(t)
            names.extend(ns)
        return RecordTerm(tuple(args)), names

    def plain(self, rec: RecordType) -> bool:
        for f in rec.fields:
            t = self.types.get(((), f.type.name))
            if isinstance(t, AdtType):
                return False
            if isinstance(t, RecordType) and not self.plain(t):
                return False
        return True

    def record(self, tname: str) -> RecordType | None:
        t = self.types.get(((), tname))
        return t if isinstance(t, RecordType) else None

    def run(self):
        prog = self.prog
        insts = [i for i in prog.instances if i.component in COMPS and i.scope.components in ((), ("Parse",))]
        units = list(prog.units)
        rels = list(prog.relations)
        if not insts:
            units, rels = self.ctor_picks(units, rels)
            if not self.picks:
                return prog, {}, {}, self.unpicked
        for inst in insts:
            sc = inst.scope.components
            mine = [u for u in units if u.head.relation.instances == (inst.name,)
                    and u.scope.components == sc]
            units = [u for u in units if u not in mine]
            new_rels, new_units, pick, reads = self.convert(inst, mine)
            rels.extend(new_rels)
            units.extend(new_units)
            self.picks[inst.name] = pick
            pick.scope = sc
            if inst.component == "TiebreakResolutions":
                units = self.defect_aparts(inst, pick, reads, units, rels)
            pick.cvars = list(reads[3])
            pick.spread = reads[4]
            if all(isinstance(t, Variable) or isinstance(t, RecordTerm) and all(isinstance(a, Variable) for a in t.args)
                   for t in reads[4].values()):
                pick.ones = self.one_keys(pick)
            if pick.ones is not None:
                units, rels = self.fold(inst, pick, units, rels)
            units = [self.rewrite_reads(u, inst, pick, reads) for u in units]
        for r in rels:
            if sum(c.type.name == RES for c in r.columns) > 1:
                for p_ in self.picks.values():
                    if p_.comp == "TiebreakResolutions":
                        p_.notes.append(f"{r.name} compares two resolutions")
        rels, units = self.drop_res(rels, units)
        types = tuple(t for t in prog.types if t.name != RES)
        prog = dc_replace(prog, relations=tuple(rels), units=tuple(units), types=types,
                          instances=tuple(i for i in prog.instances if i not in insts))
        return prog, self.picks, self.dropped, self.unpicked

    # ---- ONE

    def one_keys(self, pick: Pick) -> list[list[str]] | None:
        """The pick's ONE keys where every apart is two item atoms that
        agree on some columns and differ on the rest; else None."""
        keys = [[v for v in pick.cvars if v in pick.slot]]
        for body in pick.aparts:
            k = self.never_key(body, pick.item, pick.cvars, pick.spread)
            if k is None:
                return None
            if self.unused_key(pick, k):
                return None
            if k not in keys:
                keys.append(k)
        return keys

    @staticmethod
    def unused_key(pick: Pick, key: list[str]) -> bool:
        """Whether `key`, the joined columns of an apart, has an item's own
        column in a `TiebreakResolutions` pick. A `ONE` mark keeps a row for
        every value of its key, and a tiebreak may leave an item unused."""
        return pick.comp == "TiebreakResolutions" and any(
            not term_vars(pick.spread.get(v, Variable(v)), set()) <= set(pick.slot) for v in key)

    @staticmethod
    def never_key(body, item: Atom, cvars: list[str], spread: dict) -> list[str] | None:
        atoms = [l for l in body if isinstance(l, AtomLiteral)]
        rest = [l for l in body if not isinstance(l, AtomLiteral)]
        if len(atoms) != 2 or any(a.negated or a.atom.relation != item.relation
                                  or len(a.atom.args) != len(item.args) for a in atoms):
            return None
        joined: set[str] = set()
        differ: set[frozenset] = set()
        def align(p, x, y) -> bool:
            """Whether the item's term `p` read at `x` and at `y` is joined or differs variable by variable."""
            if isinstance(p, RecordTerm):
                return (isinstance(x, RecordTerm) and isinstance(y, RecordTerm) and len(p.args) == len(x.args) == len(y.args)
                        and all(align(*q) for q in zip(p.args, x.args, y.args)))
            if not isinstance(p, Variable):
                return True
            if not (isinstance(x, Variable) and isinstance(y, Variable)):
                return False
            if x == y:
                joined.add(p.name)
            else:
                differ.add(frozenset((x.name, y.name)))
            return True
        for p, x, y in zip(item.args, atoms[0].atom.args, atoms[1].atom.args):
            if not align(p, x, y):
                return None

        def pair(c):
            if isinstance(c, Comparison) and c.op == ComparisonOperator.NE and \
                    isinstance(c.lhs, Variable) and isinstance(c.rhs, Variable):
                return frozenset((c.lhs.name, c.rhs.name))
            return None
        groups = []
        for l in rest:
            if pair(l) is not None:
                groups.append({pair(l)})
            elif isinstance(l, Disjunction) and all(len(b) == 1 and pair(b[0]) is not None for b in l.branches):
                groups.append({pair(b[0]) for b in l.branches})
            else:
                return None
        if len(groups) != 1 or groups[0] != differ:
            return None
        return [v for v in cvars if (vs := term_vars(spread.get(v, Variable(v)), set())) and vs <= joined]

    def fold(self, inst, pick: Pick, units, rels):
        """The item relation's clauses as the picked relation's, where the
        pick is the item relation's only reader."""
        sc = inst.scope.components
        rn = pick.item.relation
        r = next((x for x in rels if x.name == rn.name and x.scope.components == sc), None)
        mine = [u for u in units if u.head.relation == rn and u.scope.components == sc]
        if rn.instances or r is None or not mine or any(u.body is None for u in mine):
            return units, rels
        # `rewrite_reads` runs after this, and turns a read of the generator into a read of the item relation
        gen = GENERATORS[pick.comp].relation
        read = {rn, RelationName(("parse",), rn.name),
                RelationName((inst.name,), gen), RelationName(("parse", inst.name), gen)}
        if any(read & reads_of(u.body) for u in units if u not in mine and u.body):
            return units, rels
        pick.fold = [a.name if isinstance(a, Variable) else
                     next((v for v, s in pick.spread.items() if s == a), None) for a in pick.item.args]
        rels = [dc_replace(r, name=inst.name) if x is r else x for x in rels
                if not (x.name == inst.name and x.scope.components == sc)]
        units = [dc_replace(u, head=dc_replace(u.head, relation=RelationName((), inst.name)))
                 if u in mine else u for u in units]
        return units, rels

    def ctor_picks(self, units, rels):
        """A head term of type `TiebreakResolution` that holds variables,
        `$Ctor(V..)` or a record `[V..]`: the atoms of the clause's body that
        bind V.. become a picked relation of one row. The pick has the case
        columns of the head's relation (the columns of type `Choice` and
        `OpenValue`) before V.., and a clause with the same term shares it."""
        adt = self.types.get(((), RES))
        if isinstance(adt, RecordType):
            units, rels = self.record_picks(units, rels, adt)
        elif not isinstance(adt, AdtType):
            return units, rels
        ctors = {c.name: c for c in adt.constructors} if isinstance(adt, AdtType) else {}
        decls = {r.name: r for r in rels if r.scope.components == () and r.name not in self.picks}
        out = []
        made: dict[tuple[str, str], tuple[str, list[Column]]] = {}   # (relation, constructor) -> the pick's relation and columns
        items: dict[tuple[str, str], str] = {}   # the pick's item relation
        seen: set[tuple] = set()
        for u in units:
            r = decls.get(u.head.relation.name) if not u.head.relation.instances and not u.scope.components else None
            ii = [i for i, c in enumerate(r.columns) if c.type.name == RES] if r is not None else []
            t = u.head.args[ii[0]] if len(ii) == 1 and u.body else None
            if isinstance(adt, AdtType):
                shape = (t.name, list(zip(t.args, ctors[t.name].fields))) \
                    if isinstance(t, ConstructorTerm) and t.name in ctors and t.args else None
            else:
                shape = ("", list(zip(t.args, adt.fields))) \
                    if isinstance(t, RecordTerm) and len(t.args) == len(adt.fields) else None
            if shape is None:
                out.append(u)
                continue
            assert r is not None and u.body is not None
            ctor, fields = shape
            vs = [a.name for a, _ in fields if isinstance(a, Variable)]
            case_cols = [i for i, c in enumerate(r.columns) if c.type.name in CASE_TYPES]
            case_terms = tuple(u.head.args[i] for i in case_cols)
            sel = self.pick_body(u.body, vs, case_terms) if len(vs) == len(fields) == len(set(vs)) else None
            if sel is None:
                self.unpicked[(u.head.relation.name, u.span.first if u.span else 0)] = \
                    f"a {'`$' + ctor + '`' if ctor else 'record'} resolution of `{u.head.relation.name}` has no pick"
                out.append(u)
                continue
            body, moved = sel
            key = (u.head.relation.name, ctor)
            if key not in made:
                name = ctor[:1].lower() + ctor[1:] if ctor else "resolution"
                taken = {x.name for x in rels}
                while name in taken:
                    name += "2"
                names = [c.name for c in (r.columns[i] for i in case_cols)]
                cols = [r.columns[i] for i in case_cols]
                for v, (_, f) in zip(vs, fields):
                    while v in names:
                        v += "_"
                    names.append(v)
                    cols.append(Column(v, f.type))
                rels.append(self.decl(name, cols))
                made[key] = (name, cols)
                atom = Atom(RelationName((), name), case_terms + tuple(Variable(v) for v in vs), 0)
                self.picks[name] = Pick(name, "Resolution", u.span.first if u.span else 0, atom, [], [], vs,
                                        cvars=vs, ones=[[]], fold=[None] * len(case_cols) + vs)
            name, cols = made[key]
            head = Atom(RelationName((), name), case_terms + tuple(Variable(v) for v in vs), 0)
            if term_vars(tuple(body), set()) <= set(vs) | term_vars(case_terms, set()):
                pbody = tuple(body)
            else:
                # the atoms hold other variables, which would be columns of a relation with a `ONE` mark: the pick reads their projection
                item = name + "_item"
                if key not in items:
                    while item in {x.name for x in rels}:
                        item += "2"
                    rels.append(self.decl(item, cols))
                    items[key] = item
                ihead = dc_replace(head, relation=RelationName((), items[key]))
                if unlined((ihead, tuple(body))) not in seen:
                    seen.add(unlined((ihead, tuple(body))))
                    self.next_unit += 1
                    out.append(dc_replace(u, id=UnitId(self.next_unit), head=ihead, body=tuple(body)))
                pbody = (AtomLiteral(ihead, False),)
            if unlined((head, pbody)) not in seen:
                seen.add(unlined((head, pbody)))
                self.next_unit += 1
                out.append(dc_replace(u, id=UnitId(self.next_unit), head=head, body=pbody))
            rest, placed = [], False
            for l in u.body:
                if not placed and l in body:
                    rest.append(AtomLiteral(head, False))
                    placed = True
                if l not in moved:
                    rest.append(l)
            hargs = tuple(Variable("Res__") if i == ii[0] else a for i, a in enumerate(u.head.args))
            out.append(dc_replace(u, head=dc_replace(u.head, args=hargs), body=tuple(rest)))
        return out, rels

    @staticmethod
    def pick_body(body, vs: list[str], case_terms) -> tuple[list, list] | None:
        """The literals of a clause's `body` that state the values of `vs`,
        and those of them that its pick replaces, or None where no atoms bind
        `vs`. Where the positive atoms whose variables are `vs` or in the
        head's case terms bind all of `vs`, they and the negations and
        comparisons over those variables are the literals. Otherwise they
        are the atoms that hold a variable of `vs`, each atom that shares
        another variable with them, and the negations and comparisons over
        their variables. An atom of `impl_choice` joins them where it binds a
        case variable that they leave unbound. The replaced literals are
        those that hold no variable outside `vs` and the case terms."""
        V = set(vs)
        K = V | term_vars(case_terms, set())
        lits = list(body)
        pos = [l for l in lits if isinstance(l, AtomLiteral) and not l.negated]

        def vars_(l) -> set[str]:
            return term_vars(l, set())

        def bound(ls) -> set[str]:
            return set().union(set(), *(term_vars(l.atom.args, set()) for l in ls))
        sel = [l for l in pos if vars_(l) <= K and vars_(l) & V]
        if not V <= bound(sel):
            sel = [l for l in pos if vars_(l) & V]
            if not V <= bound(sel):
                return None
            while True:
                free = bound(sel) - K
                more = [l for l in pos if l not in sel and (vars_(l) - K) & free]
                if not more:
                    break
                sel += more
        W = K | bound(sel)
        sel += [l for l in lits if l not in sel and (isinstance(l, Comparison) or isinstance(l, AtomLiteral) and l.negated)
                and vars_(l) <= W]
        missing = K - bound(sel)
        for l in sorted((l for l in pos if l not in sel and vars_(l) <= K), key=lambda l: l.atom.relation.name != "impl_choice"):
            if missing & vars_(l):
                sel.append(l)
                missing -= vars_(l)
        if missing:
            return None
        sel = [l for l in lits if l in sel]
        moved = [l for l in sel if vars_(l) <= K and not (isinstance(l, AtomLiteral) and l.atom.relation.name == "impl_choice")]
        return sel, moved

    def record_picks(self, units, rels, rec: RecordType):
        """A relation whose one column has the record type `TiebreakResolution`,
        and whose every clause heads it with a record of distinct variables:
        each row of the relation is one resolution. The column becomes the
        record's fields, a read of the relation takes them from the record
        that its column is compared with, and the relation is a pick with one
        `ONE` mark, so a model keeps one of its rows."""
        n = len(rec.fields)
        found: dict[str, list[Unit]] = {}
        for r in rels:
            if r.scope.components or len(r.columns) != 1 or r.columns[0].type.name != RES:
                continue
            us = [u for u in units if u.head.relation.name == r.name and not u.head.relation.instances
                  and not u.scope.components]
            if us and all(u.body and isinstance(u.head.args[0], RecordTerm) and len(u.head.args[0].args) == n
                          and all(isinstance(a, Variable) for a in u.head.args[0].args)
                          and len({a.name for a in u.head.args[0].args if isinstance(a, Variable)}) == n
                          for u in us):
                found[r.name] = us
        if not found:
            return units, rels

        def read(conj):
            out = list(conj)
            for k, l in enumerate(out):
                if not (isinstance(l, AtomLiteral) and not l.negated and l.atom.relation.name in found
                        and not l.atom.relation.instances):
                    continue
                t = l.atom.args[0]
                parts = None
                if isinstance(t, RecordTerm) and len(t.args) == n:
                    parts = t.args
                elif isinstance(t, Variable):
                    for m, c in enumerate(out):
                        if isinstance(c, Comparison) and c.op == ComparisonOperator.EQ:
                            for a, b in ((c.lhs, c.rhs), (c.rhs, c.lhs)):
                                if a == t and isinstance(b, RecordTerm) and len(b.args) == n and parts is None:
                                    parts = b.args
                                    out[m] = None
                if parts is None:
                    parts = tuple(Wildcard() for _ in range(n))
                out[k] = dc_replace(l, atom=dc_replace(l.atom, args=tuple(parts)))
            return [l for l in out if l is not None]

        new_units = []
        for u in units:
            if u.head.relation.name in found and u in found[u.head.relation.name]:
                u = dc_replace(u, head=dc_replace(u.head, args=u.head.args[0].args))
            if u.body is not None:
                u = dc_replace(u, body=tuple(map_lits(u.body, read)))
            new_units.append(u)
        new_rels = []
        for r in rels:
            if r.name in found:
                r = dc_replace(r, columns=tuple(Column(f.name, f.type) for f in rec.fields))
                us = found[r.name]
                vs = [f.name for f in rec.fields]
                head = Atom(RelationName((), r.name), tuple(Variable(v) for v in vs), 0)
                self.picks[r.name] = Pick(r.name, "Resolution", us[0].span.first if us[0].span else 0, head, [], [], vs,
                                          cvars=vs, ones=[[]], fold=vs)
            new_rels.append(r)
        return new_units, new_rels

    # ---- one instance

    def var_types(self, t, tname: str, out: dict[str, str]) -> bool:
        """The type of each variable of a pattern term of type `tname`."""
        if isinstance(t, Variable):
            out[t.name] = tname
            return True
        rec = self.record(tname)
        if isinstance(t, RecordTerm) and rec is not None and len(rec.fields) == len(t.args):
            return all(self.var_types(a, f.type.name, out) for a, f in zip(t.args, rec.fields))
        return False

    def convert(self, inst, mine: list[Unit]):
        comp = inst.component
        targs = [a.name for a in inst.type_args]
        ktype = targs[0]
        gen_rel, order, type_args = GENERATORS[comp]
        types_ = (ktype, *("Position" if i is None else targs[i] for i in type_args))
        conf_rel = None if comp == "TiebreakResolutions" else "conflict"
        gens = [u for u in mine if u.head.relation.name == gen_rel and u.body is not None]
        confs = [u for u in mine if u.head.relation.name == conf_rel and u.body is not None]
        notes = [f"input {u.head.relation.name}" for u in mine if u not in gens and u not in confs]
        keyed = ktype != "Unit"
        sc = inst.scope.components

        def parts(u):   # (key, slot, item) terms of a generator head
            return tuple(u.head.args[i] for i in order)

        # the pattern: the generator heads as records of variables, one shape
        pat = None
        if gens:
            def tree(t):
                return isinstance(t, Variable) or isinstance(t, RecordTerm) and all(tree(a) for a in t.args)
            heads = [parts(u)[0 if keyed else 1:] for u in gens]
            if all(all(tree(t) for t in h) for h in heads) and len({canon(h) for h in heads}) == 1:
                pat = heads[0]
        generic = pat is None
        if generic:
            pat = tuple(Variable(n) for n in (["Key"] if keyed else []) + ["S", "X"])
        vtypes: dict[str, str] = {}
        for t, ty in zip(pat, types_[0 if keyed else 1:]):
            if not self.var_types(t, ty, vtypes):
                generic = True
        key_p = pat[0] if keyed else None
        slot_p, item_p = pat[-2], pat[-1]
        cvars = []
        for t in pat:
            for v in ordered_vars(t):
                if v not in cvars:
                    cvars.append(v)
        cols = [Column(v, TypeName((), vtypes.get(v, "number"))) for v in cvars]

        # the item relation: one existing atom, or a relation of its own
        item_atom = pool_atom = None
        new_rels, new_units = [], []
        # a keyed pick of a key that no case fixes also picks one key
        one_key = comp == "TiebreakResolutions" and keyed and not self.case_only(ktype) and bool(gens)
        if not one_key and len(gens) == 1 and not generic and len(gens[0].body) == 1 and \
                isinstance(gens[0].body[0], AtomLiteral) and not gens[0].body[0].negated:
            a = gens[0].body[0].atom
            avs = [x.name for x in a.args if isinstance(x, Variable)]
            if all(isinstance(x, (Variable, Wildcard)) for x in a.args) and \
                    sorted(avs) == sorted(cvars):
                item_atom = a
        if item_atom is None:
            iname = inst.name + "_item"
            new_rels.append(self.decl(iname, cols, sc))
            pool = inst.name + "_pool" if one_key else iname
            if one_key:
                new_rels.append(self.decl(pool, cols, sc))
            for u in gens:
                if generic:
                    args = parts(u)[0 if keyed else 1:]
                else:
                    # the head's distinct variables, in the order the pattern's are
                    m = dict(zip(cvars, [Variable(v) for v in ordered_vars(parts(u)[0 if keyed else 1:])]))
                    args = tuple(m[v] for v in cvars)
                new_units.append(dc_replace(u, head=dc_replace(u.head, relation=RelationName((), pool),
                                                                 args=tuple(args))))
            item_atom = Atom(RelationName((), iname), tuple(Variable(v) for v in cvars), 0)
            if one_key:
                pool_atom = Atom(RelationName((), pool), item_atom.args, 0)
                self.key_pick(inst, gens[0], pool_atom, item_atom, ordered_vars(key_p), cvars, cols, new_rels, new_units)
        new_rels.append(self.decl(inst.name, cols, sc))

        # field variables for the record columns
        taken = set(cvars)
        spread = {}
        for v in cvars:
            taken.discard(v)
            spread[v] = self.spread(vtypes.get(v, "number"), v, taken)[0]
        sp = lambda t: tsubst(t, spread)  # noqa: E731
        key_s, slot_s, item_s = (sp(key_p) if keyed else None), sp(slot_p), sp(item_p)
        slot_vars = term_vars((key_s, slot_s), set())
        item_vars = term_vars(item_s, set())
        pick = Pick(inst.name, comp, inst.span.first if inst.span else 0, sp(item_atom),
                    sorted(term_vars(key_s, set())), sorted(slot_vars), sorted(item_vars - slot_vars),
                    notes=notes)
        pick.pool = sp(pool_atom) if pool_atom is not None else None
        pat_s = (key_s, slot_s, item_s)

        def at(m):
            """The item atom at a binding of the pattern's variables."""
            return AtomLiteral(tsubst(sp(item_atom), m), False)

        def two(t, which: set[str]):
            return tsubst(t, {v: Variable(v + "2") for v in term_vars(t, set()) & which})

        # apart: the conflicts
        for u in confs:
            k, a, b = u.head.args
            vs = term_vars((u.head.args, u.body), set())
            m1, m2, s = self.unify_apart([(key_s, k), (item_s, a)] if keyed else [(item_s, a)],
                                         [(key_s, k), (item_s, b)] if keyed else [(item_s, b)], vs)
            body = fix_cmps(tsubst(tuple(u.body), s))
            first = [at(fill(m1, pat_s)), at(fill(m2, pat_s))]
            rest = list(body)
            for j, t in enumerate(first):
                for l in rest:
                    if isinstance(l, AtomLiteral) and not l.negated and l.atom.relation == t.atom.relation \
                            and len(l.atom.args) == len(t.atom.args) and all(
                                x == y or isinstance(x, Wildcard) for x, y in zip(t.atom.args, l.atom.args)):
                        first[j] = l
                        rest.remove(l)
                        break
            pick.aparts.append(tuple(first + rest))
        # apart: one piece at every cell it covers; one slot per item
        only_slot = term_vars(slot_s, set()) - item_vars
        ident = {v: Variable(v) for v in term_vars(pat_s, set())}
        if comp == "CoverForcing" and only_slot:
            if only_slot != term_vars(slot_s, set()):
                pick.notes.append("a piece shares part of its cell")
            S2 = two(slot_s, only_slot)
            X2 = two(item_s, item_vars)
            m_s2x = {**ident, **{v: Variable(v + "2") for v in only_slot}}
            m_s2x2 = {**m_s2x, **{v: Variable(v + "2") for v in item_vars}}
            # the first read leaves out the slot-only variables: the third read tests the piece at a cell
            m_x = {**ident, **{v: Wildcard() for v in only_slot}}
            pick.aparts.append((at(m_x), at(m_s2x2), at(m_s2x), ne(item_s, X2)))
        # an item whose term holds its slot's stands in one slot, also under a generic pattern
        item_holds_slot = len(gens) == 1 and term_vars(parts(gens[0])[1], set()) <= term_vars(parts(gens[0])[2], set())
        if comp == "TiebreakResolutions" and only_slot and not item_holds_slot:
            m2 = {**ident, **{v: Variable(v + "2") for v in only_slot}}
            pick.aparts.append((at(ident), at(m2), ne(slot_s, two(slot_s, only_slot))))
        def item_at(ka, kb, taken: set[str]):
            """The item atoms of two assignments (key, slot, item), and the split."""
            def pairs(k, sl, x):
                return ([(key_s, k)] if keyed else []) + [(slot_s, sl), (item_s, x)]
            m1, m2, s_ = self.unify_apart(pairs(*ka), pairs(*kb), taken)
            return at(fill(m1, pat_s)), at(fill(m2, pat_s)), s_
        reads = (comp, keyed, pat_s, cvars, spread, item_at)
        return new_rels, new_units, pick, reads

    def case_only(self, tname: str) -> bool:
        """Whether a value of type `tname` is fixed by a case: `Choice`, a
        type of a field of it that has constructors, or a record of such."""
        choice = self.types.get(((), "Choice"))
        cases = {"Choice"}
        todo = [f.type.name for f in choice.fields] if isinstance(choice, RecordType) else []
        if isinstance(choice, AdtType):
            todo += [f.type.name for k in choice.constructors for f in k.fields]
        while todo:
            t = todo.pop()
            decl = self.types.get(((), t))
            if t not in cases and isinstance(decl, AdtType):
                cases.add(t)
                todo += [f.type.name for k in decl.constructors for f in k.fields]
        rec = self.record(tname)
        return tname in cases or rec is not None and all(self.case_only(f.type.name) for f in rec.fields)

    def key_pick(self, inst, gen: Unit, pool: Atom, item: Atom, kvars: list[str], cvars: list[str],
                 cols: list[Column], new_rels: list, new_units: list) -> None:
        """A relation of one key of the candidates in `pool`, with a `ONE`
        mark, and the item relation `item` as the candidates at that key. The
        resolutions of each key are the models of the pick at that key, so a
        model reads the candidates of one key and one grid shows one key."""
        sc = inst.scope.components
        kname = inst.name + "_key"
        kcols = [cols[cvars.index(v)] for v in kvars]
        new_rels.append(self.decl(kname, kcols, sc))
        pooled = AtomLiteral(pool, False)
        keys = AtomLiteral(dc_replace(pool, args=tuple(Variable(v) if v in kvars else Wildcard() for v in cvars)), False)
        katom = Atom(RelationName((), kname), tuple(Variable(v) for v in kvars), 0)
        for head, body in ((katom, (keys,)), (item, (pooled, AtomLiteral(katom, False)))):
            self.next_unit += 1
            new_units.append(dc_replace(gen, id=UnitId(self.next_unit), head=head, body=body))
        self.picks[kname] = Pick(kname, "Resolution", inst.span.first if inst.span else 0, katom, [], [], kvars,
                                 scope=sc, cvars=kvars, ones=[[]], fold=kvars)

    def defect_aparts(self, inst, pick: Pick, reads, units, rels):
        """A relation over one resolution that two assignments of it derive,
        read only to drop the resolutions it holds: its bodies are aparts."""
        item_at = reads[-1]
        sc = inst.scope.components
        path = (inst.name,)
        for r in rels:
            idx = [i for i, c in enumerate(r.columns) if c.type.name == RES]
            if len(idx) != 1 or r.scope.components != sc:
                continue
            ri = idx[0]
            mine = [u for u in units if u.head.relation.name == r.name and not u.head.relation.instances
                    and u.scope.components == sc]
            if not mine or any(u.body is None for u in mine):
                continue
            reads_ = []

            def scan(lits):
                for l in lits:
                    if isinstance(l, AtomLiteral) and l.atom.relation == RelationName((), r.name):
                        reads_.append(l)
                    elif isinstance(l, Disjunction):
                        for b in l.branches:
                            scan(b)
            for u in units:
                if u not in mine and u.body:
                    scan(u.body)
            if not reads_ or any(not l.negated for l in reads_):
                continue
            bodies = []
            for u in mine:
                R = u.head.args[ri]
                if not isinstance(R, Variable):
                    break
                assigns = [l for l in u.body if isinstance(l, AtomLiteral) and not l.negated
                           and l.atom.relation == RelationName(path, "assign")
                           and l.atom.args[1] == R]
                rest = [l for l in u.body if l not in assigns]
                if len(assigns) != 2 or R.name in term_vars(tuple(rest), set()):
                    break
                taken = term_vars(u.body, set())
                a1, a2, s = item_at(*[(a.atom.args[0], a.atom.args[2], a.atom.args[3]) for a in assigns], taken)
                bodies.append(fix_cmps(tsubst(tuple([a1, a2] + rest), s)))
            else:
                pick.aparts.extend(bodies)
                units = [u for u in units if u not in mine]

                def fn(lits, name=r.name):
                    return [l for l in lits if not (isinstance(l, AtomLiteral) and l.negated
                                                    and l.atom.relation == RelationName((), name))]
                units = [dc_replace(u, body=tuple(map_lits(u.body, fn))) if u.body else u for u in units]
        self.gated_aparts(inst, pick, reads, units, rels)
        return units

    def gated_aparts(self, inst, pick: Pick, reads, units, rels) -> None:
        """The aparts of the clauses of a relation `r` over one resolution
        that gates the models: every read of `r` is `NOT r(K, Res)` in a
        clause `c(K, Res) :- resolution(K, Res), NOT r(K, Res)`. A clause of
        `r` that two chosen candidates make true, once the relations over the
        resolution that have one clause are inlined, is an apart. Its two
        candidates are two `assign` reads, or an `assign` read and a negated
        `assign` read, for which the second candidate is any other item at
        that slot. `r` keeps the clause, which also holds where a slot has no
        candidate."""
        item_at = reads[-1]
        sc = inst.scope.components
        path = (inst.name,)
        assign, resolution = RelationName(path, "assign"), RelationName(path, "resolution")

        def mine(r):
            return [u for u in units if u.head.relation.name == r.name and not u.head.relation.instances
                    and u.scope.components == sc]

        def res_col(r):
            idx = [i for i, c in enumerate(r.columns) if c.type.name == RES]
            return idx[0] if len(idx) == 1 and r.scope.components == sc else None

        def inline(lits, R):
            """`lits`, each read of a relation over `R` with one clause replaced by that clause's body."""
            for _ in range(3):
                out, changed = [], False
                for l in lits:
                    q = next((x for x in rels if isinstance(l, AtomLiteral) and not l.negated
                              and x.name == l.atom.relation.name and not l.atom.relation.instances
                              and res_col(x) is not None), None)
                    qs = mine(q) if q is not None else []
                    if len(qs) != 1 or qs[0].body is None or l.atom.args[res_col(q)] != R \
                            or not all(isinstance(a, Variable) for a in qs[0].head.args) \
                            or len({a.name for a in qs[0].head.args}) != len(qs[0].head.args):
                        out.append(l)
                        continue
                    u = qs[0]
                    m = dict(zip((a.name for a in u.head.args), l.atom.args))
                    for v in first_vars(u.body):
                        if v not in m:
                            m[v] = self.fresh(v)
                    out.extend(tsubst(tuple(u.body), m))
                    changed = True
                lits = out
                if not changed:
                    break
            return lits

        for r in rels:
            ri = res_col(r)
            clauses = mine(r)
            if ri is None or not clauses or any(u.body is None for u in clauses):
                continue
            readers = [u for u in units if u not in clauses and u.body and RelationName((), r.name) in reads_of(u.body)]
            if not readers:
                continue
            for u in readers:
                gate = [l for l in u.body if isinstance(l, AtomLiteral) and l.atom.relation in (resolution, RelationName((), r.name))]
                if len(u.body) != 2 or len(gate) != 2 or {l.negated for l in gate} != {False, True} \
                        or gate[0].atom.args != gate[1].atom.args:
                    break
            else:
                for u in clauses:
                    R = u.head.args[ri]
                    if not isinstance(R, Variable):
                        continue
                    lits = inline(list(u.body), R)
                    on = [l for l in lits if isinstance(l, AtomLiteral) and l.atom.relation == assign and l.atom.args[1] == R]
                    pos, neg = [l for l in on if not l.negated], [l for l in on if l.negated]
                    rest = [l for l in lits if l not in on and not (
                        isinstance(l, AtomLiteral) and not l.negated and l.atom.relation == resolution and l.atom.args[1] == R)]
                    if R.name in term_vars(tuple(rest), set()):
                        continue
                    taken = term_vars(tuple(lits), set())
                    if len(pos) == 2 and not neg:
                        a1, a2, s = item_at(*[(a.atom.args[0], a.atom.args[2], a.atom.args[3]) for a in pos], taken)
                        pick.aparts.append(fix_cmps(tsubst(tuple([a1, a2] + rest), s)))
                    elif len(pos) == 1 and len(neg) == 1 and pos[0].atom.args[0] == neg[0].atom.args[0] \
                            and not isinstance(neg[0].atom.args[3], Wildcard):
                        p_, n_ = pos[0].atom, neg[0].atom
                        X = self.fresh("X")
                        taken.add(X.name)
                        a1, a2, s = item_at((p_.args[0], p_.args[2], p_.args[3]), (n_.args[0], n_.args[2], X), taken)
                        other = Comparison(ComparisonOperator.NE, X, n_.args[3], 0)
                        pick.aparts.append(fix_cmps(tsubst(tuple([a1, a2] + rest + [other]), s)))

    def unify_apart(self, pairs_a, pairs_b, taken: set[str]):
        """The bindings of the two sides of an apart, and one substitution for
        both. A variable that both sides read is split once, at the first
        side, and the second side reads its parts; each side's own variables
        get the side's suffix."""
        m1, s1, _ = self.unify(pairs_a, taken, "")
        m2, s2, _ = self.unify([(p, tsubst(t, s1)) for p, t in pairs_b], taken, "2")
        return m1, m2, {**s1, **s2}

    def unify(self, pairs, taken: set[str], suffix: str):
        """The binding of pattern variables by actual terms, the
        substitution that splits an actual variable spanning a record, and
        the pairs of actual terms that a repeated pattern variable meets and
        that must be equal. Of two such terms, a variable that a split
        introduced is replaced by the other one."""
        m: dict = {}
        s: dict = {}
        eqs: list = []
        made: set[str] = set()

        def merge(a, b):
            """Make the terms a (bound earlier) and b equal."""
            if isinstance(b, Variable) and b.name in made:
                old, new = b, a
            elif isinstance(a, Variable) and a.name in made:
                old, new = a, b
            else:
                eqs.append((a, b))
                return
            r = {old.name: new}
            for d in (m, s):
                for k in d:
                    d[k] = tsubst(d[k], r)
            eqs[:] = [tsubst(e, r) for e in eqs]
            made.discard(old.name)

        def go(p, t):
            if isinstance(p, Variable):
                if p.name in m and m[p.name] != t and not isinstance(t, Wildcard):
                    if isinstance(m[p.name], Wildcard):
                        m[p.name] = t
                    else:
                        merge(m[p.name], t)
                    return
                m.setdefault(p.name, t)
                return
            if isinstance(t, Wildcard):
                for v in ordered_vars(p):
                    m.setdefault(v, Wildcard())
                return
            if isinstance(t, Variable):
                names = [v + suffix for v in ordered_vars(p)]
                if set(names) & taken:
                    names = [f"{t.name}_{v.lower()}" for v in ordered_vars(p)]
                taken.update(names)
                made.update(names)
                rec = rebuild(p, iter(names))
                s[t.name] = rec
                go(p, rec)
                return
            if isinstance(t, RecordTerm) and len(t.args) == len(p.args):
                for a, b in zip(p.args, t.args):
                    go(a, b)
                return
            for v in ordered_vars(p):
                m.setdefault(v, Wildcard())
        for p, t in pairs:
            go(p, t)
        return m, s, eqs

    def decl(self, name: str, cols, scope=()) -> RelationDecl:
        self.next_decl += 1
        return RelationDecl(DeclId(self.next_decl), name, Scope(scope), tuple(cols), (), (), None)

    # ---- reads of the instance's outputs

    def rewrite_reads(self, u: Unit, inst, pick: Pick, reads) -> Unit:
        comp, keyed, pat_s, cvars, spread, _ = reads
        key_s, slot_s, item_s = pat_s
        name = inst.name
        if u.body is None:
            return u
        if u.scope.components == inst.scope.components:
            path, out_path = (name,), ()
        elif inst.scope.components == ("Parse",) and not u.scope.components:
            path, out_path = ("parse", name), ("parse",)
        else:
            return u
        subst: dict = {}
        equal: list = []   # the equalities the read being converted needs
        taken = term_vars((u.head, u.body), set())

        def bind(k, s, x):
            """The binding of the pattern's variables at a read's key, slot and item."""
            pairs = ([(key_s, k)] if keyed else []) + ([(slot_s, s)] if s is not None else []) + [(item_s, x)]
            m, s_, eqs = self.unify(pairs, taken, "")
            subst.update(s_)
            equal.extend(Comparison(ComparisonOperator.EQ, x, y, 0) for x, y in eqs)
            return m

        def generated(k, s, x):
            return AtomLiteral(tsubst(pick.pool or pick.item, fill(bind(k, s, x), pat_s)), False)

        def picked(k, s, x):
            m = bind(k, s, x)
            val = {v: fill(m, pat_s).get(v, Wildcard()) if not isinstance(spread[v], RecordTerm)
                   else tsubst(spread[v], fill(m, pat_s)) for v in cvars}
            args = tuple(val[v] if v else Wildcard() for v in (pick.fold or cvars))
            return AtomLiteral(Atom(RelationName(out_path, name), args, 0), False)

        def fn(lits):
            out = []
            pos = {(l.atom.relation.name, l.atom.args) for l in lits if isinstance(l, AtomLiteral)
                   and not l.negated and l.atom.relation.instances == path}
            for l in lits:
                if not (isinstance(l, AtomLiteral) and l.atom.relation.instances == path):
                    out.append(l)
                    continue
                equal.clear()
                a, rn = l.atom.args, l.atom.relation.name
                if comp == "CoverForcing" and rn == "forced":
                    out.append(dc_replace(picked(a[0], None, a[1]), negated=l.negated))
                elif rn in ("ruled_out", "dead") and l.negated and \
                        any(p_[0] in ("forced", "alive") and p_[1][:2] == a[:2] for p_ in pos):
                    continue
                elif comp == "PlacementPruning" and rn == "alive":
                    out.append(dc_replace(picked(a[0], a[2], a[1]), negated=l.negated))
                elif comp == "TiebreakResolutions" and rn == "assign":
                    out.append(dc_replace(picked(a[0], a[2], a[3]), negated=l.negated))
                elif comp == "TiebreakResolutions" and rn == "resolution" and not l.negated:
                    # a positive `assign` at the same key reads the pick there, so it
                    # already says the key has a model; any other literal that binds
                    # the key does not
                    if any(o is not l and isinstance(o, AtomLiteral) and not o.negated
                           and o.atom.relation.instances == path and o.atom.relation.name == "assign"
                           and o.atom.args[0] == a[0] for o in lits):
                        continue
                    out.append(picked(a[0], Wildcard(), Wildcard()))
                elif comp == "TiebreakResolutions" and rn == "resolution" and isinstance(a[1], Wildcard):
                    # no resolution at the key: the key has no model
                    out.append(dc_replace(picked(a[0], Wildcard(), Wildcard()), negated=True))
                elif rn == GENERATORS[comp].relation:
                    k, s, x = (a[i] for i in GENERATORS[comp].order)
                    out.append(dc_replace(generated(k, s, x), negated=l.negated))
                else:
                    pick.notes.append(f"read {rn}")
                    out.append(l)
                if not l.negated:
                    out.extend(equal)
            return out

        body = prune_disj(tuple(map_lits(u.body, fn)))
        u = dc_replace(u, body=body)
        if subst:
            u = tsubst(u, subst)
            u = dc_replace(u, body=fix_cmps(u.body))
        return u

    # ---- the resolution columns

    def drop_res(self, rels, units):
        drop: dict[str, list[int]] = {}
        out_rels = []
        for r in rels:
            idx = [i for i, c in enumerate(r.columns) if c.type.name == RES]
            if idx:
                drop[r.name] = idx
                self.dropped[(r.scope.components, r.name)] = tuple(idx)
                r = dc_replace(r, columns=tuple(c for i, c in enumerate(r.columns) if i not in idx))
            out_rels.append(r)
        if not drop:
            return out_rels, units
        res_vars: set[str] = set()

        def strip(atom: Atom) -> Atom:
            idx = drop.get(atom.relation.name) if not atom.relation.instances else None
            if not idx:
                return atom
            for i in idx:
                term_vars(atom.args[i], res_vars)
            return dc_replace(atom, args=tuple(a for i, a in enumerate(atom.args) if i not in idx))

        def fn(lits):
            return [dc_replace(l, atom=strip(l.atom)) if isinstance(l, AtomLiteral) else l for l in lits]

        stripped = []
        for u in units:
            u = dc_replace(u, head=strip(u.head))
            if u.body is not None:
                u = dc_replace(u, body=tuple(map_lits(u.body, fn)))
            stripped.append(u)

        def fn2(lits):
            return [l for l in lits if not (isinstance(l, Comparison) and
                                            term_vars((l.lhs, l.rhs), set()) & res_vars)]
        return out_rels, [dc_replace(u, body=tuple(map_lits(u.body, fn2))) if u.body is not None else u
                          for u in stripped]


def reads_of(lits) -> set[RelationName]:
    """The relations an atom anywhere in `lits` reads."""
    out: set[RelationName] = set()

    def go(x):
        if isinstance(x, Atom):
            out.add(x.relation)
        if isinstance(x, tuple):
            for y in x:
                go(y)
        elif is_dataclass(x) and not isinstance(x, type):
            for f in dc_fields(x):
                go(getattr(x, f.name))
    go(tuple(lits))
    return out


def rewrite(prog):
    """The program with its constraint components rewritten, its picks by
    name, the index of each `TiebreakResolution` column dropped from a
    relation, by the relation's scope and name, and the head terms of that
    type that no pick replaces, by their relation and line."""
    return Rewriter(prog).run()
