"""Solving over an engine: the grids cases give on an input, the pair runs,
the variations of a solver's program, the proposer probe and the Determine
run, and the helpers of those runs that the checks read as well."""

import threading
import weakref
from collections.abc import Callable, Iterator, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from enum import Enum
from itertools import combinations
from typing import Literal

from arc.task import Alt, Example, Task
from engine import (
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
    Resolved,
    Row,
    Rows,
    RunFailure,
    RunResult,
    Scope,
    Tuples,
    UnitId,
    Value,
)
from engine.engine import CompileError
from engine.program import Atom, RelationDecl, RigidCall, Unit
from solver.model import (
    TOP,
    Base,
    Branch,
    Case,
    DeriveBranch,
    Solver,
    StoreBranch,
    StoredGrid,
    atoms_of,
    enumerates,
    cases as cases_of,
    has_determine,
    instance_of,
    own,
    parse_with_lib,
    proposer_names,
    proposers_path,
    column_types,
)
from solver.problems import (
    InWitnessFile,
    Named,
    ProblemKind,
    Fault,
    Undecided,
    UndecidedForm,
)
from solver.vocabulary import (
    CHOICE,
    DETERMINE,
    ENUMERATOR,
    EX_IN,
    EX_OUT,
    IDENT,
    INPUT,
    OUTPUT,
    PARAMS,
    PROPOSE,
    TIEBREAK_RESOLUTION,
)
from solver.witness import (
    AssignArg,
    AssignRows,
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
)

IMPL = RelationName((), ENUMERATOR)
"""`impl_choice`, which holds the cases a run gives."""


@dataclass(frozen=True)
class Assignment:
    """A value for each parameter or stored relation it names; the others
    keep their stored values."""

    values: tuple[tuple[str, RelationValue], ...]


@dataclass(frozen=True)
class Grids:
    """The grids a case gives, one per tiebreak resolution
    (solver-file.md:98), and the resolution value of each where `out` has
    a resolution column, the grid's identity (solver-file.md:168)."""

    grids: tuple[Grid, ...]
    resolutions: tuple[Value, ...] = field(default=(), compare=False)


type Outcome = Grids | Undefined | RunFailure
"""principles.md:49 (defined), solver-file.md:98."""


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

    Cases that take the same `@derive` and `@store` branches share one
    run, with `impl_choice` holding their bases, and each case reads its
    grids from `out` at its case (solver-file.md:98); where `out` has no
    case column, each base runs alone. In that run each parameter `assign`
    names holds its value there, save one a `@derive` branch of the cases
    derives: for that one the value reassigns its stored value, which the
    cases do not read (history 826). Each `@derive` branch's parameter
    holds the values its proposer gives with `input` as its example
    (solver-file.md:120); where the proposer gives none, the cases are
    undefined on `input`, and no run holds the parameter empty
    (principles.md "Two parameterizations"). Each `@store` branch's
    relation holds the value `assign` gives it, else the value it stores
    at the cases' bases (`stored_value`, solver-file.md:137; history 1131).
    A case with no cells in `out`, or a grid that is not total, is
    undefined (principles.md:49).

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
class GroupRuns:
    """The runs `outcomes` makes on one input, in its order, and `out`'s
    case and resolution columns (`out_columns`), by which each case reads
    its grids from its run."""

    columns: tuple[int | None, int | None]
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


def read_run(columns: tuple[int | None, int | None], run: GroupRun
             ) -> dict[Case, Outcome]:
    """The outcome of each case of one run (`read_runs`)."""
    result = run.result
    if not isinstance(result, Tuples):
        return dict.fromkeys(run.cases, result)
    case_col, res_col = columns
    read = _read_of(result, case_col)
    return {c: read.grids(res_col, c.base) for c in run.cases}


def read_case(columns: tuple[int | None, int | None], run: GroupRun,
              case: Case) -> Outcome:
    """The outcome of one case of a run (`read_run`)."""
    result = run.result
    if not isinstance(result, Tuples):
        return result
    case_col, res_col = columns
    return _read_of(result, case_col).grids(res_col, case.base)


