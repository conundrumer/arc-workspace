"""`features`: which rules each case reaches, how the cases compare, and
what a run adds to that."""

import json
from dataclasses import fields
from pathlib import Path

import pytest

from dl import cli, features_run, solve
from dl.corpus import literal_count
from dl.dlparse import parse
from dl.features import CaseFeatures, features_report, render_features
from dl.features_run import report_of
from dl.paths import all_stems
from dl.solve import PairResult, TaskResult, VariantResult, solver_file

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

ONE_CASE = (".decl out(p: Position, col: Color)\n"
            "out(P, Col) :- in(P, Col), helper(P).\n"
            ".decl helper(p: Position)\n"
            "helper(P) :- in(P, _).\n")

TIED = (".type Choice = A {} | B {} | C {}\n"
        ".decl out(p: Position, col: Color, c: Choice)\n"
        "out(P, Col, $A()) :- in(P, Col).\n"
        "out(P, Col, $B()) :- in(P, Col).\n")


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


# --- what a case reaches ---

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


def test_a_params_rule_is_reached_through_its_instance(solvers):
    by_case = rows(solvers, TWO_CASES)
    # a_p is read as `params.a_p`, and its fact stands inside the comp.
    assert by_case["A"].reach_facts == 3  # tag, a_p, both_p


def test_a_lib_instance_is_fed_by_every_rule_that_writes_it(solvers):
    by_case = rows(solvers, TWO_CASES)
    # B reads `inv.offset`, which the `inv.cell` rule feeds.
    assert by_case["B"].reach_rules == by_case["A"].reach_rules + 1
    assert by_case["B"].lib_instances == 1
    assert by_case["B"].distinct_lib_units == 1
    assert by_case["A"].lib_instances == 0


def test_the_shapes_of_a_case_count_over_its_whole_reach(solvers):
    row = rows(solvers, TWO_CASES)["A"]
    assert row.negations == 1
    assert row.disjunctions == 1
    assert row.aggregates == 1
    assert row.comparisons == 3  # N > 0, K = count, K > 0


# --- a record-typed Choice ---

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


def test_a_record_head_seeds_the_cases_it_names(solvers):
    by_case = rows(solvers, RECORD)
    own = {case: row.rules for case, row in by_case.items()}
    # The `out` rule names both constructors, so only that case owns it.
    assert own["[Object, Tall]"] == 1
    assert set(own.values()) == {0, 1}


# --- how the cases compare ---

def test_a_solver_without_a_choice_is_one_case(solvers):
    put(solvers, ONE_CASE)
    (row,) = features_report(STEM).cases
    assert row.case == "(out)"
    assert row.cases_in_file == 1
    assert row.atoms_ratio_min == 1.0
    assert row.facts_ratio_min == 1.0
    assert row.is_smallest_atoms and row.is_smallest_facts
    # What `out` reaches is the whole of it, and none of it is shared.
    assert row.atoms == row.reach_atoms == literal_count(parse(ONE_CASE))
    assert row.shared_atoms == 0


def test_a_tie_marks_every_tied_case_smallest(solvers):
    by_case = rows(solvers, TIED.replace(" | C {}", ""))
    assert all(r.is_smallest_atoms and r.atoms_ratio_min == 1.0
               for r in by_case.values())


def test_a_case_that_reaches_nothing_leaves_the_ratios_empty(solvers):
    by_case = rows(solvers, TIED)
    assert by_case["C"].atoms == 0
    assert by_case["C"].atoms_ratio_min == 1.0
    assert by_case["A"].atoms_ratio_min is None
    assert by_case["A"].is_smallest_atoms is False


def test_the_ratios_measure_against_the_smallest_case(solvers):
    by_case = rows(solvers, TWO_CASES)
    own = min(r.atoms for r in by_case.values())
    reached = min(r.reach_atoms for r in by_case.values())
    for row in by_case.values():
        assert row.atoms_ratio_min == pytest.approx(row.atoms / own)
        assert row.reach_atoms_ratio_min == pytest.approx(
            row.reach_atoms / reached)
    assert sum(r.is_smallest_reach_atoms for r in by_case.values()) == 1


def test_the_reach_ratios_rank_cases_that_own_no_rule_alone(solvers):
    """Under a record `Choice` a rule lands in several cases at once, so the
    reach is what tells the cases apart."""
    by_case = rows(solvers, RECORD)
    # Only the `out` head names both constructors, so it alone is owned.
    assert sorted(r.atoms for r in by_case.values()) == [0, 0, 0, 0, 0, 4]
    assert {r.is_smallest_reach_atoms for r in by_case.values()} == {True, False}
    assert by_case["[Object, Tall]"].reach_atoms_ratio_min > 1.0


@pytest.mark.skipif(not all_stems(), reason="no solvers in the corpus")
def test_every_solver_s_cases_and_shared_and_unreached_are_its_size():
    for stem in all_stems():
        report = features_report(stem)
        first = report.cases[0]
        total = (sum(r.atoms for r in report.cases)
                 + first.shared_atoms + first.unreached_atoms)
        assert total == literal_count(
            parse(solver_file(stem)[0].read_text())), stem


# --- the run ---

def _pair(named_grids) -> PairResult:
    variants = [
        VariantResult(name=name, ok=grid is not None, actual=grid or [],
                      error=None if grid is not None else "malformed")
        for name, grid in named_grids
    ]
    return PairResult(kind="train", idx=0, ok=all(v.ok for v in variants),
                      variants=variants)


