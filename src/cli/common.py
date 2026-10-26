"""What the commands share: the engine, the solver an argument names, the
limits of a run on one grid, the grid a caller writes, and the stamp of
the code a run loads."""

import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import TextIO

from arc.task import task_file
from arc.task import GridFormError, read_grid
from checker.finding import Finding
from checker.judged import parse_fault
from checker.lint.form.components import check_determine_schema
from checker.lint.form.open_value_fields import check_open_value_field
from checker.render.determination import determination_lines
from checker.readable import finding_of
from checker.render import commands, finding_lines
from checker.render.no_result import run_failed
from checker.runs import Runs
from cli import text
from engine import (
    CompileError,
    Grid,
    Limits,
    RunFailure,
    UngroundedVariable,
    checkout,
)
from engine.program import as_grid
from solver.determine import KeysOff, off_key_blocks
from solver.load import load
from solver.aggregate import Solver, solver_file
from solver.problems import Fault
from solver.outcome import Assignment
from solver.vocabulary import OUTPUT
from solver.witness import AssignValue, read_assign
from souffle import SouffleEngine
from souffle.engine import FUNCTOR_DIR
from souffle.functors import FUNCTOR_SOURCE

CPU_SECONDS = 20.0
"""The CPU seconds one run on one grid may take."""

LIMITS = Limits(cpu_seconds=CPU_SECONDS, wall_seconds=2 * CPU_SECONDS)
"""The limits of one run on one grid."""


def engine() -> SouffleEngine:
    """The engine every command runs through, with the functor library
    under `programs/` and the run cache under `.cache/`."""
    return SouffleEngine()


# The solver an argument names


def stem_of(arg: str) -> str:
    """The stem an argument names: a stem, a file name, or the path of a
    solver file."""
    name = Path(arg).name
    return name[:-3] if name.endswith(".dl") else name


def solver_path(arg: str) -> Path:
    """The solver file an argument names: the path as given where a file
    stands there, else the file of that name under `checkout.solvers()`."""
    path = Path(arg if arg.endswith(".dl") else f"{arg}.dl")
    if path.exists():
        return path
    return solver_file(path.stem) if path.parent == Path(".") \
        else checkout.solvers() / path


def missing(arg: str) -> bool:
    """True, with its line on stderr, where no solver file stands at the
    argument."""
    path = solver_path(arg)
    if path.is_file():
        return False
    print(text.NO_SOLVER.format(path=path), file=sys.stderr)
    return True


def all_stems() -> list[str]:
    """The solver stems, dotfiles aside."""
    return sorted(p.stem for p in checkout.solvers().glob("*.dl")
                  if not p.name.startswith("."))


def load_solver(arg: str, eng: SouffleEngine) -> Solver:
    """The solver an argument names (`solver_path`), its stem the file's
    name: a path to a file anywhere, its name starting with the task id,
    or a stem under `programs/solvers/`."""
    return load(stem_of(arg), eng, solver_path(arg))


def command_solver(arg: str, eng: SouffleEngine, task: bool = True
                   ) -> Solver | None:
    """The solver a command runs on (`load_solver`); None, with its line
    on stderr, where no solver file stands at the argument (`missing`),
    or, under `task`, where its task has no task file (`no_task`)."""
    if missing(arg):
        return None
    solver = load_solver(arg, eng)
    if task and no_task(solver):
        return None
    return solver


def no_task(solver: Solver) -> bool:
    """True, with its line on stderr, where the solver's task has no task
    file."""
    if solver.task is not None:
        return False
    print(text.NO_TASK.format(
        stem=solver.stem,
        path=checkout.shown(task_file(solver.task_id))),
        file=sys.stderr)
    return True


def compile_failure(eng: SouffleEngine, solver: Solver
                    ) -> Fault | CompileError | UngroundedVariable \
        | None:
    """The fault of a solver that does not parse (`parse_fault`), or else
    the engine's rejection of its program, from a run on the empty input;
    None where the program compiles."""
    parse = parse_fault(solver)
    if parse is not None:
        return parse
    got = Runs(eng, solver, LIMITS).relations_on(None, [OUTPUT],
                                                 Assignment(()))
    return got if isinstance(got, CompileError | UngroundedVariable) \
        else None


def compiles(eng: SouffleEngine, solver: Solver) -> bool:
    """True where the solver's program compiles; False, with the lines of
    its `compile_failure` (`failed_lines`), where it does not."""
    failure = compile_failure(eng, solver)
    if failure is not None:
        print("\n".join(failed_lines(solver, failure)))
        return False
    off = open_value_off(eng, solver)
    if off:
        print("\n".join(commands.lint_section(solver, off)))
        return False
    return True


def open_value_off(eng: SouffleEngine, solver: Solver) -> list[Finding]:
    """The lint findings of the fields of `OpenValue` off their form
    (`checker.lint.form.open_value_fields`): a run reads its grids
    through those fields, so a command runs nothing where one stands."""
    return check_open_value_field(solver, Runs(eng, solver, LIMITS))


