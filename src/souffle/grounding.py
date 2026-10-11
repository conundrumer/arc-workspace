"""The variables a program leaves ungrounded, read from its units before
any run: Souffle rejects such a program, so a run of it is not made. An
atom of a relation declared `inline` is read as Souffle reads it once it
inlines the relation, and only a variable of the program's own clause, or
a wildcard of an inline atom of that clause, named as `_`, is named, since
the variable Souffle names there is one of the inline rule, under a name
the program does not hold."""

from collections.abc import Callable, Iterable, Iterator
from dataclasses import replace
from itertools import count, product

from engine.engine import UngroundedVariable
from engine.program import (
    Aggregate,
    Atom,
    AtomLiteral,
    BodyLiteral,
    BoolLiteral,
    Cast,
    Comparison,
    ComparisonOperator,
    ConstructorTerm,
    DeclId,
    Disjunction,
    Program,
    Qualifier,
    RecordTerm,
    Scope,
    Term,
    Unit,
    Variable,
    Wildcard,
    literal_aggregates,
    own,
    subterms,
    with_literal_terms,
    with_subterms,
)
from souffle.index import Tree, tree_of

type Conjunct = AtomLiteral | Comparison
"""A literal of a body with its disjunctions split (`_conjunctions`)."""


def ungrounded(program: Program) -> UngroundedVariable | None:
    """The first variable that a rule of the program's own text leaves
    ungrounded, in the order of the units; None where there is none. A
    rule stands in the program's own text at the top level or in a
    component that an instance or another component names. Each rule is
    read as Souffle reads it, one clause per choice of a branch of each
    disjunction (`_first_ungrounded`). A rule of an inline relation is
    read only where an atom of the relation stands, since Souffle removes
    the rule once it inlines it."""
    named = {i.component for i in program.instances} \
        | {c.base for c in program.components if c.base is not None}
    inline = _Inline(program)
    for unit in program.units:
        if unit.body is None or not own(unit.span) \
                or not set(unit.scope.components) <= named \
                or inline.declaration(unit.head, unit.scope) is not None:
            continue
        found = _first_ungrounded(unit, inline)
        if found is not None:
            return found
    return None


def grounded_without(program: Program, unit: Unit, atom: Atom) -> bool:
    """Whether the rest of the clause of `unit` grounds every variable of
    `atom`, an atom of the clause's body or of a disjunction branch in it,
    found by identity: each clause the body gives (`_conjunctions`) that
    holds `atom`, with `atom` left out and its arguments added to the
    head, leaves no variable ungrounded (`_first_ungrounded`). Raises
    `ValueError` where `atom` stands in no such place."""
    def is_atom(x: Conjunct) -> bool:
        return isinstance(x, AtomLiteral) and x.atom is atom

    holding = [c for c in _conjunctions(unit.body or ())
               if any(is_atom(x) for x in c)]
    if not holding:
        raise ValueError("the atom stands in no body literal or disjunction "
                         "branch of the unit")
    inline = _Inline(program)
    head = replace(unit.head, args=unit.head.args + atom.args)
    return all(_first_ungrounded(replace(unit, head=head, body=tuple(
        x for x in c if not is_atom(x))), inline) is None for c in holding)


