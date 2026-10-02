"""Solving over an engine: the grids cases give on an input, the pair runs,
the variations of a solver's program, the proposer probe and the Determine
run, and the helpers of those runs that the checks read as well."""

import hashlib
import json
import threading
from collections.abc import Callable, Iterator, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field, fields, is_dataclass, replace
from enum import Enum
from itertools import combinations
from typing import TYPE_CHECKING, Annotated

from pathlib import Path

from arc.task import Alt, Example, Task, pair_name
from engine import (
    checkout,
    AdtValue,
    Engine,
    Grid,
    GridInput,
    GridValue,
    IndexedGrids,
    InputValue,
    Limits,
    ParseFailure,
    Program,
    RecordValue,
    RelationName,
    RelationValue,
    RemovalTarget,
    Row,
    Rows,
    RunFailure,
    RunResult,
    Tuples,
    UnitId,
    Value,
)
from engine.engine import (
    AnchorOffStamp,
    CellOffForm,
    Classed,
    CompileError,
    RemoveUnit,
    SizeOffLayout,
    resolved,
)
from engine.memo import ByIdentity, Once, write_whole
from engine.program import (
    POSE_COLUMN,
    Atom,
    DefinedName,
    NumberTerm,
    RecordTerm,
    RelationDecl,
    RigidCall,
    Term,
    Unit,
)
from solver.annotations import VerdictWord
from engine.program import as_grid, body_atoms, grid_lists, grid_size, term_value
from engine.quotes import quotes
from solver.model import (
    branch_witnesses,
    is_concept_branch,
    constructors_taken,
    path_constructors,
    TOP,
    Base,
    Branch,
    Case,
    Choice,
    ChoicePoint,
    ConstructorBranch,
    DeriveBranch,
    assignable,
    constructor_named,
    is_concept_case,
    other_branches,
    Solver,
    StoreBranch,
    Parameter,
    StoredGrid,
    enumerates,
    every_base,
    case_types,
    cases as cases_of,
    dependence,
    has_determine,
    instance_of,
    own,
    proposer_names,
    proposers_program,
    column_types,
)
from solver.problems import (
    InWitnessFile,
    Named,
    ProblemKind,
    AnchorWithoutStamp,
    Fault,
    GridCellOffForm,
    GridOffLayout,
    Storage,
    Undecided,
    UndecidedForm,
    WitnessFileRole,
)
from solver.vocabulary import (
    CHOICE,
    DETERMINE,
    DETERMINE_SCOPE,
    IMPL,
    EX_IN,
    EX_OUT,
    IDENT,
    INPUT,
    OUTPUT,
    PARAMS,
    PARAMS_SCOPE,
    PROPOSE,
    TIEBREAK_RESOLUTION,
)
from solver.witness import (
    AnchoredGrid,
    AssignArg,
    AssignRows,
    AssignValue,
    Cell,
    ConflictingCells,
    Entry,
    GroupGrid,
    InconsistentBounds,
    MissingCells,
    NegativeEdges,
    NoDerivedValue,
    NoOutput,
    Resolutions,
    Undefined,
    UndefinedReason,
    same_output,
)

if TYPE_CHECKING:
    from typing_extensions import TypeIs

    from solver.names import Denoted



@dataclass(frozen=True)
class Assignment:
    """A value for each parameter or stored relation it names; the others
    keep their stored values."""

    values: tuple[tuple[str, RelationValue], ...]


@quotes("solver-file.md", "Cases",
        "A case's model reads its output grids from `out` at that case, one "
        "grid per tiebreak resolution")
@quotes("solver-file.md", "Alt outputs",
        "The solver enumerates a tiebreak's resolutions through a trailing "
        "`out` column of type `TiebreakResolution`.")
@dataclass(frozen=True)
class Grids:
    """The grids a case gives, one per tiebreak resolution, and the
    resolution value of each where `out` has a resolution column, the grid's
    identity."""

    grids: tuple[Grid, ...]
    resolutions: tuple[Value, ...] = field(default=(), compare=False)


type Outcome = Annotated[Grids | Undefined | RunFailure,
    quotes("principles.md", "Models and tasks",
           "A model is defined at an assignment and input when its output is "
           "nonempty and contains only total grids."),
    quotes("solver-file.md", "Cases",
           "and is undefined on an input where a grid's facts give two frame "
           "sizes.")]
"""What a case gives on an input: its grids, undefined, or the failure of
its run."""


def is_result(outcome: Outcome | Fault) -> "TypeIs[Grids | Undefined]":
    """Whether a run gave a result: grids, or undefined; not a run's
    failure, nor the fault that stopped the run."""
    return isinstance(outcome, Grids | Undefined)


def group_grid(outcome: Grids | Undefined) -> GroupGrid:
    """An outcome as a witness file's group holds it: one grid as a grid,
    more than one as a grid per resolution (history 1119), undefined as
    it is."""
    if isinstance(outcome, Undefined):
        return outcome
    if len(outcome.grids) == 1:
        return outcome.grids[0]
    return Resolutions(outcome.grids, outcome.resolutions)


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

    The solver's `program` is the one that runs, so a variation runs
    through here on the solver with its program replaced. `limits` are
    those of a run on one grid, which the command passes from its option,
    as they are for every solve function."""
    return _outcomes(engine, solver, cases, input, assign, limits, _Stored())


class _Stored:
    """The value each `@store` branch stores at a group's bases
    (`stored_value`), computed once for the runs of `outcomes`, and across
    the pairs of `pairs`."""

    def __init__(self) -> None:
        self.values: dict[tuple[tuple[Base, ...], RelationName],
                          StoredValue | RunFailure] = {}
        self.once: Once[tuple[tuple[Base, ...], RelationName],
                        StoredValue | RunFailure] = Once(self.values)

    def get(self, key: tuple[tuple[Base, ...], RelationName],
            compute: Callable[[], "StoredValue | RunFailure"]
            ) -> "StoredValue | RunFailure":
        """The value under `key`, computed once however many threads ask
        for it."""
        return self.once.get(
            key, lambda: self.values.setdefault(key, compute()))


def _outcomes(engine: Engine, solver: Solver, cases: Sequence[Case],
              input: Grid, assign: Assignment, limits: Limits,
              stored: _Stored) -> dict[Case, Outcome]:
    """`outcomes`, with the stored values `stored` holds."""
    return _outcomes_on(engine, solver, cases, ((input, assign),), limits,
                        stored)[0]


def outcomes_on(engine: Engine, solver: Solver, cases: Sequence[Case],
                inputs: Sequence[tuple[Grid, Assignment]], limits: Limits
                ) -> list[dict[Case, Outcome]]:
    """`outcomes` on each input at its assignment, in the order of
    `inputs`, the runs of every input made at once."""
    return _outcomes_on(engine, solver, cases, inputs, limits, _Stored())


def _outcomes_on(engine: Engine, solver: Solver, cases: Sequence[Case],
                 inputs: Sequence[tuple[Grid, Assignment]], limits: Limits,
                 stored: _Stored) -> list[dict[Case, Outcome]]:
    """`outcomes_on`, with the stored values `stored` holds."""
    return [read_runs(runs, cases)
            for runs in _runs_on(engine, solver, cases, inputs, limits, stored)]


@dataclass(frozen=True)
class GroupRun:
    """One run `outcomes` makes: the cases that read their grids from it,
    in the order given, and its result, or why the group has none."""

    cases: tuple[Case, ...]
    result: RunResult | Undefined


@dataclass(frozen=True)
class RunColumns:
    """How a case reads its grids from a group's run: `out`'s case and
    resolution columns (`out_columns`), and, where the run classes the
    cases (`classed`), the relation of the representatives' rows and the
    relation of the classes."""

    case: int | None
    resolution: int | None
    classed: tuple[RelationName, RelationName] | None = None


@dataclass(frozen=True)
class GroupRuns:
    """The runs `outcomes` makes on one input, in its order, and `out`'s
    case and resolution columns (`out_columns`), by which each case reads
    its grids from its run."""

    columns: RunColumns
    runs: tuple[GroupRun, ...]


def group_runs(engine: Engine, solver: Solver, cases: Sequence[Case],
               input: Grid, assign: Assignment, limits: Limits) -> GroupRuns:
    """The runs `outcomes` makes for `cases` on `input` at `assign`; its
    result is `read_runs` of them."""
    return _runs_on(engine, solver, cases, ((input, assign),), limits,
                    _Stored())[0]


def read_runs(runs: GroupRuns, cases: Sequence[Case]) -> dict[Case, Outcome]:
    """The outcome of each of `cases` from `runs`, by case in the order
    given: the failure of its run, else the grids its run's `out` holds at
    its case (`outcomes`)."""
    got: dict[Case, Outcome] = {}
    for run in runs.runs:
        got.update(read_run(runs.columns, run))
    return {c: got[c] for c in dict.fromkeys(cases)}


def read_run(columns: RunColumns, run: GroupRun) -> dict[Case, Outcome]:
    """The outcome of each case of one run (`read_runs`)."""
    result = run.result
    if not isinstance(result, Tuples):
        return dict.fromkeys(run.cases, result)
    read = _read_of(result, columns)
    return {c: read.grids(columns.resolution, c.base) for c in run.cases}


def read_case(columns: RunColumns, run: GroupRun, case: Case) -> Outcome:
    """The outcome of one case of a run (`read_run`)."""
    result = run.result
    if not isinstance(result, Tuples):
        return result
    return _read_of(result, columns).grids(columns.resolution, case.base)


def _runs_on(engine: Engine, solver: Solver, cases: Sequence[Case],
             inputs: Sequence[tuple[Grid, Assignment]], limits: Limits,
             stored: _Stored) -> list[GroupRuns]:
    """The runs of `outcomes_on` on each input. The probes of the inputs
    run at once, then each group's program is built and run on each
    input, all at once, since building a `@store` branch's program runs
    the program too; each result is read by its place in the order of
    the inputs and the groups."""
    case_col, res_col = out_columns(solver.program)
    groups = case_groups(solver, cases)
    unread = _unread_units(engine, solver, groups)
    columns = RunColumns(case_col, res_col)
    outputs = [OUTPUT]
    if case_col is not None:
        cls = classed(engine, solver.program)
        solver = replace(solver, program=cls.program)
        columns = RunColumns(case_col, res_col, (cls.rows, cls.classes))
        outputs = [cls.rows, cls.classes]
    derives = any(isinstance(b, DeriveBranch) for g in groups
                  for b in g[0].branches)
    proposals: list[Proposals | RunFailure | None] = (
        at_once(lambda i: probe(engine, input_task(i[0]), limits), inputs)
        if derives else [None] * len(inputs))
    tasks = [(k, members, drop) for k in range(len(inputs))
             for members, drop in zip(groups, unread, strict=True)]

    def ran(task: tuple[int, tuple[Case, ...], frozenset[UnitId]]
            ) -> RunResult | Undefined:
        k, members, drop = task
        input, assign = inputs[k]
        bases = tuple(dict.fromkeys(c.base for c in members
                                    if c.base is not None))
        run = _program(engine, solver, bases, members[0].branches, input,
                       assign, proposals[k], limits, stored, drop)
        return run if not isinstance(run, Program) else engine.run(
            run, {INPUT: GridInput(input)}, outputs, limits)

    got: list[list[GroupRun]] = [[] for _ in inputs]
    for (k, members, _drop), result in zip(tasks, at_once(ran, tasks),
                                           strict=True):
        got[k].append(GroupRun(tuple(members), result))
    return [GroupRuns(columns, tuple(g)) for g in got]


def _unread_units(engine: Engine, solver: Solver,
                  groups: Sequence[tuple[Case, ...]]
                  ) -> list[frozenset[UnitId]]:
    """For each group, the units of the solver's own text that no case of
    the group depends on (`dependence`): its run leaves them out, so that
    the run's text, which keys its stored result, holds the units its
    cases depend on, and an edit to a unit reruns only the groups whose
    cases depend on it."""
    own_units = frozenset(u.id for u in solver.program.units if own(u.span))
    read = _read_units(_enumerated(engine, solver),
                       [c.base for g in groups for c in g])
    return [own_units.difference(*(read[c.base] for c in g)) for g in groups]


def _enumerated(engine: Engine, solver: Solver) -> Solver:
    """The solver as its runs read it: with `impl_choice` holding every
    value of `Choice`, so that the clauses that enumerate its cases, which
    no group's run holds (`restricted`), are no unit a case depends on,
    and the solver and the solver with every case restored leave the
    same units out of the same group's run."""
    choice = solver.choice
    every = None if choice is None else every_base(choice)
    if not every or not enumerates(solver.program):
        return solver
    return replace(solver, program=restricted(engine, solver, tuple(every)))


