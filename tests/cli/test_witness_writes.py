"""The witness writes of `record`: no command creates a task's witness
file, and `record --all` rewrites only the groups and writes nothing where
a run fails. A file created in the witness directory, or a lost `assign`
or judged output, would pass unseen in use."""

from pathlib import Path

import pytest

import cli.record
from engine import WallLimit
from solver import witness
from solver.witness import (
    AssignRows,
    Entry,
    Group,
    Groups,
    RejectedOutput,
    WitnessFile,
)

STEM = "5582e5ca"
SOLVER = f"""\
// {STEM}
.type Choice =
    // the input as it is
    Keep {{}}
    // every cell in the stored color
  | Fill {{}}

.decl out(p: Position, col: Color, ch: Choice)

.comp Params {{
    // --- $Fill ---
    .decl fill(c: Color) fill(5).
}}

.init params = Params

// --- $Keep ---
out(P, C, $Keep()) :- in(P, C).

// --- $Fill ---
out(P, C, $Fill()) :- in(P, _), params.fill(C).
"""


@pytest.fixture
def solvers(root: Path) -> Path:
    """The test checkout's solvers directory, holding the solver of
    `STEM`, which has no witness file."""
    solvers = root / "programs" / "solvers"
    (solvers / f"{STEM}.dl").write_text(SOLVER)
    (root / "grid.txt").write_text("0 1\n1 0\n")
    return solvers


def test_record_does_not_create_the_task_file(solvers: Path, capsys):
    witnesses = solvers.parent / "witnesses"
    grid = solvers.parent.parent / "grid.txt"
    assert cli.record.cmd_record(STEM, "probe", "probe", str(grid)) == 2
    assert not (witnesses / f"{STEM}.wit.json").exists()
    assert "no witness file at" in capsys.readouterr().err
    named = f"{witnesses}/../witnesses/{STEM}.wit.json"
    assert cli.record.cmd_record(STEM, "probe", "probe", str(grid),
                                 witness_file=named) == 2
    assert not (witnesses / f"{STEM}.wit.json").exists()
    assert "no witness file at" in capsys.readouterr().err


def test_record_all_keeps_each_witness_but_its_groups_and_writes_nothing_on_a_failure(
        solvers: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    target = tmp_path / "copy.wit.json"
    g = ((1, 2),)
    entries = [
        Entry("a", "keep against fill", g, (("fill", AssignRows(((7,),))),),
              Groups((Group(("$Keep",), ((0, 0),)),))),
        Entry("b", "judged", g, (), RejectedOutput(((5, 5),))),
        Entry("c", "c", ((3,),), (), Groups((Group(("$Keep",), ((3,),)),))),
    ]
    target.write_text(witness.text(WitnessFile(STEM, tuple(entries))))
    outcomes = cli.record.case_outcomes
    fail = True

    def failing(runs, entry):
        if entry.id == "c" and fail:
            return WallLimit(1.0)
        return outcomes(runs, entry)

    monkeypatch.setattr(cli.record, "case_outcomes", failing)
    before = target.read_text()
    assert cli.record.cmd_record_all(STEM, str(target)) == 1
    assert target.read_text() == before
    fail = False
    assert cli.record.cmd_record_all(STEM, str(target)) == 0
    file, problems = witness.read(target.read_text())
    assert problems == ()
    assert file is not None
    a, b, c = file.entries
    assert a == Entry("a", "keep against fill", g, entries[0].assign, Groups((
        Group(("concept",), g), Group(("$Fill",), ((7, 7),)))))
    assert b == entries[1]
    assert c.output == Groups((Group(("concept",), ((3,),)),
                               Group(("$Fill",), ((5,),))))
    assert not (solvers.parent / "witnesses" / f"{STEM}.wit.json").exists()
