"""The `grid`, `relation` and `record` commands: a run of one solver on a
grid the caller writes, and the writes of `record` into the witness
file."""

import argparse
import sys
from collections.abc import Iterable, Mapping
from dataclasses import replace
from pathlib import Path

from checker import Runs
from checker.branches import entry_outcomes
from checker.render import commands
from checker.render.branches import record_lines
from cli import text
from cli.common import (
    LIMITS,
    assign_arg,
    command_solver,
    compiles,
    engine,
    failure_lines,
    load_solver,
    print_faults,
    solver_path,
    written_grids,
)
from souffle import SouffleEngine
from souffle.parser import relation_name
from engine import Engine, Resolved, RunFailure, checkout
from engine.program import RelationName, Scope
from solver import witness
from solver.model import Case, Solver, grid_stored, read_witness
from solver import solve
from solver.names import Denoted, denote, name
from solver.problems import Fault, InWitnessFile, WitnessFileRole
from solver.solve import Assignment, assigned
from solver.witness import (
    AssignValue,
    Entry,
    Group,
    Groups,
    Outcomes,
    PartitionChanged,
    RejectedOutput,
    WitnessFile,
    assign_with_grids,
    grouped,
    members,
    rerecorded,
)

# The witness file a command reads or writes


def target(solver: Solver, given: str | None) -> Path:
    """The witness file a command reads: `given` where the caller names
    one, the task's otherwise."""
    return Path(given) if given else witness.path(solver.task_id)


def in_witness_dir(path: Path) -> bool:
    return path.resolve().is_relative_to(witness.path("").parent.resolve())


def absent(path: Path, creates: bool) -> bool:
    """True, with its line on stderr, where no file stands at `path` and
    the command does not create one there: a command that writes creates
    a file outside the witness directory, and no command creates one in
    it."""
    if path.exists() or (creates and not in_witness_dir(path)):
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
    """The solver with the witness file at `path` in place of the task's;
    None, with the file's problems on stderr, where it is off its
    shape."""
    if not path.exists():
        return replace(solver, witness_file=None)
    file, problems = read_file(solver, path, WitnessFileRole.TASK)
    if file is None or problems:
        print_faults(solver, problems)
        return None
    return replace(solver, witness_file=file)


def lined_solver(solver: Solver, at: Path, creates: bool) -> Solver | None:
    """The solver with the witness file at `at` in place of the task's
    (`with_file`); None, with its line on stderr, where no file stands
    there and the command creates none (`absent`), or where the file is
    off its shape."""
    if absent(at, creates):
        return None
    return with_file(solver, at)


ASSIGN_ID = "assign"
"""The witness entry a problem of an `--assign` object is placed at."""


