"""The solver checker reports a `@witness` line whose plausibility or
verdict differs from those of the first line of its id: one witness has
one verdict (docs/handbook/principles.md#witnesses)."""

from checker import Runs
from checker.finding import AtLine, Kind
from checker.payloads.witness import WitnessTextDiffers
from checker.witness import check_witness_lines
from engine import Limits
from solver.annotations import (
    NamedVerdict,
    Plausibility,
    Verdict,
    VerdictWord,
    WitnessLine,
)
from tests.checker.build import Builder, FakeEngine, annotations, solver


def _witness(line: int, constructor: str, verdict: Verdict) -> WitnessLine:
    return WitnessLine("w1", Plausibility.VARIANT, verdict, line, (), (),
                       None, constructor)


def _found(second: Verdict) -> list[object]:
    b = Builder()
    b.relation("out", ("x", "number"), line=1)
    s = solver(b.program(), annotations(witnesses=(
        _witness(3, "a", VerdictWord.CONCEPT), _witness(7, "b", second))))
    runs = Runs(FakeEngine(), s, Limits(10.0, 10.0))  # type: ignore[arg-type]
    return [(f.kind, f.where, f.payload) for f in check_witness_lines(s, runs)]


def test_two_branches_that_give_one_witness_two_verdicts_are_reported(
) -> None:
    assert _found(NamedVerdict("b")) == [
        (Kind.ANNOTATION, AtLine(7),
         WitnessTextDiffers("w1", 3, Plausibility.VARIANT,
                            VerdictWord.CONCEPT))]


def test_two_branches_that_give_one_witness_one_verdict_are_not() -> None:
    assert _found(VerdictWord.CONCEPT) == []
