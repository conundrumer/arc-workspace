"""The lint checks on shapes that the corpus's edits rewrite away, each
mirroring an edit family observed across the solvers, and the checks
that read the style doc beside them: `choice-domain`, `shared-read` and
`decl-placement`. Relation-level checks read the relations of the scopes
that hold program code, less the case enumeration's."""

from collections.abc import Iterator, Sequence
from dataclasses import dataclass, replace

from checker.finding import (
    Code,
    Finding,
    LintCode,
    LintCounted,
    LintMarked,
    LintNamed,
    LintSentence,
)
from checker.judged import base_names
from checker.lint.form import case_column_facts
from checker.lint.view import (
    TOP,
    View,
    aggregates,
    atoms_read,
    bare,
    conjunctions,
    disjunctions,
    flatten,
    lint,
    literal_terms,
    literal_vars,
    positive_atoms,
    subterms,
    term_vars,
    view,
)
from checker.runs import Runs
from engine import Resolved
from engine.program import (
    AdtType,
    AggregateOperator,
    Atom,
    AtomLiteral,
    BodyLiteral,
    BoolLiteral,
    Comparison,
    ComparisonOperator,
    ConstructorTerm,
    DeclId,
    DefinedName,
    Disjunction,
    Instance,
    Intrinsic,
    IntrinsicCall,
    NumberTerm,
    Qualifier,
    RecordTerm,
    RelationDecl,
    RelationName,
    Term,
    Unit,
    Variable,
    Wildcard,
    own,
)
from engine.quotes import quotes
from solver.category import Category
from solver.model import (
    bases_of,
    Section,
    Solver,
    UnderMarker,
    Unmarked,
    lists_case,
    Parameter,
    section_at,
)
from solver.case_types import (
    compared,
    substituted_atom,
    substituted_literal,
)
from solver.dependence import dependence
from solver.solve import per_case
from solver.vocabulary import (
    COMPOSE,
    DETERMINE,
    EX_IN,
    EX_OUT,
    INPUT,
    OUTPUT,
    PARAMS,
)

EXAMPLE_SOURCES = frozenset({INPUT.name, EX_IN.name, EX_OUT.name})
"""The relations the runner fills per example."""

COMMON_SUBEXPR_MIN = 2
"""The literals a shared window must span."""

IMAGE_COMPS = {"apply": "D4Map.conflict",
               COMPOSE: "OffsetInvariance.mismatch"}
"""The lib component whose defining rule reads one valued cell set at a
cell and at its image, by the lib relation that takes the cell onto the
image."""


# Shared views


def _determined(v: View) -> set[str]:
    """The relations of `Params` a `Determine` relation mirrors
    (solver-file.md, under "Determination"): `Parameter.determined` and
    `DerivedRelation.mirrored`."""
    params = v.solver.params
    return {p.name for p in params.parameters if p.determined} \
        | {d.name for d in params.derived if d.mirrored}


def _style_relations(v: View) -> list[RelationDecl]:
    return [r for r in v.program_relations()
            if v.comp_of(r.scope) != PARAMS]


def _head_is(v: View, unit: Unit, decl: RelationDecl) -> bool:
    h = v.head(unit)
    return h is not None and h.id == decl.id


def _recursive(v: View, decl: RelationDecl) -> bool:
    return any(_head_is(v, u, decl) for u, _a, _n in v.uses(decl))


def _inlinable(v: View, decl: RelationDecl) -> bool:
    """Substituting the relation away is on the table: a derived relation
    other than `out` or a determined parameter, with no `choice-domain`,
    whose rules and uses share its scope."""
    if decl.scope == TOP and decl.name == OUTPUT.name:
        return False
    if v.comp_of(decl.scope) in (DETERMINE, PARAMS) \
            and decl.name in _determined(v):
        return False
    if decl.choice_domain:
        return False
    defs = v.defs(decl)
    if not any(d.body is not None for d in defs):
        return False
    return all(u.scope == decl.scope for u in defs) and \
        all(u.scope == decl.scope for u, _a, _n in v.uses(decl))


def _aggregate_of(unit: Unit, atom: Atom) -> AggregateOperator | None:
    """The operator of the aggregate whose body holds `atom`, if any."""
    for lit in (*(unit.body or ()),):
        for agg in aggregates(lit):
            if any(isinstance(x, AtomLiteral) and x.atom is atom
                   for x in agg.body):
                return agg.op
    return None


def _drops_columns(unit: Unit) -> bool:
    """The head loses information from the body: a body variable or
    wildcard no head column carries."""
    if unit.body is None:
        return False
    head = literal_vars(unit.head)
    if any(literal_vars(lit) - head for lit in unit.body):
        return True
    return any(isinstance(a, Wildcard) for x in atoms_read(unit)
               for a in x.args)


def _relation_claims(v: View
                     ) -> tuple[dict[DeclId, Category],
                                dict[Category, list[Finding]]]:
    """The relation-level rules in order, strongest claim first: a
    relation one rule flags, a later one does not (`dead`, then
    `alias-inline`, `negated-use`, `pass-through`, `chain-join`,
    `single-consumer`); each relation's claim, and each rule's findings.
    Computed once per view (`View.held`)."""
    claims: dict[DeclId, Category] = {}
    found: dict[Category, list[Finding]] = {}

    def run(category: Category, decls: Sequence[RelationDecl], rule) -> None:
        out: list[Finding] = []
        for d in decls:
            if d.id in claims:
                continue
            f = rule(v, d)
            if f is not None:
                claims[d.id] = category
                out.append(f)
        found[category] = out

    found[Category.DEAD] = _dead(v, claims)
    style = _style_relations(v)
    run(Category.ALIAS_INLINE, style, _alias_inline)
    run(Category.NEGATED_USE, style, _negated_use)
    run(Category.PASS_THROUGH, style, _pass_through)
    run(Category.CHAIN_JOIN, style, _chain_join)
    run(Category.SINGLE_CONSUMER, v.program_relations(), _single_consumer)
    return claims, found


def _claimed(solver: Solver, runs: Runs, category: Category) -> list[Finding]:
    v = view(solver, runs)
    _claims, found = v.held(_relation_claims)
    return list(found[category])


# Relation-level rules


