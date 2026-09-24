"""Souffle's output as candidates: each caller gets its own."""

import shutil
import subprocess
from pathlib import Path

import pytest

from dl.facts import grid_to_facts, parse_output
from dl.source import OUT_CELLS, SOLVE_DIRECTIVES, build_source, expand_macros

needs_souffle = pytest.mark.skipif(
    shutil.which("souffle") is None, reason="souffle not installed",
)


def _output(color: int) -> str:
    return f"---\nout\n===\n[0, 0, 0, 0]\t{color}\n===\n"


def test_a_changed_output_parses_again_and_a_caller_changes_only_its_copy():
    first = parse_output(_output(1))
    first[0].grid[0][0] = 9
    first[0].missing.append((0, 0))
    again = parse_output(_output(1))
    assert (again[0].grid, again[0].missing) == ([[1]], [])
    assert parse_output(_output(2))[0].grid == [[2]]


TYPES = """\
.type Position = [t: number, b: number, l: number, r: number]
.type Color = number
.type Choice = Plain {} | Shift {d: number}
.type Res = Low {} | High {}
.decl in(p: Position, col: Color)
"""

ONE_CASE_COLUMN = TYPES + """\
.decl out(p: Position, col: Color, ch: Choice)
out(P, C, $Plain()) :- in(P, C).
out(P, 5, $Shift(D)) :- in(P, _), (D = 1 ; D = 2).
"""

TWO_CASE_COLUMNS = TYPES + """\
.decl out(p: Position, col: Color, ch: Choice, res: Res)
out(P, C, $Plain(), $Low()) :- in(P, C).
out(P, 5, $Shift(2), $High()) :- in(P, _).
"""


def _souffle_stdout(program: str, tmp_path: Path) -> str:
    """Souffle's output on a two-cell grid. The built program includes
    `../lib.dl`, which stands empty here: the program declares its own
    types."""
    (tmp_path / "lib.dl").write_text("")
    (tmp_path / "solvers").mkdir(exist_ok=True)
    path = tmp_path / "solvers" / "p.dl"
    path.write_text(program)
    return subprocess.run(
        ["souffle", "-w", "-D-", str(path)], input=grid_to_facts([[1, 2]]),
        capture_output=True, text=True, check=True).stdout


@needs_souffle
@pytest.mark.parametrize("source", [ONE_CASE_COLUMN, TWO_CASE_COLUMNS])
def test_the_built_output_reads_as_out_itself_prints(source, tmp_path):
    """The built program prints each case by ordinal; parsed, it is what
    printing `out` gives, case spellings included."""
    built = build_source(source)
    assert f".output {OUT_CELLS}" in built
    printed = parse_output(_souffle_stdout(
        f"{expand_macros(source)}\n{SOLVE_DIRECTIVES}", tmp_path))
    assert [c.case for c in printed] in (
        ["$Plain", "$Shift(1)", "$Shift(2)"],
        ["$Plain\t$Low", "$Shift(2)\t$High"])
    assert parse_output(_souffle_stdout(built, tmp_path)) == printed
