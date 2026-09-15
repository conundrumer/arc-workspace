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


def test_a_null_outcome_matches_an_error(solvers, monkeypatch):
    _write(solvers, [_entry({"Copy": None})])
    monkeypatch.setattr(
        witness, "run_dl_source",
        lambda source, rows, solver_path=None: [
            Candidate("$Copy", [], [], [], error="negative edge distance b=-1")])

    assert witness.witness_report(STEM) == []


def test_a_null_outcome_matches_a_silent_case(solvers, monkeypatch):
    """A case that emits nothing has no grid to read, so it stands as
    ill-formed."""
    _write(solvers, [_entry({"Copy": [[1, 2]], "Flip": None})])
    monkeypatch.setattr(witness, "run_dl_source", _emit([("$Copy", [[1, 2]])]))

    assert witness.witness_report(STEM) == []


def test_a_case_the_entry_does_not_name_is_unlisted(solvers, monkeypatch):
    _write(solvers, [_entry({"Copy": [[1, 2]]})])
    monkeypatch.setattr(witness, "run_dl_source",
                        _emit([("$Copy", [[1, 2]]), ("$Flip", [[2, 1]])]))

    (found,) = witness.witness_report(STEM)
    assert (found.kind, found.case) == (witness.UNLISTED, "Flip")
    assert witness.render_witness([found])[0] == (
        "two-colors: case Flip is not listed")
    assert "no drift" in witness.render_witness([found])


def test_a_rejected_output_a_case_produces_reports(solvers, monkeypatch):
    _write(solvers, [_entry([[9, 9]])])
    monkeypatch.setattr(witness, "run_dl_source",
                        _emit([("$Copy", [[1, 2]]), ("$Flip", [[9, 9]])]))

    (found,) = witness.witness_report(STEM)
    assert (found.kind, found.case) == (witness.DRIFT, "Flip")
    assert witness.render_witness([found])[0] == (
        "two-colors: case Flip produces the rejected output")


def test_a_record_case_is_keyed_without_its_dollars(solvers, monkeypatch):
    """A record `Choice` prints as `[$Table, $Lookup]` on the run, and the
    entry names that case as `[Table, Lookup]`."""
    _write(solvers, [_entry({"[Table, Lookup]": [[1, 2]],
                             "[Derive, Lookup]": [[2, 1]]})])
    monkeypatch.setattr(witness, "run_dl_source",
                        _emit([("[$Table, $Lookup]", [[1, 2]]),
                               ("[$Derive(g=Iso), $Lookup]", [[2, 1]])]))

    assert witness.witness_report(STEM) == []


def test_a_solver_without_a_choice_takes_the_out_case(solvers, monkeypatch):
    _write(solvers, [_entry({"(out)": [[1, 2]]})])
    monkeypatch.setattr(witness, "run_dl_source", _emit([("", [[1, 2]])]))

    assert witness.witness_report(STEM) == []


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


def test_an_assignment_names_its_parameters_on_the_entrys_line(
        solvers, monkeypatch):
    (solvers / f"{STEM}.dl").write_text(PARAMS)
    _write(solvers, [_entry({"Copy": [[1, 2]]}, assign={"arr_dim": [[5]]})])
    monkeypatch.setattr(witness, "run_dl_source", _emit([("$Copy", [[3, 3]])]))

    (drift,) = witness.witness_report(STEM)
    assert witness.render_witness([drift])[0] == (
        "two-colors [arr_dim]: case Copy drifted")


def test_no_witness_file_is_no_failure(solvers, monkeypatch, capsys):
    monkeypatch.setattr(witness, "run_dl_source", _emit([("", [[1, 2]])]))

    assert cli.cmd_witness(STEM) == 0
    assert capsys.readouterr().out == "no witness file\n"


def test_the_command_exits_one_on_drift(solvers, monkeypatch, capsys):
    _write(solvers, [_entry({"Copy": [[1, 2]]})])
    monkeypatch.setattr(witness, "run_dl_source", _emit([("$Copy", [[3, 3]])]))

    assert cli.cmd_witness(STEM) == 1
    assert "case Copy drifted" in capsys.readouterr().out


def test_the_command_exits_zero_on_an_unlisted_case(solvers, monkeypatch, capsys):
    _write(solvers, [_entry({"Copy": [[1, 2]]})])
    monkeypatch.setattr(witness, "run_dl_source",
                        _emit([("$Copy", [[1, 2]]), ("$Flip", [[2, 1]])]))

    assert cli.cmd_witness(STEM) == 0
    assert "is not listed" in capsys.readouterr().out


def test_audit_prints_the_witness_section(solvers, monkeypatch, capsys):
    _write(solvers, [_entry({"Copy": [[1, 2]]})])
    monkeypatch.setattr(witness, "run_dl_source", _emit([("$Copy", [[1, 2]])]))
    monkeypatch.setattr(cli, "_print_sweep", lambda *a: 0)
    monkeypatch.setattr(cli, "_print_deletions", lambda stem: 0)

    assert cli.cmd_audit(STEM) == 0
    out = capsys.readouterr().out
    assert "--- witness ---\n" in out
    assert out.endswith("no drift\n")


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


def test_the_deviation_fields_load_and_default_empty(solvers):
    _write(solvers, [_entry({"Copy": [[1, 2]]}, violates=["one seam"],
                            rejected=["Flip"]),
                     _entry({"Copy": [[1, 2]]})])
    loaded = witness.load_witnesses(STEM)
    assert loaded.entries[0].violates == ["one seam"]
    assert loaded.entries[0].rejected == ["Flip"]
    assert loaded.entries[1].violates == [] and loaded.entries[1].rejected == []


def test_an_unknown_key_on_an_entry_is_rejected(solvers):
    _write(solvers, [_entry({"Copy": [[1, 2]]}, hypotheses=["the seam moves"])])

    with pytest.raises(ValueError, match=f"{STEM}.wit.json"):
        witness.load_witnesses(STEM)


def test_the_written_files_hold_to_the_schema():
    """Every witness file in the repo holds to the shape style.md states."""
    paths = sorted(witness.WITNESS_DIR.glob("*.wit.json"))
    assert paths
    for path in paths:
        assert witness.load_witnesses(path.name.removesuffix(".wit.json"))