def _dead(v: View, claims: dict[DeclId, Category]) -> list[Finding]:
    exempt = {d.id for d in v.program_relations()
              if (d.scope == TOP and d.name == OUTPUT.name)
              or (v.comp_of(d.scope) in (DETERMINE, PARAMS)
                  and d.name in _determined(v))}
    dead: set[DeclId] = set()
    changed = True
    while changed:
        changed = False
        for d in v.program_relations():
            if d.id in dead or d.id in exempt:
                continue
            live = [u for u, _a, _n in v.uses(d)
                    if (h := v.head(u)) is None or h.id not in dead]
            if not live:
                dead.add(d.id)
                changed = True
    out: list[Finding] = []
    for d in sorted((d for d in v.program_relations() if d.id in dead),
                    key=lambda d: d.span.first):
        claims[d.id] = Category.DEAD
        out.append(lint(d.span.first, LintNamed(
            Category.DEAD, LintSentence.DEAD, (d.name,))))
    return out


@quotes("procedure.md", "Simplify",
        "Express what the code claims with less code.")
def check_dead(solver: Solver, runs: Runs) -> list[Finding]:
    """A relation no clause reads, to a fixpoint: removing a dead
    relation's rules can orphan the relations those rules read. Serves the
    purest form: nothing the concept does not use."""
    return _claimed(solver, runs, Category.DEAD)


def _lib_inline(v: View) -> tuple[frozenset[str], frozenset[str]]:
    """The lib's top-level inline relations, and those among them whose
    expansion introduces no variable, which Souffle negates when the use
    binds every column."""
    inline = frozenset(r.name for r in v.program.relations
                       if not own(r.span) and r.scope == TOP
                       and Qualifier.INLINE in r.qualifiers)
    clauses: dict[str, list[Unit]] = {}
    for u in v.program.units:
        if u.span is not None and not own(u.span) and u.body is not None \
                and u.scope == TOP and not u.head.relation.instances \
                and u.head.relation.name in inline:
            clauses.setdefault(u.head.relation.name, []).append(u)

    def closed(u: Unit) -> bool:
        head = literal_vars(u.head)
        for lit in u.body or ():
            if isinstance(lit, BoolLiteral):
                continue
            if isinstance(lit, AtomLiteral) and lit.negated:
                return False
            if not isinstance(lit, AtomLiteral | Comparison):
                return False
            if literal_vars(lit) - head:
                return False
            if isinstance(lit, AtomLiteral) and any(
                    _has_wild(a) for a in lit.atom.args):
                return False
            if isinstance(lit, Comparison) and any(
                    isinstance(s, IntrinsicCall)
                    and s.functor == Intrinsic.RANGE
                    for side in (lit.lhs, lit.rhs) for s in subterms(side)):
                return False
        return True

    negatable = {n for n in inline if all(closed(u) for u in clauses.get(n, []))}
    changed = True
    while changed:
        changed = False
        for n in list(negatable):
            for u in clauses.get(n, []):
                for lit in u.body or ():
                    if isinstance(lit, AtomLiteral) \
                            and not lit.atom.relation.instances \
                            and lit.atom.relation.name in inline \
                            and lit.atom.relation.name not in negatable:
                        negatable.discard(n)
                        changed = True
                        break
    return inline, frozenset(negatable)


def _has_wild(t: Term) -> bool:
    return any(isinstance(s, Wildcard) for s in subterms(t))


def _single_atom(unit: Unit) -> Atom | None:
    """The one positive atom a clause's body holds, None where its body is
    anything else."""
    if unit.body is None or len(unit.body) != 1:
        return None
    lit = unit.body[0]
    if isinstance(lit, AtomLiteral) and not lit.negated:
        return lit.atom
    return None


def _alias_inline(v: View, decl: RelationDecl) -> Finding | None:
    """A pure rename: one rule, one positive atom, every column carried
    through."""
    if not _inlinable(v, decl):
        return None
    defs = v.defs(decl)
    if len(defs) != 1:
        return None
    d = defs[0]
    atom = _single_atom(d)
    if atom is None or atom.relation.instances:
        return None
    head_vars = [a.name for a in d.head.args if isinstance(a, Variable)]
    atom_vars = [a.name for a in atom.args if isinstance(a, Variable)]
    if len(head_vars) != len(d.head.args) or len(atom_vars) != len(atom.args):
        return None
    if len(set(head_vars)) != len(head_vars) or set(head_vars) != set(atom_vars):
        return None
    inline, negatable = v.held(_lib_inline)
    if v.is_lib(v.relation(d, atom)) and atom.relation.name in inline \
            and atom.relation.name not in negatable \
            and any(n for _u, _a, n in v.uses(decl)):
        return None
    return lint(decl.span.first, LintCode(
        Category.ALIAS_INLINE, LintSentence.ALIAS, (d.head, atom), ()))


@quotes("procedure.md", "Simplify",
        "Has unusual or needless indirection.")
def check_alias_inline(solver: Solver, runs: Runs) -> list[Finding]:
    """A relation that renames another: one rule, one positive atom, every
    column carried through. Serves the purest form: a rewrite family the
    corpus's edits take (nothing verbose)."""
    return _claimed(solver, runs, Category.ALIAS_INLINE)


def _projection(v: View, d: Unit) -> bool:
    """The rule projects a single positive atom: negating the head is
    negating the atom with the dropped columns wildcarded."""
    atom = _single_atom(d)
    if atom is None:
        return False
    inline, negatable = v.held(_lib_inline)
    head_vars = {a.name for a in d.head.args if isinstance(a, Variable)}
    if v.is_lib(v.relation(d, atom)) and not atom.relation.instances \
            and atom.relation.name in inline:
        if atom.relation.name not in negatable \
                or literal_vars(atom) - head_vars \
                or any(_has_wild(a) for a in atom.args):
            return False
    counts: dict[str, int] = {}
    for arg in atom.args:
        for name in term_vars(arg):
            counts[name] = counts.get(name, 0) + 1
    head_ok = all(isinstance(a, Variable) and a.name in counts
                  for a in d.head.args)
    nested_drop = any(
        isinstance(arg, RecordTerm | ConstructorTerm)
        and (_has_wild(arg) or term_vars(arg) - head_vars)
        for arg in atom.args)
    return head_ok and not nested_drop and all(
        n == 1 for name, n in counts.items() if name not in head_vars)


