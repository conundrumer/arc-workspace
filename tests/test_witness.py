"""Witness files: the outcomes a solver's cases are pinned to."""

from pathlib import Path

import pytest

from arc.jsonio import format_file
from dl import cli, solve, witness
from dl.facts import Candidate

STEM = "abcd1234"


@pytest.fixture
def solvers(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A solvers directory holding one stem, with a witness directory beside
    it and Souffle stubbed out."""
    (tmp_path / f"{STEM}.dl").write_text("// stub\n")
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
    return {"id": "two-colors", "hypothesis": "the seam moves",
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
    assert witness.render_witness([]) == ["no drift"]


def test_a_changed_grid_drifts(solvers, monkeypatch):
    _write(solvers, [_entry({"Copy": [[1, 2]], "Flip": [[2, 1]]})])
    monkeypatch.setattr(witness, "run_dl_source",
                        _emit([("$Copy", [[1, 2]]), ("$Flip", [[3, 3]])]))

    (drift,) = witness.witness_report(STEM)
    assert (drift.kind, drift.case) == (witness.DRIFT, "Flip")
    assert drift.expected == [[2, 1]] and drift.actual == [[3, 3]]
    lines = witness.render_witness([drift])
    assert lines[0] == "two-colors: case Flip drifted"
    assert "  expected:" in lines


PARAMS = (".comp Params {\n"
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
