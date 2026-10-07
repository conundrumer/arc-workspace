"""The `record` command: the writes of `record` into the witness file,
and a run of the solver's cases on an entry's input as `record` prints
it."""

import argparse
import sys
from collections.abc import Iterable
from dataclasses import replace
from pathlib import Path

from checker import Runs
from checker.branches.witnesses import entry_outcomes
from checker.render import commands, recording
from checker.render.built import record_lines
from cli import text
from cli.common import (
    LIMITS,
    command_solver,
    compiles,
    engine,
    failure_lines,
    load_solver,
    print_faults,
    solver_path,
    written_grids,
)
from cli.witness_file import absent, assign_of, lined_solver, target, with_file
from souffle import SouffleEngine
from engine import RunFailure
from solver import witness
from solver.model import Case
from solver.aggregate import Solver
from solver.problems import Fault, WitnessFileRole
from solver.witness import (
    Entry,
    Groups,
    PartitionChanged,
    RejectedOutput,
    WitnessFile,
    grouped,
    rerecorded,
)

# A run of the solver's cases on an entry's input


type Failure = RunFailure | Fault


def _entry_failure(entry_id: str, solver: Solver, failure: Failure) -> str:
    """The line of an entry whose run again gave no result."""
    return commands.entry_line(entry_id, "; ".join(failure_lines(solver,
                                                                 failure)))


def shown_lines(solver: Solver, entry: Entry, cases: Iterable[Case], of: int
           ) -> list[str]:
    """A run as `record` prints it: the renderer's block without the
    blank line that leads it in a `derive` or `store` section; `cases`
    are the cases its groups were built from."""
    return record_lines(entry, solver, tuple(cases), of)


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
    changes = args.separates is not None or args.assign is not None
    if args.file is None and changes \
            and _held_entry(args.stem, args.id, args.witness_file) is not None:
        if args.assign is None and args.separates is not None:
            return cmd_reseparate(args.stem, args.id, args.separates,
                                  args.witness_file)
        return cmd_rerecord(args.stem, args.id, args.witness_file,
                            args.separates, args.assign)
    if args.separates is None:
        if args.file or args.assign:
            print(text.NEW_NEEDS_SEPARATES, file=sys.stderr)
            return 2
        return cmd_rerecord(args.stem, args.id, args.witness_file)
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
    lined = lined_solver(solver, at)
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
    print(recording.REMOVED.format(id=entry_id, path=at))
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
    print(recording.RESEPARATED.format(id=entry_id, path=at))
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
    assign = assign_of(eng, solver, assign_text)
    if assign is None:
        return 2
    grids = written_grids(path, 2, text.ONE_SEPARATOR)
    if grids is None:
        return 2
    grid, judged = grids[0], (grids[1] if len(grids) == 2 else None)
    at = target(solver, witness_file)
    lined = with_file(solver, at)
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
    lines = shown_lines(solver, entry, (c for c, _g in outcomes), runs.case_count)
    if judged is not None:
        lines += recording.judged_lines(judged)
        entry = replace(entry, output=RejectedOutput(judged))
    print("\n".join(lines))
    print()
    if not _write(solver, at, [entry]):
        return 2
    print(recording.WROTE.format(id=entry_id, path=at))
    return 0


def cmd_rerecord(arg: str, entry_id: str,
                 witness_file: str | None = None,
                 separates: str | None = None,
                 assign_text: str | None = None) -> int:
    """Run the witness `entry_id` again on its stored input, at the
    `assign` the caller gives or else the one the file holds, and rewrite
    its groups as `record` writes them, with the `separates` text the
    caller gives or else the one the file holds."""
    eng = engine()
    got = _entry_of(arg, entry_id, witness_file, eng)
    if got is None:
        return 2
    solver, lined, at, old = got
    if assign_text is not None:
        assign = assign_of(eng, solver, assign_text)
        if assign is None:
            return 2
        old = replace(old, assign=assign)
    if separates is not None:
        old = replace(old, separates=separates)
    lined = _with_entry(lined, old)
    if not compiles(eng, solver):
        return 1
    runs = Runs(eng, lined, LIMITS)
    got = rerecorded(lined, old, lambda: entry_outcomes(runs, old))
    if not isinstance(got, tuple):
        print(_entry_failure(entry_id, solver, got), file=sys.stderr)
        return 1
    entry, change = got
    built = runs.cases_or_none if isinstance(entry.output, Groups) else ()
    print("\n".join(shown_lines(lined, entry, built, runs.case_count)))
    if not _write(solver, at, [entry]):
        return 2
    print()
    print(recording.RERECORDED_ONE.format(id=entry_id, path=at,
                                     change=recording.rerecord_text(change)))
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
        print(commands.entry_line(e.id, recording.rerecord_text(change)))
        out.append(entry)
    n = len(entries)
    if failed:
        print(recording.WROTE_NOTHING.format(path=at, failed=failed, n=n))
        return 1
    written = witness.put_changed(at, solver.task_id, out)
    if not isinstance(written, bool):
        print_faults(solver, written)
        return 2
    if not written:
        print(recording.unchanged_file(n, at))
        return 0
    print(recording.rerecorded_all(n, at, changed))
    return 0


def cmd_format(arg: str, witness_file: str | None = None) -> int:
    """Rewrite the witness file through the writer, adding no entry."""
    solver = command_solver(arg, engine(), task=False)
    if solver is None:
        return 2
    at = target(solver, witness_file)
    if absent(at):
        return 2
    if not _write(solver, at, []):
        return 2
    print(recording.FORMATTED.format(path=at))
    return 0