def _negated_use(v: View, decl: RelationDecl) -> Finding | None:
    """Referenced only under negation, every rule a single-atom
    projection."""
    if not _inlinable(v, decl):
        return None
    uses = v.uses(decl)
    if not uses or any(not n for _u, _a, n in uses):
        return None
    defs = v.defs(decl)
    if not defs or any(not _projection(v, d) for d in defs):
        return None
    canon = defs[0].head.args
    parts: list[Code] = []
    for d in defs:
        carried = {a.name: canon[i] for i, a in enumerate(d.head.args)
                   if isinstance(a, Variable)}
        atom = _single_atom(d)
        assert atom is not None
        terms: dict[str, Term] = {name: carried.get(name, Wildcard())
                                  for name in literal_vars(atom)}
        parts.append(AtomLiteral(substituted_atom(atom, terms), True))
    use = Atom(decl.scoped_name, canon, decl.span.first)
    return lint(decl.span.first, LintCode(
        Category.NEGATED_USE, LintSentence.NEGATED_USE,
        (AtomLiteral(use, True),), tuple(parts), (decl.name,)))


@quotes("procedure.md", "Simplify",
        "Has unusual or needless indirection.")
def check_negated_use(solver: Solver, runs: Runs) -> list[Finding]:
    """A relation read only under negation whose every rule projects one
    atom: the negation reads the atom directly. Serves the purest form, as
    `check_alias_inline` does."""
    return _claimed(solver, runs, Category.NEGATED_USE)


def _pass_through(v: View, decl: RelationDecl) -> Finding | None:
    """Consumed only by pure forwarding rules of one relation."""
    if not _inlinable(v, decl) or _recursive(v, decl):
        return None
    ext = [(u, a, n) for u, a, n in v.uses(decl) if not _head_is(v, u, decl)]
    if not ext or any(n or _aggregate_of(u, a) is not None
                      for u, a, n in ext):
        return None
    heads = {h.id: h for u, _a, _n in ext if (h := v.head(u)) is not None}
    if len(heads) != 1 or len(ext) != sum(1 for u, _a, _n in ext
                                          if v.head(u) is not None):
        return None
    (consumer,) = heads.values()
    if consumer.id == decl.id or v.is_lib(consumer) \
            or v.comp_of(consumer.scope) == PARAMS \
            or (consumer.scope == TOP and consumer.name == OUTPUT.name):
        return None
    for u, atom, _n in ext:
        if u.body is None or len(u.body) != 1:
            return None
        head_vars = {a.name for a in u.head.args if isinstance(a, Variable)}
        if {a.name for a in atom.args if isinstance(a, Variable)} - head_vars:
            return None
    return lint(decl.span.first, LintNamed(
        Category.PASS_THROUGH, LintSentence.PASS_THROUGH,
        (decl.name, consumer.name)))


@quotes("procedure.md", "Simplify",
        "Has unusual or needless indirection.")
def check_pass_through(solver: Solver, runs: Runs) -> list[Finding]:
    """A relation consumed only by pure forwarding rules of one other
    relation, a hint: the corpus keeps this shape as a named union member,
    so the call is the session's. Serves the purest form."""
    return _claimed(solver, runs, Category.PASS_THROUGH)


def _single_consumer(v: View, decl: RelationDecl) -> Finding | None:
    """One rule, one positive use, a body of at most two literals."""
    if not _inlinable(v, decl):
        return None
    defs = v.defs(decl)
    if len(defs) != 1 or defs[0].body is None or _recursive(v, decl):
        return None
    body = defs[0].body
    if len(body) > 2 or not any(isinstance(x, AtomLiteral) and not x.negated
                                for x in body):
        return None
    uses = v.uses(decl)
    if len(uses) != 1 or uses[0][2]:
        return None
    u, atom, _n = uses[0]
    op = _aggregate_of(u, atom)
    if op in (AggregateOperator.COUNT, AggregateOperator.SUM) \
            and _drops_columns(defs[0]):
        return None
    return lint(decl.span.first, LintCounted(
        Category.SINGLE_CONSUMER, LintSentence.SINGLE_CONSUMER,
        (decl.name,), 1, atom.line))


@quotes("style.md", "Program",
        "The single-consumer hint also applies to relations in Params.")
def check_single_consumer(solver: Solver, runs: Runs) -> list[Finding]:
    """A relation of one rule and one positive use, with a body of at most
    two literals, a hint: the corpus both inlines and keeps this shape. It
    applies to the relations in Params too. Serves the purest form."""
    return _claimed(solver, runs, Category.SINGLE_CONSUMER)


def _join_partner(v: View, unit: Unit, atom: Atom, col: int
                  ) -> tuple[DeclId, int, Atom] | None:
    """The relation, column and atom the key variable at `col` of a use
    joins, when the variable stands there and in that atom alone."""
    if col >= len(atom.args) or not isinstance(atom.args[col], Variable):
        return None
    name = atom.args[col].name  # type: ignore[union-attr]
    if unit.body is None or name in literal_vars(unit.head):
        return None
    if sum(1 for a in atom.args if name in term_vars(a)) != 1:
        return None
    partner: tuple[DeclId, int, Atom] | None = None
    for lit in unit.body:
        if isinstance(lit, AtomLiteral) and not lit.negated \
                and lit.atom is not atom:
            hits = [i for i, a in enumerate(lit.atom.args)
                    if name in term_vars(a)]
            if len(hits) > 1 or (hits and partner is not None):
                return None
            if hits:
                if not isinstance(lit.atom.args[hits[0]], Variable):
                    return None
                d = v.relation(unit, lit.atom)
                if d is None or v.is_lib(d):
                    return None
                partner = (d.id, hits[0], lit.atom)
        elif not (isinstance(lit, AtomLiteral) and lit.atom is atom) \
                and name in literal_vars(lit):
            return None
    return partner


def _chain_join(v: View, decl: RelationDecl) -> Finding | None:
    """A column that, at every use, only keys a join against one other
    relation the join fully absorbs."""
    if decl.scope != TOP or not _inlinable(v, decl):
        return None
    if any(_single_atom(d) is None for d in v.defs(decl)):
        return None
    uses = v.uses(decl)
    if not uses or any(n or _aggregate_of(u, a) is not None
                       for u, a, n in uses):
        return None
    for col in range(len(decl.columns)):
        partners: set[tuple[DeclId, int]] = set()
        joined: list[Atom] = []
        for u, atom, _n in uses:
            p = _join_partner(v, u, atom, col)
            if p is None:
                break
            partners.add((p[0], p[1]))
            joined.append(p[2])
        else:
            if len(partners) != 1:
                continue
            q_id, _ = partners.pop()
            q = v.decls.get(q_id)
            if not isinstance(q, RelationDecl):
                continue
            ids = {id(a) for a in joined}
            if not all(id(a) in ids for _u, a, _n in v.uses(q)):
                continue
            return lint(decl.span.first, LintNamed(
                Category.CHAIN_JOIN, LintSentence.CHAIN_JOIN,
                (decl.name, decl.columns[col].name, q.name)))
    return None


