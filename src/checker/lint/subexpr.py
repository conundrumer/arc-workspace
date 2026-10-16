"""The lint check on a run of literals two bodies of one scope share,
up to renaming (`common-subexpr`)."""

from collections.abc import Iterator, Sequence

from checker.finding import (
    Finding,
    LintCounted,
    LintSentence,
)
from checker.lint.view import (
    View,
    bare,
    choice_tags,
    flatten,
    head_ctors,
    lint,
    literal_terms,
    subterms,
    unit_line,
    unit_section,
    view,
)
from checker.runs import Runs
from engine.program import (
    Atom,
    AtomLiteral,
    BodyLiteral,
    Disjunction,
    Term,
    Unit,
    Variable,
)
from engine.quotes import quotes
from solver.aggregate import Solver
from solver.case_types import (
    substituted_atom,
    substituted_literal,
)
from solver.category import Category

COMMON_SUBEXPR_MIN = 2
"""The literals a shared window must span."""


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
    tags = set(choice_tags(solver, v))
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
                    pair = (unit_line(prev), unit_line(u))
                    if pair not in reported:
                        reported.add(pair)
                        f = _subexpr(v, tags, width, prev, u)
                        if f is not None:
                            out.append(f)
                else:
                    seen.setdefault(sig, u)
    return out


def _subexpr(v: View, tags: set[str], width: int, prev: Unit, cur: Unit
             ) -> Finding | None:
    if unit_section(v, prev) != unit_section(v, cur):
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
    return lint(unit_line(cur), LintCounted(
        Category.COMMON_SUBEXPR,
        LintSentence.COMMON_SUBEXPR_MERGE if merge
        else LintSentence.COMMON_SUBEXPR,
        (prev.head.relation.name,), width, unit_line(prev)))
