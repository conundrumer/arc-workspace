"""The `grid`, `relation` and `record` commands: a run of one solver on a
grid the caller writes, and the writes of `record` into the witness
file."""

import argparse
import sys
from collections.abc import Iterable, Mapping
from dataclasses import replace
from pathlib import Path

from checker import Runs
from checker.judged import base_constructors
from checker.readable import finding_of
from checker.render import commands, failure_text, finding_lines
from checker.render.branches import record_lines
from checker.render.commands import (
    GroupsChanged,
    GroupsKept,
    JudgedKept,
    NamesRewritten,
    RecordChange,
)
from cli import text
from cli.common import (
    LIMITS,
    assign_arg,
    compile_failure,
    failed_lines,
    engine,
    grid_text,
    load_solver,
    missing,
    no_task,
    parse_grid,
    sections,
    shown_path,
)
from engine import Grid, Resolved, RunFailure
from engine.program import RelationName, Scope
from solver import witness
from solver.model import Case, Solver, StoredGrid, concept_branch
from solver.names import Denoted, cases_of, denote, model_of, name
from solver.names import denoted_cases as cases_denoted
from solver.problems import Fault
from solver.solve import (
    Assignment, Grids, assignment, group_grid, relations_at)
from solver.witness import (
    AssignValue,
    Entry,
    Group,
    GroupGrid,
    Groups,
    RejectedOutput,
    same_output,
    Undefined,
    WitnessFile,
    grouped,
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
    print(line.format(path=shown_path(path)), file=sys.stderr)
    return True


def read_file(solver: Solver, path: Path
              ) -> tuple[WitnessFile | None, tuple[Fault, ...]]:
    """The witness file at `path`, with each `assign` value of a
    GRID-stored parameter read as a grid, and what could not be read."""
    file, problems = witness.read(path.read_text())
    if file is None:
        return None, problems
    grids = frozenset(p.name for p in solver.params.parameters
                      if isinstance(p.stored, StoredGrid))
    file, more = witness.with_grids(file, grids)
    return file, problems + more


def with_file(solver: Solver, path: Path) -> Solver | None:
    """The solver with the witness file at `path` in place of the task's;
    None, with the file's problems on stderr, where it is off its
    shape."""
    if not path.exists():
        return replace(solver, witness_file=None)
    file, problems = read_file(solver, path)
    if file is None or problems:
        for p in problems:
            for line in finding_lines(solver, finding_of(p)):
                print(line, file=sys.stderr)
        return None
    return replace(solver, witness_file=file)


def _assignment(solver: Solver, assign: tuple[tuple[str, AssignValue], ...]
                ) -> Assignment | None:
    """The assignment an `--assign` object states; None, with the problem
    on stderr, where it names what the solver lacks."""
    grids = frozenset(p.name for p in solver.params.parameters
                      if isinstance(p.stored, StoredGrid))
    file, _problems = witness.with_grids(
        WitnessFile(solver.task_id, (Entry("assign", "", ((0,),), assign,
                                           Groups(())),)), grids)
    at = assignment(solver, file.entries[0])
    if isinstance(at, Fault):
        for line in finding_lines(solver, finding_of(at)):
            print(line, file=sys.stderr)
        return None
    return at


# A run of the solver's cases on an entry's input


type Failure = RunFailure | Fault

type Outcomes = tuple[tuple[Case, GroupGrid], ...]


def case_outcomes(runs: Runs, entry: Entry) -> Outcomes | Failure:
    """What each case of the solver gives on the entry's input at its
    `assign`, in the order the cases come in: a grid, a list of grids per
    resolution (history 1119), or undefined. The first run with no
    result, or the problem that stops the entry's assignment, in its
    place."""
    solver_cases = runs.cases
    if not isinstance(solver_cases, tuple):
        return solver_cases
    at = runs.assignment(entry)
    if isinstance(at, Fault):
        return at
    out: list[tuple[Case, GroupGrid]] = []
    for c in solver_cases:
        got = runs.outcome(entry, c)
        if not isinstance(got, Grids | Undefined):
            return got
        out.append((c, group_grid(got)))
    return tuple(out)


def members(outcomes: Outcomes, group: Group) -> tuple[Case, ...]:
    """The cases a group of `grouped(solver, outcomes)` holds: those that
    give its grid."""
    return tuple(c for c, g in outcomes if same_output(g, group.grid))


def failure_lines(solver: Solver, failure: Failure) -> list[str]:
    if isinstance(failure, Fault):
        return finding_lines(solver, finding_of(failure))
    return [commands.RUN_FAILED.format(error=failure_text(failure))]


def _shown(solver: Solver, entry: Entry, cases: Iterable[Case]
           ) -> list[str]:
    """A run as `record` prints it: the renderer's block without the
    blank line that leads it in a `derive` or `store` section; `cases`
    are the cases its groups were built from."""
    return record_lines(entry, solver, tuple(cases))[1:]


# `grid`


def _stand_ins(solver: Solver, solver_cases: tuple[Case, ...],
               denoted: Denoted) -> list[Case]:
    """The model of the branches a `--case` name denotes
    (`solver.names.model_of`, principles.md:116) where it is a case of the
    solver; where it is none, the solver's cases that take those branches
    (`solver.names.cases_of`) and differ from the concept case at the
    fewest choice points."""
    model = model_of(solver, denoted, solver_cases)
    if model is not None and model in solver_cases:
        return [model]
    taking = cases_of(solver, denoted, solver_cases)
    firsts = set() if solver.choice is None else {
        concept_branch(p).name for p in solver.choice.points
        if p.constructors}

    def away(c: Case) -> int:
        return sum(1 for n in base_constructors(c.base) if n not in firsts) \
            + len(c.branches)

    least = min((away(c) for c in taking), default=0)
    return [c for c in taking if away(c) == least]


def cmd_grid(arg: str, path: str | None = None, every: bool = False,
             only: list[str] | None = None,
             assign_text: str | None = None) -> int:
    """What each case of the solver gives on a grid the caller writes, by the name
    `record` writes; with `every`, each case by its own name
    (`solver.names.name`); with `only`, the
    case each name denotes, or the solver's cases that stand for it."""
    if missing(arg):
        return 2
    assign = assign_arg(assign_text)
    if assign is None:
        return 2
    eng = engine()
    solver = load_solver(arg, eng)
    if _assignment(solver, assign) is None:
        return 2
    written = grid_text(path)
    if written is None:
        return 2
    if len(sections(written)) > 1:
        print(text.GRID_ONE.format(command="grid"), file=sys.stderr)
        return 2
    grid = parse_grid(written)
    if grid is None:
        return 2
    failure = compile_failure(eng, solver)
    if failure is not None:
        print("\n".join(failed_lines(solver, failure)))
        return 1
    runs = Runs(eng, solver, LIMITS)
    solver_cases = runs.cases
    if not isinstance(solver_cases, tuple):
        print(commands.RUN_FAILED.format(error=failure_text(solver_cases)),
              file=sys.stderr)
        return 1
    entry = Entry("grid", "", grid, assign, Groups(()))
    outcomes = case_outcomes(runs, entry)
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
            stand_ins = _stand_ins(solver, solver_cases, denoted)
            if not stand_ins:
                print(text.NO_HELD_TAKES.format(name=value), file=sys.stderr)
                return 2
            kept |= set(stand_ins)
        groups = Groups(tuple(
            Group(tuple(name(solver, c)
                        for c in members(outcomes, g) if c in kept), g.grid)
            for g in groups.groups
            if any(c in kept for c in members(outcomes, g))))
    elif every:
        groups = Groups(tuple(
            Group(tuple(name(solver, c) for c in members(outcomes, g)),
                  g.grid) for g in groups.groups))
    shown = [c for c, _g in outcomes if not only or c in kept]
    print("\n".join(_shown(solver, replace(entry, output=groups), shown)))
    return 0


# `relation`


def cmd_relation(arg: str, args: list[str],
                 assign_text: str | None = None) -> int:
    """The rows of each relation `args` names, on a grid the caller
    writes; the last of `args` is the grid file where it is `-` or a
    file."""
    if missing(arg):
        return 2
    path = None
    if len(args) > 1 and (args[-1] == "-" or Path(args[-1]).is_file()):
        args, path = args[:-1], args[-1]
    assign = assign_arg(assign_text)
    if assign is None:
        return 2
    eng = engine()
    solver = load_solver(arg, eng)
    at = _assignment(solver, assign)
    if at is None:
        return 2
    written = grid_text(path)
    if written is None:
        return 2
    if len(sections(written)) > 1:
        print(text.GRID_ONE.format(command="relation"), file=sys.stderr)
        return 2
    grid = parse_grid(written)
    if grid is None:
        return 2
    failure = compile_failure(eng, solver)
    if failure is not None:
        print("\n".join(failed_lines(solver, failure)))
        return 1
    index = eng.index(solver.program)
    names: list[RelationName] = []
    columns: list[tuple[tuple[str, ...], tuple[str, ...]]] = []
    decls = {r.id: r for r in solver.program.relations}
    unknown = False
    for a in args:
        parts = a.split(".")
        rel = RelationName(tuple(parts[:-1]), parts[-1])
        got = index.resolve(rel, Scope(()))
        decl = decls.get(got.declaration) if isinstance(got, Resolved) \
            else None
        if decl is None:
            print(text.NO_RELATION.format(name=a), file=sys.stderr)
            unknown = True
            continue
        names.append(rel)
        columns.append((tuple(c.name for c in decl.columns),
                        tuple(c.type for c in decl.columns)))
    if unknown:
        return 2
    ran = relations_at(eng, solver, Case(None, ()), grid, names, at, LIMITS)
    if isinstance(ran, witness.Undefined):
        print(commands.NO_GRID, file=sys.stderr)
        return 1
    if not isinstance(ran, Mapping):
        print(commands.RUN_FAILED.format(error=failure_text(ran)),
              file=sys.stderr)
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
    return cmd_record(args.stem, args.id, args.separates, args.file,
                      args.assign, args.witness_file)


def _write(solver: Solver, at: Path, entries: list[Entry]) -> bool:
    """Put `entries` into the witness file at `at`; False, with the
    file's problems on stderr, where it is off its shape."""
    problems = witness.put(at, solver.task_id, entries)
    for p in problems:
        for line in finding_lines(solver, finding_of(p)):
            print(line, file=sys.stderr)
    return not problems


def _hint(solver: Solver, entry_id: str) -> str | None:
    """The `@witness` line the session adds for a new entry, where no
    `@witness`, `@derive` or `@store` line of that id stands."""
    a = solver.annotations
    if any(w.id == entry_id for w in a.witnesses):
        return None
    denoted = denote(solver, entry_id)
    if isinstance(denoted, Denoted) and not denoted.constructors \
            and len(denoted.branches) == 1:
        return None
    return commands.WITNESS_HINT.format(id=entry_id)


def cmd_record(arg: str, entry_id: str, separates: str,
               path: str | None = None, assign_text: str | None = None,
               witness_file: str | None = None) -> int:
    """Run the solver's cases on a grid the caller writes and write the run
    into the witness file as the entry `entry_id`."""
    if missing(arg):
        return 2
    assign = assign_arg(assign_text)
    if assign is None:
        return 2
    eng = engine()
    solver = load_solver(arg, eng)
    if no_task(solver):
        return 2
    if _assignment(solver, assign) is None:
        return 2
    written = grid_text(path)
    if written is None:
        return 2
    parts = sections(written)
    if len(parts) > 2:
        print(text.ONE_SEPARATOR, file=sys.stderr)
        return 2
    grid = parse_grid(parts[0])
    if grid is None:
        return 2
    judged: Grid | None = None
    if len(parts) == 2:
        judged = parse_grid(parts[1])
        if judged is None:
            return 2
    at = target(solver, witness_file)
    if absent(at, creates=True):
        return 2
    lined = with_file(solver, at)
    if lined is None:
        return 2
    failure = compile_failure(eng, solver)
    if failure is not None:
        print("\n".join(failed_lines(solver, failure)))
        return 1
    entry = Entry(entry_id, separates, grid, assign, Groups(()))
    outcomes = case_outcomes(Runs(eng, lined, LIMITS), entry)
    if not isinstance(outcomes, tuple):
        print("\n".join(failure_lines(solver, outcomes)), file=sys.stderr)
        return 1
    entry = replace(entry, output=grouped(solver, outcomes))
    lines = _shown(solver, entry, (c for c, _g in outcomes))
    if judged is not None:
        lines += commands.judged_lines(judged)
        entry = replace(entry, output=RejectedOutput(judged))
    print("\n".join(lines))
    print()
    if not _write(solver, at, [entry]):
        return 2
    print(commands.WROTE.format(id=entry_id, path=at))
    if (hint := _hint(solver, entry_id)) is not None:
        print(hint)
    return 0


def _listing[T](groups: Iterable[tuple[Iterable[T], GroupGrid]]
                ) -> frozenset[tuple[frozenset[T], GroupGrid]]:
    """Groups as what each lists and its grid, in no order."""
    return frozenset((frozenset(cs), g) for cs, g in groups)


def _again(solver: Solver, runs: Runs, entry: Entry
           ) -> tuple[Entry, RecordChange] | Failure:
    """The entry with its groups run again on its input and `assign`, and
    what that changes in it; a judged output stays. The failure where a
    run gives no result."""
    if isinstance(entry.output, RejectedOutput):
        return entry, JudgedKept()
    outcomes = case_outcomes(runs, entry)
    if not isinstance(outcomes, tuple):
        return outcomes
    groups = grouped(solver, outcomes)
    got = replace(entry, output=groups)
    if _listing((g.cases, g.grid) for g in groups.groups) \
            == _listing((g.cases, g.grid) for g in entry.output.groups):
        return got, GroupsKept()
    among = [c for c, _g in outcomes]
    old: list[tuple[frozenset[Case], GroupGrid]] = []
    unheld = 0
    for g in entry.output.groups:
        listed: set[Case] = set()
        for n in g.cases:
            denoted = cases_denoted(solver, n, among)
            if isinstance(denoted, Fault) or not denoted:
                unheld += 1
            else:
                listed |= denoted
        old.append((frozenset(listed), g.grid))
    if not unheld and _listing(old) == _listing(
            (members(outcomes, g), g.grid) for g in groups.groups):
        return got, NamesRewritten()
    was = {c for cs, _g in old for c in cs}
    return got, GroupsChanged(len(set(among) - was), unheld)


def cmd_rerecord(arg: str, entry_id: str,
                 witness_file: str | None = None) -> int:
    """Run the witness `entry_id` again on its stored input and `assign`,
    and rewrite its groups as `record` writes them."""
    if missing(arg):
        return 2
    eng = engine()
    solver = load_solver(arg, eng)
    at = target(solver, witness_file)
    if absent(at, creates=False):
        return 2
    lined = with_file(solver, at)
    if lined is None or lined.witness_file is None:
        return 2
    old = next((e for e in lined.witness_file.entries if e.id == entry_id),
               None)
    if old is None:
        print(text.NO_ENTRY.format(id=entry_id, path=at), file=sys.stderr)
        return 2
    failure = compile_failure(eng, solver)
    if failure is not None:
        print("\n".join(failed_lines(solver, failure)))
        return 1
    runs = Runs(eng, lined, LIMITS)
    got = _again(lined, runs, old)
    if not isinstance(got, tuple):
        print(commands.entry_line(
            entry_id, "; ".join(failure_lines(solver, got))), file=sys.stderr)
        return 1
    entry, change = got
    built = runs.cases if isinstance(entry.output, Groups) \
        and isinstance(runs.cases, tuple) else ()
    print("\n".join(_shown(lined, entry, built)))
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
    if missing(arg):
        return 2
    eng = engine()
    solver = load_solver(arg, eng)
    at = target(solver, witness_file)
    if absent(at, creates=False):
        return 2
    lined = with_file(solver, at)
    if lined is None or lined.witness_file is None:
        return 2
    failure = compile_failure(eng, solver)
    if failure is not None:
        print("\n".join(failed_lines(solver, failure)))
        return 1
    runs = Runs(eng, lined, LIMITS)
    entries = list(lined.witness_file.entries)
    failed = 0
    changed = 0
    out: list[Entry] = []
    for e in entries:
        got = _again(lined, runs, e)
        if not isinstance(got, tuple):
            failed += 1
            print(commands.entry_line(
                e.id, "; ".join(failure_lines(solver, got))))
            continue
        entry, change = got
        changed += isinstance(change, GroupsChanged)
        print(commands.entry_line(e.id, commands.rerecord_text(change)))
        out.append(entry)
    n = len(entries)
    if failed:
        print(commands.WROTE_NOTHING.format(path=at, failed=failed, n=n))
        return 1
    written = witness.put_changed(at, solver.task_id, out)
    if not isinstance(written, bool):
        for p in written:
            for line in finding_lines(solver, finding_of(p)):
                print(line, file=sys.stderr)
        return 2
    if not written:
        print(commands.unchanged_file(n, at))
        return 0
    print(commands.rerecorded_all(n, at, changed))
    return 0


def cmd_format(arg: str, witness_file: str | None = None) -> int:
    """Rewrite the witness file through the writer, adding no entry."""
    if missing(arg):
        return 2
    eng = engine()
    solver = load_solver(arg, eng)
    at = target(solver, witness_file)
    if absent(at, creates=False):
        return 2
    if not _write(solver, at, []):
        return 2
    print(commands.FORMATTED.format(path=at))
    return 0

