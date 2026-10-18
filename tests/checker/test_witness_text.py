"""The solver checker reports a `@witness` line whose plausibility or
verdict differs from those of the first line of its id: one witness has
one verdict (docs/handbook/principles.md#witnesses)."""

from dataclasses import replace

from checker import Runs
from checker.finding import AtLine, Kind
from checker.payloads.witness import WitnessTextDiffers
from checker.witness import check_witness_lines
from engine import DeclId, Limits
from solver.annotations import (
    NamedVerdict,
    Plausibility,
    Verdict,
    VerdictWord,
    WitnessLine,
)
from solver.model import Choice, ChoicePoint, ConstructorBranch
from solver.witness import Entry, Groups, WitnessFile
from tests.checker.build import Builder, FakeEngine, annotations, solver


class _Engine(FakeEngine):
    """A fake engine that reads a constructor written with `$`."""

    def prefixed(self, text: str) -> str | None:
        return text[1:] if text.startswith("$") else None


def _point(field: str, *ctors: str) -> ChoicePoint:
    return ChoicePoint((field,), field, DeclId(0), tuple(
        ConstructorBranch(c, (), (), 1, True) for c in ctors))


def _witness(line: int, constructor: str, verdict: Verdict) -> WitnessLine:
    return WitnessLine("w1", Plausibility.VARIANT, verdict, line, (), (),
                       None, constructor)


def _found(second: Verdict, first: Verdict = VerdictWord.CONCEPT,
           entry: bool = False) -> list[object]:
    b = Builder()
    b.relation("out", ("x", "number"), line=1)
    s = solver(b.program(), annotations(witnesses=(
        _witness(3, "a", first), _witness(7, "b", second))))
    s = replace(
        s, engine=_Engine(),
        choice=Choice(DeclId(0), (), (_point("p", "P0", "A"),
                                      _point("q", "Q0", "B"))),
        witness_file=WitnessFile("0000test", (Entry(
            "w1", "", ((0,),), (), Groups(())),)) if entry else None)
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


def test_names_whose_parts_stand_in_another_order_are_one_verdict() -> None:
    assert _found(NamedVerdict("$B & $A"), NamedVerdict("$A & $B")) == []


def test_other_beside_a_verdict_is_reported_where_no_entry_has_the_id(
) -> None:
    assert _found(VerdictWord.OTHER) == [
        (Kind.ANNOTATION, AtLine(7),
         WitnessTextDiffers("w1", 3, Plausibility.VARIANT,
                            VerdictWord.CONCEPT))]


def test_other_beside_a_verdict_is_not_reported_where_an_entry_has_the_id(
) -> None:
    assert _found(VerdictWord.OTHER, entry=True) == []