def test_an_ill_formed_case_is_separated_from_a_well_formed_one():
    report = report_of([_pair([("$A", [[1]]), ("$B", None)])], ["A", "B"])
    assert report.separating == {"A": 1, "B": 1}
    assert report.illformed == {"A": 0, "B": 1}
    assert report.classes == 2
    assert report.separates["A"]["B"] == 1


def test_cases_emitting_the_same_grid_share_one_class():
    report = report_of([_pair([("$A", [[1]]), ("$B", [[1]])])], ["A", "B"])
    assert report.separating == {"A": 0, "B": 0}
    assert report.classes == 1


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


def test_a_resolution_column_is_no_case():
    """A `TiebreakResolution` term stands last in the variant name and names
    no case; a solver with no `Choice` keeps its one case."""
    pairs = [_pair([("$Sit(1)", [[1]]), ("$Sit(2)", [[2]])])]
    report = report_of(pairs, resolution=True)
    assert report.cases == ["(out)"]
    assert report.separating == {"(out)": 0}
    assert report.classes == 1


def test_a_case_ahead_of_the_resolution_column_still_names_the_case():
    pairs = [_pair([("$ByColor\t$Sit(1)", [[1]]),
                    ("$ByObject\t$Sit(1)", [[2]])])]
    report = report_of(pairs, ["ByColor", "ByObject"], resolution=True)
    assert report.cases == ["ByColor", "ByObject"]
    assert report.separating == {"ByColor": 1, "ByObject": 1}


def test_the_run_reads_every_pair_of_the_task(solvers, monkeypatch):
    seen: list[str] = []

    def task(stem: str) -> TaskResult:
        seen.append(stem)
        return TaskResult(stem=stem, pairs=[_pair([("$A", [[1]])]),
                                            _pair([("$A", [[2]])])])

    put(solvers, TIED)
    monkeypatch.setattr(features_run, "run_task", task)
    report = features_run.run_features(STEM, ["A", "B"])
    assert seen == [STEM]
    # B emits nothing on either pair, which tells it apart from A there.
    assert report.separating == {"A": 2, "B": 2}


# --- the sweep columns ---

SWEEP = ("bg: 6 values\n"
         "bg: stored (0); train also admits [(8)]; test refutes [(8)] — "
         "a determination from train alone could pick it\n"
         "fill: unique = (4) ✓\n"
         "seeds: unique as a set = {(1), (2)} ✓\n"
         "shape: not swept — derived\n"
         "budget 180s; elapsed 3s\n")


def _column(out: str, name: str) -> list[str]:
    lines = [line.split("\t") for line in out.splitlines()]
    return [row[lines[0].index(name)] for row in lines[1:]]


def test_a_cached_sweep_counts_the_open_and_the_settled(solvers, capsys):
    put(solvers, TWO_CASES)
    cache = solvers / "sweep"
    cache.mkdir()
    (cache / f"{STEM}.txt").write_text(SWEEP)
    (cache / f"{STEM}.sha").write_text(cli._code_hash(STEM))

    assert cli.cmd_features(STEM) == 0
    out = capsys.readouterr().out
    assert _column(out, "open_params") == ["1", "1"]
    assert _column(out, "pinned_params") == ["2", "2"]  # not the derived line


def test_a_stale_cached_sweep_is_skipped_with_a_reason(solvers, capsys):
    put(solvers, TWO_CASES)
    cache = solvers / "sweep"
    cache.mkdir()
    (cache / f"{STEM}.txt").write_text(SWEEP)
    (cache / f"{STEM}.sha").write_text("0" * 64)

    assert cli.cmd_features(STEM) == 0
    caught = capsys.readouterr()
    assert "is stale" in caught.err
    assert _column(caught.out, "open_params") == ["-", "-"]


def test_a_cached_sweep_with_no_hash_counts_as_unverified(solvers, capsys):
    """The caches made before the hash carry none. `features` runs no sweep,
    so it counts them and notes on stderr that they stand unverified."""
    put(solvers, TWO_CASES)
    cache = solvers / "sweep"
    cache.mkdir()
    (cache / f"{STEM}.txt").write_text(SWEEP)

    assert cli.cmd_features(STEM) == 0
    caught = capsys.readouterr()
    assert "is unverified" in caught.err
    assert _column(caught.out, "open_params") == ["1", "1"]
    assert _column(caught.out, "pinned_params") == ["2", "2"]


# --- the two renderings ---

def test_the_header_row_is_the_dataclass_fields():
    assert render_features([])[0].split("\t") == [
        f.name for f in fields(CaseFeatures)]


def test_the_json_holds_the_rows_the_matrix_and_the_solvers_left_out(
        solvers, monkeypatch, capsys):
    put(solvers, TIED.replace(" | C {}", ""))
    monkeypatch.setattr(
        features_run, "run_task",
        lambda stem: TaskResult(stem=stem,
                                pairs=[_pair([("$A", [[1]]), ("$B", [[2]])])]))

    assert cli.cmd_features(STEM, run=True, as_json=True) == 0
    payload = json.loads(capsys.readouterr().out)
    (solver,) = payload["solvers"]
    assert [c["case"] for c in solver["cases"]] == ["A", "B"]
    assert solver["separates"] == {"A": {"B": 1}, "B": {"A": 1}}
    assert all(c["pairs_separating"] == 1 for c in solver["cases"])
    assert payload["skipped"] == [
        {"stem": STEM, "reason": "no cached sweep at "
                                 f".scratch/retro/sweep/{STEM}.txt"}]


def test_a_solver_outside_the_dialect_reports_and_exits_non_zero(
        solvers, capsys):
    put(solvers, "out(P) :- in(P\n")
    assert cli.cmd_features(STEM) == 1
    assert f"{STEM}: L2:" in capsys.readouterr().err
