"""The grids cases give on an input: `outcomes`, which every run of cases
goes through, and the program and the relations of one case on an input."""

from collections.abc import Mapping, Sequence

from engine import (
    Engine,
    Grid,
    Limits,
    Program,
    RelationName,
    Rows,
    RunFailure,
    Tuples,
)
from solver.aggregate import (
    Solver,
)
from solver.determine import probe
from solver.group_runs import StoredValues, assigned, group_program, read_runs, run_input, runs_on
from solver.model import (
    Case,
    DeriveBranch,
)
from solver.outcome import Assignment, Outcome
from solver.problems import (
    Fault,
    InWitnessFile,
    WitnessFileRole,
)
from solver.run_parts import (
    input_task,
)
from solver.vocabulary import (
    INPUT,
)
from solver.witness import (
    Entry,
    Undefined,
)


def outcomes(engine: Engine, solver: Solver, cases: Sequence[Case],
             input: Grid, assign: Assignment, limits: Limits
             ) -> Mapping[Case, Outcome]:
    """The grids each of `cases` gives on `input` at `assign`, or
    undefined, or the failure of a run it needs, by case in the order
    given.

    Cases that take the same `@derive` and `@store` branches share one run,
    with `impl_choice` holding their bases, and each case reads its grids from
    `out` at its case (solver-file.md, under "Cases"); where `out` has no case
    column, each base runs alone. In that run each parameter `assign` names
    holds its value there, save one a `@derive` branch of the cases derives:
    for that one the value reassigns its stored value, which the cases do not
    read (history 826). Each `@derive` branch's parameter holds the values its
    proposer gives with `input` as its example (solver-file.md, under
    "Params"); where the proposer gives none, the cases are undefined on
    `input`, and no run holds the parameter empty (principles.md, under
    "Stored or derived"). Each `@store` branch's relation holds the value
    `assign` gives it, else the value it stores at the cases' bases
    (`stored_value`, solver-file.md, under "Program"; history 1131). A case
    with no cells in `out`, or a grid that is not total, is undefined
    (principles.md, under "Models and tasks").

    Every run of cases goes through here, those of `pairs` and of every
    variation among them: the solver's `program` is the one that runs, so a
    variation runs on the solver with its program replaced. `limits` are
    those of a run on one grid, which the command passes from its option,
    as they are for every solve function."""
    return _outcomes(engine, solver, cases, input, assign, limits, StoredValues())


def _outcomes(engine: Engine, solver: Solver, cases: Sequence[Case],
              input: Grid, assign: Assignment, limits: Limits,
              stored: StoredValues) -> dict[Case, Outcome]:
    """`outcomes`, with the stored values `stored` holds."""
    return _outcomes_on(engine, solver, cases, ((input, assign),), limits,
                        stored)[0]


def outcomes_on(engine: Engine, solver: Solver, cases: Sequence[Case],
                inputs: Sequence[tuple[Grid, Assignment]], limits: Limits
                ) -> list[dict[Case, Outcome]]:
    """`outcomes` on each input at its assignment, in the order of
    `inputs`, the runs of every input made at once."""
    return _outcomes_on(engine, solver, cases, inputs, limits, StoredValues())


def _outcomes_on(engine: Engine, solver: Solver, cases: Sequence[Case],
                 inputs: Sequence[tuple[Grid, Assignment]], limits: Limits,
                 stored: StoredValues) -> list[dict[Case, Outcome]]:
    """`outcomes_on`, with the stored values `stored` holds."""
    return [read_runs(runs, cases)
            for runs in runs_on(engine, solver, cases, inputs, limits, stored)]


def outcome(engine: Engine, solver: Solver, case: Case, input: Grid,
            assign: Assignment, limits: Limits) -> Outcome:
    """The grids `case` gives on `input` at `assign`, or undefined, or the
    run's failure: `outcomes` for the one case."""
    return outcomes(engine, solver, (case,), input, assign, limits)[case]


def relations_at(engine: Engine, solver: Solver, case: Case,
                 input: Grid | None, relations: Sequence[RelationName],
                 assign: Assignment, limits: Limits, cap: int | None = None
                 ) -> Mapping[RelationName, Rows] | Undefined | RunFailure:
    """The rows each of `relations`, named from the top level, holds when
    `case` runs on `input` at `assign`, the empty input where `input` is
    None: one run of the program `outcomes` builds for the case, with
    `impl_choice` holding its base and its `@derive` and `@store` branches
    in place. Undefined where a derivation of the case gives its parameter
    no value on the input; the run's failure, or that of a run the program
    needs, as the engine gives it. A relation with no rows maps to none.
    With `cap`, a relation holds at most `cap` plus one of its rows, all of
    them where it has at most `cap`, and the run prints none past those.

    The solver's `program` is the one that runs, so a variation runs
    through here on the solver with its program replaced. A relation the
    run does not output raises `ValueError` (`output_rows`)."""
    run = case_program(engine, solver, case, input, assign, limits)
    if not isinstance(run, Program):
        return run
    got = engine.run(run, {INPUT: run_input(input)}, list(relations), limits,
                     None if cap is None else dict.fromkeys(relations, cap))
    if not isinstance(got, Tuples):
        return got
    return output_rows(got, relations)


def output_rows(got: Tuples, relations: Sequence[RelationName]
                ) -> Mapping[RelationName, Rows]:
    """The rows of each of `relations` in a run's result. A relation the
    run does not output is a caller's error: `ValueError`."""
    missing = [r.text for r in relations if r not in got.relations]
    if missing:
        raise ValueError(f"the run outputs no {', '.join(missing)}")
    return {r: got.relations[r] for r in relations}


def case_program(engine: Engine, solver: Solver, case: Case,
                 input: Grid | None, assign: Assignment, limits: Limits
                 ) -> Program | Undefined | RunFailure:
    """The program `case` runs on `input`, the empty input where it is
    None, at `assign`, as `outcomes` builds it, with `impl_choice` holding
    the case's base, and as it stands for a case with no base; undefined
    where a derivation gives its parameter no value on `input`, and the
    failure of a run it needs where that run fails."""
    proposals = None if not any(isinstance(b, DeriveBranch)
                                for b in case.branches) \
        else probe(engine, input_task(() if input is None else input), limits)
    bases = () if case.base is None else (case.base,)
    return group_program(engine, solver, bases, case.branches, input, assign,
                    proposals, limits, StoredValues())


def assignment(engine: Engine, solver: Solver, entry: Entry,
               file: WitnessFileRole) -> Assignment | Fault:
    """The assignment a witness entry's `assign` states (solver-file.md, under
    "Witness file"): each parameter or `@store` relation it names with its
    rows, a string read as the lib constant it names and a list as a record,
    and a grid as the value of a parameter stored by one GRID call, under that
    call's keys and in its form, a sparse form reading every cell as a value:
    for a `GRID_STAMP` call, a grid of the call's size anchored where the
    call marks `@`, or a grid of any size at the anchor the entry gives. A
    name, a constant or a grid it cannot place is the problem in its place,
    at the entry of `file`."""
    return assigned(engine, solver, entry.assign,
                    InWitnessFile(entry.id, file))