class _Inline:
    """The relations of a program declared `inline`, each with its rules:
    the units of the text that declares it whose head names it with no
    instance. A unit of another text that feeds the relation, through an
    instance or from a component that extends the declaring one, is left
    out, since it feeds the relation of some instances only."""

    def __init__(self, program: Program):
        decls = [r for r in program.relations
                 if Qualifier.INLINE in r.qualifiers]
        self._names = {r.name for r in decls}
        self._tree: Tree | None = tree_of(program) if decls else None
        self._rules: dict[DeclId, list[Unit]] = {r.id: [] for r in decls}
        for unit in program.units:
            got = self.declaration(unit.head, unit.scope)
            if got is not None and got[1] == unit.scope \
                    and not unit.head.relation.instances:
                self._rules[got[0]].append(unit)

    def declaration(self, atom: Atom, scope: Scope
                    ) -> tuple[DeclId, Scope] | None:
        """The inline relation `atom` names when read in `scope`, as its
        declaration's id and the scope that declares it; None where it
        names another relation."""
        if self._tree is None or atom.relation.name not in self._names:
            return None
        hit = self._tree.resolve(atom.relation, scope)
        if hit is None or Qualifier.INLINE not in hit.decl.qualifiers:
            return None
        return hit.decl.id, hit.decl.scope

    def clauses(self, clause: tuple[Conjunct, ...], scope: Scope,
                fresh: Iterator[int], within: frozenset[DeclId] = frozenset()
                ) -> Iterator[tuple[Conjunct, ...]]:
        """The clauses Souffle makes of `clause`, read in `scope`, once it
        inlines each positive atom of an inline relation: one per choice
        of a rule of each such atom, in which the atom gives way to an
        equality of each of its arguments with the rule head's, then the
        rule's body, inlined in turn, the rule's variables renamed apart
        and each wildcard of the atom made a variable of its own, as
        Souffle names them. A negated atom stays as it is, as does an atom
        of a relation of `within`, whose rules reach themselves, which
        Souffle refuses."""
        parts: list[list[tuple[Conjunct, ...]]] = []
        for lit in clause:
            got = None if not isinstance(lit, AtomLiteral) or lit.negated \
                else self.declaration(lit.atom, scope)
            if got is None or got[0] in within:
                parts.append([(lit,)])
                continue
            assert isinstance(lit, AtomLiteral)
            parts.append([c for rule in self._rules[got[0]]
                          for c in self._inlined(lit.atom, rule, fresh,
                                                 within | {got[0]})])
        return _choices(parts)

    def own_wildcards(self, clause: tuple[Conjunct, ...], scope: Scope,
                      fresh: Iterator[int]
                      ) -> tuple[tuple[Conjunct, ...], set[str]]:
        """`clause`, read in `scope`, with each wildcard of its positive
        atoms of inline relations made a variable of its own (`_named`),
        and the names of those variables."""
        out: list[Conjunct] = []
        wildcards: set[str] = set()
        for lit in clause:
            if isinstance(lit, AtomLiteral) and not lit.negated \
                    and self.declaration(lit.atom, scope) is not None:
                args = tuple(_named(a, fresh) for a in lit.atom.args)
                wildcards |= {v for t in args for v in _variables(t)} \
                    - {v for t in lit.atom.args for v in _variables(t)}
                lit = replace(lit, atom=replace(lit.atom, args=args))
            out.append(lit)
        return tuple(out), wildcards

    def _inlined(self, atom: Atom, rule: Unit, fresh: Iterator[int],
                 within: frozenset[DeclId]) -> Iterator[tuple[Conjunct, ...]]:
        """The clauses that stand in an atom's place for one rule of its
        relation (`clauses`)."""
        n = next(fresh)

        def rename(name: str) -> str:
            return f"<inlined_{name}_{n}>"

        bound = tuple(
            Comparison(ComparisonOperator.EQ, _named(a, fresh),
                       _named(_renamed(h, rename), fresh), atom.line)
            for a, h in zip(atom.args, rule.head.args, strict=True))
        body = () if rule.body is None \
            else tuple(_renamed_literal(x, rename) for x in rule.body)
        for alternative in _conjunctions(body):
            for inner in self.clauses(alternative, rule.scope, fresh, within):
                yield (*bound, *inner)


def _first_ungrounded(unit: Unit, inline: _Inline
                      ) -> UngroundedVariable | None:
    """The first variable of one of the rule's clauses, in the order its
    head and body name them, that the clause does not ground, each clause
    read in each form Souffle gives it once it inlines its atoms of inline
    relations (`_Inline.clauses`). A clause grounds a variable that
    stands, alone or in a record or a constructor, in a positive atom of
    a relation not inlined, or in any positive atom of an aggregate's
    body, which is not inlined here; and, by `=`, each such
    variable of one side where the other side's variables are grounded,
    an aggregate counting as grounded. A variable that stands only in an
    aggregate is not read, so a variable named here is one Souffle
    reports, and Souffle may report one not named here. A wildcard of a
    positive atom of an inline relation in the clause itself is read as a
    variable of its own, as Souffle reads it, and is named as `_`."""
    assert unit.body is not None
    fresh = count()
    for clause in _conjunctions(unit.body):
        clause, wildcards = inline.own_wildcards(clause, unit.scope, fresh)
        occurrences = list(_occurrences(unit.head, clause))
        for inlined in inline.clauses(clause, unit.scope, fresh):
            grounded = _grounded(inlined)
            for name, line in occurrences:
                if name not in grounded:
                    return UngroundedVariable(
                        "_" if name in wildcards else name, line or None)
    return None


