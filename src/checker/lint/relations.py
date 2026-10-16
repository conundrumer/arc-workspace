"""The relation-level lint checks on shapes that the corpus's edits
rewrite away, each mirroring an edit family observed across the solvers.
They read the relations of the scopes that hold program code, less the
case enumeration's."""

from collections.abc import Sequence

from checker.finding import (
    Code,
    Finding,
    LintCode,
    LintCounted,
    LintNamed,
    LintSentence,
)
from checker.lint.view import (
    TOP,
    View,
    aggregates,
    atoms_read,
    lint,
    literal_vars,
    subterms,
    term_vars,
    view,
)
from checker.runs import Runs
from engine.program import (
    AggregateOperator,
    Atom,
    AtomLiteral,
    BoolLiteral,
    Comparison,
    ConstructorTerm,
    DeclId,
    Instance,
    Intrinsic,
    IntrinsicCall,
    Qualifier,
    RecordTerm,
    RelationDecl,
    Term,
    Unit,
    Variable,
    Wildcard,
    own,
)
from engine.quotes import quotes
from solver.aggregate import Solver
from solver.case_types import (
    substituted_atom,
)
from solver.category import Category
from solver.graph import chain_relation
from solver.vocabulary import (
    DETERMINE,
    OUTPUT,
    PARAMS,
)

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


def _stored(v: View) -> frozenset[DeclId]:
    """The relations the solver's `@store` lines are choice points on: the
    declaration a bare line stands above, and the relation a line above an
    `.init` names (`solver.graph.chain_relation`)."""
    out: set[DeclId] = set()
    for s in v.solver.annotations.stores:
        if s.above is None:
            continue
        if s.relation is None:
            out.add(s.above)
            continue
        inst = v.program.declaration(s.above)
        if not isinstance(inst, Instance):
            continue
        d = chain_relation(v.program, inst.component, s.relation)
        if d is not None:
            out.add(d.id)
    return frozenset(out)


def _inlinable(v: View, decl: RelationDecl) -> bool:
    """Substituting the relation away is on the table: a derived relation
    other than `out`, a determined parameter or a relation a `@store` line
    is a choice point on (`_stored`), with no `choice-domain`, whose rules
    and uses share its scope. Substituting a `@store` relation away
    removes the choice point the line is a branch of."""
    if decl.scope == TOP and decl.name == OUTPUT.name:
        return False
    if v.comp_of(decl.scope) in (DETERMINE, PARAMS) \
            and decl.name in _determined(v):
        return False
    if decl.id in v.held(_stored):
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


def lib_inline(v: View) -> tuple[frozenset[str], frozenset[str]]:
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
                    has_wild(a) for a in lit.atom.args):
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


def has_wild(t: Term) -> bool:
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
    inline, negatable = v.held(lib_inline)
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
    inline, negatable = v.held(lib_inline)
    head_vars = {a.name for a in d.head.args if isinstance(a, Variable)}
    if v.is_lib(v.relation(d, atom)) and not atom.relation.instances \
            and atom.relation.name in inline:
        if atom.relation.name not in negatable \
                or literal_vars(atom) - head_vars \
                or any(has_wild(a) for a in atom.args):
            return False
    counts: dict[str, int] = {}
    for arg in atom.args:
        for name in term_vars(arg):
            counts[name] = counts.get(name, 0) + 1
    head_ok = all(isinstance(a, Variable) and a.name in counts
                  for a in d.head.args)
    nested_drop = any(
        isinstance(arg, RecordTerm | ConstructorTerm)
        and (has_wild(arg) or term_vars(arg) - head_vars)
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
