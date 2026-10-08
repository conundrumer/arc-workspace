"""The `grid` and `relation` commands: a run of one solver on a grid the
caller writes."""

import sys
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path

from checker import Runs
from checker.branches.witnesses import entry_outcomes
from checker.render import recording, relation, run_pairs
from cli import text
from cli.common import (
    LIMITS,
    assign_arg,
    command_solver,
    compiles,
    engine,
    failure_lines,
    written_grids,
)
from cli.record import shown_lines
from cli.witness_file import assign_of, assignment
from engine import Resolved
from engine.program import RelationName, Scope
from solver import witness, witnessed_cases
from solver.model import Case
from solver.aggregate import Solver
from solver.names import Denoted, denote, name
from solver.witness import Entry, Group, Groups, Outcomes, grouped, members
from souffle.parser import relation_name


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
    case each name denotes, or the solver's cases that stand for it. Then
    each constructor of `Choice` that no case of the solver takes
    (`recording.untaken_constructor_lines`)."""
    eng = engine()
    solver = command_solver(arg, eng, task=False)
    if solver is None:
        return 2
    assign = assign_of(eng, solver, assign_text)
    if assign is None:
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
            stand_ins = witnessed_cases.stand_ins(solver, solver_cases, denoted)
            if not stand_ins:
                print(text.NO_WITNESSED_TAKES.format(name=value), file=sys.stderr)
                return 2
            kept |= set(stand_ins)
        groups = _by_name(solver, outcomes, groups, kept)
    elif every:
        groups = _by_name(solver, outcomes, groups)
    shown = [c for c, _g in outcomes if not only or c in kept]
    lines = shown_lines(solver, replace(entry, output=groups), shown,
                   runs.case_count)
    of_solver = runs.solver_cases
    if not isinstance(of_solver, tuple):
        print("\n".join(failure_lines(solver, of_solver)), file=sys.stderr)
        return 1
    untaken = recording.untaken_constructor_lines(solver, of_solver)
    print("\n".join([*lines, *([""] + untaken if untaken else [])]))
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
    at = assignment(eng, solver, assign)
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
                        tuple(c.type.text for c in decl.columns)))
    if unknown:
        return 2
    ran = runs.relations_on(grid, names, at)
    if isinstance(ran, witness.Undefined):
        print(run_pairs.NO_GRID, file=sys.stderr)
        return 1
    if not isinstance(ran, Mapping):
        print("\n".join(failure_lines(solver, ran)), file=sys.stderr)
        return 1
    out: list[str] = []
    for i, (rel, (cols, types)) in enumerate(zip(names, columns,
                                                 strict=True)):
        if i:
            out.append("")
        rows = [[relation.souffle_text(solver, v, t) for v, t in
                 zip(r, types, strict=True)]
                for r in ran[rel]]
        out += relation.relation_lines(args[i], cols, rows)
    print("\n".join(out))
    return 0
