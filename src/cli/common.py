"""What the commands share: the engine, the solver an argument names, the
limits of a run on one grid, the grid a caller writes, and the stamp of
the code a run loads."""

import hashlib
import json
import re
import sys
from pathlib import Path

from arc.task import TASKS_DIR
from arc.task import as_grid as checked_grid
from checker.readable import finding_of
from checker.render import commands, finding_lines
from cli import text
from engine import checkout
from engine import (
    CompileError,
    Grid,
    Limits,
    UngroundedVariable,
)
from solver.model import Case, Solver, load
from solver.problems import ProblemKind, Fault
from solver.solve import Assignment, as_grid, relations_at
from solver.vocabulary import OUTPUT
from solver.witness import AssignValue
from solver.witness import read as read_witness_file
from souffle import SouffleEngine

LIMITS = Limits(cpu_seconds=5.0, wall_seconds=10.0)
"""The limits of one run on one grid: five CPU seconds, and a wall clock
of twice that."""


def engine() -> SouffleEngine:
    """The engine every command runs through, with the functor library
    under `programs/` and the run cache under `.scratch/`."""
    return SouffleEngine()


# The solver an argument names


def stem_of(arg: str) -> str:
    """The stem an argument names: a stem, a file name, or the path of a
    solver file."""
    name = Path(arg).name
    return name[:-3] if name.endswith(".dl") else name


def solver_path(arg: str) -> Path:
    """The solver file an argument names: the path as given where a file
    stands there, else the file of that name under `programs/solvers/`."""
    path = Path(arg if arg.endswith(".dl") else f"{arg}.dl")
    return path if path.exists() else checkout.solvers() / path


def missing(arg: str) -> bool:
    """True, with its line on stderr, where no solver file stands at the
    argument, or it stands outside `programs/solvers/`, which `load` does
    not read."""
    path = solver_path(arg)
    if path.exists() \
            and path.resolve().parent == checkout.solvers().resolve():
        return False
    print(text.NO_SOLVER.format(path=path), file=sys.stderr)
    return True


def all_stems() -> list[str]:
    """The solver stems, dotfiles aside."""
    return sorted(p.stem for p in checkout.solvers().glob("*.dl")
                  if not p.name.startswith("."))


def load_solver(arg: str, eng: SouffleEngine) -> Solver:
    return load(stem_of(arg), eng)


def no_task(solver: Solver) -> bool:
    """True, with its line on stderr, where the solver's task has no task
    file."""
    if solver.task is not None:
        return False
    print(text.NO_TASK.format(
        stem=solver.stem,
        path=shown_path(TASKS_DIR / f"{solver.task_id}.json")),
        file=sys.stderr)
    return True


def compile_failure(eng: SouffleEngine, solver: Solver
                    ) -> Fault | CompileError | UngroundedVariable \
        | None:
    """The fault of a solver that does not parse, or else the
    engine's rejection of its program, from a run on the empty input; None
    where the program compiles."""
    parse = next((p for p in solver.problems
                  if p.kind == ProblemKind.PARSE_FAILURE), None)
    if parse is not None:
        return parse
    got = relations_at(eng, solver, Case(None, ()), None, [OUTPUT],
                       Assignment(()), LIMITS)
    return got if isinstance(got, CompileError | UngroundedVariable) \
        else None


def failed_lines(solver: Solver,
                 failure: Fault | CompileError | UngroundedVariable
                 ) -> list[str]:
    """The lines a `compile_failure` prints, before anything runs."""
    if isinstance(failure, Fault):
        return finding_lines(solver, finding_of(failure))
    return [commands.failed_line(solver, failure)]


def shown_path(path: Path) -> Path:
    """A path as a line shows it: from the repository root where it
    stands under it."""
    repo = checkout.ROOT
    for p, root in ((path.absolute(), repo), (path.resolve(), repo.resolve())):
        if p.is_relative_to(root):
            return p.relative_to(root)
    return path.resolve()


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
    """The grid the text writes: one line per row, one digit per cell,
    spaces and commas between cells optional, blank lines and `#` lines
    skipped, and text that starts with `[` read as JSON. None, with its
    line on stderr, where it writes none."""
    stripped = written.strip()
    try:
        if stripped.startswith("["):
            rows = json.loads(stripped)
        else:
            rows = [[int(ch) for ch in re.sub(r"[\s,]", "", line)]
                    for line in stripped.splitlines()
                    if line.strip() and not line.lstrip().startswith("#")]
        return as_grid(checked_grid(rows))
    except (ValueError, json.JSONDecodeError, TypeError) as e:
        print(text.BAD_GRID.format(error=e), file=sys.stderr)
        return None


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
    if not isinstance(data, dict):
        print(text.ASSIGN_NOT_OBJECT, file=sys.stderr)
        return None
    file, problems = read_witness_file(json.dumps({
        "id": "", "witnesses": [{"id": "assign", "separates": "",
                                 "input": [[0]], "assign": data,
                                 "output": [[0]]}]}))
    if file is None or problems or not file.entries:
        print(text.ASSIGN_NOT_OBJECT, file=sys.stderr)
        return None
    return file.entries[0].assign


# The stamp

SOURCES = ["src/engine/**/*.py", "src/souffle/**/*.py", "src/solver/**/*.py",
           "src/checker/**/*.py", "src/cli/**/*.py", "programs/lib.dl",
           "programs/lib/*.dl", "programs/proposers.dl",
           "programs/lib_functors.cpp"]
"""What a run's result depends on besides the solver and the task: the
packages' code and the Souffle sources every solver includes."""


def stamp() -> str:
    """A short hash of the sources, the same for two runs with the same
    code."""
    digest = hashlib.sha256()
    for pattern in SOURCES:
        for path in sorted(checkout.ROOT.glob(pattern)):
            digest.update(str(path.relative_to(checkout.ROOT)).encode()
                          + b"\0")
            digest.update(path.read_bytes() + b"\0")
    return digest.hexdigest()[:10]
