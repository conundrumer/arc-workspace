"""The solver's cases, and what an `@ignore: derive` line takes out of
them. A wrong case of the solver runs as well as a right one, so no run
shows it."""

from pathlib import Path

import pytest

from engine import AdtValue, DeclId, Limits, RelationName, Tuples
from engine.program import AtomLiteral, ConstructorTerm, Variable
from solver import model
from solver.model import Case, DeriveBranch, StoredAtDerive
from tests.solver.fake import (
    FakeEngine,
    adt,
    atom,
    comment,
    component,
    instance,
    program,
    relation,
    unit,
)

A, B = AdtValue("A", ()), AdtValue("B", ())
BG, FG, MG = DeclId(10), DeclId(13), DeclId(15)
P, C, CH = Variable("P"), Variable("C"), Variable("Ch")


@pytest.fixture
def solvers(root: Path) -> Path:
    (root / "programs" / "solvers" / "0000aaaa.dl").write_text("")
    return root


def _cases(bg_ignore: str, fg_ignore: str) -> tuple[Case, ...]:
    """The cases of a solver whose bases both read `bg` and `fg` and
    only `B` reads `mg`, each under a `@derive` line, with an `@ignore`
    line under the lines on `bg` and `fg`."""
    parsed = program(
        types=[adt(1, "Choice", 2, [("A", 3), ("B", 4)])],
        relations=[
            relation(5, "impl_choice", 5, columns=[("ch", "Choice")]),
            relation(10, "bg", 10, ("Params",), [("c", "Color")]),
            relation(13, "fg", 13, ("Params",), [("c", "Color")]),
            relation(15, "mg", 15, ("Params",), [("c", "Color")]),
            relation(18, "out", 18, columns=[
                ("p", "Position"), ("col", "Color"), ("ch", "Choice")]),
            relation(30, "propose", 31, ("DominantColor",), [("c", "Color")]),
            relation(34, "propose", 35, ("RarestColor",), [("c", "Color")]),
        ],
        components=[component(7, "Params", 7, 16),
                    component(29, "DominantColor", 30, 32),
                    component(33, "RarestColor", 34, 36)],
        instances=[instance(17, "params", "Params", 17)],
        units=[
            # Both cases read bg and fg; only B reads mg.
            unit(1, 20, atom(20, "out", P, C, CH), [
                AtomLiteral(atom(20, "params.bg", C), False),
                AtomLiteral(atom(20, "params.fg", C), True)]),
            unit(2, 21, atom(21, "out", P, C, ConstructorTerm("B", ())), [
                AtomLiteral(atom(21, "params.mg", C), False)]),
        ],
        comments=[
            comment(1, "// 0000aaaa"),
            comment(8, "// @derive DominantColor: ordinary derived", BG),
            comment(9, bg_ignore, BG),
            comment(11, "// @derive DominantColor: ordinary derived", FG),
            comment(12, fg_ignore, FG),
            comment(14, "// @derive DominantColor: ordinary derived", MG),
        ])
    impl = RelationName((), "impl_choice")
    engine = FakeEngine(parsed, lambda _p, _i, outputs: Tuples(
        {impl: ((A,), (B,))} if list(outputs) == [impl] else {}, 0.0))
    solver = model.load("0000aaaa", engine)
    assert solver.problems == ()
    assert StoredAtDerive("bg") in solver.branches
    got = model.cases(solver, engine, Limits(5.0, 10.0))
    assert isinstance(got, tuple)
    return got


def _derive(cases: tuple[Case, ...], parameter: str) -> DeriveBranch:
    return next(b for c in cases for b in c.branches
                if isinstance(b, DeriveBranch) and b.parameter == parameter)


def test_points_under_their_readers_and_ignores(solvers: Path) -> None:
    # The name leaves out the branch of the line it stands under.
    got = _cases("// @ignore: derive $B — fails Equivalence",
                 "// @ignore: derive — fails Subsumption")
    bg, mg = _derive(got, "bg"), _derive(got, "mg")
    assert got == (Case(A, ()), Case(A, (bg,)), Case(B, ()), Case(B, (mg,)))


def test_a_named_ignore_takes_its_line_branch_and_each_named_branch(
        solvers: Path) -> None:
    got = _cases("// @ignore: derive fg=stored — fails Equivalence",
                 "// @ignore: derive $B & bg=DominantColor — fails Subsumption")
    bg, fg, mg = (_derive(got, p) for p in ("bg", "fg", "mg"))
    assert set(got) == {
        Case(A, ()), Case(A, (fg,)), Case(A, (bg, fg)),
        Case(B, ()), Case(B, (fg,)), Case(B, (mg,)), Case(B, (fg, mg))}


def test_a_proposer_ignore_takes_its_one_derivation(solvers: Path) -> None:
    got = _cases("// @ignore: derive RarestColor — fails Fit",
                 "// @ignore: derive — fails Subsumption")
    bg, mg = _derive(got, "bg"), _derive(got, "mg")
    assert set(got) == {Case(A, ()), Case(A, (bg,)), Case(B, ()),
                        Case(B, (bg,)), Case(B, (mg,)), Case(B, (bg, mg))}
