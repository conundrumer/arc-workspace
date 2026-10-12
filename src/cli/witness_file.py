"""The witness file and the `--assign` object a command that runs one
solver reads: the file the caller names or the task's, read in place
of the task's, and the assignment the object states."""

import sys
from pathlib import Path

from checker.render import commands
from cli import text
from cli.common import assign_arg, print_faults
from engine import Engine, checkout
from solver import witness
from solver.aggregate import Solver, grid_stored, read_witness
from solver.problems import Fault, InWitnessFile, WitnessFileRole
from solver.outcome import Assignment
from solver.group_runs import assigned
from solver.witness_swap import with_witness_file
from solver.witness import AssignValue, WitnessFile, assign_with_grids


def target(solver: Solver, given: str | None) -> Path:
    """The witness file a command reads: `given` where the caller names
    one, the task's otherwise."""
    return Path(given) if given else witness.path(solver.task_id)


def in_witness_dir(path: Path) -> bool:
    return path.resolve().is_relative_to(witness.path("").parent.resolve())


def absent(path: Path) -> bool:
    """True, with its line on stderr, where no file stands at `path` for
    a command that reads one there. A command that writes a witness reads
    the file with `with_file`, and writes it through `witness.put`."""
    if path.exists():
        return False
    line = commands.NO_WITNESS_FILE if in_witness_dir(path) else text.NO_FILE
    print(line.format(path=checkout.shown(path)), file=sys.stderr)
    return True


def read_file(solver: Solver, path: Path, role: WitnessFileRole
              ) -> tuple[WitnessFile | None, tuple[Fault, ...]]:
    """The witness file at `path`, with each `assign` value of a
    GRID-stored parameter read as a grid, and what could not be read,
    placed in the file `role`."""
    return read_witness(path.read_text(), solver.params, role)


def with_file(solver: Solver, path: Path) -> Solver | None:
    """The solver with the witness file at `path` in place of the task's,
    with the faults of that file in place of those of the task's
    (`with_witness_file`); None, with the file's problems on stderr, where
    it is off its shape."""
    if not path.exists():
        return with_witness_file(solver, None)
    file, problems = read_file(solver, path, WitnessFileRole.TASK)
    if file is None or problems:
        print_faults(solver, problems)
        return None
    return with_witness_file(solver, file)


def lined_solver(solver: Solver, at: Path) -> Solver | None:
    """The solver with the witness file at `at` in place of the task's
    (`with_file`); None, with its line on stderr, where no file stands
    there (`absent`), or where the file is off its shape."""
    if absent(at):
        return None
    return with_file(solver, at)


ASSIGN_ID = "assign"
"""The witness entry a problem of an `--assign` object is placed at."""


def assignment(eng: Engine, solver: Solver,
                assign: tuple[tuple[str, AssignValue], ...]
                ) -> Assignment | None:
    """The assignment an `--assign` object states; None, with the problem
    on stderr, where it names what the solver lacks."""
    at = assigned(eng, solver,
                  assign_with_grids(assign, grid_stored(solver.params)),
                  InWitnessFile(ASSIGN_ID, WitnessFileRole.ASSIGN))
    if isinstance(at, Fault):
        print_faults(solver, [at])
        return None
    return at


def assign_of(eng: Engine, solver: Solver, written: str | None
               ) -> tuple[tuple[str, AssignValue], ...] | None:
    """The `--assign` object as an entry's `assign` (`assign_arg`), with
    each value of a parameter stored by a GRID call read as a grid where
    it has a grid's shape, as the witness file's reader reads an entry's
    `assign`; None, with the problem on stderr, where it is off its shape
    or names what the solver lacks (`assignment`)."""
    assign = assign_arg(written)
    if assign is None or assignment(eng, solver, assign) is None:
        return None
    return assign_with_grids(assign, grid_stored(solver.params))
