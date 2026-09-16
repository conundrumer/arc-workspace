"""`features`: which rules each case reaches, and what a run adds to that."""

from pathlib import Path

import pytest

from dl import cli, features_run, solve
from dl.corpus import literal_count
from dl.dlparse import parse
from dl.features import CaseFeatures, features_report
from dl.features_run import report_of
from dl.paths import all_stems
from dl.solve import PairResult, VariantResult, solver_file

STEM = "abcd1234"

TWO_CASES = """\
.type Choice = A {} | B {}

.decl out(p: Position, col: Color, c: Choice)

.comp Params {
    .decl a_p(n: number) a_p(1).
    .decl b_p(n: number) b_p(2).
    .decl both_p(n: number) both_p(3).
}
.init params = Params

.init inv = OffsetInvariance<Unit, Color>
inv.cell($U(), P, Col) :- in(P, Col).

.decl tag(c: Choice)
tag($A()).

.decl shared_rel(p: Position)
shared_rel(P) :- in(P, _), params.both_p(_).

out(P, Col, $A()) :-
    in(P, Col), shared_rel(P), params.a_p(N), N > 0,
    ( shared_rel(P) ; !shared_rel(P) ),
    K = count : { in(_, 1) }, K > 0.

out(P, Col, $B()) :-
    in(P, Col), shared_rel(P), params.b_p(_), inv.offset($U(), P).
"""

RECORD = """\
.type Dec = Object {} | Line {}
.type Extent = Tall {} | Mid {} | Short {}
.type Choice = [d: Dec, e: Extent]

.decl out(p: Position, col: Color, c: Choice)

.decl part(p: Position, d: Dec)
part(P, $Object()) :- in(P, _).
part(P, $Line()) :- in(P, _).

.decl span(p: Position, e: Extent)
span(P, $Tall()) :- in(P, _).
span(P, $Mid()) :- in(P, _).
span(P, $Short()) :- in(P, _).

out(P, Col, [$Object(), $Tall()]) :- in(P, Col), part(P, _), span(P, _).
"""


@pytest.fixture
def solvers(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A solvers directory of its own, with a sweep cache beside it."""
    monkeypatch.setattr(solve, "SOLVERS_DIR", tmp_path)
    monkeypatch.setattr(cli, "SWEEP_CACHE", tmp_path / "sweep")
    monkeypatch.setattr(cli, "build_functors", lambda: None)
    return tmp_path


def put(solvers: Path, source: str, stem: str = STEM) -> Path:
    path = solvers / f"{stem}.dl"
    path.write_text(source)
    return path


def rows(solvers: Path, source: str) -> dict[str, CaseFeatures]:
    put(solvers, source)
    return {r.case: r for r in features_report(STEM).cases}


def test_a_head_constructor_seeds_its_case_whatever_the_head_relation(solvers):
    by_case = rows(solvers, TWO_CASES)
    # `tag($A()).` heads no `out`, and is A's alone.
    assert by_case["A"].facts == 2  # tag and a_p
    assert by_case["B"].facts == 1  # b_p


def test_a_rule_two_cases_reach_is_shared(solvers):
    by_case = rows(solvers, TWO_CASES)
    assert by_case["A"].shared_rules == 1   # shared_rel
    assert by_case["A"].shared_facts == 1   # both_p
    assert by_case["A"].shared_atoms == by_case["B"].shared_atoms
    assert by_case["A"].reach_rules > by_case["A"].rules


def test_a_record_choice_gives_one_case_per_combination(solvers):
    by_case = rows(solvers, RECORD)
    assert list(by_case) == ["[Object, Tall]", "[Object, Mid]",
                             "[Object, Short]", "[Line, Tall]",
                             "[Line, Mid]", "[Line, Short]"]
    assert [r.case_index for r in by_case.values()] == list(range(6))
    assert all(r.cases_in_file == 6 for r in by_case.values())


def test_a_case_does_not_reach_another_case_s_constructor(solvers):
    by_case = rows(solvers, RECORD)
    # `[Object, Tall]` seeds on the `part($Object())` and `span($Tall())`
    # rules and on the `out` head that names both, and reaches no other
    # branch of either component.
    assert by_case["[Object, Tall]"].reach_rules == 3
    assert by_case["[Object, Mid]"].reach_rules == 2


@pytest.mark.skipif(not all_stems(), reason="no solvers in the corpus")
def test_every_solver_s_cases_and_shared_and_unreached_are_its_size():
    for stem in all_stems():
        report = features_report(stem)
        first = report.cases[0]
        total = (sum(r.atoms for r in report.cases)
                 + first.shared_atoms + first.unreached_atoms)
        assert total == literal_count(
            parse(solver_file(stem)[0].read_text())), stem


def _pair(named_grids) -> PairResult:
    variants = [
        VariantResult(name=name, ok=grid is not None, actual=grid or [],
                      error=None if grid is not None else "malformed")
        for name, grid in named_grids
    ]
    return PairResult(kind="train", idx=0, ok=all(v.ok for v in variants),
                      variants=variants)


def test_an_undefined_case_is_separated_from_a_defined_one():
    report = report_of([_pair([("$A", [[1]]), ("$B", None)])], ["A", "B"])
    assert report.separating == {"A": 1, "B": 1}
    assert report.undefined == {"A": 0, "B": 1}
    assert report.classes == 2
    assert report.separates["A"]["B"] == 1


def test_a_record_case_label_drops_the_dollars():
    """A record case prints as `[$Table, $Lookup]` on the run and labels as
    `[Table, Lookup]`, each constructor stripped of its `$` and of its
    arguments."""
    assert features_run.case_label("[$Table, $Lookup]") == "[Table, Lookup]"
    assert features_run.case_label(
        "[$Derive(g=Iso), $Lookup]") == "[Derive, Lookup]"
    report = report_of([_pair([("[$Table, $Lookup]", [[1]]),
                               ("[$Derive(g=Iso), $Lookup]", [[2]])])])
    assert report.cases == ["[Table, Lookup]", "[Derive, Lookup]"]