def _runs_on(engine: Engine, solver: Solver, cases: Sequence[Case],
             inputs: Sequence[tuple[Grid, Assignment]], limits: Limits,
             stored: _Stored) -> list[GroupRuns]:
    """The runs of `outcomes_on` on each input. The probes of the inputs
    run at once, then each group's program is built in order, then the
    groups' runs are made at once; each result is read by its place in
    that order."""
    program = solver.program
    columns = out_columns(program)
    case_col = columns[0]
    shared = solver.choice is None or case_col is not None
    groups: dict[tuple[tuple[Branch, ...], Base | None], list[Case]] = {}
    for case in dict.fromkeys(cases):
        groups.setdefault((case.branches, None if shared else case.base),
                          []).append(case)
    derives = any(isinstance(b, DeriveBranch) for branches, _ in groups
                  for b in branches)
    proposals: list[Proposals | RunFailure | None] = (
        at_once(lambda i: probe(engine, _single(i[0]), limits), inputs)
        if derives else [None] * len(inputs))
    built: list[tuple[int, list[Case], Grid, Program | Undefined | RunFailure]] = []
    for k, (input, assign) in enumerate(inputs):
        for (branches, _base), members in groups.items():
            bases = tuple(dict.fromkeys(c.base for c in members
                                        if c.base is not None))
            built.append((k, members, input, _program(
                engine, solver, bases, branches, input, assign, proposals[k],
                limits, stored)))

    def ran(b: tuple[int, list[Case], Grid, Program | Undefined | RunFailure]
            ) -> RunResult | Undefined:
        _k, _members, input, run = b
        return run if not isinstance(run, Program) else engine.run(
            run, {INPUT: GridInput(input)}, [OUTPUT], limits)

    got: list[list[GroupRun]] = [[] for _ in inputs]
    for (k, members, _input, _run), result in zip(built, at_once(ran, built),
                                                    strict=True):
        got[k].append(GroupRun(tuple(members), result))
    return [GroupRuns(columns, tuple(g)) for g in got]


class _Read:
    """What one run's `out` gives: its rows by base, the margins of each
    position value (`_grid_of`), and the grids already read, by base."""

    def __init__(self, rows: Rows, case_col: int | None) -> None:
        self.rows = rows
        self.case_col = case_col
        self.by_base = _rows_by_base(rows, case_col)
        self.margins: dict[int, _Place | None] = {}
        self.read: dict[tuple[int | None, Value | None], Grids | Undefined] = {}
        self.lock = threading.Lock()

    def grids(self, res_col: int | None, base: Base | None
              ) -> Grids | Undefined:
        mine = base if self.case_col is not None else None
        key = (res_col, mine)
        with self.lock:
            got = self.read.get(key)
            if got is None:
                got = self.read[key] = _grids(
                    res_col, self.rows if mine is None
                    else self.by_base.get(mine, ()), self.margins)
            return got


_READS: dict[int, tuple[weakref.ref[Tuples], int | None, _Read]] = {}
_READS_LOCK = threading.Lock()


def _read_of(result: Tuples, case_col: int | None) -> _Read:
    """The reading of `result`'s `out`, made once per result: the engine
    gives the same result for a run made again."""
    key = id(result)
    with _READS_LOCK:
        held = _READS.get(key)
        if held is not None and held[0]() is result and held[1] == case_col:
            return held[2]
    read = _Read(result.relations.get(OUTPUT, ()), case_col)
    with _READS_LOCK:
        _READS[key] = (weakref.ref(result,
                                   lambda _r, key=key: _READS.pop(key, None)),
                       case_col, read)
    return read


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
                 assign: Assignment, limits: Limits
                 ) -> Mapping[RelationName, Rows] | Undefined | RunFailure:
    """The rows each of `relations`, named from the top level, holds when
    `case` runs on `input` at `assign`, the empty input where `input` is
    None: one run of the program `outcomes` builds for the case, with
    `impl_choice` holding its base and its `@derive` and `@store` branches
    in place. Undefined where a derivation of the case gives its parameter
    no value on the input; the run's failure, or that of a run the program
    needs, as the engine gives it. A relation with no rows maps to none.

    The solver's `program` is the one that runs, so a variation runs
    through here on the solver with its program replaced. A relation the
    run does not output raises `ValueError` (`output_rows`)."""
    proposals = None if not any(isinstance(b, DeriveBranch)
                                for b in case.branches) \
        else probe(engine, _single(() if input is None else input), limits)
    bases = () if case.base is None else (case.base,)
    run = _program(engine, solver, bases, case.branches, input, assign,
                   proposals, limits, _Stored())
    if not isinstance(run, Program):
        return run
    got = engine.run(run, {INPUT: _input(input)}, list(relations), limits)
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


