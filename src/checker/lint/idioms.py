"""The lint checks that read a lib idiom off the declared types of the
program's columns: a lib relation's defining chain written out by hand,
and an enumerator over a value another atom already binds."""

from dataclasses import dataclass
from enum import Enum

from checker.finding import Code, Finding, LintCode, LintSentence
from checker.lint.view import (
    View,
    bare,
    flatten,
    lint,
    literal_vars,
    positive_atoms,
    subterms,
    term_vars,
    view,
)
from checker.runs import Runs
from engine.program import (
    PRIMITIVES,
    AdtType,
    Atom,
    AtomLiteral,
    BodyLiteral,
    Comparison,
    ComparisonOperator,
    ConstructorTerm,
    FunctorCall,
    Qualifier,
    RecordTerm,
    RecordType,
    RelationName,
    SubtypeType,
    Term,
    UnionType,
    Unit,
    Variable,
    Wildcard,
    own,
)
from engine.quotes import quotes
from solver.category import Category
from solver.model import Solver, compared
from solver.vocabulary import (
    COMPOSE,
    ELEM_SUFFIX,
)


def _unpacked(term: Term) -> set[str]:
    """The variables a term binds where its value is bound: the term, and
    those inside a record or constructor, which unpack."""
    match term:
        case Variable(name=name):
            return {name}
        case RecordTerm(args=args) | ConstructorTerm(args=args):
            return {n for a in args for n in _unpacked(a)}
        case _:
            return set()


def _positive(lit: BodyLiteral) -> Atom | None:
    return lit.atom if isinstance(lit, AtomLiteral) and not lit.negated \
        else None


@dataclass
class Columns:
    """The declared type of each column of an atom, and the columns an
    atom grounds, off the declarations of the solver and the lib."""

    v: View

    def __post_init__(self) -> None:
        self.records = {t.name: [f.type for f in t.fields]
                        for t in self.v.program.types
                        if isinstance(t, RecordType)}
        self.ctors = {c.name: [f.type for f in c.fields]
                      for t in self.v.program.types
                      if isinstance(t, AdtType) for c in t.constructors}
        self._grounded: dict[object, frozenset[int]] = {}

    def columns(self, unit: Unit, atom: Atom) -> list[str] | None:
        return self.v.column_types(unit, atom)

    def var_types(self, unit: Unit, atom: Atom) -> dict[str, set[str]]:
        """Each variable of an atom and the declared types of the columns
        that bind it, through the fields of a record or constructor."""
        out: dict[str, set[str]] = {}

        def bind(arg: Term, t: str) -> None:
            match arg:
                case Variable(name=name):
                    out.setdefault(name, set()).add(t)
                case RecordTerm(args=args) if t in self.records:
                    for sub, ft in zip(args, self.records[t]):
                        bind(sub, ft)
                case ConstructorTerm(name=name, args=args) \
                        if name in self.ctors:
                    for sub, ft in zip(args, self.ctors[name]):
                        bind(sub, ft)
                case _:
                    pass

        cols = self.columns(unit, atom)
        for arg, t in zip(atom.args, cols or ()):
            bind(arg, t)
        return out

    def grounded(self, unit: Unit, atom: Atom) -> frozenset[int] | None:
        """The columns an atom grounds: each, for a relation that is not
        inline; for an inline one, each that every clause of it grounds."""
        d = self.v.relation(unit, atom)
        if d is None:
            return None
        if d.id in self._grounded:
            return self._grounded[d.id]
        if Qualifier.INLINE not in d.qualifiers:
            return frozenset(range(len(d.columns)))
        self._grounded[d.id] = frozenset()
        clauses = self.v.defs(d)
        out = set(range(len(d.columns))) if clauses else set()
        for u in clauses:
            bound = self._clause_grounds(u)
            out &= {i for i, arg in enumerate(u.head.args)
                    if not any(isinstance(x, Wildcard)
                               for x in subterms(arg))
                    and term_vars(arg) <= bound}
        self._grounded[d.id] = frozenset(out)
        return self._grounded[d.id]

    def _clause_grounds(self, unit: Unit) -> set[str]:
        if unit.body is None:
            return set()
        out: set[str] = set()
        for lit in unit.body:
            a = _positive(lit)
            if a is None:
                continue
            cols = self.grounded(unit, a)
            if cols is None:
                continue
            for i, arg in enumerate(a.args):
                if i in cols:
                    out |= _unpacked(arg)
        eqs = [x for x in unit.body if isinstance(x, Comparison)
               and x.op == ComparisonOperator.EQ]
        changed = True
        while changed:
            changed = False
            for eq in eqs:
                for side, value in ((eq.lhs, eq.rhs), (eq.rhs, eq.lhs)):
                    new = _unpacked(side) - out
                    if new and term_vars(value) <= out:
                        out |= new
                        changed = True
        return out


