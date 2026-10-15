"""The lint checks on a clause head's columns: a literal zero in a head,
and one variable in two of a head's arguments. Each reads the heads of the
relations the solver's own text declares, those of an instance of a
component the solver declares too, and no head of a relation of an
instance of a lib component: the lib component fixes its columns, and what
such a head states is a value of the instance."""

from collections.abc import Iterator

from checker.finding import Finding, LintNamed, LintSentence
from checker.lint.bans import ZERO_MACROS
from checker.lint.view import View, lint, subterms, view
from checker.runs import Runs
from engine.program import DefinedName, NumberTerm, Unit, Variable
from engine.quotes import quotes
from solver.aggregate import Solver
from solver.category import Category


def _own_heads(v: View) -> Iterator[Unit]:
    """The units program style applies to whose head is a relation the
    solver's own text declares."""
    return (u for u in v.style_units() if not v.is_lib(v.head(u)))


@quotes("encoding.md", "Numbers",
        "**Zero is absence.** A `0` counts nothing that is present.")
def check_head_zero(solver: Solver, runs: Runs) -> list[Finding]:
    """A head that states `0` or `ZERO` in an argument, at any depth, a
    hint: a fact's head too."""
    v = view(solver, runs)
    out: list[Finding] = []
    for u in _own_heads(v):
        zeros = [solver.engine.text(t) for a in u.head.args for t in subterms(a)
                 if (isinstance(t, NumberTerm) and t.value == 0)
                 or (isinstance(t, DefinedName) and t.name in ZERO_MACROS)]
        if zeros:
            out.append(lint(u.head.line, LintNamed(
                Category.HEAD_ZERO, LintSentence.HEAD_ZERO,
                (u.head.relation.text,), tuple(dict.fromkeys(zeros))),
                (u.id,)))
    return out


@quotes("principles.md", "Stored or derived",
        "**Redundant value.** A value that follows from another parameter in "
        "every variant task is derived data rather than a second parameter.")
def check_head_repeat(solver: Solver, runs: Runs) -> list[Finding]:
    """A variable that stands in two of a rule head's arguments, at any
    depth, a hint."""
    v = view(solver, runs)
    out: list[Finding] = []
    for u in _own_heads(v):
        if u.body is None:
            continue
        seen: dict[str, int] = {}
        for a in u.head.args:
            for name in dict.fromkeys(t.name for t in subterms(a)
                                      if isinstance(t, Variable)):
                seen[name] = seen.get(name, 0) + 1
        repeated = tuple(n for n, k in seen.items() if k > 1)
        if repeated:
            out.append(lint(u.head.line, LintNamed(
                Category.HEAD_REPEAT, LintSentence.HEAD_REPEAT,
                (u.head.relation.text,), repeated), (u.id,)))
    return out