@quotes("procedure.md", "Simplify",
        "Has unusual or needless indirection.")
def check_chain_join(solver: Solver, runs: Runs) -> list[Finding]:
    """A column that, at every use, only keys a join against one other
    relation the join fully absorbs, a hint: fuse and project the column
    out. Serves the purest form."""
    return _claimed(solver, runs, Category.CHAIN_JOIN)


@quotes("principles.md", "Choice points and open parameters",
        "**choice point**: an undetermined property whose possible answers "
        "are models represented by cases.")
@quotes("solver-file.md", "Alt outputs",
        "The solver enumerates a tiebreak's resolutions through a trailing "
        "`out` column of type `TiebreakResolution`.")
def check_choice_domain(solver: Solver, runs: Runs) -> list[Finding]:
    """A `choice-domain` declaration in program code: the relation keeps
    one arbitrary tuple per key, so which one it keeps is a choice the
    program does not state. Serves the concept's form: every choice the
    model makes is stated (principles.md, under
    "Choice points and open parameters")."""
    v = view(solver, runs)
    return [lint(d.span.first, LintNamed(
                Category.CHOICE_DOMAIN, LintSentence.CHOICE_DOMAIN,
                (d.name,), d.choice_domain))
            for d in v.program_relations() if d.choice_domain]


# Shared parameters


def _tags(solver: Solver, v: View) -> dict[str, int]:
    """The constructors of the choice ADTs, each with its field count."""
    out: dict[str, int] = {}
    if solver.choice is None:
        return out
    for p in solver.choice.points:
        td = v.program.declaration(p.declaration)
        if isinstance(td, AdtType):
            for c in td.constructors:
                out[c.name] = len(c.fields)
    return out


def _tag(name: str, fields: int) -> ConstructorTerm:
    return ConstructorTerm(name, (Wildcard(),) * fields)


def head_ctors(unit: Unit) -> set[str]:
    """The constructors a clause's head carries: the ones its arguments
    spell, and the ones a body equality `V = <term>` sets a head variable
    to."""
    bound: dict[str, list[Term]] = {}
    for var, term in compared(unit, ComparisonOperator.EQ):
        bound.setdefault(var, []).append(term)
    out: set[str] = set()
    seen: set[str] = set()
    work: list[Term] = list(unit.head.args)
    while work:
        for t in subterms(work.pop()):
            if isinstance(t, ConstructorTerm):
                out.add(t.name)
            elif isinstance(t, Variable) and t.name not in seen:
                seen.add(t.name)
                work += bound.get(t.name, [])
    return out


@dataclass(frozen=True)
class RelNode:
    """A relation the program declares."""

    decl: DeclId


@dataclass(frozen=True)
class InstanceNode:
    """An instance of a lib component, read as opaque."""

    decl: DeclId


@quotes("solver-file.md", "Cases",
        "**Case markers.** Cases do not interleave: each case's Params and "
        "clauses are under its marker.")
@quotes("style.md", "Params",
        "A parameter that every case reads is declared above the case "
        "markers, and so are its facts when it has no case column. A "
        "parameter that some case never reads goes under the marker of the "
        "cases that read it.")
@quotes("solver-file.md", "Params",
        "Each of its facts stands under the marker of the case its case "
        "column holds.")
def check_shared_read(solver: Solver, runs: Runs) -> list[Finding]:
    """A parameter under a marker that lists no case, below a marker that
    lists one; a fact under a marker of a shared parameter with no case
    column (`solver.solve.per_case`); a fact of a parameter with a case
    column outside the marker of its case (`case_column_facts`); and a
    shared parameter some case of the solver never reads
    (`solver.dependence.Dependence.reads_parameter`), or that no case reads,
    which no marker of a case is the place of. The last two are judged
    where the run that enumerates the solver's cases gives a result. A
    marker that lists no case above every marker that lists one leaves the
    parameters under it shared. Every relation `Params` declares is read, a
    derived one too, since the rule is about what cases share, whatever
    feeds the relation. Where one stands is `Parameter.section` or
    `DerivedRelation.section`. Serves the concept's form."""
    v = view(solver, runs)
    choice = solver.choice
    if choice is None:
        return []
    written = {d.id: d for d in v.written_relations}
    out: list[Finding] = []
    shared: list[tuple[str, RelationDecl]] = []
    for p in (*solver.params.parameters, *solver.params.derived):
        d = written.get(p.declaration)
        if d is None:
            continue
        match p.section:
            case Unmarked():
                shared.append((p.name, d))
                if isinstance(p, Parameter) and \
                        per_case(solver, p.name) is None:
                    out += [lint(line, LintMarked(
                        Category.SHARED_READ, LintSentence.SHARED_FACT_MARKED,
                        d.name, m))
                        for _u, line, m in v.marked_facts(d) if m is not None]
            case UnderMarker(marker=m) if not lists_case(solver, m):
                out.append(lint(d.span.first, LintMarked(
                    Category.SHARED_READ, LintSentence.MARKER_LISTS_NO_CASE,
                    d.name, m)))
            case UnderMarker():
                pass
    every = runs.solver_cases
    if not isinstance(every, tuple):
        return out
    out += case_column_facts(solver, v, every)
    bases = bases_of(every)
    rd = dependence(runs.engine, solver, bases)
    for name, d in sorted(shared, key=lambda s: s[1].name):
        unread = [b for b in bases if not rd.reads_parameter(b, name)]
        if len(unread) == len(bases):
            out.append(lint(d.span.first, LintMarked(
                Category.SHARED_READ, LintSentence.SHARED_NO_READER, d.name,
                None)))
        elif unread:
            out.append(lint(d.span.first, LintMarked(
                Category.SHARED_READ, LintSentence.SHARED_UNREAD_BY_ONE
                if len(unread) == 1 else LintSentence.SHARED_UNREAD, d.name,
                None, cases=base_names(solver, unread, bases))))
    return out


# Rule-level rules


def _key(lits: Sequence[BodyLiteral]) -> tuple[BodyLiteral, ...]:
    return bare(tuple(lits))


@quotes("style.md", "Disjunction",
        "Clauses that share a head and a frame belong in one clause.")