def case_program(engine: Engine, solver: Solver, case: Case, input: Grid,
                 assign: Assignment, limits: Limits
                 ) -> Program | Undefined | RunFailure:
    """The program `case` runs on `input` at `assign`, as `outcomes`
    builds it, with `impl_choice` holding the case's base, and as it
    stands for a case with no base; undefined where a derivation gives its
    parameter no value on `input`, and the failure of a run it needs where
    that run fails."""
    proposals = None if not any(isinstance(b, DeriveBranch)
                                for b in case.branches) \
        else probe(engine, _single(input), limits)
    bases = () if case.base is None else (case.base,)
    return _program(engine, solver, bases, case.branches, input, assign,
                    proposals, limits, _Stored())


def _program(engine: Engine, solver: Solver, bases: tuple[Base, ...],
             branches: tuple[Branch, ...], input: Grid | None,
             assign: Assignment,
             proposals: "Proposals | RunFailure | None", limits: Limits,
             stored: _Stored) -> Program | Undefined | RunFailure:
    """The program the cases of `bases` that take `branches` run on
    `input`, the empty input where it is None, at `assign` (`outcomes`),
    with `proposals` the proposer probe of the input."""
    held_program = restricted(engine, solver, bases)
    run = held_program
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
                key = (bases, b.relation)
                if key not in stored.values:
                    stored.values[key] = stored_value(
                        engine, solver, held_program, b, limits)
                got = stored.values[key]
                if not isinstance(got, StoredValue):
                    return got
                value = got.rows
                if len(got.columns) < got.arity:
                    here = engine.run(run, {INPUT: _input(input)},
                                      [b.relation], limits)
                    if not isinstance(here, Tuples):
                        return here
                    value = got.on(here.relations.get(b.relation, ()))
            run = engine.fix_relation(run, b.relation, value)
    return run


def assignment(solver: Solver, entry: Entry) -> Assignment | Fault:
    """The assignment a witness entry's `assign` states
    (solver-file.md:180, :188-192): each parameter or `@store` relation it
    names with its rows, a string read as the lib constant it names and a
    list as a record, and a grid as the value of a parameter stored by one
    GRID call, under that call's keys. A name, a constant or a grid it
    cannot place is the problem in its place."""
    where = InWitnessFile(entry.id)
    params = {p.name: p for p in solver.params.parameters}
    stored = {b.spelled for b in solver.branches
              if isinstance(b, StoreBranch)}
    out: list[tuple[str, RelationValue]] = []
    for name, value in entry.assign:
        if name not in params and name not in stored:
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
        if param is None or not isinstance(param.stored, StoredGrid) \
                or len(param.stored.grids) != 1:
            return Fault(
                ProblemKind.UNDECIDED, where,
                Undecided(UndecidedForm.GRID_FOR_KEYED_PARAMETER, name))
        out.append((name, GridValue(param.stored.grids[0].keys, value)))
    return Assignment(tuple(out))


def _arg_value(arg: AssignArg, constants: Mapping[str, Value]) -> Value | None:
    """An `assign` argument as a value: a number, a lib constant, or a
    record of such; None where a string names no constant."""
    if isinstance(arg, str):
        return constants.get(arg)
    if isinstance(arg, tuple):
        vals = [_arg_value(a, constants) for a in arg]
        if any(v is None for v in vals):
            return None
        return RecordValue(tuple(v for v in vals if v is not None))
    return arg


# The runs' parts


def scaled(limits: Limits, grids: int) -> Limits:
    """The limits of a run over `grids` examples: the limits of a run on
    one grid, once per example."""
    n = max(1, grids)
    return Limits(cpu_seconds=limits.cpu_seconds * n,
                  wall_seconds=limits.wall_seconds * n)


def as_grid(grid: Sequence[Sequence[int]]) -> Grid:
    """A task's grid, rows of lists, as the engine's grid, rows of
    tuples."""
    return tuple(tuple(r) for r in grid)