def _elem_tables(v: View) -> tuple[dict[str, str], dict[str, set[str]]]:
    """Each lib `*_elem` relation with the element type it holds, and each
    type with the types wider than it: a union is wider than its members,
    a subtype's base wider than it, transitively."""
    elem = dict(v.solver.lib.elems)
    wider: dict[str, set[str]] = {}
    for t in v.program.types:
        if own(t.span):
            continue
        if isinstance(t, SubtypeType):
            wider.setdefault(t.name, set()).add(t.base)
        elif isinstance(t, UnionType):
            for m in t.members:
                wider.setdefault(m, set()).add(t.name)
    for ws in wider.values():
        ws.difference_update(PRIMITIVES)
    changed = True
    while changed:
        changed = False
        for ws in wider.values():
            more = set().union(*(wider.get(w, set()) for w in ws)) - ws
            if more:
                ws |= more
                changed = True
    return elem, wider


class Binding(Enum):
    """Where an `*_elem` atom stands to the atoms that bind its variable
    (prompts/run_dl.md#enumerator)."""

    BOUND = "bound"
    BINDING = "binding"


def enumerator_binder(v: View, cols: Columns, unit: Unit, atom: Atom
                      ) -> tuple[Atom, Binding] | None:
    """The atom that binds the variable of an `*_elem` atom over one
    variable, and whether, in each expansion of the body, it stands before
    the `*_elem` atom (BOUND) or not (BINDING); None where some expansion
    holds no atom that binds it."""
    if unit.body is None or not atom.relation.name.endswith(ELEM_SUFFIX) \
            or len(atom.args) != 1 or not isinstance(atom.args[0], Variable):
        return None
    name = atom.args[0].name
    elem, wider_of = _elem_tables(v)
    wider = wider_of.get(elem.get(atom.relation.name, ""), set())

    def binds(o: Atom) -> bool:
        if o is atom or o.relation.name.endswith(ELEM_SUFFIX):
            return False
        g = cols.grounded(unit, o)
        if g is None or not any(name in _unpacked(a)
                                for i, a in enumerate(o.args) if i in g):
            return False
        types = cols.var_types(unit, o)
        return name in types and not types[name] <= wider

    first: Atom | None = None
    binding = Binding.BOUND
    for flat in flatten(unit.body):
        at = next((i for i, x in enumerate(flat)
                   if isinstance(x, AtomLiteral) and x.atom is atom), None)
        if at is None:
            continue
        binders = [(i, a) for i, x in enumerate(flat)
                   if (a := _positive(x)) is not None and binds(a)]
        if not binders:
            return None
        if first is None:
            first = binders[0][1]
        if binders[0][0] > at:
            binding = Binding.BINDING
    return None if first is None else (first, binding)


@quotes("style.md", "Idioms",
        "**Narrowing.** When a clause binds an argument of a lib relation to "
        "a head column of a narrower type, it takes that type's `*_elem` "
        "atom.")
def check_domain_enumerator(solver: Solver, runs: Runs) -> list[Finding]:
    """An `*_elem` atom whose variable an atom before it already binds, a
    hint. An atom that binds it first stays quiet. Serves readability."""
    v = view(solver, runs)
    cols = Columns(v)
    out: list[Finding] = []
    for u in v.program_units():
        if u.body is None:
            continue
        for a in positive_atoms(flatten(u.body)):
            found = enumerator_binder(v, cols, u, a)
            if found is not None and found[1] == Binding.BOUND:
                out.append(lint(a.line, LintCode(
                    Category.DOMAIN_ENUMERATOR,
                    LintSentence.DOMAIN_ENUMERATOR, (a, a.args[0]), (),
                    (found[0].relation.text,))))
    return out


