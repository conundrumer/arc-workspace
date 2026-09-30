"""An `@ignore` line dismisses the finding of its category on its
relation, and a line that dismisses nothing is itself a finding
(solver-file.md:134-136). A wrong dismissal hides a finding, which no run
shows."""

from checker import Runs, check_lint
from checker.finding import Kind, LintCounted, LintIgnore, LintSentence
from engine import Limits
from solver.annotations import IgnoreForm, IgnoreLine
from solver.category import Category
from tests.checker.build import (
    Builder,
    FakeEngine,
    annotations,
    atom,
    pos,
    solver,
    var,
)


LIMITS = Limits(10.0, 10.0)


def _program(ignored: Category):
    b = Builder()
    out = b.relation("out", ("x", "number"), line=1)
    a = b.relation("a", ("x", "number"), line=3)
    b.relation("p", ("x", "number"), line=5)
    b.relation("q", ("x", "number"), line=6)
    b.unit(atom("a", var("X"), line=4), pos(atom("p", var("X"), line=4)),
           pos(atom("q", var("X"), line=4)))
    b.unit(atom("out", var("X"), line=7), pos(atom("a", var("X"), line=7)))
    b.fact(atom("p", var("X"), line=8))
    b.fact(atom("q", var("X"), line=9))
    ignore = IgnoreLine(IgnoreForm.LINT, ignored, None, None, "judged", 2,
                        a.id)
    assert out.name == "out"
    s = solver(b.program(), annotations(ignores=(ignore,)))
    return s, Runs(FakeEngine(), s, LIMITS)  # type: ignore[arg-type]


def test_an_ignore_line_of_the_category_dismisses_the_hint() -> None:
    s, runs = _program(Category.SINGLE_CONSUMER)
    found = check_lint(s, runs)
    assert not [f for f in found
                if f.payload.category in (Category.SINGLE_CONSUMER,  # type: ignore[union-attr]
                                          Category.IGNORE)]


def test_an_ignore_line_of_another_category_is_idle_and_keeps_nothing(
) -> None:
    s, runs = _program(Category.DEAD)
    found = check_lint(s, runs)
    hints = [f.payload for f in found if f.kind == Kind.HINT]
    idle = [f.payload for f in found
            if isinstance(f.payload, LintIgnore)]
    assert [p for p in hints if isinstance(p, LintCounted)
            and p.category == Category.SINGLE_CONSUMER
            and p.names == ("a",) and p.on_relation]
    assert [p.sentence for p in idle] == [LintSentence.IDLE_IGNORE]
    assert idle[0].ignore.category == Category.DEAD
    assert idle[0].site is not None and idle[0].site.text == "a"