def check_choice_tag(solver: Solver, runs: Runs) -> list[Finding]:
    """Clauses identical but for a distinct nullary constructor in one head
    argument, where some relation's facts already enumerate both tags: one
    clause ranges over the tags. Serves the purest form."""
    v = view(solver, runs)
    units = v.program_units()
    facts: list[set[str]] = []
    have: dict[DeclId | str, set[str]] = {}
    for u in v.program.units:
        if u.body is not None:
            continue
        d = v.head(u)
        key: DeclId | str = d.id if d is not None else u.head.relation.name
        for a in u.head.args:
            if isinstance(a, ConstructorTerm) and not a.args:
                have.setdefault(key, set()).add(a.name)
    facts = list(have.values())
    out: list[Finding] = []
    for i, u in enumerate(units):
        if u.body is None or u.span is None:
            continue
        for o in units[:i]:
            if o.body is None or o.scope != u.scope or o.span is None \
                    or _section(v, o) != _section(v, u):
                continue
            if o.head.relation != u.head.relation \
                    or len(o.head.args) != len(u.head.args):
                continue
            if _key(o.body) != _key(u.body):
                continue
            diff = [j for j, (a, b) in enumerate(zip(u.head.args, o.head.args))
                    if bare(a) != bare(b)]
            if len(diff) != 1:
                continue
            tags = [x.head.args[diff[0]] for x in (u, o)]
            names = [t.name for t in tags
                     if isinstance(t, ConstructorTerm) and not t.args]
            if len(names) == 2 and any(set(names) <= s for s in facts):
                out.append(lint(u.span.first, LintCode(
                    Category.CHOICE_TAG, LintSentence.CHOICE_TAG,
                    (tags[1], tags[0]), ())))
                break
    return out


@quotes("style.md", "Disjunction",
        "A clause does not range over choice tags through a disjunction.")
def check_cross_choice(solver: Solver, runs: Runs) -> list[Finding]:
    """A disjunction whose branches bind different choice tags: choices stay
    separate rules. Serves the concept's form."""
    v = view(solver, runs)
    tags = _tags(solver, v)
    out: list[Finding] = []
    for u in v.program_units():
        for disj in disjunctions(u):
            binds = [{t.name for lit in b for top in literal_terms(lit, True)
                      for t in subterms(top)
                      if isinstance(t, ConstructorTerm)} & set(tags)
                     for b in disj.branches]
            named = [b for b in binds if b]
            if len(named) >= 2 and any(b != named[0] for b in named):
                found = sorted(set().union(*named))
                out.append(lint(disj.line, LintCode(
                    Category.CROSS_CHOICE, LintSentence.CROSS_CHOICE,
                    tuple(_tag(t, tags[t]) for t in found), ())))
    return out


@quotes("procedure.md", "Simplify",
        "Express what the code claims with less code.")
@quotes("procedure.md", "Simplify",
        "Has repetition where a principled form exists.")
def check_subsumed_atom(solver: Solver, runs: Runs) -> list[Finding]:
    """`R(X, _)` beside `R(X, Y)` in one body, or one atom twice: the
    wildcard atom adds nothing. Serves the purest form."""
    v = view(solver, runs)
    out: list[Finding] = []
    for u in v.program_units():
        for body in conjunctions(u):
            atoms = [x.atom for x in body
                     if isinstance(x, AtomLiteral) and not x.negated]
            for i, a in enumerate(atoms):
                for j, b in enumerate(atoms):
                    if i == j or a.relation != b.relation \
                            or len(a.args) != len(b.args):
                        continue
                    pairs = list(zip(a.args, b.args))
                    if all(bare(x) == bare(y) for x, y in pairs):
                        if i < j:
                            out.append(lint(b.line, LintCode(
                                Category.SUBSUMED_ATOM,
                                LintSentence.ATOM_TWICE, (b,), ())))
                    elif all(isinstance(x, Wildcard)
                             or bare(x) == bare(y)
                             for x, y in pairs):
                        out.append(lint(a.line, LintCode(
                            Category.SUBSUMED_ATOM,
                            LintSentence.ATOM_ADDS_NOTHING, (a, b), ())))
    return out


def _holds(flat: list[BodyLiteral], atom: Atom) -> bool:
    return any(isinstance(x, AtomLiteral) and x.atom is atom for x in flat)


def _other_side(cmp: Comparison, name: str) -> Term | None:
    if isinstance(cmp.lhs, Variable) and cmp.lhs.name == name:
        return cmp.rhs
    if isinstance(cmp.rhs, Variable) and cmp.rhs.name == name:
        return cmp.lhs
    return None


@quotes("style.md", "Idioms",
        "**Complement tests.** The test negates the relation of the values it "
        "excludes: `!params.bg(Col)` for non-bg.")
def check_named_complement(solver: Solver, runs: Runs) -> list[Finding]:
    """`R(V), X != V` against a relation of one fact: `!R(X)` says it
    directly. Serves the purest form."""
    v = view(solver, runs)
    out: list[Finding] = []
    for u in v.program_units():
        if u.body is None:
            continue
        flats = list(flatten(u.body))
        for atom in positive_atoms(flats):
            if len(atom.args) != 1 or not isinstance(atom.args[0], Variable):
                continue
            d = v.relation(u, atom)
            if d is None or v.is_lib(d):
                continue
            defs = v.defs(d)
            if len(defs) != 1 or defs[0].body is not None:
                continue
            name = atom.args[0].name
            if name in literal_vars(u.head):
                continue
            found: tuple[Comparison, Term] | None = None
            ok = True
            for flat in flats:
                if not _holds(flat, atom):
                    continue
                others = [x for x in flat
                          if not (isinstance(x, AtomLiteral) and x.atom is atom)
                          and name in literal_vars(x)]
                if len(others) != 1 or not isinstance(others[0], Comparison) \
                        or others[0].op != ComparisonOperator.NE:
                    ok = False
                    break
                cmp = others[0]
                other = _other_side(cmp, name)
                if other is None:
                    ok = False
                    break
                bound = {n for x in flat
                         if isinstance(x, AtomLiteral) and not x.negated
                         and x.atom is not atom for n in literal_vars(x)}
                if term_vars(other) - bound:
                    ok = False
                    break
                if found is None:
                    found = (cmp, other)
                elif found[0] is not cmp:
                    ok = False
                    break
            if not ok or found is None:
                continue
            cmp, other = found
            out.append(lint(atom.line, LintCode(
                Category.NAMED_COMPLEMENT, LintSentence.NAMED_COMPLEMENT,
                (atom, cmp),
                (AtomLiteral(replace(atom, args=(other,)), True),))))
    return out


