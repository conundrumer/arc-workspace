"""Witness files: the outcomes a solver's cases are pinned to."""

from pathlib import Path

import pytest

from arc.jsonio import format_file
from dl import cli, solve, witness
from dl.annotations import FORMS, SLUG_FORM, Branch, read
from dl.facts import Candidate
from dl.models import NO_CHOICE, CaseId, HeldCase, NoChoice

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
    assert loaded is not None
    assert loaded.id == STEM
    output = loaded.entries[0].output
    assert isinstance(output, dict) and output["Flip"] is None
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
        "the `assign` value of `first_axis` holds `H`, which is not a lib "
        "constant",
        "the `assign` value of `box` holds `Top`, which is not a lib "
        "constant",
    ]


def test_a_verdict_of_an_unheld_model_reads_as_that_models_output():
    """A verdict naming a branch model whose case `impl_choice` does not
    hold reads as that case's output, which the report runs. A held case
    departs under the verdict where its output differs from that one, so a
    held case that gives the verdict's grid leaves the approximation
    without a witness, and the verdict is no finding of its own."""
    source = (
        "// @rule foot: the foot stands beside the block\n"
        "//     @approximated: the foot stands on the dot's line\n"
        "//     @witness two-colors: borderline Near\n"
        ".type U = NeedA {} | Near {} | Skip {}\n"
        ".type O = NeedB {} | SkipO {} | OtherO {}\n"
        ".type Choice = [u: U, o: O]\n"
        ".decl impl_choice(ch: Choice)\n")
    held = [CaseId(c) for c in ("[NeedA, NeedB]", "[Near, SkipO]",
                                "[Near, OtherO]")]
    space = witness.case_space(source)
    assert witness.unheld_verdicts(source, space, held) == {
        "two-colors": [CaseId("[Near, NeedB]")]}

    def notes(near: list[list[int]]) -> list[str]:
        outcomes: dict[str, dict[CaseId, witness.Got]] = {"two-colors": {
            **dict(zip(held, [None, [[1]], [[2]]], strict=True)),
            CaseId("[Near, NeedB]"): near}}
        return [d.note for d in witness._annotation_findings(
            source, [witness.Entry("two-colors", "", [[1]])], held, space,
            outcomes)]

    assert notes([[3]]) == []
    assert notes([[2]]) == [
        "`@rule foot` is approximated and no witness under its "
        "`@approximated:` shows case `[Near, OtherO]` giving an output "
        "other than the verdict's"]


GRID_PARAMS = """.comp Params {
    .decl shape(p: Position)
    GRID_MASK_2x2(shape,
        1, _,
        _, 1)
}
"""


def test_assign_replaces_a_grid_call() -> None:
    """An `assign` on a parameter a GRID call stores replaces that call.
    Facts added beside the call would join its cells, and the run would
    read the union with no sign of it."""
    facts = witness.assigned_source(GRID_PARAMS, {"shape": [[[0, 1, 0, 1]]]})
    assert "GRID_" not in facts and "shape([0, 1, 0, 1])." in facts
    grid = witness.assigned_source(GRID_PARAMS, {"shape": [[0, 1, 1]]})
    assert "GRID_MASK_1x3(shape,\n        _, 1, 1)" in grid
    assert grid.count("GRID_") == 1


def test_record_all_keeps_each_witness_but_its_groups_and_writes_nothing_on_a_failure(
        solvers, monkeypatch, tmp_path):
    """`record --all` rewrites only the groups: a lost `assign` or judged
    output would pass unseen. A failed run leaves the file as it was."""
    target = tmp_path / "copy.wit.json"
    grid = [[1, 2], [3, 4]]
    entries = [
        {"id": "a", "separates": "it's a", "input": grid,
         "assign": {"x": [[1]]}, "output": [{"cases": ["Old"], "grid": grid}]},
        {"id": "b", "separates": "b", "input": grid, "output": [[5]]},
        {"id": "c", "separates": "c", "input": [[7]],
         "output": [{"cases": ["Old"], "grid": grid}]},
    ]
    target.write_text(format_file({"id": STEM, "witnesses": entries}))
    monkeypatch.setattr(cli, "assign_findings", lambda assign, source: [])

    def outcomes(stem, solver, source, g, assign, show):
        if g == [[7]] and fail:
            raise TimeoutError("slow")
        return {"New": g, "Copy=1": [[9]]}

    monkeypatch.setattr(cli, "_record_outcomes", outcomes)
    fail = True
    before = target.read_text()
    assert cli.cmd_record_all(STEM, str(target)) == 1
    assert target.read_text() == before
    fail = False
    assert cli.cmd_record_all(STEM, str(target)) == 0
    after = witness.read_witness_data(STEM, target)["witnesses"]
    groups = [{"cases": ["New"], "grid": grid},
              {"cases": ["Copy=1"], "grid": [[9]]}]
    assert after[0] == {**entries[0], "output": groups}
    assert after[1] == entries[1]
    assert after[2]["output"] == [{"cases": ["New"], "grid": [[7]]},
                                  {"cases": ["Copy=1"], "grid": [[9]]}]
    assert not (solvers / "witnesses" / f"{STEM}.wit.json").exists()


def test_the_built_witnesses_read_the_witness_file_given(tmp_path, monkeypatch):
    # Under --witness-file, the reports that decide which branches get a
    # built witness read that file, not the task's.
    from dl import derive, store
    file = tmp_path / "own.wit.json"
    read: list = []

    def reader(empty):
        def report(stem, witness_file=None):
            read.append(witness_file)
            return empty
        return report
    monkeypatch.setattr(derive, "derive_report",
                        reader(derive.Report([], [])))
    monkeypatch.setattr(store, "store_report", reader(store.Report()))
    space = NoChoice()
    derived = Branch("derive", "p", "Prop", 1)
    stored = Branch("store", "q", witness.STORED, 2)
    space.lines = [derived, stored]
    space.runner = {CaseId(b.name): HeldCase(NO_CHOICE, (b,))
                    for b in space.lines}
    witness.built_witnesses(STEM, space, set(), file)
    assert read == [file, file]