# Lib idioms


@dataclass(frozen=True)
class InA:
    """An argument of the chain's first atom, by index."""

    index: int


@dataclass(frozen=True)
class InB:
    """An argument of the chain's second atom, by index."""

    index: int


@dataclass(frozen=True)
class Partner:
    """The second atom's argument at the commutative slot the link does
    not take."""


type Slot = InA | InB | Partner

PARTNER = Partner()


@dataclass(frozen=True)
class Chain:
    """A lib relation's defining body as the two atoms a hand-written
    clause carries: each atom's relation, arity and linking slot (the
    second's, the slots the link may take where the relation is
    commutative there), the replacement's arguments, and the guards:
    slot pairs that must or must not read alike, and slots that must be
    wildcards."""

    prim: str
    a: tuple[str, int, int]
    b: tuple[str, int, tuple[int, ...]]
    out: tuple[Slot, ...]
    equal: tuple[tuple[Slot, Slot], ...] = ()
    wild: tuple[Slot, ...] = ()
    distinct: tuple[tuple[Slot, Slot], ...] = ()


CHAINS = (
    Chain("neighbor", ("step_offset", 2, 1), (COMPOSE, 3, (0, 1)),
          (PARTNER, InA(0), InB(2))),
    Chain("jump", ("jump_offset", 3, 2), (COMPOSE, 3, (0, 1)),
          (PARTNER, InA(0), InA(1), InB(2))),
    Chain("same_line", ("split", 4, 3), ("split", 4, (3,)),
          (InA(1), InA(0), InB(0)),
          equal=((InA(1), InB(1)),), wild=(InA(2), InB(2)),
          distinct=((InA(0), InB(0)),)),
)
"""The lib relations whose defining chain the check reads."""


def _delta_out(v: View) -> dict[str, int]:
    """Each top-level lib relation that builds a Box record from its other
    columns alone, with that record's column: its one clause states the
    record from the other columns, or sets it by a functor call over them,
    or reads it off another such relation."""
    boxes = v.solver.lib.box_types
    decls = {d.name: d for d in v.program.relations
             if not own(d.span) and not d.scope.components}
    clauses: dict[str, list[Unit]] = {}
    for u in v.program.units:
        if u.span is not None and not own(u.span) \
                and not u.scope.components and not u.head.relation.instances:
            clauses.setdefault(u.head.relation.name, []).append(u)

    def slot(name: str, reading: frozenset[str]) -> int | None:
        rules = clauses.get(name)
        if name not in decls or rules is None or len(rules) != 1:
            return None
        d, u = decls[name], rules[0]
        at = [i for i, c in enumerate(d.columns) if c.type in boxes]
        if len(at) != 1 or len(u.head.args) != len(d.columns):
            return None
        out = u.head.args[at[0]]
        inputs = {n for i, a in enumerate(u.head.args) if i != at[0]
                  for n in term_vars(a)}
        if isinstance(out, RecordTerm):
            return at[0] if term_vars(out) <= inputs else None
        if not isinstance(out, Variable):
            return None
        if any(var == out.name and isinstance(value, FunctorCall)
               and term_vars(value) <= inputs
               for var, value in compared(u, ComparisonOperator.EQ)):
            return at[0]
        for lit in u.body or ():
            if (a := _positive(lit)) is not None \
                    and not a.relation.instances \
                    and a.relation.name not in reading \
                    and (k := slot(a.relation.name,
                                   reading | {a.relation.name})) is not None \
                    and k < len(a.args) and a.args[k] == out \
                    and {n for i, x in enumerate(a.args) if i != k
                         for n in term_vars(x)} <= inputs:
                return at[0]
        return None

    return {n: k for n in decls
            if (k := slot(n, frozenset({n}))) is not None}