_READ_UNITS: ByIdentity[Program, tuple[tuple[object, ...],
                                      dict[Base | None, frozenset[UnitId]]]] \
    = ByIdentity()
"""`_read_units`'s units by base, for each program while it lives, with
the parts of the solver the result also reads."""


def _read_units(solver: Solver, bases: Sequence[Base | None]
                ) -> dict[Base | None, frozenset[UnitId]]:
    """The units each of `bases` depends on (`dependence`), computed once
    per base for the solver's program."""
    program = solver.program
    parts = (solver.choice, solver.annotations.markers, solver.params)
    memo = _READ_UNITS.guarded(program, parts, dict)
    missing = [b for b in dict.fromkeys(bases) if b not in memo]
    if missing:
        found: dict[Base | None, set[UnitId]] = {b: set() for b in missing}
        for uid, readers in dependence(solver, missing).units.items():
            for b in readers:
                if b in found:
                    found[b].add(uid)
        for b, units in found.items():
            memo.setdefault(b, frozenset(units))
    return {b: memo[b] for b in bases}


def _without(engine: Engine, program: Program, drop: frozenset[UnitId]
             ) -> Program:
    """`program` without the units of `drop` it holds, kept while
    `program` lives: a group's program runs on every input."""
    drop = frozenset(u.id for u in program.units if u.id in drop)
    if not drop:
        return program

    def make() -> Program:
        got = program
        for uid in sorted(drop, key=lambda u: u.index):
            got = engine.remove(got, RemoveUnit(uid))
        return got

    return _WITHOUT.keyed(program, drop, make)


_WITHOUT: ByIdentity[Program, dict[frozenset[UnitId], Program]] = ByIdentity()


def case_groups(solver: Solver, cases: Sequence[Case]
                ) -> list[tuple[Case, ...]]:
    """The groups `outcomes` runs `cases` in, each in one run, in the order
    of their first case: the cases that take the same `@derive` and
    `@store` branches, and each base alone where `out` has no case
    column."""
    shared = solver.choice is None \
        or out_columns(solver.program)[0] is not None
    groups: dict[tuple[tuple[Branch, ...], Base | None], list[Case]] = {}
    for case in dict.fromkeys(cases):
        groups.setdefault((case.branches, None if shared else case.base),
                          []).append(case)
    return [tuple(g) for g in groups.values()]


def classed(engine: Engine, program: Program) -> Classed:
    """`program` with the rules that class a run's cases by equal `out`
    rows (`Engine.classify` of `out`'s case column), so that a run outputs
    `out` at each class's representative alone and the
    case-to-representative table, and the cases are compared in the run."""
    case_col = out_columns(program)[0]
    assert case_col is not None
    return engine.classify(program, OUTPUT, case_col)


class _Read:
    """What one run's `out` gives: its rows by base, the margins of each
    position value (`_grid_of`), and the grids already read, by base.
    `classes` gives each case's representative, whose rows `rows` holds,
    for a run of `classed`."""

    def __init__(self, rows: Rows, case_col: int | None,
                 classes: Mapping[Value, Value] | None = None) -> None:
        self.rows = rows
        self.case_col = case_col
        self.classes = classes
        self.by_base = _rows_by_base(rows, case_col)
        self.margins: dict[int, _Place | None] = {}
        self.read: dict[tuple[int | None, Value | None], Grids | Undefined] = {}
        self.lock = threading.Lock()

    def grids(self, res_col: int | None, base: Base | None
              ) -> Grids | Undefined:
        mine = base if self.case_col is not None else None
        if self.classes is not None and mine is not None:
            rep = self.classes.get(mine)
            if rep is None:
                return Undefined(NoOutput())
            mine = rep
        key = (res_col, mine)
        with self.lock:
            got = self.read.get(key)
            if got is None:
                got = self.read[key] = _grids(
                    res_col, self.rows if mine is None
                    else self.by_base.get(mine, ()), self.margins)
            return got


_READS: ByIdentity[Tuples, dict[RunColumns, _Read]] = ByIdentity()


def _read_of(result: Tuples, columns: RunColumns) -> _Read:
    """The reading of `result`'s `out`, made once per result: the engine
    gives the same result for a run made again."""

    def make() -> _Read:
        rels = result.relations
        if columns.classed is not None:
            rows, classes = columns.classed
            return _Read(rels[rows], columns.case,
                         {r[0]: r[1] for r in rels[classes]})
        return _Read(rels[OUTPUT], columns.case)

    return _READS.keyed(result, columns, make)


RUNS_AT_ONCE = 16
"""The most engine calls `at_once` has going; the engine bounds its own
processes further."""


