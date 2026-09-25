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


def test_the_annotation_checks_report_what_they_accept_silently(solvers,
                                                                monkeypatch):
    """A `@witness` line off the form, a nested line carrying its indent
    before the comment marker, and a block whose `@reassigned` parameters
    are not the entry's `assign` keys. The reader takes both nesting forms, so the
    `@reassigned` line in the accepted form reaches its block. The run passes
    every grid, so nothing else reports these."""
    (solvers / f"{STEM}.dl").write_text(
        "// @scene bands: the input carries bands\n"
        "// @witness Two Colors: plausible concept\n"
        + WITNESS_LINE
        + "//     @reassigned arr_dim\n"
        + "    // @relaxed bands\n")
    _write(solvers, [_entry({"Copy": [[1, 2]]})])
    monkeypatch.setattr(witness, "run_dl_source", _emit([("$Copy", [[1, 2]])]))

    notes = [d.note for d in witness.witness_report(STEM)
             if d.kind == witness.ANNOTATION]
    assert notes == [
        "`// @witness Two Colors: plausible concept` is off the `@witness` "
        f"form, which is {FORMS['witness']}, the id {SLUG_FORM}",
        "`// @relaxed bands` carries its indent before `//`; a nested line "
        "carries it after, as `//     @relaxed bands`",
        "`@reassigned` names `arr_dim`; the witness's `assign` names "
        "no parameter",
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

    notes = [d.note for d in witness.witness_report(STEM)
             if d.kind == witness.ANNOTATION]
    assert notes == ["`@rule inside` is approximated and has no `@witness` "
                     "line under its `@approximated:`"]


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


def test_an_assign_string_that_is_no_constant_is_a_finding():
    """Souffle reads a name that is no `#define` as a variable and fails on
    the fact, so each such string, at any depth of a record, is a finding,
    and a lib constant is none."""
    assert witness.assign_findings({
        "first_axis": [["SYM_TB"], ["H"]],
        "box": [[["ZERO", ["DIR_T", "Top"]]]],
    }) == [
        "the `assign` value of `first_axis` holds `H`, which is no constant "
        "of the lib",
        "the `assign` value of `box` holds `Top`, which is no constant of "
        "the lib",
    ]