def keys_off_lines(runs: Runs) -> list[str]:
    """Where a RIGID block's relations of `Determine` do not lead with the
    same key columns (`solver.determine.off_key_blocks`), the line that
    reports the determination as not run and the lint section of the
    `check_determine_schema` findings; none elsewhere."""
    solver = runs.solver
    off = off_key_blocks(solver)
    if not off:
        return []
    return determination_lines(solver, KeysOff(off), []) \
        + commands.lint_section(solver, check_determine_schema(solver, runs))


def failed_lines(solver: Solver,
                 failure: Fault | CompileError | UngroundedVariable
                 ) -> list[str]:
    """The lines a `compile_failure` prints, before anything runs: the
    fault's (`failure_lines`), or the engine's rejection under the
    solver's name."""
    if isinstance(failure, Fault):
        return failure_lines(solver, failure)
    return [commands.failed_line(solver, failure)]


def failure_lines(solver: Solver, failure: RunFailure | Fault) -> list[str]:
    """The lines of a fault, or of a run that gave no result, as a
    command prints them once its runs began."""
    if isinstance(failure, Fault):
        return fault_lines(solver, [failure])
    return [run_failed(failure)]


def fault_lines(solver: Solver, faults: Sequence[Fault]) -> list[str]:
    """The lines of each fault, as every command prints it."""
    return [ln for f in faults for ln in finding_lines(solver, finding_of(f))]


def print_faults(solver: Solver, faults: Sequence[Fault],
                 file: TextIO = sys.stderr) -> None:
    """The faults' lines (`fault_lines`), on stderr unless `file` says
    otherwise."""
    for line in fault_lines(solver, faults):
        print(line, file=file)


# The grid a caller writes

SEPARATOR = "---"
"""The line that splits a witness input from the judged output behind it."""


def grid_text(path: str | None) -> str | None:
    """The grid text at the path a caller gives, from stdin when the path
    is omitted or `-`. None, with its line on stderr, where no file stands
    there."""
    if path in (None, "-"):
        return sys.stdin.read()
    p = Path(str(path))
    if not p.exists():
        print(text.NO_GRID_FILE.format(path=p), file=sys.stderr)
        return None
    return p.read_text()


def sections(written: str) -> list[str]:
    """The grid texts the caller wrote, split at each separator line."""
    out: list[str] = [""]
    for line in written.splitlines():
        if line.strip() == SEPARATOR:
            out.append("")
        else:
            out[-1] += line + "\n"
    return out


def parse_grid(written: str) -> Grid | None:
    """The grid the text writes (`arc.task.read_grid`). None, with its
    line on stderr, where it writes none."""
    try:
        return as_grid(read_grid(written))
    except GridFormError as e:
        print(text.BAD_GRID.format(error=e), file=sys.stderr)
        return None


def written_grids(path: str | None, most: int, too_many: str
                  ) -> list[Grid] | None:
    """The grids a caller writes at `path` (`grid_text`), one per section
    (`sections`), at most `most` of them. None, with its line on stderr,
    where no file stands there, where the text holds more sections, with
    the line `too_many`, or where a section writes no grid."""
    written = grid_text(path)
    if written is None:
        return None
    parts = sections(written)
    if len(parts) > most:
        print(too_many, file=sys.stderr)
        return None
    grids: list[Grid] = []
    for part in parts:
        grid = parse_grid(part)
        if grid is None:
            return None
        grids.append(grid)
    return grids


def assign_arg(written: str | None
               ) -> tuple[tuple[str, AssignValue], ...] | None:
    """The `--assign` object as a witness entry's `assign`, read by the
    witness file's reader; empty where the flag is omitted. None, with its
    line on stderr, where the text is no `assign` object."""
    if written is None:
        return ()
    try:
        data = json.loads(written)
    except json.JSONDecodeError as e:
        print(text.BAD_ASSIGN_JSON.format(error=e), file=sys.stderr)
        return None
    got, problems = read_assign(data)
    if got is None or problems:
        print(text.ASSIGN_NOT_OBJECT, file=sys.stderr)
        return None
    return got


# The stamp

SOURCES = ["src/engine/**/*.py", "src/souffle/**/*.py", "src/solver/**/*.py",
           "src/checker/**/*.py", "src/cli/**/*.py", "src/arc/**/*.py",
           "src/controlled_markdown/**/*.py",
           "programs/lib.dl",
           "programs/lib/*.dl", "programs/proposers.dl",
           (FUNCTOR_DIR / FUNCTOR_SOURCE).relative_to(
               checkout.ROOT).as_posix()]
"""What a run's result depends on besides the solver and the task: the
packages' code and the Souffle sources every solver includes."""


def stamp() -> str:
    """A short hash of the sources, the same for two runs with the same
    code."""
    return checkout.sources_digest(SOURCES)[:10]