def _assignment(eng: Engine, solver: Solver,
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


# A run of the solver's cases on an entry's input


type Failure = RunFailure | Fault


def _entry_failure(entry_id: str, solver: Solver, failure: Failure) -> str:
    """The line of an entry whose run again gave no result."""
    return commands.entry_line(entry_id, "; ".join(failure_lines(solver,
                                                                 failure)))


def _shown(solver: Solver, entry: Entry, cases: Iterable[Case], of: int
           ) -> list[str]:
    """A run as `record` prints it: the renderer's block without the
    blank line that leads it in a `derive` or `store` section; `cases`
    are the cases its groups were built from."""
    return record_lines(entry, solver, tuple(cases), of)


# `grid`


def _by_name(solver: Solver, outcomes: Outcomes, groups: Groups,
             kept: set[Case] | None = None) -> Groups:
    """The groups of `grouped(solver, outcomes)` with each case named by
    its own name (`solver.names.name`); with `kept`, the cases of `kept`
    alone, and the groups that hold one of them."""
    out: list[Group] = []
    for g in groups.groups:
        cases = [c for c in members(outcomes, g) if kept is None or c in kept]
        if cases:
            out.append(Group(tuple(name(solver, c) for c in cases), g.grid))
    return Groups(tuple(out))


def cmd_grid(arg: str, path: str | None = None, every: bool = False,
             only: list[str] | None = None,
             assign_text: str | None = None) -> int:
    """What each case of the solver gives on a grid the caller writes, by the name
    `record` writes; with `every`, each case by its own name
    (`solver.names.name`); with `only`, the
    case each name denotes, or the solver's cases that stand for it."""
    eng = engine()
    solver = command_solver(arg, eng, task=False)
    if solver is None:
        return 2
    assign = assign_arg(assign_text)
    if assign is None or _assignment(eng, solver, assign) is None:
        return 2
    grids = written_grids(path, 1, text.GRID_ONE.format(command="grid"))
    if grids is None:
        return 2
    grid = grids[0]
    if not compiles(eng, solver):
        return 1
    runs = Runs(eng, solver, LIMITS)
    solver_cases = runs.cases
    if not isinstance(solver_cases, tuple):
        print("\n".join(failure_lines(solver, solver_cases)), file=sys.stderr)
        return 1
    entry = Entry("grid", "", grid, assign, Groups(()))
    outcomes = entry_outcomes(runs, entry)
    if not isinstance(outcomes, tuple):
        print("\n".join(failure_lines(solver, outcomes)), file=sys.stderr)
        return 1
    groups = grouped(solver, outcomes)
    kept: set[Case] = set()
    if only:
        for value in only:
            denoted = denote(solver, value)
            if not isinstance(denoted, Denoted):
                print(text.NO_CASE_NAMED.format(stem=solver.stem, name=value),
                      file=sys.stderr)
                return 2
            stand_ins = solve.stand_ins(solver, solver_cases, denoted)
            if not stand_ins:
                print(text.NO_HELD_TAKES.format(name=value), file=sys.stderr)
                return 2
            kept |= set(stand_ins)
        groups = _by_name(solver, outcomes, groups, kept)
    elif every:
        groups = _by_name(solver, outcomes, groups)
    shown = [c for c, _g in outcomes if not only or c in kept]
    print("\n".join(_shown(solver, replace(entry, output=groups), shown,
                           runs.case_count)))
    return 0


# `relation`


def cmd_relation(arg: str, args: list[str],
                 assign_text: str | None = None) -> int:
    """The rows of each relation `args` names, on a grid the caller
    writes; the last of `args` is the grid file where it is `-` or a
    file."""
    eng = engine()
    solver = command_solver(arg, eng, task=False)
    if solver is None:
        return 2
    path = None
    if len(args) > 1 and (args[-1] == "-" or Path(args[-1]).is_file()):
        args, path = args[:-1], args[-1]
    assign = assign_arg(assign_text)
    if assign is None:
        return 2
    at = _assignment(eng, solver, assign)
    if at is None:
        return 2
    grids = written_grids(path, 1, text.GRID_ONE.format(command="relation"))
    if grids is None:
        return 2
    grid = grids[0]
    if not compiles(eng, solver):
        return 1
    runs = Runs(eng, solver, LIMITS)
    index = runs.index
    names: list[RelationName] = []
    columns: list[tuple[tuple[str, ...], tuple[str, ...]]] = []
    unknown = False
    for a in args:
        rel = relation_name(a)
        got = index.resolve(rel, Scope(()))
        decl = solver.program.relation(got.declaration) \
            if isinstance(got, Resolved) else None
        if decl is None:
            print(text.NO_RELATION.format(name=a), file=sys.stderr)
            unknown = True
            continue
        names.append(rel)
        columns.append((tuple(c.name for c in decl.columns),
                        tuple(c.type for c in decl.columns)))
    if unknown:
        return 2
    ran = runs.relations_on(grid, names, at)
    if isinstance(ran, witness.Undefined):
        print(commands.NO_GRID, file=sys.stderr)
        return 1
    if not isinstance(ran, Mapping):
        print("\n".join(failure_lines(solver, ran)), file=sys.stderr)
        return 1
    out: list[str] = []
    for i, (rel, (cols, types)) in enumerate(zip(names, columns,
                                                 strict=True)):
        if i:
            out.append("")
        rows = [[commands.souffle_text(solver, v, t) for v, t in
                 zip(r, types, strict=True)]
                for r in ran[rel]]
        out += commands.relation_lines(args[i], cols, rows)
    print("\n".join(out))
    return 0


# `record`


def dispatch(args: argparse.Namespace) -> int:
    if args.remove:
        if (args.id is None or args.file or args.separates or args.assign
                or args.every or args.as_format):
            print(text.REMOVE_ALONE, file=sys.stderr)
            return 2
        return cmd_remove(args.stem, args.id, args.witness_file)
    if args.as_format:
        if (args.id or args.file or args.separates or args.assign
                or args.every):
            print(text.FORMAT_ALONE, file=sys.stderr)
            return 2
        return cmd_format(args.stem, args.witness_file)
    if args.every:
        if args.id or args.file or args.separates or args.assign:
            print(text.ALL_ALONE, file=sys.stderr)
            return 2
        return cmd_record_all(args.stem, args.witness_file)
    if args.id is None:
        print(text.RECORD_NEEDS, file=sys.stderr)
        return 2
    if args.separates is None:
        if args.file or args.assign:
            print(text.NEW_NEEDS_SEPARATES, file=sys.stderr)
            return 2
        return cmd_rerecord(args.stem, args.id, args.witness_file)
    if args.file is None and args.assign is None:
        held = _held_entry(args.stem, args.id, args.witness_file)
        if held is not None:
            return cmd_reseparate(args.stem, args.id, args.separates,
                                  args.witness_file)
    return cmd_record(args.stem, args.id, args.separates, args.file,
                      args.assign, args.witness_file)


def _file_of(arg: str, witness_file: str | None, eng: SouffleEngine
             ) -> tuple[Solver, Solver, Path, WitnessFile] | None:
    """The solver, the solver with its witness file (`lined_solver`), the
    file's path and the file; None, with its line on stderr, where one of
    them is not there."""
    solver = command_solver(arg, eng, task=False)
    if solver is None:
        return None
    at = target(solver, witness_file)
    lined = lined_solver(solver, at, creates=False)
    if lined is None or lined.witness_file is None:
        return None
    return solver, lined, at, lined.witness_file


def _entry_of(arg: str, entry_id: str, witness_file: str | None,
              eng: SouffleEngine
              ) -> tuple[Solver, Solver, Path, Entry] | None:
    """The solver, the solver with its witness file, the file's path and
    its entry `entry_id` (`_file_of`); None where one of them is not
    there, with its line on stderr."""
    got = _file_of(arg, witness_file, eng)
    if got is None:
        return None
    solver, lined, at, file = got
    old = file.entry(entry_id)
    if old is None:
        print(text.NO_ENTRY.format(id=entry_id, path=at), file=sys.stderr)
        return None
    return solver, lined, at, old


def _held_entry(arg: str, entry_id: str, witness_file: str | None
                ) -> Entry | None:
    """The witness file's entry `entry_id`, where the solver and the file
    stand and hold it; None otherwise, and nothing is printed."""
    if not solver_path(arg).is_file():
        return None
    solver = load_solver(arg, engine())
    at = target(solver, witness_file)
    if not at.is_file():
        return None
    file, problems = witness.read(at.read_text(), WitnessFileRole.TASK)
    if file is None or problems:
        return None
    return file.entry(entry_id)


def cmd_remove(arg: str, entry_id: str,
               witness_file: str | None = None) -> int:
    """Take the witness `entry_id` out of the witness file."""
    got = _entry_of(arg, entry_id, witness_file, engine())
    if got is None:
        return 2
    solver, _lined, at, _old = got
    problems = witness.remove(at, solver.task_id, [entry_id])
    print_faults(solver, problems)
    if problems:
        return 2
    print(commands.REMOVED.format(id=entry_id, path=at))
    return 0


def cmd_reseparate(arg: str, entry_id: str, separates: str,
                   witness_file: str | None = None) -> int:
    """Rewrite the `separates` text of the witness `entry_id`, its input,
    `assign` and groups kept."""
    got = _entry_of(arg, entry_id, witness_file, engine())
    if got is None:
        return 2
    solver, _lined, at, old = got
    if not _write(solver, at, [replace(old, separates=separates)]):
        return 2
    print(commands.RESEPARATED.format(id=entry_id, path=at))
    return 0


def _write(solver: Solver, at: Path, entries: list[Entry]) -> bool:
    """Put `entries` into the witness file at `at`; False, with the
    file's problems on stderr, where it is off its shape."""
    problems = witness.put(at, solver.task_id, entries)
    print_faults(solver, problems)
    return not problems


def _with_entry(solver: Solver, entry: Entry) -> Solver:
    """The solver with `entry` in its witness file, as `put` writes it
    (`solver.witness.with_entry`). The cases `record` groups are then the cases witnessed with the
    entry's input among the file's (solver-file.md, under "Cases"), which
    `witness` reads on the file `record` writes."""
    held = () if solver.witness_file is None \
        else solver.witness_file.entries
    entries = witness.with_entry(held, entry.id, entry, lambda e: e.id)
    return replace(solver, witness_file=WitnessFile(solver.task_id,
                                                    tuple(entries)))


def cmd_record(arg: str, entry_id: str, separates: str,
               path: str | None = None, assign_text: str | None = None,
               witness_file: str | None = None) -> int:
    """Run the solver's cases on a grid the caller writes and write the run
    into the witness file as the entry `entry_id`."""
    eng = engine()
    solver = command_solver(arg, eng)
    if solver is None:
        return 2
    assign = assign_arg(assign_text)
    if assign is None or _assignment(eng, solver, assign) is None:
        return 2
    grids = written_grids(path, 2, text.ONE_SEPARATOR)
    if grids is None:
        return 2
    grid, judged = grids[0], (grids[1] if len(grids) == 2 else None)
    at = target(solver, witness_file)
    lined = lined_solver(solver, at, creates=True)
    if lined is None:
        return 2
    if not compiles(eng, solver):
        return 1
    entry = Entry(entry_id, separates, grid, assign, Groups(()))
    runs = Runs(eng, _with_entry(lined, entry), LIMITS)
    outcomes = entry_outcomes(runs, entry)
    if not isinstance(outcomes, tuple):
        print("\n".join(failure_lines(solver, outcomes)), file=sys.stderr)
        return 1
    entry = replace(entry, output=grouped(solver, outcomes))
    lines = _shown(solver, entry, (c for c, _g in outcomes), runs.case_count)
    if judged is not None:
        lines += commands.judged_lines(judged)
        entry = replace(entry, output=RejectedOutput(judged))
    print("\n".join(lines))
    print()
    if not _write(solver, at, [entry]):
        return 2
    print(commands.WROTE.format(id=entry_id, path=at))
    return 0


def cmd_rerecord(arg: str, entry_id: str,
                 witness_file: str | None = None) -> int:
    """Run the witness `entry_id` again on its stored input and `assign`,
    and rewrite its groups as `record` writes them."""
    eng = engine()
    got = _entry_of(arg, entry_id, witness_file, eng)
    if got is None:
        return 2
    solver, lined, at, old = got
    if not compiles(eng, solver):
        return 1
    runs = Runs(eng, lined, LIMITS)
    got = rerecorded(lined, old, lambda: entry_outcomes(runs, old))
    if not isinstance(got, tuple):
        print(_entry_failure(entry_id, solver, got), file=sys.stderr)
        return 1
    entry, change = got
    built = runs.cases_or_none if isinstance(entry.output, Groups) else ()
    print("\n".join(_shown(lined, entry, built, runs.case_count)))
    if not _write(solver, at, [entry]):
        return 2
    print()
    print(commands.RERECORDED_ONE.format(id=entry_id, path=at,
                                     change=commands.rerecord_text(change)))
    return 0


def cmd_record_all(arg: str, witness_file: str | None = None) -> int:
    """Run every witness of the file again, as `cmd_rerecord` runs one;
    the file is written once, where its text is not what the writer
    writes (group order included), and not where any run fails. Changed
    groups are counted where the cases a group holds changed."""
    eng = engine()
    got = _file_of(arg, witness_file, eng)
    if got is None:
        return 2
    solver, lined, at, file = got
    if not compiles(eng, solver):
        return 1
    runs = Runs(eng, lined, LIMITS)
    entries = list(file.entries)
    failed = 0
    changed = 0
    out: list[Entry] = []
    for e in entries:
        got = rerecorded(lined, e, lambda: entry_outcomes(runs, e))
        if not isinstance(got, tuple):
            failed += 1
            print(_entry_failure(e.id, solver, got))
            continue
        entry, change = got
        changed += isinstance(change, PartitionChanged)
        print(commands.entry_line(e.id, commands.rerecord_text(change)))
        out.append(entry)
    n = len(entries)
    if failed:
        print(commands.WROTE_NOTHING.format(path=at, failed=failed, n=n))
        return 1
    written = witness.put_changed(at, solver.task_id, out)
    if not isinstance(written, bool):
        print_faults(solver, written)
        return 2
    if not written:
        print(commands.unchanged_file(n, at))
        return 0
    print(commands.rerecorded_all(n, at, changed))
    return 0


def cmd_format(arg: str, witness_file: str | None = None) -> int:
    """Rewrite the witness file through the writer, adding no entry."""
    solver = command_solver(arg, engine(), task=False)
    if solver is None:
        return 2
    at = target(solver, witness_file)
    if absent(at, creates=False):
        return 2
    if not _write(solver, at, []):
        return 2
    print(commands.FORMATTED.format(path=at))
    return 0