def _delta_vars(deltas: dict[str, int], ext: list[Atom]) -> set[str]:
    """The variables that hold an Offset: outputs of the delta relations,
    and `compose` outputs whose operands both hold one."""
    out: set[str] = set()
    for a in ext:
        k = deltas.get(a.relation.name)
        if k is not None and len(a.args) > k:
            out |= term_vars(a.args[k])
    changed = True
    while changed:
        changed = False
        for a in ext:
            if a.relation.name != COMPOSE or len(a.args) != 3:
                continue
            ops = [term_vars(a.args[i]) for i in (0, 1)]
            if all(vs and vs <= out for vs in ops):
                new = term_vars(a.args[2]) - out
                if new:
                    out |= new
                    changed = True
    return out


def _pairs(ext: list[Atom], deltas: set[str]
           ) -> list[tuple[Atom, Atom, str, Atom]]:
    """Each chain match among the lib atoms `ext`, in source order: the two
    atoms, the linking variable, and the relation's atom that states
    them."""
    out: list[tuple[Atom, Atom, str, Atom]] = []

    def var_at(atom: Atom, i: int) -> str | None:
        arg = atom.args[i]
        return arg.name if isinstance(arg, Variable) else None

    for spec in CHAINS:
        rel_a, ar_a, slot_a = spec.a
        rel_b, ar_b, slots_b = spec.b
        for at_a, a in enumerate(ext):
            if a.relation.name != rel_a or len(a.args) != ar_a:
                continue
            link = var_at(a, slot_a)
            if link is None:
                continue
            for at_b, b in enumerate(ext):
                if at_b == at_a or b.relation.name != rel_b \
                        or len(b.args) != ar_b:
                    continue
                if rel_a == rel_b and at_b < at_a:
                    continue
                slot_b = next((i for i in slots_b if var_at(b, i) == link),
                              None)
                if slot_b is None:
                    continue

                def slot(ref: Slot, a: Atom = a, b: Atom = b,
                         slot_b: int = slot_b) -> Term:
                    match ref:
                        case InA(index=i):
                            return a.args[i]
                        case InB(index=i):
                            return b.args[i]
                        case Partner():
                            (i,) = [i for i in spec.b[2] if i != slot_b]
                            return b.args[i]

                if any(bare(slot(x)) != bare(slot(y))
                       for x, y in spec.equal):
                    continue
                if any(not isinstance(slot(s), Wildcard) for s in spec.wild):
                    continue
                if any(bare(slot(x)) == bare(slot(y))
                       for x, y in spec.distinct):
                    continue
                if PARTNER in spec.out and term_vars(slot(PARTNER)) & deltas:
                    continue
                args = tuple(slot(r) for r in spec.out)
                if any(link in term_vars(t) for t in args):
                    continue
                out.append((a, b, link,
                            Atom(RelationName((), spec.prim), args, a.line)))
    return out


@quotes("procedure.md", "Simplify",
        "Reimplements what the lib provides.")
def check_lib_idiom(solver: Solver, runs: Runs) -> list[Finding]:
    """A lib relation's defining chain written out by hand, with the linking
    value confined to the chain: name it with the relation. Serves the
    purest form: the lib names the idiom."""
    v = view(solver, runs)
    deltas = _delta_out(v)
    out: list[Finding] = []
    for u in v.program_units():
        if u.body is None:
            continue
        head_vars = literal_vars(u.head)
        found: dict[tuple[int, int], list] = {}
        for flat in flatten(u.body):
            ext = [a for x in flat if (a := _positive(x)) is not None
                   and v.is_lib(v.relation(u, a))]
            for a, b, link, prim in _pairs(ext, _delta_vars(deltas, ext)):
                clean = link not in head_vars and not any(
                    not (isinstance(x, AtomLiteral)
                         and (x.atom is a or x.atom is b))
                    and link in literal_vars(x) for x in flat)
                entry = found.setdefault((id(a), id(b)), [a, b, prim, True])
                entry[3] = entry[3] and clean
        for a, b, prim, clean in found.values():
            if clean:
                code: tuple[Code, ...] = (a, b)
                out.append(lint(a.line, LintCode(
                    Category.LIB_IDIOM, LintSentence.LIB_IDIOM, code,
                    (prim,))))
    return out
