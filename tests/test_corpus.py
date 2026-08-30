"""The parsed view of the solver corpus."""

from dl.corpus import each_solver
from dl.dlparse import Index, Program
from dl.paths import SOLVERS_DIR


def test_each_solver():
    path, program, idx = next(each_solver())
    assert path.parent == SOLVERS_DIR and path.suffix == ".dl"
    assert isinstance(program, Program)
    assert isinstance(idx, Index) and idx.program is program