def _conjunctions(body: tuple[BodyLiteral, ...]
                  ) -> Iterator[tuple[Conjunct, ...]]:
    """The clauses a body gives, one per choice of a branch of each
    disjunction, in the order of the branches."""
    parts: list[list[tuple[Conjunct, ...]]] = []
    for lit in body:
        match lit:
            case AtomLiteral() | Comparison():
                parts.append([(lit,)])
            case Disjunction(branches=branches):
                parts.append([c for b in branches for c in _conjunctions(b)])
            case BoolLiteral():
                pass
    return _choices(parts)


def _choices(parts: list[list[tuple[Conjunct, ...]]]
             ) -> Iterator[tuple[Conjunct, ...]]:
    """The clauses that one choice of an alternative of each part gives,
    the parts in order."""
    for choice in product(*parts):
        yield tuple(x for c in choice for x in c)


def _grounded(clause: tuple[Conjunct, ...]) -> set[str]:
    """The variables a clause grounds (`_first_ungrounded`)."""
    out = _in_atoms(clause)
    equalities = [c for c in clause if isinstance(c, Comparison)
                  and c.op == ComparisonOperator.EQ]
    while True:
        before = len(out)
        for c in equalities:
            if set(_variables(c.rhs)) <= out:
                out |= _bound(c.lhs)
            if set(_variables(c.lhs)) <= out:
                out |= _bound(c.rhs)
        if len(out) == before:
            return out


def _in_atoms(body: Iterable[BodyLiteral]) -> set[str]:
    """The variables the positive atoms of a body ground, those of the
    aggregates its literals hold included, through disjunctions."""
    out: set[str] = set()
    for lit in body:
        match lit:
            case AtomLiteral(atom=atom, negated=negated):
                if not negated:
                    out |= set().union(*(_bound(t) for t in atom.args))
            case Disjunction(branches=branches):
                for b in branches:
                    out |= _in_atoms(b)
            case Comparison() | BoolLiteral():
                pass
        for agg in literal_aggregates(lit):
            out |= _in_atoms(agg.body)
    return out


def _bound(term: Term) -> set[str]:
    """The variables a grounded term grounds: itself where it is one, and
    those of the records, constructors and casts it is."""
    match term:
        case Variable(name=name):
            return {name}
        case RecordTerm(args=args) | ConstructorTerm(args=args):
            return set().union(*(_bound(a) for a in args))
        case Cast(term=inner):
            return _bound(inner)
    return set()


def _occurrences(head: Atom, clause: tuple[Conjunct, ...]
                 ) -> Iterator[tuple[str, int]]:
    """The variables of a clause outside its aggregates, each with the
    line it stands on, 0 for a part an operation wrote: the head's, then
    the body's, left to right."""
    for t in head.args:
        yield from ((v, head.line) for v in _variables(t))
    for lit in clause:
        if isinstance(lit, AtomLiteral):
            for t in lit.atom.args:
                yield from ((v, lit.atom.line) for v in _variables(t))
        else:
            for t in (lit.lhs, lit.rhs):
                yield from ((v, lit.line) for v in _variables(t))


def _variables(term: Term) -> Iterator[str]:
    """The variables of a term outside its aggregates, left to right."""
    if isinstance(term, Aggregate):
        return
    if isinstance(term, Variable):
        yield term.name
    for t in subterms(term):
        yield from _variables(t)


def _named(term: Term, fresh: Iterator[int]) -> Term:
    """`term` with each wildcard it holds outside its aggregates made a
    variable that stands nowhere else."""
    if isinstance(term, Wildcard):
        return Variable(f"<underscore_{next(fresh)}>")
    if isinstance(term, Aggregate):
        return term
    return with_subterms(term, lambda t: _named(t, fresh))


def _renamed(term: Term, rename: Callable[[str], str]) -> Term:
    """`term` with each variable it holds, those of its aggregates
    included, named as `rename` gives it."""
    match term:
        case Variable(name=name):
            return Variable(rename(name))
        case Aggregate(expr=expr, body=body):
            return replace(term, expr=None if expr is None
                           else _renamed(expr, rename),
                           body=tuple(_renamed_literal(x, rename) for x in body))
    return with_subterms(term, lambda t: _renamed(t, rename))


def _renamed_literal(lit: BodyLiteral, rename: Callable[[str], str]
                     ) -> BodyLiteral:
    """`lit` with each variable it holds named as `rename` gives it
    (`_renamed`)."""
    if isinstance(lit, Disjunction):
        return replace(lit, branches=tuple(
            tuple(_renamed_literal(x, rename) for x in b) for b in lit.branches))
    return with_literal_terms(lit, lambda t: _renamed(t, rename))
