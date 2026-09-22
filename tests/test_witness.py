"""Witness files: the outcomes a solver's cases are pinned to."""

from pathlib import Path

import pytest

from arc.jsonio import format_file
from dl import cli, solve, witness
from dl.annotations import FORMS, SLUG_FORM, read
from dl.facts import Candidate

STEM = "abcd1234"

# A `@witness` line per entry the tests write, so the pairing of lines to
# entries reports nothing and each test reads its own finding alone.
WITNESS_LINE = "// @witness two-colors: plausible concept\n"
STUB = WITNESS_LINE


@pytest.fixture
def solvers(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A solvers directory holding one stem, with a witness directory beside
    it and Souffle stubbed out."""
    (tmp_path / f"{STEM}.dl").write_text(STUB)
    wit = tmp_path / "witnesses"
    wit.mkdir()
    monkeypatch.setattr(solve, "SOLVERS_DIR", tmp_path)
    monkeypatch.setattr(witness, "WITNESS_DIR", wit)
    monkeypatch.setattr(cli, "build_functors", lambda: None)
    monkeypatch.setattr(cli, "compile_error", lambda stem: None)
    return tmp_path


def _write(solvers: Path, entries: list[dict]) -> None:
    (solvers / "witnesses" / f"{STEM}.wit.json").write_text(
        format_file({"id": STEM,
                     "witnesses": entries}))


def _entry(output, **rest) -> dict:
    return {"id": "two-colors", "separates": "the seam moves",
            "input": [[1, 2]], "output": output} | rest


def _emit(cases):
    """A run_dl_source stand-in emitting (variant, grid) pairs, no defects."""
    return lambda source, rows, solver_path=None: [
        Candidate(v, g, [], []) for v, g in cases
    ]


def test_expected_outcomes_hold(solvers, monkeypatch):
    _write(solvers, [_entry({"Copy": [[1, 2]], "Flip": [[2, 1]]})])
    monkeypatch.setattr(witness, "run_dl_source",
                        _emit([("$Copy", [[1, 2]]), ("$Flip", [[2, 1]])]))

    assert witness.witness_report(STEM) == []
    assert witness.render_witness([]) == ["witness: ok"]


def test_a_changed_grid_reports_both_grids(solvers, monkeypatch):
    _write(solvers, [_entry({"Copy": [[1, 2]], "Flip": [[2, 1]]})])
    monkeypatch.setattr(witness, "run_dl_source",
                        _emit([("$Copy", [[1, 2]]), ("$Flip", [[3, 3]])]))

    (drift,) = witness.witness_report(STEM)
    assert (drift.kind, drift.cases) == (witness.DRIFT, ["Flip"])
    assert drift.expected == [[2, 1]] and drift.actual == [[3, 3]]
    lines = witness.render_witness([drift])
    assert lines[0] == ("two-colors: case Flip gives an output the witness "
                        "does not name")
    assert "  the witness's output:" in lines
    assert "  the solver's output:" in lines


def test_the_annotation_checks_report_what_they_accept_silently(solvers,
                                                                monkeypatch):
    """A `@witness` line off the form, a nested line carrying its indent
    before the comment marker, an entry no line names, a block whose
    `@reassigned` parameters are not the entry's `assign` keys, and an entry
    whose `assign` is empty. The reader takes both nesting forms, so the
    `@reassigned` line in the accepted form reaches its block. The run passes
    every grid, so nothing else reports these."""
    (solvers / f"{STEM}.dl").write_text(
        "// @scene bands: the input carries bands\n"
        "// @witness Two Colors: plausible concept\n"
        + WITNESS_LINE
        + "//     @reassigned arr_dim\n"
        + "    // @relaxed bands\n")
    _write(solvers, [_entry({"Copy": [[1, 2]]}),
                     _entry({"Copy": [[1, 2]]}, assign={})
                     | {"id": "orphan"}])
    monkeypatch.setattr(witness, "run_dl_source", _emit([("$Copy", [[1, 2]])]))

    notes = [d.note for d in witness.witness_report(STEM)]
    assert notes == [
        "`// @witness Two Colors: plausible concept` is off the `@witness` "
        f"form, which is {FORMS['witness']}, the id {SLUG_FORM}",
        "`// @relaxed bands` carries its indent before `//`; a nested line "
        "carries it after, as `//     @relaxed bands`",
        "`@reassigned` names `arr_dim`; the witness's `assign` names "
        "no parameter",
        "`assign` is empty; omit the key",
        "witness `orphan` of the file is named by no `@witness` line",
    ]


def test_a_nested_witness_joins_the_claim_it_stands_under():
    """A `@witness` line indented after `//` under an `@approximated:` line
    joins that claim, and the source's blocks as well. One under a claim with
    no `@approximated:` line is malformed."""
    ann = read("// @rule inside: a non-bg cell is erased to bg\n"
               "//     @approximated: a cell lies inside a container\n"
               "//     @witness far-marks: variant Shape\n"
               "//         @reassigned some_param\n"
               "// @rule pass: every other cell passes through\n"
               "//     @witness stray: variant concept\n")

    inside, passes = ann.claims
    (block,) = inside.witnesses
    assert (block.id, block.approximates, block.reassigned) == (
        "far-marks", "inside", ["some_param"])
    assert [w.id for w in ann.witnesses] == ["far-marks"]
    assert passes.witnesses == []
    (bad,) = ann.malformed
    assert bad.line == 6 and "`@approximated:`" in bad.why


def test_an_approximated_claim_with_no_witness_reports(solvers, monkeypatch):
    """A `@rule` line the header approximates states a witness under its
    `@approximated:` line. The run passes every grid, so nothing else
    reports the claim."""
    (solvers / f"{STEM}.dl").write_text(
        "// @rule inside: a non-bg cell is erased to bg\n"
        "//     @approximated: a cell lies inside a container\n"
        + WITNESS_LINE)
    _write(solvers, [_entry({"Copy": [[1, 2]]})])
    monkeypatch.setattr(witness, "run_dl_source", _emit([("$Copy", [[1, 2]])]))

    notes = [d.note for d in witness.witness_report(STEM)]
    assert notes == ["`@rule inside` is approximated and has no `@witness` "
                     "line under its `@approximated:`"]


PARAMS = (WITNESS_LINE
          + "//     @reassigned arr_dim\n"
          + "//     @reassigned band_axis\n"
          + ".comp Params {\n"
          "    .decl arr_dim(k: number) arr_dim(3).\n"
          "    .decl band_axis(a: Axis) band_axis(AXIS_V).\n"
          "}\n")


def test_an_assignment_rewrites_the_source_the_run_sees(solvers, monkeypatch):
    (solvers / f"{STEM}.dl").write_text(PARAMS)
    _write(solvers, [_entry({"Copy": [[1, 2]]},
                            assign={"arr_dim": [[5]],
                                    "band_axis": [["AXIS_H"]]})])
    seen: list[str] = []

    def record(source, rows, solver_path=None):
        seen.append(source)
        return [Candidate("$Copy", [[1, 2]], [], [])]

    monkeypatch.setattr(witness, "run_dl_source", record)

    assert witness.witness_report(STEM) == []
    (source,) = seen
    assert "arr_dim(5)." in source and "arr_dim(3)" not in source
    assert "band_axis(AXIS_H)." in source and "AXIS_V" not in source


def test_the_file_loads_what_it_was_written_with(solvers):
    _write(solvers, [_entry({"Copy": [[1, 2]], "Flip": None},
                            assign={"arr_dim": [[5]]}),
                     _entry([[9, 9]])])
    loaded = witness.load_witnesses(STEM)
    assert loaded.id == STEM
    assert loaded.entries[0].output["Flip"] is None
    assert loaded.entries[0].assign == {"arr_dim": [[5]]}
    assert loaded.entries[1].rejected_output
    assert loaded.entries[1].output == [[9, 9]]


def test_the_written_files_hold_to_the_schema():
    """Every witness file in the repo holds to the shape procedure.md states."""
    paths = sorted(witness.WITNESS_DIR.glob("*.wit.json"))
    assert paths
    for path in paths:
        assert witness.load_witnesses(path.name.removesuffix(".wit.json"))