def at_once[T, R](fn: Callable[[T], R], items: Sequence[T]) -> list[R]:
    """`fn` on each of `items`, in threads, the results in the order of
    `items`: the engine's runs spend their time in processes of their own,
    so runs that do not depend on each other are made at once."""
    if len(items) <= 1:
        return [fn(x) for x in items]
    with ThreadPoolExecutor(max_workers=min(len(items), RUNS_AT_ONCE)) as pool:
        return list(pool.map(fn, items))


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
    got = engine.run(run, {INPUT: _input(input)}, list(relations), limits,
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


def _input(input: Grid | None) -> InputValue:
    """A grid as the run's `in`, the empty input where it is None."""
    return () if input is None else GridInput(input)


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
    return _program(engine, solver, bases, case.branches, input, assign,
                    proposals, limits, _Stored())


def _program(engine: Engine, solver: Solver, bases: tuple[Base, ...],
             branches: tuple[Branch, ...], input: Grid | None,
             assign: Assignment,
             proposals: "Proposals | RunFailure | None", limits: Limits,
             stored: _Stored, drop: frozenset[UnitId] = frozenset()
             ) -> Program | Undefined | RunFailure:
    """The program the cases of `bases` that take `branches` run on
    `input`, the empty input where it is None, at `assign` (`outcomes`),
    with `proposals` the proposer probe of the input, and without the
    units of `drop`."""
    held_program = restricted(engine, solver, bases)
    run = _without(engine, held_program, drop)
    derived = {b.parameter for b in branches if isinstance(b, DeriveBranch)}
    params = {p.name for p in solver.params.parameters}
    for name, value in assign.values:
        if name in params and name not in derived:
            run = engine.fix_relation(run, parameter(solver, name), value)
    assigned = dict(assign.values)
    for b in branches:
        if isinstance(b, DeriveBranch):
            if not isinstance(proposals, Proposals):
                if proposals is None:
                    raise ValueError("a `@derive` branch runs with no probe")
                return proposals
            values = proposals.values.get(b.proposer, ())
            if not values:
                return Undefined(NoDerivedValue(b.parameter, b.proposer))
            run = engine.fix_relation(run, parameter(solver, b.parameter),
                                      values)
        elif isinstance(b, StoreBranch):
            value = assigned.get(b.spelled)
            if value is None:
                got = stored.get((bases, b.relation), lambda b=b: stored_value(
                    engine, solver, held_program, b, limits))
                if not isinstance(got, StoredValue):
                    return got
                value = got.stored_rows()
                if not got.keyed_by_case:
                    here = engine.run(run, {INPUT: _input(input)},
                                      [b.relation], limits)
                    if not isinstance(here, Tuples):
                        return here
                    value = got.on(here.relations[b.relation])
            run = engine.fix_relation(run, b.relation, value)
    return run


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


def assigned(engine: Engine, solver: Solver,
             assign: tuple[tuple[str, AssignValue], ...],
             where: InWitnessFile) -> Assignment | Fault:
    """The assignment an `assign` value states (`assignment`), a problem
    placed at `where`. A grid for a parameter one GRID call stores is
    placed by the engine's `place_grid`; a name no parameter has is a
    `@store` relation (`assignable`)."""
    params = {p.name: p for p in solver.params.parameters}
    out: list[tuple[str, RelationValue]] = []
    for name, value in assign:
        if not assignable(solver, name):
            return Fault(ProblemKind.ASSIGN_NAMES_NOTHING, where,
                                  Named(name))
        if isinstance(value, AssignRows):
            rows: list[Row] = []
            for fact in value.rows:
                row = [_arg_value(a, solver.lib.constants) for a in fact]
                if any(v is None for v in row):
                    return Fault(ProblemKind.ASSIGN_NAMES_NOTHING,
                                          where, Named(name))
                rows.append(tuple(v for v in row if v is not None))
            out.append((name, tuple(rows)))
            continue
        param = params.get(name)
        grid, anchor = (value.grid, value.anchor) \
            if isinstance(value, AnchoredGrid) else (value, None)
        match param:
            case Parameter(stored=StoredGrid(grids=(call,))):
                pass
            case None:
                if anchor is not None:
                    return Fault(ProblemKind.ANCHOR_WITHOUT_STAMP, where,
                                 AnchorWithoutStamp(
                                     name, Storage.STORED_RELATION))
                return Fault(ProblemKind.GRID_OFF_LAYOUT, where,
                             GridOffLayout(name, None, grid_size(grid)))
            case Parameter(stored=stored):
                if anchor is not None:
                    return Fault(ProblemKind.ANCHOR_WITHOUT_STAMP, where,
                                 AnchorWithoutStamp(name, Storage.GRID_CALLS
                                                    if isinstance(stored, StoredGrid)
                                                    else Storage.FACTS))
                return Fault(ProblemKind.GRID_OFF_LAYOUT, where,
                             GridOffLayout(name, None, grid_size(grid)))
        match engine.place_grid(call.layout, call.anchor,
                                GridValue(call.keys, grid, anchor)):
            case GridValue() as placed:
                out.append((name, placed))
            case AnchorOffStamp():
                return Fault(ProblemKind.ANCHOR_WITHOUT_STAMP, where,
                             AnchorWithoutStamp(name, call.layout))
            case CellOffForm(cell=cell, value=v):
                return Fault(ProblemKind.GRID_CELL_OFF_FORM, where,
                             GridCellOffForm(name, call.layout, cell, v))
            case SizeOffLayout(given=given):
                return Fault(ProblemKind.GRID_OFF_LAYOUT, where,
                             GridOffLayout(name, call.layout, given))
    return Assignment(tuple(out))


def _arg_value(arg: AssignArg, constants: Mapping[str, Value]) -> Value | None:
    """An `assign` argument as a value: a number, a lib constant, or a
    record of such; None where a string names no constant
    (`term_value` of the term the argument writes)."""
    return term_value(_arg_term(arg), constants.get)


def _arg_term(arg: AssignArg) -> Term:
    """The term an `assign` argument writes: a number, a constant's name,
    or a record."""
    if isinstance(arg, str):
        return DefinedName(arg)
    if isinstance(arg, tuple):
        return RecordTerm(tuple(_arg_term(a) for a in arg))
    return NumberTerm(arg)


# The runs' parts


def scaled(limits: Limits, grids: int) -> Limits:
    """The limits of a run over `grids` examples: the limits of a run on
    one grid, once per example."""
    n = max(1, grids)
    return Limits(cpu_seconds=limits.cpu_seconds * n,
                  wall_seconds=limits.wall_seconds * n)


def over_examples(limits: Limits, task: Task) -> Limits:
    """The limits of a run over every example of `task` (`scaled`)."""
    return scaled(limits, len(task.train) + len(task.test))


def parameter(solver: Solver, name: str) -> RelationName:
    """A parameter as the program reads it, `params.<rel>`
    (solver-file.md, under "Params")."""
    inst = instance_of(solver.program, PARAMS)
    if inst is None:
        raise ValueError(f"{solver.stem}: no instance of `Params`")
    return RelationName((inst.name,), name)


def restricted(engine: Engine, solver: Solver, bases: tuple[Base, ...]
            ) -> Program:
    """The solver's program with `impl_choice` holding `bases`, where the
    program enumerates its cases; as it stands where `bases` is empty."""
    program = solver.program
    if not bases or not enumerates(program):
        return program
    return _RESTRICTED.keyed(program, (engine, bases),
                             lambda: _holding(engine, program, bases))


def _holding(engine: Engine, program: Program, bases: Sequence[Base]
             ) -> Program:
    """`program` with `impl_choice` holding exactly `bases`."""
    return engine.fix_relation(program, IMPL, tuple((b,) for b in bases))


_RESTRICTED: ByIdentity[Program, dict[tuple[Engine, tuple[Base, ...]],
                                      Program]] = ByIdentity()
"""`restricted`'s programs, for each program they restrict while it
lives, with the engine that built them: a survey's variant runs on every
pair and in every group of cases."""


@quotes("solver-file.md", "Program",
        "**`@store` directive.** The relation, or the instance's relation the "
        "line names, has one value on every input, and the line is a branch "
        "of a choice point on it")
@dataclass(frozen=True)
class StoredValue:
    """The value a `@store` branch stores: the columns of the relation that
    hold one value on every input, and the rows of that value, each row over
    those columns alone, at each value of the columns that carry the case
    (`case_columns`). The other columns are the value's keys, which the
    relation's clauses give on each input."""

    arity: int
    columns: tuple[int, ...]
    case: tuple[int, ...]
    rows: tuple[tuple[Row, Rows], ...]
    """At each value of the case columns, the value's rows."""

    @property
    def keyed_by_case(self) -> bool:
        """Whether every column outside the value carries the case, so
        that the relation's rows are the stored rows at each case,
        whatever the input."""
        return all(i in self.columns or i in self.case
                   for i in range(self.arity))

    def stored_rows(self) -> Rows:
        """The relation's rows where it is keyed by the case alone
        (`keyed_by_case`): the value's rows at each value of the case
        columns."""
        out: dict[Row, None] = {}
        for key, rows in self.rows:
            for row in rows:
                at = dict(zip(self.case, key, strict=True)) \
                    | dict(zip(self.columns, row, strict=True))
                out[tuple(at[i] for i in range(self.arity))] = None
        return tuple(out)

    def on(self, derived: Rows) -> Rows:
        """The relation's rows on an input where its clauses give
        `derived`: each key its clauses give, with each row of the value
        at the key's case columns."""
        keys = [i for i in range(self.arity) if i not in self.columns]
        at_case = dict(self.rows)
        out: dict[Row, None] = {}
        for key in dict.fromkeys(tuple(r[i] for i in keys) for r in derived):
            held = dict(zip(keys, key, strict=True))
            for row in at_case.get(tuple(held[i] for i in self.case), ()):
                at = held | dict(zip(self.columns, row, strict=True))
                out[tuple(at[i] for i in range(self.arity))] = None
        return tuple(out)


def stored_value(engine: Engine, solver: Solver, program: Program,
                 branch: StoreBranch, limits: Limits
                 ) -> StoredValue | RunFailure:
    """The value a `@store` branch stores (solver-file.md, under "Program"),
    from the relation's rows in `program` on each input of the task's pairs. A
    column that carries the case (`case_columns`) is a key, never a column of
    the value (solver-file.md, under "Program"). The value's columns are every
    other column where the rows are one set on every input. Else they are the
    most such columns, the first in column order among equals, whose rows are
    one set on every input and whose rows on each input are the same at each
    key, a key being the rows' part over the other columns: the relation is
    then its keys, which its clauses give on each input, with the value at
    each, as the old tool stored it. Else every column that carries no case.
    The value's rows are the relation's rows over its columns on the first
    train input. The relation's arity is the one its declaration gives, a
    relation empty on every input included.
    `outcomes` passes the program with `impl_choice` holding the bases of
    the cases that take the branch, at the stored assignment."""
    if solver.task is None or not solver.task.train:
        raise ValueError(f"{solver.stem}: no train input to store "
                         f"`{branch.relation.text}` from")
    per_input: list[Rows] = []
    for _pair, ex in examples(solver.task):
        got = engine.run(program, {INPUT: GridInput(as_grid(ex.input))},
                         [branch.relation], limits)
        if not isinstance(got, Tuples):
            return got
        per_input.append(got.relations[branch.relation])
    first = per_input[0]
    types = column_types(program, branch.relation)
    arity = len(types)
    case = case_columns(solver, types)

    def one_value(cols: tuple[int, ...]) -> bool:
        sets = [{tuple(r[i] for i in (*case, *cols)) for r in rows}
                for rows in per_input]
        return all(x == sets[0] for x in sets)

    def product(cols: tuple[int, ...]) -> bool:
        keys = [i for i in range(arity) if i not in cols]
        for rows in per_input:
            by_key: dict[Row, set[Row]] = {}
            for r in rows:
                by_key.setdefault(tuple(r[i] for i in keys), set()).add(
                    tuple(r[i] for i in cols))
            by_case: dict[Row, set[frozenset[Row]]] = {}
            for k, v in by_key.items():
                held = dict(zip(keys, k, strict=True))
                by_case.setdefault(tuple(held[i] for i in case),
                                   set()).add(frozenset(v))
            if any(len(v) > 1 for v in by_case.values()):
                return False
        return True

    every = tuple(i for i in range(arity) if i not in case)
    cols = every
    if not one_value(every):
        constant = [i for i in every if one_value((i,))]
        subsets = [c for n in range(len(constant), 0, -1)
                   for c in combinations(constant, n)
                   if one_value(c) and product(c)]
        cols = subsets[0] if subsets else every
    rows: dict[Row, dict[Row, None]] = {}
    for r in first:
        rows.setdefault(tuple(r[i] for i in case), {})[
            tuple(r[i] for i in cols)] = None
    return StoredValue(arity, cols, case, tuple(
        (k, tuple(v)) for k, v in rows.items()))


def relation_decl(engine: Engine, program: Program,
                  relation: RelationName) -> RelationDecl:
    """The declaration of `relation`, named from the top level; its
    columns' types are `solver.model.column_types`. Raises `ValueError`
    where it resolves to no declaration."""
    return program.declared_relation(
        resolved(engine.index(program), relation, TOP).declaration)


def case_columns(solver: Solver, of: RelationName | Sequence[str]
                 ) -> tuple[int, ...]:
    """The columns of the relation `of` of the solver's program, or of a
    relation of column types `of`, as the model resolves them
    (`solver.model.column_types`), that carry the case: of type `Choice`, of an
    ADT that stands in `Choice` (solver-file.md, under "Types"), or of a record
    type with a field of such a type, a component's type parameter read through
    the instance, which carries the case in that field and is a key in its
    other fields (`solver.model.case_types`, as `dependence` reads them). A
    case column is a key of a stored value, never one of its columns."""
    if solver.choice is None:
        return ()
    types = column_types(solver.program, of) \
        if isinstance(of, RelationName) else of
    case = case_types(solver).types
    return tuple(i for i, t in enumerate(types) if t in case)


def out_decl(program: Program) -> RelationDecl | None:
    """`out`'s declaration in the solver's own text at the top level; None
    where it declares none."""
    return next((r for r in program.relations if r.name == OUTPUT.name
                 and r.scope == TOP and own(r.span)), None)


def out_columns(program: Program) -> tuple[int | None, int | None]:
    """The case column and the resolution column of `out`, by type
    (solver-file.md, under "Cases" and "Alt outputs"); None where `out` has
    none."""
    decl = out_decl(program)
    if decl is None:
        return None, None
    types = [c.type for c in decl.columns]
    case = types.index(CHOICE) if CHOICE in types else None
    res = (types.index(TIEBREAK_RESOLUTION)
           if TIEBREAK_RESOLUTION in types else None)
    return case, res


@dataclass(frozen=True)
class Margins:
    """A `Position` value (lib.dl: `.type Position = Box`, `[t, b, l, r]`):
    a cell's distances to the top, bottom, left and right edges of its
    grid."""

    top: int
    bottom: int
    left: int
    right: int

    @property
    def cell(self) -> Cell:
        """The cell's row and column."""
        return self.top, self.left

    @property
    def size(self) -> Cell:
        """The height and width of the grid the cell stands in."""
        return self.top + self.bottom + 1, self.left + self.right + 1


def position(value: object) -> Margins | None:
    """The margins a `Position` value holds; None where `value` is no
    record of four numbers."""
    if not isinstance(value, RecordValue) or len(value.fields) != 4:
        return None
    t, b, l, r = value.fields
    if type(t) is not int or type(b) is not int or type(l) is not int \
            or type(r) is not int:
        return None
    return Margins(t, b, l, r)


type _Place = tuple[Cell, Cell, tuple[int, int, int, int] | None]
"""What `_grid_of` reads of a position value: the cell, the size of its
grid, and its margins where one of them is negative."""

_UNSEEN = object()


def _place(value: object) -> _Place | None:
    m = position(value)
    if m is None:
        return None
    edges = (m.top, m.bottom, m.left, m.right)
    return m.cell, m.size, edges if min(edges) < 0 else None


def _grid_of(cells: Sequence[Row], places: dict[int, _Place | None]
             ) -> Grid | UndefinedReason:
    """The total grid the cells give, or why they give none, as the old
    tool read `out`: a cell with a negative distance to an edge, two frame
    sizes, a cell with two colors, or a cell of the frame with none.
    `places` holds what is read of each position value already read, by
    the value's identity, as the rows of one run share their values."""
    at: dict[Cell, int] = {}
    two: set[Cell] = set()
    sizes: dict[Cell, None] = {}
    negative: dict[tuple[int, int, int, int], None] = {}
    for row in cells:
        color = row[1]
        key = id(row[0])
        p = places.get(key, _UNSEEN)
        if p is _UNSEEN:
            p = places[key] = _place(row[0])
        if p is None or type(color) is not int:
            raise ValueError(f"`out` holds a row with no cell: {row}")
        cell, size, below = p  # type: ignore[misc]
        if below is not None:
            negative[below] = None
            continue
        sizes[size] = None
        first = at.setdefault(cell, color)
        if first != color:
            two.add(cell)
    if negative:
        return NegativeEdges(tuple(negative))
    if len(sizes) != 1:
        return InconsistentBounds(tuple(sizes))
    if two:
        return ConflictingCells(tuple(sorted(two)))
    (height, width), = sizes
    missing = tuple((i, j) for i in range(height) for j in range(width)
                    if (i, j) not in at)
    if missing:
        return MissingCells(missing)
    return tuple(tuple(at[(i, j)] for j in range(width))
                 for i in range(height))


def grids_of(program: Program, rows: Rows, case: Case) -> Grids | Undefined:
    """The grids `out`'s rows hold at `case`, one per resolution in the order
    of the resolution values (solver-file.md, under "Cases"), or undefined,
    with the reason of the first resolution that gives no total grid
    (principles.md, under "Models and tasks")."""
    case_col, res_col = out_columns(program)
    return _grids(res_col, [r for r in rows if case_col is None or case.base is None
                            or r[case_col] == case.base], {})


def _rows_by_base(rows: Rows, case_col: int | None) -> dict[Value, list[Row]]:
    """`out`'s rows by the base in their case column, each list in the
    rows' order; empty where `out` has no case column."""
    return {} if case_col is None else _by_value(rows, case_col)


def _by_value(rows: Sequence[Row], col: int) -> dict[Value, list[Row]]:
    """`rows` by their value in column `col`, each list in the rows' order,
    the values in the order they first stand. The rows of one run share one
    object per distinct value, so the rows are grouped by object first and
    each object is hashed once; where two objects are equal, by value."""
    by_id: dict[int, list[Row]] = {}
    for r in rows:
        group = by_id.get(id(r[col]))
        if group is None:
            group = by_id[id(r[col])] = []
        group.append(r)
    out = {group[0][col]: group for group in by_id.values()}
    if len(out) == len(by_id):
        return out
    out = {}
    for r in rows:
        out.setdefault(r[col], []).append(r)
    return out


def _grids(res_col: int | None, mine: Sequence[Row],
           margins: dict[int, _Place | None]) -> Grids | Undefined:
    """`grids_of` over the rows of one case, with `res_col` `out`'s
    resolution column and `margins` as `_grid_of` reads it."""
    by_res: dict[Value | None, list[Row]] = (
        {None: list(mine)} if res_col is None
        else {k: v for k, v in _by_value(mine, res_col).items()})
    if not mine:
        return Undefined(NoOutput())
    grids: list[Grid] = []
    keys = sorted(by_res, key=lambda v: () if v is None else value_key(v))
    for key in keys:
        grid = _grid_of(by_res[key], margins)
        if not isinstance(grid, tuple):
            return Undefined(grid)
        grids.append(grid)
    return Grids(tuple(grids), tuple(k for k in keys if k is not None))


def value_key(value: Value) -> tuple[object, ...]:
    """An order on values built from their parts: numbers, then symbols,
    then records by their fields, then ADT values by constructor and
    arguments."""
    match value:
        case bool() | int() | float():
            return (0, value)
        case str():
            return (1, value)
        case RecordValue(fields=fields):
            return (2, tuple(value_key(f) for f in fields))
        case AdtValue(constructor=c, args=args):
            return (3, c, tuple(value_key(a) for a in args))


def row_key(row: Row) -> tuple[object, ...]:
    """An order on rows built from their values' parts (`value_key`)."""
    return tuple(value_key(v) for v in row)


def input_task(grid: Grid) -> Task:
    """A task whose one example is `grid`, with no output, for the probe of
    one input."""
    return Task(train=[], test=[Example(input=grid_lists(grid),
                                        output=[])])


# Pairs


class TaskSection(Enum):
    """The section of the task a pair stands in."""

    TRAIN = "train"
    TEST = "test"


@quotes("principles.md", "Models and tasks",
        "**fit**: a model fits a split task at an assignment when its output "
        "on each pair's input is that pair's candidate, including for the "
        "test pairs.")
@dataclass(frozen=True)
class PairId:
    """A pair of the task, by section and index."""

    section: TaskSection
    index: int

    @property
    def text(self) -> str:
        """The pair as every command writes it (`arc.task.pair_name`)."""
        return pair_name(self.section.value, self.index)


@quotes("solver-file.md", "Alt outputs",
        "An alt with kind `rule` gives the pair a second candidate. An alt "
        "with kind `tiebreak` gives resolutions within one candidate.")
class AltKind(Enum):
    """How a pair's alt output differs from its output: a `rule` alt is a
    second candidate, a `tiebreak` alt another resolution within the
    output's."""

    RULE = "rule"
    TIEBREAK = "tiebreak"


def alt_kind(alt: Alt) -> AltKind:
    """The kind the task file gives `alt`."""
    return AltKind(alt.kind)


@quotes("principles.md", "Models and tasks",
        "**candidate**: a set of a pair's accepted outputs that differ only "
        "in a tiebreak.")
class Candidate(Enum):
    """A pair's candidate outputs: its output and its alt."""

    OUTPUT = "output"
    ALT = "alt"


@dataclass(frozen=True)
class CaseOnPair:
    """What a case gives on a pair, and the candidates its grids match."""

    case: Case
    outcome: Outcome
    matches: tuple[Candidate, ...]


@dataclass(frozen=True)
class PairRuns:
    """Every case of the solver's run on one pair."""

    pair: PairId
    cases: tuple[CaseOnPair, ...]


def examples(task: Task) -> Iterator[tuple[PairId, Example]]:
    """The task's pairs, train then test, each with its id."""
    for i, ex in enumerate(task.train):
        yield PairId(TaskSection.TRAIN, i), ex
    for i, ex in enumerate(task.test):
        yield PairId(TaskSection.TEST, i), ex


def candidates(ex: Example) -> tuple[tuple[Candidate, frozenset[Grid]], ...]:
    """A pair's candidates as sets of accepted outputs (principles.md, under
    "Models and tasks"; solver-file.md, under "Alt outputs")."""
    output = as_grid(ex.output)
    if ex.alt is None:
        return ((Candidate.OUTPUT, frozenset({output})),)
    alt = as_grid(ex.alt.grid)
    if alt_kind(ex.alt) is AltKind.TIEBREAK:
        return ((Candidate.OUTPUT, frozenset({output, alt})),)
    return ((Candidate.OUTPUT, frozenset({output})),
            (Candidate.ALT, frozenset({alt})))


def matching(cands: Sequence[tuple[Candidate, frozenset[Grid]]],
             outcome: Outcome) -> tuple[Candidate, ...]:
    """The candidates of `cands`, a pair's (`candidates`), that `outcome`
    matches: the set of its grids is the candidate's set of accepted outputs
    (principles.md, under "Models and tasks")."""
    if not isinstance(outcome, Grids):
        return ()
    got = frozenset(outcome.grids)
    return tuple(c for c, accepted in cands if got == accepted)


type RunOn = Callable[[Sequence[Case], Sequence[tuple[Grid, Assignment]]],
                      Sequence[Mapping[Case, Outcome]]]
"""What each of the cases gives on each input at its assignment, in the
order of the inputs, as `outcomes_on` gives it: a caller that holds runs
gives its own, so that a run it holds is not made again."""


def pairs(engine: Engine, solver: Solver, limits: Limits,
          cases: Sequence[Case] | None = None, run: RunOn | None = None
          ) -> tuple[PairRuns, ...] | RunFailure:
    """Per train and test pair, per case: the run and the judged profile
    (`pair_runs`), of `cases`, else of the solver's cases, from `run`,
    else from `outcomes_on`. Where the run that enumerates the solver's
    cases fails, its failure; a solver with no task has no pair."""
    if solver.task is None:
        return ()
    if cases is None:
        every = cases_of(solver, engine, limits)
        if not isinstance(every, tuple):
            return every
        cases = every
    inputs = task_inputs(solver.task)
    got = run(cases, inputs) if run is not None \
        else outcomes_on(engine, solver, cases, inputs, limits)
    return pair_runs(solver.task, cases, got)


def pair_runs(task: Task, cases: Sequence[Case],
              got: Sequence[Mapping[Case, Outcome]]) -> tuple[PairRuns, ...]:
    """`pairs` of `cases`, from `got`, what each case gives on each pair's
    input in the order of `examples`. A case matches a candidate when the set
    of its grids is the candidate's set of accepted outputs (`matching`; a
    `tiebreak` alt joins the output's candidate, a `rule` alt is a second one,
    solver-file.md, under "Alt outputs")."""
    return tuple(pair_on(pair, ex, cases, here)
                 for (pair, ex), here in zip(examples(task), got, strict=True))


def pair_on(pair: PairId, ex: Example, cases: Sequence[Case],
            here: Mapping[Case, Outcome]) -> PairRuns:
    """One pair's runs: each of `cases` with what it gives on the pair's
    input, `here`, matched against the pair's candidates (`pair_runs`)."""
    cands = candidates(ex)
    return PairRuns(pair, tuple(
        CaseOnPair(case, here[case], matching(cands, here[case]))
        for case in cases))


# Witnessed cases


def recorded_inputs(engine: Engine, solver: Solver, entries: Sequence[Entry],
                    file: WitnessFileRole
                    ) -> list[tuple[Grid, Assignment]]:
    """The recorded inputs: the task's inputs, train then test, at the
    stored assignment, then each of `entries`', entries of `file`, inputs
    at its entry's assignment, each once. An entry whose assignment the
    model cannot place (`assignment`) gives none."""
    out: list[tuple[Grid, Assignment]] = []
    if solver.task is not None:
        out += task_inputs(solver.task)
    out += [(e.input, at)
            for e, at in entry_assignments(engine, solver, entries, file)]
    return list(dict.fromkeys(out))


def task_inputs(task: Task) -> list[tuple[Grid, Assignment]]:
    """The task's inputs, train then test (`examples`), each at the stored
    assignment."""
    return [(as_grid(ex.input), Assignment(())) for _pair, ex in examples(task)]


def entry_assignments(engine: Engine, solver: Solver, entries: Sequence[Entry],
                      file: WitnessFileRole
                      ) -> list[tuple[Entry, Assignment]]:
    """Each of `entries`, entries of `file`, at its assignment
    (`assignment`), in order; an entry whose assignment the model cannot
    place is left out."""
    return [(e, at) for e in entries
            if isinstance(at := assignment(engine, solver, e, file), Assignment)]


type Taken = tuple[str, tuple[str, ...]] | Branch
"""A non-concept branch a case takes: a constructor, by its name and its
point's path, or a `@derive` or `@store` branch."""


def taken(solver: Solver, case: Case) -> frozenset[Taken]:
    """The non-concept branches `case` takes: each constructor of its base
    other than its point's first, and its `@derive` and `@store`
    branches."""
    out: set[Taken] = set(case.branches)
    choice = solver.choice
    if choice is not None and case.base is not None:
        out |= {(ctor, p.path)
                for p, ctor in constructors_taken(choice, case.base)
                if not is_concept_branch(p, ctor)}
    return frozenset(out)


def rejected(solver: Solver, branch: Taken) -> bool:
    """Whether `branch` is rejected: it has a `@witness` line or a
    `@derive` or `@store` line, and every verdict on it is `concept`."""
    if isinstance(branch, tuple):
        verdicts = [w.verdict for w in branch_witnesses(solver, branch[0])]
    elif isinstance(branch, DeriveBranch | StoreBranch) \
            and branch.line is not None:
        verdicts = [branch.line.verdict]
    else:
        verdicts = []
    return bool(verdicts) and all(v is VerdictWord.CONCEPT for v in verdicts)


def constructor_denoted(choice: Choice, point: ChoicePoint,
                        ctor: ConstructorBranch) -> "Denoted":
    """The branches a model of `ctor` at `point` fixes: `ctor`, and the
    constructor at each point above it through which it is reached."""
    from solver.names import Denoted

    parents: list[ConstructorBranch] = []
    for name in path_constructors(choice, point.path):
        parent = constructor_named(choice, name)
        assert parent is not None, "a point's path names its constructors"
        parents.append(parent)
    return Denoted((*parents, ctor), ())


def branch_models(solver: Solver, cases: Sequence[Case]) -> list[Case]:
    """The model of each branch other than a point's concept branch, among
    `cases` (`branch_model`): a constructor at its choice point, and each
    `@derive` and `@store` branch."""
    from solver.names import Denoted

    denoted: list[Denoted] = []
    choice = solver.choice
    if choice is not None:
        denoted += [constructor_denoted(choice, p, c)
                    for p in choice.points for c in other_branches(p)]
    denoted += [Denoted((), (b,)) for b in solver.branches
                if isinstance(b, DeriveBranch | StoreBranch)]
    return [m for d in denoted
            if (m := branch_model(solver, cases, d)) is not None]


def branch_model(solver: Solver, cases: Sequence[Case], d: "Denoted"
                 ) -> Case | None:
    """The case of `cases` that stands for the model of the branch `d`
    names: its model (`solver.names.model_of`) where that is one of
    `cases`; else the case of `cases` that takes the branch and differs
    from the concept case at the fewest points, constructors and branches
    counted alike (`taken`), ties by name order; None where no case of
    `cases` takes it."""
    from solver.names import name

    tied = stand_ins(solver, cases, d)
    return min(tied, key=lambda c: name(solver, c)) if tied else None


def stand_ins(solver: Solver, cases: Sequence[Case], d: "Denoted"
              ) -> list[Case]:
    """The cases of `cases` that can stand for the model of the branch `d`
    names: its model (`solver.names.model_of`) alone where that is one of
    `cases`; else every case of `cases` that takes the branch and differs
    from the concept case at the fewest points, constructors and branches
    counted alike (`taken`), in the order of `cases`; none where no case
    takes it."""
    from solver.names import cases_of, model_of

    model = model_of(solver, d, cases)
    if model is not None and model in cases:
        return [model]
    taking = cases_of(solver, d, cases)
    if not taking:
        return []
    away = {c: len(taken(solver, c)) for c in taking}
    least = min(away.values())
    return [c for c in taking if away[c] == least]


def witnessed_among(solver: Solver, cases: Sequence[Case],
                    got: Sequence[Mapping[Case, Outcome]]) -> tuple[Case, ...]:
    """The witnessed cases of `cases`, in their order, from `got`, what
    every case gives on each recorded input (`witnessed`): an output is
    the grids over the tiebreak resolutions, or undefined with its reason
    and cells."""
    took = {c: taken(solver, c) for c in cases}
    rejects = {b for t in took.values() for b in t if rejected(solver, b)}
    requires: dict[Taken, frozenset[Taken]] = {}
    for t in took.values():
        for b in t:
            requires[b] = requires[b] & t if b in requires else t

    def stacked(t: frozenset[Taken]) -> bool:
        mine = list(t & rejects)
        return any(y not in requires[x] and x not in requires[y]
                   for i, x in enumerate(mine) for y in mine[i + 1:])

    kept = set(branch_models(solver, cases))
    kept |= {c for c in cases if is_concept_case(solver, c)}
    out: list[Case] = []
    for c in cases:
        if any(not is_result(o[c]) for o in got):
            out.append(c)
            continue
        if stacked(took[c]):
            continue
        if c in kept:
            out.append(c)
            continue
        extended = [d for d in cases if took[d] < took[c]]
        if any(all(not same_output(o[d], o[c]) for d in extended)
               for o in got):
            out.append(c)
    return tuple(out)


WITNESSED_DIR = "witnessed"
"""The directory under the run cache that holds `witnessed`'s results."""


def witnessed_key(solver: Solver, entries: Sequence[Entry], limits: Limits
                  ) -> str:
    """The key of the witnessed cases of the solver on `entries`' inputs:
    the content of its program, of its annotations and of its branches,
    a line a survey proposes among them, without where their parts stand
    or the comments (`_placeless`), of the entries and of the task, the
    limits, and the tool's sources."""
    h = hashlib.sha256()
    h.update(repr((_placeless(solver.program),
                   _placeless(solver.annotations),
                   _placeless(solver.branches), tuple(entries),
                   solver.task, limits)).encode())
    for path in sorted((checkout.ROOT / "src").rglob("*.py")):
        h.update(b"\0" + path.read_bytes())
    return h.hexdigest()


_PLACES = frozenset({"span", "line", "comments", "layout"})
"""The fields `_placeless` leaves out: where a part stands in the file,
and the comments, whose annotations the solver's annotations hold."""


def _placeless(x: object) -> object:
    """A value that states `x` without where its parts stand in the file
    and without its comments: what the witnessed cases read of a program
    or of its annotations, so that an edit to a comment that is no
    annotation, or a line moved, keeps their key."""
    if isinstance(x, tuple | list):
        return tuple(_placeless(y) for y in x)
    if isinstance(x, Mapping):
        return tuple((_placeless(k), _placeless(v)) for k, v in x.items())
    if is_dataclass(x) and not isinstance(x, type):
        return (type(x).__name__, tuple(
            (f.name, _placeless(getattr(x, f.name))) for f in fields(x)
            if f.name not in _PLACES))
    return x


def _witnessed_path(key: str) -> Path:
    return checkout.cache() / WITNESSED_DIR / f"{key}.json"


def held_witnessed(key: str, solver: Solver, cases: Sequence[Case]
                   ) -> tuple[Case, ...] | None:
    """The witnessed cases kept under `key` (`hold_witnessed`), of
    `cases`, the solver's cases, in their order; None where none are kept,
    or where a kept name is the name of none of `cases`."""
    from solver.names import name
    try:
        got = json.loads(_witnessed_path(key).read_text())
    except (OSError, ValueError):
        return None
    picked = got.get("witnessed") if isinstance(got, dict) else None
    if not isinstance(picked, list):
        return None
    by_name = {name(solver, c): c for c in cases}
    if not all(isinstance(n, str) and n in by_name for n in picked):
        return None
    kept = set(picked)
    return tuple(c for n, c in by_name.items() if n in kept)


def hold_witnessed(key: str, solver: Solver,
                   witnessed: Sequence[Case]) -> None:
    """Keeps `witnessed` under `key`, by the cases' names
    (`solver.names.name`)."""
    from solver.names import name
    path = _witnessed_path(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    write_whole(path, json.dumps({
        "witnessed": [name(solver, c) for c in witnessed]}).encode())


def witnessed(engine: Engine, solver: Solver, limits: Limits,
              file: WitnessFileRole,
              entries: Sequence[Entry] | None = None, run: RunOn | None = None,
              unlined: tuple[Sequence[Case], Sequence[Case]] | None = None
              ) -> tuple[Case, ...] | RunFailure:
    """The witnessed cases of the solver's cases, in their order, or the
    failure of the run that enumerates them. A case
    extends another when it takes that case's non-concept branches and
    more (`taken`). A case is witnessed when it is the concept case or a
    branch's model (`branch_models`), or when some recorded input
    (`recorded_inputs`, the witness file's entries) shows it giving an
    output, its grids over the tiebreak resolutions or undefined with its
    reason and cells, that no case it extends gives, so that a case
    undefined where a case it extends gives a grid is witnessed and its
    Fit failure shown; and not when it takes two
    rejected branches (`rejected`) of which neither requires the other, a
    branch requiring another when every case of the solver that takes it
    takes the other. A case whose run on some recorded input
    fails or reaches a limit is witnessed, so that the failure is shown.
    Where no run failed, the result is kept on disk under `witnessed_key`,
    so that a command on an unchanged solver computes nothing.

    The recorded inputs are those of `entries`, entries of `file`, else of
    the solver's witness file; the runs on them come from `run`, else from
    `outcomes_on`.

    `unlined` is given for the solver with a line a survey proposes
    added: the cases and the witnessed cases of the solver without it. A
    case of both solvers keeps its standing there, unchanged by the line;
    of the cases that take the new branch, the witnessed ones are judged
    as above (plan §D5, the derive survey's paragraph)."""
    every = cases_of(solver, engine, limits)
    if not isinstance(every, tuple):
        return every
    if entries is None:
        entries = () if solver.witness_file is None \
            else solver.witness_file.entries
        file = WitnessFileRole.TASK
    key = witnessed_key(solver, entries, limits)
    held = held_witnessed(key, solver, every)
    if held is not None:
        return held
    inputs = recorded_inputs(engine, solver, entries, file)
    got = run(every, inputs) if run is not None \
        else outcomes_on(engine, solver, every, inputs, limits)
    out = witnessed_among(solver, every, got)
    if unlined is not None:
        before, kept, among = set(unlined[0]), set(unlined[1]), set(out)
        out = tuple(c for c in every
                    if (c in kept if c in before else c in among))
    if all(is_result(o) for g in got for o in g.values()):
        hold_witnessed(key, solver, out)
    return out


# Variations


@dataclass(frozen=True)
class FixParam:
    parameter: str
    rows: Rows


@dataclass(frozen=True)
class FixGrid:
    parameter: str
    grid: GridValue


@dataclass(frozen=True)
class TakeStore:
    """The `@store` branch on `relation`, with `rows` the value stored."""

    relation: RelationName
    rows: Rows


@dataclass(frozen=True)
class TakeDerive:
    """The `@derive` branch of `parameter` by `proposer`, with the values
    the proposer probe gives."""

    parameter: str
    proposer: str
    values: Rows


@dataclass(frozen=True)
class Restrict:
    """`impl_choice` holding exactly `cases`."""

    cases: tuple[Case, ...]


@dataclass(frozen=True)
class Remove:
    target: RemovalTarget


type Variation = FixParam | FixGrid | TakeStore | TakeDerive | Restrict | Remove


def variation(engine: Engine, solver: Solver, v: Variation) -> Program:
    """The solver's program under `v`, built from the engine's operations
    alone: `fix_relation` for each of the fixing variations and `Restrict`,
    and `remove` for `Remove`."""
    program = solver.program
    match v:
        case FixParam(parameter=p, rows=rows):
            return engine.fix_relation(program, parameter(solver, p), rows)
        case FixGrid(parameter=p, grid=grid):
            return engine.fix_relation(program, parameter(solver, p), grid)
        case TakeStore(relation=rel, rows=rows):
            return engine.fix_relation(program, rel, rows)
        case TakeDerive(parameter=p, values=values):
            return engine.fix_relation(program, parameter(solver, p), values)
        case Restrict(cases=cases):
            return _holding(engine, program, list(dict.fromkeys(
                c.base for c in cases if c.base is not None)))
        case Remove(target=target):
            return engine.remove(program, target)


# Probe and Determine


@dataclass(frozen=True)
class Proposals:
    """The values each proposer of `programs/proposers.dl` gives over a
    task's examples, by proposer."""

    values: Mapping[str, Rows]


def example_inputs(task: Task) -> dict[RelationName, InputValue]:
    """`ex_in` over every example's input, train first, and `ex_out` over
    the train outputs, each with the example's index (lib.dl's runner
    contract; solver-file.md, under "Determination")."""
    return {
        EX_IN: IndexedGrids(tuple(as_grid(e.input)
                                  for e in (*task.train, *task.test))),
        EX_OUT: IndexedGrids(tuple(as_grid(e.output) for e in task.train)),
    }


type _ProbeProgram = tuple[Program, dict[str, RelationName]]
_PROBE_PROGRAMS: ByIdentity[Program, _ProbeProgram] = ByIdentity()
"""What `_probe_program` built, for each proposers program while it
lives."""


def _probe_program(engine: Engine) -> _ProbeProgram | CompileError:
    """The proposers program (`proposers_program`) with an instance of
    each proposer, and each proposer's `propose` in its instance, built
    once per proposers program; where the program does not parse, the
    probe's failure (`probe_failure`)."""
    parsed = proposers_program(engine)
    if isinstance(parsed, ParseFailure):
        return probe_failure(parsed)

    def build() -> _ProbeProgram:
        program = parsed
        outputs: dict[str, RelationName] = {}
        for name in proposer_names(parsed):
            inst = name.lower()
            program = engine.instantiate(program, name, inst)
            outputs[name] = RelationName((inst,), PROPOSE)
        return program, outputs

    return _PROBE_PROGRAMS.compute(parsed, build)


def probe_failure(parsed: ParseFailure) -> CompileError:
    """A proposers program that does not parse, as the failure of the
    probe that runs it."""
    return CompileError(parsed.line, parsed.message)


def probe(engine: Engine, task: Task, limits: Limits
          ) -> Proposals | RunFailure:
    """The proposers program run over the task's examples: each proposer
    of `programs/proposers.dl`, a component that declares `propose`, as an
    instance, with `ex_in` over every example's input and `ex_out` over
    the train outputs (proposers.dl's header). The run takes `limits`
    once per example."""
    built = _probe_program(engine)
    if isinstance(built, CompileError):
        return built
    program, outputs = built
    got = engine.run(program, example_inputs(task), list(outputs.values()),
                     over_examples(limits, task))
    if not isinstance(got, Tuples):
        return got
    return Proposals({name: got.relations[rel]
                      for name, rel in outputs.items()})


@dataclass(frozen=True)
class ParamDiff:
    """Where a determined parameter's value differs from its stored one."""

    parameter: str
    stored_only: Rows
    determined_only: Rows
    rigid: bool
    """The parameter is stored by a RIGID call: no D4 image of its block's
    stored assembly gives the determined one, and the rows are placed
    rows (`determine`)."""


@dataclass(frozen=True)
class CycleRead:
    """A read in a circular determination: the determination of
    `parameter` reads the stored value of `reads`, at the atom on `line` of
    `unit`."""

    parameter: str
    reads: str
    unit: UnitId
    line: int


@quotes("solver-file.md", "Determination",
        "`Determine` contains the determination as one relation per "
        "determined parameter, with the parameter's name and schema")
@dataclass(frozen=True)
class Determined:
    """The `Determine` component's run against the stored values: the diffs,
    the parameters it reproduces, and its cycles."""

    diffs: tuple[ParamDiff, ...]
    reproduced: tuple[str, ...]
    cycles: tuple[tuple[CycleRead, ...], ...]
    """Each group of determined parameters whose determinations read each
    other's stored values: every read inside the group, by parameter and
    the parameter it reads."""


@dataclass(frozen=True)
class NoDetermine:
    """The solver has no `Determine` comp."""


type DetermineResult = Determined | NoDetermine | RunFailure


def determine(engine: Engine, solver: Solver, limits: Limits
              ) -> DetermineResult:
    """The Determine comp over the examples, diffed against the stored values
    (solver-file.md, under "Determination"). The parameters with an `Ident`
    column compare together modulo a renaming of ids (solver-file.md, under
    "Determination"), one a RIGID call stores by the orbit of its placed rows
    at each id (`_signatures`). The other parameters a RIGID call stores
    compare together per block, up to a D4 image of the stored assembly, since
    a RIGID block exposes them only as D4 placements that transform them
    together and the stored pose is unobservable (patterns.md, under "`RIGID` —
    parameter relations coupled as a rigid assembly"): the Determine relations
    stand in for the block's charts, the program places them, and the
    parameters agree where some pose of one side gives the rows of every
    parameter of the block that the other side gives at some pose
    (`_same_pose_orbits`). A diff of such a parameter holds its placed rows.
    The runs take `limits` once per example. A solver whose task has no task
    file is a caller's error:
    `ValueError`."""
    program = solver.program
    if not has_determine(solver):
        return NoDetermine()
    task = solver.task
    if task is None:
        raise ValueError("a determination runs over the task's examples, "
                         "and the solver's task has no task file")
    params_inst = instance_of(program, PARAMS)
    det_inst = instance_of(program, DETERMINE)
    det_name = "determine" if det_inst is None else det_inst.name
    if det_inst is None:
        program = engine.instantiate(program, DETERMINE, det_name)
    determined = [p for p in solver.params.parameters if p.determined]
    if params_inst is None or not determined:
        return Determined((), (), ())
    outputs: list[RelationName] = []
    for p in determined:
        outputs += [RelationName((det_name,), p.name),
                    parameter(solver, p.name)]
    inputs: dict[RelationName, InputValue] = {INPUT: (),
                                              **example_inputs(task)}
    got = engine.run(program, inputs, outputs,
                     over_examples(limits, task))
    if not isinstance(got, Tuples):
        return got
    stored = {p.name: got.relations[parameter(solver, p.name)]
              for p in determined}
    derived = {p.name: got.relations[RelationName((det_name,), p.name)]
               for p in determined}
    rigid = rigid_parameters(solver)
    ident_cols = {p.name: [c.type for c in p.columns].index(IDENT)
                  for p in determined
                  if IDENT in [c.type for c in p.columns]}
    charts = _charts(solver, [p.name for p in determined if p.name in rigid])
    if charts:
        placed = program
        for name, chart in charts.items():
            placed = engine.fix_relation(
                placed, parameter(solver, chart),
                derived[name])
        again = engine.run(placed, inputs, [
            parameter(solver, n) for n in charts],
            over_examples(limits, task))
        if not isinstance(again, Tuples):
            return again
        for name in charts:
            derived[name] = again.relations[
                parameter(solver, name)]
    placed_ids = frozenset(n for n in charts if n in ident_cols)
    ids_agree = _signatures(stored, ident_cols, placed_ids) \
        == _signatures(derived, ident_cols, placed_ids)
    posed = _same_pose_orbits(
        solver, {n: c for n, c in charts.items() if n not in ident_cols},
        stored, derived)
    diffs: list[ParamDiff] = []
    reproduced: list[str] = []
    for p in determined:
        s, d = set(stored[p.name]), set(derived[p.name])
        if p.name in ident_cols and ids_agree or s == d \
                or p.name in posed:
            reproduced.append(p.name)
            continue
        diffs.append(ParamDiff(
            p.name, tuple(r for r in stored[p.name] if r not in d),
            tuple(r for r in derived[p.name] if r not in s),
            p.name in rigid))
    return Determined(tuple(diffs), tuple(reproduced),
                      cycles(solver, params_inst.name,
                             [p.name for p in determined]))


def rigid_parameters(solver: Solver) -> frozenset[str]:
    """The parameters a RIGID call in `Params` stores: the relations that
    are a RIGID chart, the names a call binds, and the relations its units
    feed."""
    scope = PARAMS_SCOPE
    heads = {u.id: u.head.relation for u in solver.program.units}
    out: set[str] = set()
    for m in solver.program.macros:
        if isinstance(m, RigidCall) and m.scope == scope:
            out |= set(solver.program.bound_names(m))
            out |= {heads[u].name for u in m.body
                    if u in heads and not heads[u].instances}
    return frozenset(out)


def _blocks(solver: Solver) -> dict[str, tuple[str, str]]:
    """Each relation a RIGID call in `Params` binds, with its block and the
    chart relation the call declares for it: the block's charts in the
    order the call binds its relations. A call whose charts are not one
    per name is left out, and is a fault of `load`
    (`model.instance_faults`)."""
    scope = PARAMS_SCOPE
    out: dict[str, tuple[str, str]] = {}
    for m in solver.program.macros:
        if not isinstance(m, RigidCall) or m.scope != scope:
            continue
        for name, chart in solver.program.bound_charts(m) or ():
            out[name] = (m.block, chart.name)
    return out


def rigid_charts(solver: Solver) -> dict[str, str]:
    """Each relation a RIGID call in `Params` binds, with the chart
    relation that holds its facts (`_blocks`)."""
    return {n: chart for n, (_block, chart) in _blocks(solver).items()}


def _charts(solver: Solver, names: Sequence[str]) -> dict[str, str]:
    """The chart relation of each of `names` that a RIGID call binds."""
    blocks = _blocks(solver)
    return {n: blocks[n][1] for n in names if n in blocks}


def _same_pose_orbits(solver: Solver, charts: Mapping[str, str],
                      stored: Mapping[str, Rows], derived: Mapping[str, Rows]
                      ) -> frozenset[str]:
    """The parameters of `charts` whose block agrees up to pose: the set of
    the block's placed row sets per pose, the pose left out, is one set on
    both sides, so each side is a D4 image of the other."""
    blocks = _blocks(solver)
    by_block: dict[str, list[str]] = {}
    for name in charts:
        by_block.setdefault(blocks[name][0], []).append(name)

    def orbit(rows: Mapping[str, Rows], names: Sequence[str]
              ) -> frozenset[tuple[tuple[Row, ...], ...]]:
        poses: dict[Value, list[set[Row]]] = {}
        for k, name in enumerate(names):
            for row in rows.get(name, ()):
                poses.setdefault(row[POSE_COLUMN], [set() for _ in names])[k].add(
                    tuple(v for i, v in enumerate(row) if i != POSE_COLUMN))
        return frozenset(
            tuple(tuple(sorted(rs, key=row_key)) for rs in sets)
            for sets in poses.values())

    out: set[str] = set()
    for names in by_block.values():
        if orbit(stored, names) == orbit(derived, names):
            out |= set(names)
    return frozenset(out)


type _Key = tuple[object, ...]


def _signatures(rows_by_param: Mapping[str, Rows],
                ident_cols: Mapping[str, int],
                placed: frozenset[str]) -> list[tuple[_Key, ...]]:
    """Each id's rows across the parameters, the id left out, as a sorted
    multiset: two sides with equal signatures differ by a renaming of ids
    alone. A parameter of `placed`, stored by a RIGID call, holds placed rows,
    and each id's assembly is its own: its part of the id's signature is the
    orbit of its placed rows at the id, the set over the poses of its rows at
    the pose, so that the id's assembly in any pose gives the same part
    (patterns.md, under "`RIGID` — parameter relations coupled as a rigid
    assembly")."""
    by_id: dict[Value, list[_Key]] = {}
    for name, col in ident_cols.items():
        if name not in placed:
            for row in rows_by_param.get(name, ()):
                rest = tuple(v for i, v in enumerate(row) if i != col)
                by_id.setdefault(row[col], []).append((name, row_key(rest)))
            continue
        poses: dict[Value, dict[Value, set[_Key]]] = {}
        for row in rows_by_param.get(name, ()):
            rest = tuple(v for i, v in enumerate(row)
                         if i not in (POSE_COLUMN, col))
            poses.setdefault(row[col], {}).setdefault(row[POSE_COLUMN], set()).add(
                row_key(rest))
        for id_, at in poses.items():
            orbit = sorted({tuple(sorted(rows)) for rows in at.values()})
            by_id.setdefault(id_, []).append((name, tuple(orbit)))
    return sorted(tuple(sorted(rows)) for rows in by_id.values())


def cycles(solver: Solver, params_instance: str,
           determined: Sequence[str]) -> tuple[tuple[CycleRead, ...], ...]:
    """The determined parameters whose determinations read each other's
    stored values, through the `Determine` relations between: for each
    group of them that reads around, a parameter that reads its own stored
    value included, every read inside the group, each at the first atom by
    line where it happens, in name order."""
    scope = DETERMINE_SCOPE
    feeds: dict[RelationName, list[tuple[Unit, Atom]]] = {}
    for u in solver.program.units:
        if u.scope != scope or u.body is None:
            continue
        reads = feeds.setdefault(u.head.relation, [])
        reads += [(u, a) for a, _negated in body_atoms(u.body)]

    def local(rel: RelationName) -> list[RelationName]:
        if rel.instances and rel.instances[0] != params_instance:
            return [h for h in feeds if h.instances[:1] == rel.instances[:1]]
        return [rel] if rel in feeds else []

    wanted = set(determined)
    edges: dict[str, dict[str, tuple[UnitId, int]]] = {}
    for p in determined:
        seen: set[RelationName] = set()
        stack = [RelationName((), p)]
        found: dict[str, tuple[UnitId, int]] = {}
        while stack:
            rel = stack.pop()
            if rel in seen:
                continue
            seen.add(rel)
            for u, atom in feeds.get(rel, ()):
                read = atom.relation
                if read.instances == (params_instance,) and read.name in wanted:
                    if read.name not in found \
                            or atom.line < found[read.name][1]:
                        found[read.name] = (u.id, atom.line)
                else:
                    stack += local(read)
        edges[p] = found
    # Strongly connected components (Tarjan), each with an edge inside.
    index: dict[str, int] = {}
    low: dict[str, int] = {}
    on: set[str] = set()
    path: list[str] = []
    groups: list[list[str]] = []

    def visit(v: str) -> None:
        index[v] = low[v] = len(index)
        path.append(v)
        on.add(v)
        for w in sorted(edges.get(v, {})):
            if w not in index:
                visit(w)
                low[v] = min(low[v], low[w])
            elif w in on:
                low[v] = min(low[v], index[w])
        if low[v] == index[v]:
            comp: list[str] = []
            while True:
                w = path.pop()
                on.discard(w)
                comp.append(w)
                if w == v:
                    break
            if len(comp) > 1 or v in edges.get(v, {}):
                groups.append(sorted(comp))

    for v in sorted(determined):
        if v not in index:
            visit(v)
    out = [tuple(CycleRead(p, q, *edges[p][q]) for p in group
                 for q in sorted(edges[p]) if q in group)
           for group in groups]
    return tuple(sorted(out, key=lambda c: [(r.parameter, r.reads)
                                            for r in c]))
