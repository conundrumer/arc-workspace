"""The variables that body literals of a parsed Souffle solver name."""

from engine.program import Aggregate, AtomLiteral, Comparison, Disjunction, Variable


def collect_vars(lits, out: set[str]) -> None:
    """Add to `out` the name of each variable that `lits` name, within
    aggregates and disjunctions."""
    def term(t):
        if isinstance(t, Variable):
            out.add(t.name)
        for a in getattr(t, "args", ()) or ():
            term(a)
        for x in ("lhs", "rhs", "arg", "term", "expr"):
            if hasattr(t, x) and getattr(t, x) is not None and not isinstance(getattr(t, x), str):
                term(getattr(t, x))
        if isinstance(t, Aggregate):
            collect_vars(t.body, out)
    for l in lits:
        if isinstance(l, AtomLiteral):
            for a in l.atom.args:
                term(a)
        elif isinstance(l, Comparison):
            term(l.lhs)
            term(l.rhs)
        elif isinstance(l, Disjunction):
            for b in l.branches:
                collect_vars(b, out)