@quotes("style.md", "Idioms",
        "**Complement tests.** The test negates the relation of the values it "
        "excludes: `!params.bg(Col)` for non-bg.")
def check_negated_value(solver: Solver, runs: Runs) -> list[Finding]:
    """`prim(..., K), K != c`, with `K` read nowhere else, at a lib inline
    relation Souffle negates: `!prim(..., c)` says it directly. Serves the
    purest form."""
    v = view(solver, runs)
    _inline, negatable = v.held(_lib_inline)
    out: list[Finding] = []
    for u in v.program_units():
        if u.body is None:
            continue
        head_vars = literal_vars(u.head)
        flats = list(flatten(u.body))
        for atom in positive_atoms(flats):
            if atom.relation.instances \
                    or atom.relation.name not in negatable \
                    or not v.is_lib(v.relation(u, atom)) \
                    or any(_has_wild(a) for a in atom.args):
                continue
            for i, arg in enumerate(atom.args):
                if not isinstance(arg, Variable) or arg.name in head_vars:
                    continue
                name = arg.name
                if sum(1 for a in atom.args if name in term_vars(a)) != 1:
                    continue
                const = _sole_complement(atom, name, flats)
                if const is None:
                    continue
                rest = [a for j, a in enumerate(atom.args) if j != i]
                if not all(_bound_elsewhere(atom, w, flats)
                           for a in rest for w in term_vars(a)):
                    continue
                cmp = next(x for f in flats if _holds(f, atom) for x in f
                           if isinstance(x, Comparison)
                           and name in literal_vars(x))
                new = replace(atom, args=tuple(
                    const if j == i else a for j, a in enumerate(atom.args)))
                out.append(lint(atom.line, LintCode(
                    Category.NEGATED_VALUE, LintSentence.NEGATED_VALUE,
                    (atom, cmp), (AtomLiteral(new, True),))))
                break
    return out


def _sole_complement(atom: Atom, name: str, flats: list[list[BodyLiteral]]
                     ) -> Term | None:
    const: Term | None = None
    for flat in flats:
        if not _holds(flat, atom):
            continue
        others = [x for x in flat
                  if not (isinstance(x, AtomLiteral) and x.atom is atom)
                  and name in literal_vars(x)]
        if len(others) != 1 or not isinstance(others[0], Comparison) \
                or others[0].op != ComparisonOperator.NE:
            return None
        t = _other_side(others[0], name)
        if not isinstance(t, NumberTerm | DefinedName) \
                or (const is not None and const != t):
            return None
        const = t
    return const


def _bound_elsewhere(atom: Atom, name: str, flats: list[list[BodyLiteral]]
                     ) -> bool:
    return all(any(isinstance(x, AtomLiteral) and not x.negated
                   and x.atom is not atom and name in literal_vars(x)
                   for x in flat)
               for flat in flats if _holds(flat, atom))


@dataclass(frozen=True)
class InComp:
    """The clauses of a component."""

    comp: str


@dataclass(frozen=True)
class InSection:
    """A top-level section (`solver.model.section_at`)."""

    section: Section


type Spot = InComp | InSection
"""Where a relation's references stand."""


@quotes("style.md", "Layout",
        "a file takes its block order and layout from it.")
def check_decl_placement(solver: Solver, runs: Runs) -> list[Finding]:
    """A top-level declaration whose every reference stands in one section
    or comp it is not in: move it there. `out` is the interface, declared
    under `Choice`. Serves readability."""
    v = view(solver, runs)
    out: list[Finding] = []
    for d in v.written_relations:
        if d.scope != TOP or d.name == OUTPUT.name:
            continue
        spots: set[Spot] = set()
        units = [*v.defs(d), *(u for u, _a, _n in v.uses(d))]
        for u in units:
            if u.scope != TOP:
                spots.add(InComp(u.scope.components[0]))
            else:
                spots.add(InSection(_section(v, u)))
        if len(spots) != 1:
            continue
        spot = spots.pop()
        if spot == InSection(Unmarked()) \
                or spot == InSection(section_at(solver, TOP, d.span.first)):
            continue
        out.append(lint(d.span.first, LintMarked(
            Category.DECL_PLACEMENT, LintSentence.DECL_PLACEMENT, d.name,
            spot.section.marker if isinstance(spot, InSection)
            and isinstance(spot.section, UnderMarker) else None,
            spot.comp if isinstance(spot, InComp) else None)))
    return out


@quotes("style.md", "Bans",
        "Arithmetic, raw aggregates, and `range` are banned.")
def check_argmax(solver: Solver, runs: Runs) -> list[Finding]:
    """`beaten(X) :- score(X, N), score(_, N2), N2 > N`, read only under
    negation, a hint: an aggregate in disguise; read it through a lib
    component. Serves the purest form."""
    v = view(solver, runs)
    out: list[Finding] = []
    for u in v.program_units():
        if u.body is None:
            continue
        shaped = True
        for body in flatten(u.body):
            atoms = [x.atom for x in body
                     if isinstance(x, AtomLiteral) and not x.negated]
            cmps = [x for x in body if isinstance(x, Comparison)]
            if len(body) != 3 or len(atoms) != 2 or len(cmps) != 1 \
                    or cmps[0].op not in (ComparisonOperator.LT,
                                          ComparisonOperator.GT) \
                    or atoms[0].relation != atoms[1].relation:
                shaped = False
                break
            cvars = literal_vars(cmps[0])
            v0, v1 = literal_vars(atoms[0]), literal_vars(atoms[1])
            if not (cvars & v0) or not (cvars & v1):
                shaped = False
                break
            head = literal_vars(u.head)
            if (v0 - v1) & head and (v1 - v0) & head:
                shaped = False
                break
        if not shaped:
            continue
        d = v.head(u)
        if d is None:
            continue
        uses = v.uses(d)
        if uses and all(n for _u, _a, n in uses):
            out.append(lint(_line(u),
                            LintNamed(Category.ARGMAX, LintSentence.ARGMAX,
                                      (u.head.relation.name,))))
    return out


# Task constants


@dataclass(frozen=True)
class Const:
    """Params data, or a lib relation that reads no grid."""


@dataclass(frozen=True)
class Example:
    """The runner's per-example fills."""


type Target = Const | Example | RelNode | InstanceNode
"""Where an atom's value comes from."""

CONST = Const()
EXAMPLE = Example()