def parameter(solver: Solver, name: str) -> RelationName:
    """A parameter as the program reads it, `params.<rel>`
    (solver-file.md:114)."""
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
    key = id(program)
    with _RESTRICTED_LOCK:
        held = _RESTRICTED.get(key)
        if held is not None and held[0]() is program and held[1]() is engine:
            got = held[2].get(bases)
            if got is not None:
                return got
    got = engine.fix_relation(program, IMPL, tuple((b,) for b in bases))
    with _RESTRICTED_LOCK:
        held = _RESTRICTED.get(key)
        if held is None or held[0]() is not program or held[1]() is not engine:
            held = _RESTRICTED[key] = (
                weakref.ref(program,
                            lambda _p, key=key: _RESTRICTED.pop(key, None)),
                weakref.ref(engine), {})
        held[2][bases] = got
    return got


_RESTRICTED: dict[int, tuple[weakref.ref[Program], weakref.ref[Engine],
                             dict[tuple[Base, ...], Program]]] = {}
"""`restricted`'s programs, by the identity of the program they restrict,
while that program lives: a survey's variant runs on every pair and in
every group of cases."""
_RESTRICTED_LOCK = threading.Lock()


@dataclass(frozen=True)
class StoredValue:
    """The value a `@store` branch stores: the columns of the relation
    that hold one value on every input, and the rows of that value, each
    row over those columns alone (solver-file.md:137: the relation "has
    one value on every input"). The other columns are the value's keys,
    which the relation's clauses give on each input."""

    arity: int
    columns: tuple[int, ...]
    rows: Rows

    def on(self, derived: Rows) -> Rows:
        """The relation's rows on an input where its clauses give
        `derived`: each key its clauses give, with each row of the
        value."""
        keys = [i for i in range(self.arity) if i not in self.columns]
        out: dict[Row, None] = {}
        for key in dict.fromkeys(tuple(r[i] for i in keys) for r in derived):
            for row in self.rows:
                at = dict(zip(keys, key, strict=True)) \
                    | dict(zip(self.columns, row, strict=True))
                out[tuple(at[i] for i in range(self.arity))] = None
        return tuple(out)


