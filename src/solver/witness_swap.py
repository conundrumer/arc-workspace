"""A solver with a witness file put in place, and the faults that file
gives it."""

from collections.abc import Iterable
from dataclasses import replace

from solver.aggregate import Solver
from solver.form_checks import name_problems, output_form_problems
from solver.problems import Fault, InWitnessFile, WitnessFileRole
from solver.witness import WitnessFile


def in_file(fault: Fault) -> bool:
    """Whether `fault` stands in the solver's witness file, so that it
    goes with the file."""
    return isinstance(fault.place, InWitnessFile) \
        and fault.place.file is WitnessFileRole.TASK


def with_witness_file(solver: Solver, file: WitnessFile | None,
                      read: Iterable[Fault] = ()) -> Solver:
    """`solver` with `file` as its witness file, and with the faults of the
    file it held replaced by those of `file`: `read`, what could not be
    read of it (`read_witness`), then the names its entries hold that
    denote nothing (`name_problems`) and its entries whose `output` is
    off the form their verdict takes (`output_form_problems`). Every other
    fault stands in the solver's text and stays. With `file` None the solver
    holds no witness file and no fault of one.

    `load` puts the task's file in place through it, and so does each
    command that reads another file in place of the task's and reports on
    it. A swap that builds a file for a check of its own leaves the faults
    as they are, since nothing reports the faults of that solver:
    `record`'s file with the entry it records added, for the runs on that
    entry; the one-entry file of `rerecorded`, which reads that entry's
    output-form fault alone; and the candidate file of `witness --try`,
    for the runs its survey compares."""
    placed = replace(solver, witness_file=file)
    gained = (*read, *(f for f in name_problems(placed) if in_file(f)),
              *output_form_problems(placed))
    kept = tuple(f for f in solver.problems if not in_file(f))
    return replace(placed, problems=kept + gained)
