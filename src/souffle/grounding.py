"""The variables a program leaves ungrounded, read from its units before
any run: Souffle rejects such a program, so a run of it is not made."""

from collections.abc import Iterable, Iterator
from itertools import product

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
    Disjunction,
    Program,
    RecordTerm,
    Term,
    Unit,
    Variable,
    literal_aggregates,
    own,
    subterms,
)

type Conjunct = AtomLiteral | Comparison
"""A literal of a body with its disjunctions split (`_conjunctions`)."""


def ungrounded(program: Program) -> UngroundedVariable | None:
    """The first variable that a rule of the program's own text leaves
    ungrounded, in the order of the units; None where there is none. A
    rule stands in the program's own text at the top level or in a
    component that an instance or another component names. Each rule is
    read as Souffle reads it, one clause per choice of a branch of each
    disjunction (`_first_ungrounded`)."""
    named = {i.component for i in program.instances} \
        | {c.base for c in program.components if c.base is not None}
    for unit in program.units:
        if unit.body is None or not own(unit.span) \
                or not set(unit.scope.components) <= named:
            continue
        found = _first_ungrounded(unit)
        if found is not None:
            return found
    return None


def _first_ungrounded(unit: Unit) -> UngroundedVariable | None:
    """The first variable of one of the rule's clauses, in the order its
    head and body name them, that the clause does not ground. A clause
    grounds a variable that stands in a positive atom, alone or in a
    record or a constructor, an aggregate's body included; and, by `=`,
    each such variable of one side where the other side's variables are
    grounded, an aggregate counting as grounded. A variable that stands
    only in an aggregate is not read, so a variable named here is one
    Souffle reports, and Souffle may report one not named here."""
    assert unit.body is not None
    for clause in _conjunctions(unit.body):
        grounded = _grounded(clause)
        for name, line in _occurrences(unit.head, clause):
            if name not in grounded:
                return UngroundedVariable(name, line or None)
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