def stored_value(engine: Engine, solver: Solver, program: Program,
                 branch: StoreBranch, limits: Limits
                 ) -> StoredValue | RunFailure:
    """The value a `@store` branch stores (solver-file.md:137), from the
    relation's rows in `program` on each input of the task's pairs. A
    column that carries the case (`case_columns`) is a key, never a column
    of the value (solver-file.md:104-110). The value's columns are every
    other column where the rows are one set on every input. Else they are
    the most such columns, the first in column order among
    equals, whose rows are one set on every input and whose rows on each
    input are the same at each key, a key being the rows' part over the
    other columns: the relation is then its keys, which its clauses give
    on each input, with the value at each, as the old tool stored it. Else
    every column that carries no case. The value's rows are the relation's rows over its
    columns on the first train input.
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
        per_input.append(got.relations.get(branch.relation, ()))
    first = per_input[0]
    arity = next((len(r) for rows in per_input for r in rows), 0)

    def one_value(cols: tuple[int, ...]) -> bool:
        sets = [{tuple(r[i] for i in cols) for r in rows}
                for rows in per_input]
        return all(x == sets[0] for x in sets)

    def product(cols: tuple[int, ...]) -> bool:
        keys = [i for i in range(arity) if i not in cols]
        for rows in per_input:
            by_key: dict[Row, set[Row]] = {}
            for r in rows:
                by_key.setdefault(tuple(r[i] for i in keys), set()).add(
                    tuple(r[i] for i in cols))
            if len({frozenset(v) for v in by_key.values()}) > 1:
                return False
        return True

    case = case_columns(solver, column_types(program, branch.relation))
    every = tuple(i for i in range(arity) if i not in case)
    cols = every
    if not one_value(every):
        constant = [i for i in every if one_value((i,))]
        subsets = [c for n in range(len(constant), 0, -1)
                   for c in combinations(constant, n)
                   if one_value(c) and product(c)]
        cols = subsets[0] if subsets else every
    return StoredValue(arity, cols, tuple(dict.fromkeys(
        tuple(r[i] for i in cols) for r in first)))


def relation_types(engine: Engine, program: Program,
                   relation: RelationName) -> tuple[RelationDecl, tuple[str, ...]]:
    """The declaration of `relation`, named from the top level, and the
    type each of its columns reads as, each type parameter of its
    components read through the instance's type arguments
    (solver-file.md, "Components")."""
    got = engine.index(program).resolve(relation, TOP)
    if not isinstance(got, Resolved):
        raise ValueError(f"`{relation.text}` resolves to no declaration")
    decl = next(r for r in program.relations if r.id == got.declaration)
    env: dict[str, str] = {}
    for param, arg in got.type_arguments:
        env[param] = env.get(arg, arg)
    return decl, tuple(env.get(c.type, c.type) for c in decl.columns)


def case_columns(solver: Solver, types: Sequence[str]) -> tuple[int, ...]:
    """The columns of a relation of column types `types`, as the model
    resolves them (`solver.model.column_types`), that carry the case: of
    type `Choice`, or of an ADT that stands in `Choice`
    (solver-file.md:104-110). A case column is a key of a stored value,
    never one of its columns."""
    case = {CHOICE} | ({p.type for p in solver.choice.points}
                       if solver.choice is not None else set[str]())
    return tuple(i for i, t in enumerate(types) if t in case)


def out_columns(program: Program) -> tuple[int | None, int | None]:
    """The case column and the resolution column of `out`, by type
    (solver-file.md:103, :168); None where `out` has none."""
    decl = next((r for r in program.relations if r.name == OUTPUT.name
                 and r.scope == TOP and r.span.file is None), None)
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
    """The grids `out`'s rows hold at `case`, one per resolution in the
    order of the resolution values (solver-file.md:98), or undefined, with
    the reason of the first resolution that gives no total grid
    (principles.md:49)."""
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


def _single(grid: Grid) -> Task:
    """A task whose one example is `grid`, with no output, for the probe of
    one input."""
    return Task(train=[], test=[Example(input=[list(r) for r in grid],
                                        output=[])])


# Pairs


@dataclass(frozen=True)
class PairId:
    """A pair of the task, by section and index (principles.md:74, fit)."""

    section: Literal["train", "test"]
    index: int


class AltKind(Enum):
    """How a pair's alt output differs from its output
    (solver-file.md:164-167): a `rule` alt is a second candidate, a
    `tiebreak` alt another resolution within the output's."""

    RULE = "rule"
    TIEBREAK = "tiebreak"


def alt_kind(alt: Alt) -> AltKind:
    """The kind the task file gives `alt`."""
    return AltKind(alt.kind)


class Candidate(Enum):
    """A pair's candidate outputs: its output and its alt (principles.md:65)."""

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
        yield PairId("train", i), ex
    for i, ex in enumerate(task.test):
        yield PairId("test", i), ex


def candidates(ex: Example) -> tuple[tuple[Candidate, frozenset[Grid]], ...]:
    """A pair's candidates as sets of accepted outputs (principles.md:65;
    solver-file.md:166-167)."""
    output = as_grid(ex.output)
    if ex.alt is None:
        return ((Candidate.OUTPUT, frozenset({output})),)
    alt = as_grid(ex.alt.grid)
    if alt_kind(ex.alt) is AltKind.TIEBREAK:
        return ((Candidate.OUTPUT, frozenset({output, alt})),)
    return ((Candidate.OUTPUT, frozenset({output})),
            (Candidate.ALT, frozenset({alt})))