def _target(v: View, unit: Unit, atom: Atom) -> Target:
    """Where an atom's value comes from: `CONST` for Params data and lib
    relations that read no grid, `EXAMPLE` for the runner's per-example
    fills, else the relation or instance the taint runs through."""
    r = v.index.resolve(atom.relation, unit.scope)
    if atom.relation.instances:
        if not isinstance(r, Resolved) or not r.through:
            return EXAMPLE
        inst = v.decls.get(r.through[0])
        if isinstance(inst, Instance) and inst.component == PARAMS:
            return CONST
        return InstanceNode(r.through[0])
    if not isinstance(r, Resolved):
        return EXAMPLE if atom.relation.name in EXAMPLE_SOURCES else CONST
    d = v.decls.get(r.declaration)
    if not isinstance(d, RelationDecl) or v.is_lib(d):
        return EXAMPLE if atom.relation.name in EXAMPLE_SOURCES else CONST
    if v.comp_of(d.scope) == PARAMS:
        return CONST
    return RelNode(d.id)


def _const_targets(v: View) -> set[Target]:
    """The relations and instances whose derivations reach no per-example
    source: named task constants."""
    heads: dict[Target, list[Unit]] = {}
    for u in v.program.units:
        t = _target(v, u, u.head)
        if isinstance(t, RelNode | InstanceNode):
            heads.setdefault(t, []).append(u)
    tainted: set[Target] = set()
    changed = True
    while changed:
        changed = False
        for t, units in heads.items():
            if t in tainted:
                continue
            if any((b := _target(v, u, a)) == EXAMPLE
                   or b in tainted
                   for u in units for a in atoms_read(u)):
                tainted.add(t)
                changed = True
    return set(heads) - tainted


@quotes("solver-file.md", "Params",
        "Params contains the parameterization and what derives from it.")
@quotes("principles.md", "Stored or derived",
        "A value that follows from another parameter in every variant task "
        "is derived data rather than a second parameter.")
def check_const_join(solver: Solver, runs: Runs) -> list[Finding]:
    """A variable internal to a clause's Params reads, a hint: the join
    derives a task constant, which the corpus names in its own relation;
    reads that share no variable form a product one stored relation
    replaces. Quiet inside Params and under a head that is itself a task
    constant. Serves the purest form."""
    v = view(solver, runs)
    consts = _const_targets(v)
    out: list[Finding] = []
    for u in v.program_units():
        if u.body is None or v.comp_of(u.scope) == PARAMS:
            continue
        if _target(v, u, u.head) in consts:
            continue
        seen: set[tuple[LintSentence, tuple[str, ...], tuple[str, ...]]] = set()
        for body in flatten(u.body):
            creads = [x for x in body if isinstance(x, AtomLiteral)
                      and x.atom.relation.instances
                      and _target(v, u, x.atom) == CONST]
            if len(creads) < 2:
                continue
            cvars = set().union(*(literal_vars(x) for x in creads))
            others = literal_vars(u.head)
            for x in body:
                if not any(x is c for c in creads):
                    others |= literal_vars(x)
            internal = cvars - others
            if not internal:
                continue
            rels: list[str] = []
            for x in creads:
                s = x.atom.relation.text
                if s not in rels:
                    rels.append(s)
            sets = [literal_vars(x) for x in creads]
            disjoint = all(not (a & b) for i, a in enumerate(sets)
                           for b in sets[i + 1:])
            if len(rels) > 1 and disjoint:
                key = (LintSentence.CONST_PRODUCT, tuple(rels), ())
            else:
                key = (LintSentence.CONST_JOIN, tuple(rels),
                       tuple(sorted(internal)))
            if key in seen:
                continue
            seen.add(key)
            out.append(lint(creads[0].atom.line, LintNamed(
                Category.CONST_JOIN, key[0], key[1], key[2])))
    return out


# Common subexpressions


def _canon(window: Sequence[BodyLiteral | Atom]
           ) -> tuple[BodyLiteral | Atom, ...] | None:
    """The window's literals written with each variable renamed by the
    order of its first occurrence; None where the window holds no
    atom."""
    if not any(isinstance(x, AtomLiteral | Atom) for x in window):
        return None
    terms: dict[str, Term] = {}
    for x in window:
        for name in _ordered_vars(x):
            if name not in terms:
                terms[name] = Variable(f"v{len(terms)}")
    return bare(tuple(substituted_atom(x, terms) if isinstance(x, Atom)
                      else substituted_literal(x, terms) for x in window))


def _ordered_vars(x: BodyLiteral | Atom) -> Iterator[str]:
    terms: tuple[Term, ...]
    if isinstance(x, Atom):
        terms = x.args
    elif isinstance(x, Disjunction):
        for b in x.branches:
            for y in b:
                yield from _ordered_vars(y)
        return
    else:
        terms = literal_terms(x, True)
    for t in terms:
        for s in subterms(t, into_aggregates=True):
            if isinstance(s, Variable):
                yield s.name


@quotes("style.md", "Disjunction",
        "Clauses that share a head and a frame belong in one clause.")
def check_common_subexpr(solver: Solver, runs: Runs) -> list[Finding]:
    """The same run of literals, up to renaming, in two bodies of one scope,
    a hint. A pair that spans choices, different sections or heads bound to
    different choice tags, stays quiet, and so does a later body that
    negates the earlier head. Serves the purest form."""
    v = view(solver, runs)
    tags = set(_tags(solver, v))
    seen: dict[tuple[object, ...], Unit] = {}
    reported: set[tuple[int, int]] = set()
    out: list[Finding] = []
    for u in v.program_units():
        body = list(u.body or ())
        n = len(body)
        for width in range(n, COMMON_SUBEXPR_MIN - 1, -1):
            for start in range(0, n - width + 1):
                canon = _canon(body[start:start + width])
                if canon is None:
                    continue
                sig = (u.scope, *canon)
                prev = seen.get(sig)
                if prev is not None and prev.span != u.span:
                    pair = (_line(prev), _line(u))
                    if pair not in reported:
                        reported.add(pair)
                        f = _subexpr(v, tags, width, prev, u)
                        if f is not None:
                            out.append(f)
                else:
                    seen.setdefault(sig, u)
    return out


def _line(u: Unit) -> int:
    return u.span.first if u.span is not None else u.head.line


def _section(v: View, u: Unit) -> Section:
    """The section a unit stands in (`solver.model.section_at`)."""
    return section_at(v.solver, u.scope, _line(u))