def pairs(engine: Engine, solver: Solver, limits: Limits
          ) -> tuple[PairRuns, ...] | RunFailure:
    """Per train and test pair, per case of the solver: the run and the judged
    profile, the solver's cases of a pair from `outcomes`. A case matches a
    candidate when the set of its grids is the candidate's set of accepted
    outputs (principles.md:65, :74; a `tiebreak` alt joins the output's
    candidate, a `rule` alt is a second one, solver-file.md:166-167).
    Where the run that enumerates the cases fails, its failure; a solver
    with no task has no pair."""
    if solver.task is None:
        return ()
    cases = cases_of(solver, engine, limits)
    if not isinstance(cases, tuple):
        return cases
    out: list[PairRuns] = []
    exs = list(examples(solver.task))
    every = outcomes_on(engine, solver, cases,
                        [(as_grid(ex.input), Assignment(())) for _, ex in exs],
                        limits)
    for (pair, ex), got in zip(exs, every, strict=True):
        cands = candidates(ex)
        runs: list[CaseOnPair] = []
        for case in cases:
            result = got[case]
            matches = () if not isinstance(result, Grids) else tuple(
                c for c, accepted in cands
                if frozenset(result.grids) == accepted)
            runs.append(CaseOnPair(case, result, matches))
        out.append(PairRuns(pair, tuple(runs)))
    return tuple(out)


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
            bases = list(dict.fromkeys(
                c.base for c in cases if c.base is not None))
            return engine.fix_relation(program, IMPL,
                                       tuple((b,) for b in bases))
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
    contract; solver-file.md:162)."""
    return {
        EX_IN: IndexedGrids(tuple(as_grid(e.input)
                                  for e in (*task.train, *task.test))),
        EX_OUT: IndexedGrids(tuple(as_grid(e.output) for e in task.train)),
    }


type _ProbeProgram = tuple[Program, dict[str, RelationName]] | ParseFailure
_PROBE_PROGRAMS: dict[int, tuple[weakref.ref[Engine], str, _ProbeProgram]] = {}
"""By the engine's identity, the engine, the proposers text last built and
what `_probe_program` built from it."""


def _probe_program(engine: Engine) -> _ProbeProgram:
    """The proposers program with an instance of each proposer, and each
    proposer's `propose` in its instance, built once per engine and text
    of `programs/proposers.dl`."""
    text = proposers_path().read_text()
    held = _PROBE_PROGRAMS.get(id(engine))
    if held is not None and held[0]() is engine and held[1] == text:
        return held[2]
    parsed = parse_with_lib(engine, text)
    built: _ProbeProgram
    if isinstance(parsed, ParseFailure):
        built = parsed
    else:
        program = parsed
        outputs: dict[str, RelationName] = {}
        for name in proposer_names(program):
            inst = name.lower()
            program = engine.instantiate(program, name, inst)
            outputs[name] = RelationName((inst,), PROPOSE)
        built = program, outputs
    try:
        _PROBE_PROGRAMS[id(engine)] = (weakref.ref(engine), text, built)
    except TypeError:
        pass
    return built


def probe(engine: Engine, task: Task, limits: Limits
          ) -> Proposals | RunFailure:
    """The proposers program run over the task's examples: each proposer
    of `programs/proposers.dl`, a component that declares `propose`, as an
    instance, with `ex_in` over every example's input and `ex_out` over
    the train outputs (proposers.dl's header). The run takes `limits`
    once per example."""
    built = _probe_program(engine)
    if isinstance(built, ParseFailure):
        return CompileError(built.line, built.message)
    program, outputs = built
    got = engine.run(program, example_inputs(task), list(outputs.values()),
                     scaled(limits, len(task.train) + len(task.test)))
    if not isinstance(got, Tuples):
        return got
    return Proposals({name: got.relations.get(rel, ())
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


@dataclass(frozen=True)
class Determined:
    """solver-file.md:157-162 ("Determination")."""

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
    """The Determine comp over the examples, diffed against the stored
    values (solver-file.md:157-162). The parameters with an `Ident` column
    compare together modulo a renaming of ids (solver-file.md:161), one a
    RIGID call stores by the orbit of its placed rows at each id
    (`_signatures`). The other parameters a RIGID call stores compare
    together per block, up to a D4 image of the stored assembly, since a
    RIGID block exposes them only as D4 placements that transform them
    together and the stored pose is unobservable (patterns.md:98): the
    Determine relations stand in for the block's charts, the program
    places them, and the parameters agree where some pose of one side
    gives the rows of every parameter of the block that the other side
    gives at some pose (`_same_pose_orbits`). A diff of such a parameter
    holds its placed rows. The runs take `limits` once per example."""
    program = solver.program
    if not has_determine(solver):
        return NoDetermine()
    task = solver.task or Task()
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
                    RelationName((params_inst.name,), p.name)]
    inputs: dict[RelationName, InputValue] = {INPUT: (),
                                              **example_inputs(task)}
    got = engine.run(program, inputs, outputs,
                     scaled(limits, len(task.train) + len(task.test)))
    if not isinstance(got, Tuples):
        return got
    stored = {p.name: got.relations.get(RelationName((params_inst.name,),
                                                     p.name), ())
              for p in determined}
    derived = {p.name: got.relations.get(RelationName((det_name,), p.name),
                                         ())
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
                placed, RelationName((params_inst.name,), chart),
                derived[name])
        again = engine.run(placed, inputs, [
            RelationName((params_inst.name,), n) for n in charts],
            scaled(limits, len(task.train) + len(task.test)))
        if not isinstance(again, Tuples):
            return again
        for name in charts:
            derived[name] = again.relations.get(
                RelationName((params_inst.name,), name), ())
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
    scope = Scope((PARAMS,))
    heads = {u.id: u.head.relation for u in solver.program.units}
    out = {r.name for r in solver.program.relations
           if r.scope == scope and r.chart_of is not None}
    for m in solver.program.macros:
        if isinstance(m, RigidCall) and m.scope == scope:
            out |= set(m.names)
            out |= {heads[u].name for u in m.body
                    if u in heads and not heads[u].instances}
    return frozenset(out)


def _blocks(solver: Solver) -> dict[str, tuple[str, str]]:
    """Each relation a RIGID call in `Params` binds, with its block and the
    chart relation the call declares for it: the block's charts in the
    order the call binds its relations. A call whose charts are not one
    per name is left out, and is a fault of `load`
    (`model.instance_faults`)."""
    scope = Scope((PARAMS,))
    out: dict[str, tuple[str, str]] = {}
    for m in solver.program.macros:
        if not isinstance(m, RigidCall) or m.scope != scope:
            continue
        charts = [r.name for r in solver.program.relations
                  if r.scope == scope and r.chart_of == m.block]
        if len(charts) != len(m.names):
            continue
        for name, chart in zip(m.names, charts, strict=True):
            out[name] = (m.block, chart)
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
                poses.setdefault(row[0], [set() for _ in names])[k].add(
                    row[1:])
        return frozenset(
            tuple(tuple(sorted(rs, key=lambda r: tuple(
                value_key(v) for v in r))) for rs in sets)
            for sets in poses.values())

    out: set[str] = set()
    for names in by_block.values():
        if orbit(stored, names) == orbit(derived, names):
            out |= set(names)
    return frozenset(out)


type _Key = tuple[object, ...]


def _row_key(row: Row) -> _Key:
    """An order on rows built from their values' parts."""
    return tuple(value_key(v) for v in row)


def _signatures(rows_by_param: Mapping[str, Rows],
                ident_cols: Mapping[str, int],
                placed: frozenset[str]) -> list[tuple[_Key, ...]]:
    """Each id's rows across the parameters, the id left out, as a sorted
    multiset: two sides with equal signatures differ by a renaming of ids
    alone. A parameter of `placed`, stored by a RIGID call, holds placed
    rows, and each id's assembly is its own: its part of the id's
    signature is the orbit of its placed rows at the id, the set over the
    poses of its rows at the pose, so that the id's assembly in any pose
    gives the same part (patterns.md:98)."""
    by_id: dict[Value, list[_Key]] = {}
    for name, col in ident_cols.items():
        if name not in placed:
            for row in rows_by_param.get(name, ()):
                rest = tuple(v for i, v in enumerate(row) if i != col)
                by_id.setdefault(row[col], []).append((name, _row_key(rest)))
            continue
        poses: dict[Value, dict[Value, set[_Key]]] = {}
        for row in rows_by_param.get(name, ()):
            rest = tuple(v for i, v in enumerate(row) if i not in (0, col))
            poses.setdefault(row[col], {}).setdefault(row[0], set()).add(
                _row_key(rest))
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
    scope = Scope((DETERMINE,))
    feeds: dict[RelationName, list[tuple[Unit, Atom]]] = {}
    for u in solver.program.units:
        if u.scope != scope or u.body is None:
            continue
        reads = feeds.setdefault(u.head.relation, [])
        for lit in u.body:
            reads += [(u, a) for a in atoms_of(lit)]

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