def _subexpr(v: View, tags: set[str], width: int, prev: Unit, cur: Unit
             ) -> Finding | None:
    if _section(v, prev) != _section(v, cur):
        return None
    if head_ctors(prev) & tags != head_ctors(cur) & tags:
        return None
    if any(isinstance(x, AtomLiteral) and x.negated
           and not x.atom.relation.instances
           and x.atom.relation.name == prev.head.relation.name
           for body in flatten(cur.body or ()) for x in body):
        return None
    merge = _canon([prev.head]) == _canon([cur.head])
    if not merge and width < 3:
        return None
    return lint(_line(cur), LintCounted(
        Category.COMMON_SUBEXPR,
        LintSentence.COMMON_SUBEXPR_MERGE if merge
        else LintSentence.COMMON_SUBEXPR,
        (prev.head.relation.name,), width, _line(prev)))


# Lib idioms


def _other_member(solver: Solver, v: View) -> dict[str, str]:
    """Each two-member orientation type with the lib relation that states
    the other member: the first relation, in the lib's order, of two
    columns of the type whose clauses are the facts pairing each member
    with the other."""
    pairs = {t: m for t, m in solver.lib.orientation_types.items()
             if len(m) == 2}
    facts: dict[str, set[tuple[str, ...]]] = {}
    other: set[str] = set()
    for u in v.program.units:
        if u.span is None or own(u.span) or u.scope != TOP \
                or u.head.relation.instances:
            continue
        if u.body is None and all(isinstance(a, DefinedName)
                                  for a in u.head.args):
            facts.setdefault(u.head.relation.name, set()).add(
                tuple(a.name for a in u.head.args
                      if isinstance(a, DefinedName)))
        else:
            other.add(u.head.relation.name)
    out: dict[str, str] = {}
    for d in v.program.relations:
        if own(d.span) or d.scope != TOP or d.name in other \
                or len(d.columns) != 2:
            continue
        t = d.columns[0].type
        if t != d.columns[1].type or t not in pairs or t in out:
            continue
        a, b = pairs[t]
        if facts.get(d.name) == {(a, b), (b, a)}:
            out[t] = d.name
    return out


@quotes("procedure.md", "Simplify",
        "Reimplements what the lib provides.")
def check_comp_idiom(solver: Solver, runs: Runs) -> list[Finding]:
    """A lib component's defining rule, or a lib relation, written out by
    hand: one relation read twice with a `!=` between the two reads, a hint.
    Serves the purest form: the lib names the idiom."""
    v = view(solver, runs)
    members = _other_member(solver, v)
    out: list[Finding] = []
    for u in v.program_units():
        if u.body is None:
            continue
        head_vars = literal_vars(u.head)
        seen: set[tuple[int, int]] = set()
        for flat in flatten(u.body):
            neq = [x for x in flat if isinstance(x, Comparison)
                   and x.op == ComparisonOperator.NE
                   and isinstance(x.lhs, Variable)
                   and isinstance(x.rhs, Variable)]
            if not neq:
                continue
            atoms = [x.atom for x in flat
                     if isinstance(x, AtomLiteral) and not x.negated]
            local = [a for a in atoms if not v.is_lib(v.relation(u, a))]
            sets = [a for a in atoms if any(a is x for x in local)
                    or a.relation.instances
                    or a.relation.name in EXAMPLE_SOURCES]
            for i, a in enumerate(sets):
                for b in sets[i + 1:]:
                    if (id(a), id(b)) in seen:
                        continue
                    f = _comp_idiom(v, members, u, a, b, atoms, neq,
                                    head_vars)
                    if f is not None:
                        seen.add((id(a), id(b)))
                        out.append(f)
    return out


def _comp_idiom(v: View, members: dict[str, str], unit: Unit, a: Atom,
                b: Atom, atoms: list[Atom], neq: list[Comparison],
                head_vars: set[str]) -> Finding | None:
    if a.relation != b.relation or len(a.args) != len(b.args) \
            or len(a.args) < 2:
        return None
    if sum(1 for x in atoms if x.relation == a.relation) > 2:
        return None
    diff = [i for i, (x, y) in enumerate(zip(a.args, b.args))
            if bare(x) != bare(y)]

    def compared(i: int) -> Comparison | None:
        x, y = a.args[i], b.args[i]
        if not (isinstance(x, Variable) and isinstance(y, Variable)):
            return None
        return next((c for c in neq
                     if {c.lhs, c.rhs} == {x, y}), None)

    hits = [(i, c) for i in diff if (c := compared(i)) is not None]
    if len(hits) != 1:
        return None
    k, cmp = hits[0]
    x, y = a.args[k], b.args[k]
    assert isinstance(x, Variable) and isinstance(y, Variable)
    if x.name in head_vars or y.name in head_vars:
        return None
    if any(z is not a and z is not b
           and {x.name, y.name} <= literal_vars(z) for z in atoms):
        return None
    code: tuple[Code, ...] = (a, b, replace(cmp, lhs=x, rhs=y))
    if len(diff) == 1:
        cols = v.column_types(unit, a)
        if cols is None:
            return None
        rel = members.get(cols[k])
        if rel is None:
            return None
        return lint(a.line, LintCode(
            Category.COMP_IDIOM, LintSentence.COMP_IDIOM_MEMBER, code,
            (Atom(RelationName((), rel), (x, y), a.line),)))
    if len(diff) != 2:
        return None
    (p,) = [i for i in diff if i != k]
    ap, bp = a.args[p], b.args[p]
    if not (isinstance(ap, Variable) and isinstance(bp, Variable)):
        return None
    link = _image_link(ap.name, bp.name, atoms)
    if link is None:
        return None
    return lint(a.line, LintCode(
        Category.COMP_IDIOM, LintSentence.COMP_IDIOM_IMAGE, code, (),
        (link, IMAGE_COMPS[link])))


def _image_link(p: str, q: str, atoms: list[Atom]) -> str | None:
    """The lib relation carrying `p` onto `q`, `apply` for a D4 image and
    `compose` for a shift, where one stands in the body."""
    for atom in atoms:
        name = atom.relation.name
        if atom.relation.instances or name not in IMAGE_COMPS \
                or len(atom.args) != 3:
            continue
        names = [x.name if isinstance(x, Variable) else None
                 for x in atom.args]
        src = names[:2] if name == COMPOSE else names[1:2]
        if names[2] in (p, q) and ({p, q} - {names[2]}) & set(src):
            return name
    return None

