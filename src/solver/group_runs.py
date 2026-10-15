"""The runs `outcomes` makes, one per group of cases that take the same
branches, and their reads: the program a group runs, and the grids each
case of the group reads from the run's `out`."""

import json
import threading
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace

from engine import (
    Engine,
    Grid,
    GridInput,
    GridValue,
    InputValue,
    Limits,
    Program,
    RecordValue,
    RelationName,
    RelationValue,
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
    RemoveUnit,
    SizeOffLayout,
)
from engine.memo import ByIdentity, Once
from engine.program import (
    grid_size,
    own,
)
from engine.quotes import quotes
from solver.aggregate import (
    Solver,
    assignable,
    enumerates,
    store_branch,
)
from solver.columns import (
    ArgOffType,
    ArgUnknown,
    arg_value,
    column_names,
)
from solver.dependence import dependence
from solver.probe import Proposals, probe
from solver.model import (
    Base,
    Branch,
    Case,
    DeriveBranch,
    Parameter,
    StoreBranch,
    StoredGrid,
    choice_bases,
    derived_parameters,
    every_base,
)
from solver.outcome import Assignment, Grids, Outcome
from solver.problems import (
    AnchorWithoutStamp,
    AssignArity,
    AssignType,
    Fault,
    GridCellOffForm,
    GridOffLayout,
    InWitnessFile,
    Named,
    ProblemKind,
    Storage,
)
from solver.readers import (
    parameter,
)
from solver.input_task import input_task
from solver.per_case import (
    at_every_case,
    case_reading,
    fixed_at_every_case,
    parameter_reading,
)
from solver.restricted import restricted
from solver.stored_value import StoredValue, stored_value
from solver.open_values import field_readings, open_fields
from solver.out_grids import (
    FieldValues,
    OutColumns,
    Place,
    by_value,
    case_grids,
    open_grids,
    out_columns,
    rows_by_base,
)
from solver.vocabulary import (
    INPUT,
    OUTPUT,
)
from solver.undefined import NoDerivedValue, NoOutput, Undefined
from solver.witness import AnchoredGrid, AssignArg, AssignRows, AssignValue


class StoredValues:
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


@dataclass(frozen=True)
class GroupRun:
    """One run `outcomes` makes: the cases that read their grids from it,
    in the order given, its result, or why the group has none, and, where
    `out` has an open-value column, each case's values at the fields of
    `OpenValue` on the run (`solver.open_values.open_fields`), in the order
    of the cases."""

    cases: tuple[Case, ...]
    result: RunResult | Undefined
    fields: tuple[FieldValues, ...] = ()

    def at(self, i: int) -> FieldValues:
        """The field values of the run's case `i`; none where `out` has no
        open-value column."""
        return self.fields[i] if self.fields else ()


@dataclass(frozen=True)
class RunColumns:
    """How a case reads its grids from a group's run: `out`'s columns
    (`out_columns`), and, where the run classes the cases (`classed`), the
    relation of the representatives' rows and the relation of the
    classes."""

    out: OutColumns
    classed: tuple[RelationName, RelationName] | None = None


@dataclass(frozen=True)
class GroupRuns:
    """The runs `outcomes` makes on one input, in its order, and how each
    case reads its grids from its run."""

    columns: RunColumns
    runs: tuple[GroupRun, ...]


def group_runs(engine: Engine, solver: Solver, cases: Sequence[Case],
               input: Grid, assign: Assignment, limits: Limits) -> GroupRuns:
    """The runs `outcomes` makes for `cases` on `input` at `assign`; its
    result is `read_runs` of them."""
    return runs_on(engine, solver, cases, ((input, assign),), limits,
                    StoredValues())[0]


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
    return {c: read.grids(c.base, run.at(i)) for i, c in enumerate(run.cases)}


def read_case(columns: RunColumns, run: GroupRun, case: Case) -> Outcome:
    """The outcome of one case of a run (`read_run`)."""
    result = run.result
    if not isinstance(result, Tuples):
        return result
    return _read_of(result, columns).grids(case.base,
                                           run.at(run.cases.index(case)))


def runs_on(engine: Engine, solver: Solver, cases: Sequence[Case],
            inputs: Sequence[tuple[Grid, Assignment]], limits: Limits,
            stored: StoredValues) -> list[GroupRuns]:
    """The runs of `outcomes_on` on each input. The probes of the inputs
    run at once, then each group's program is built and run on each
    input, all at once, since building a `@store` branch's program runs
    the program too; each result is read by its place in the order of
    the inputs and the groups."""
    out = out_columns(solver.program)
    groups = case_groups(solver, cases)
    unread = _unread_units(engine, solver, groups)
    fields_at = _FieldsAt(engine, solver) if out.open is not None else None
    columns = RunColumns(out)
    outputs = [OUTPUT]
    if out.case is not None or out.open is not None:
        cls = classed(engine, solver.program)
        solver = replace(solver, program=cls.program)
        columns = RunColumns(out, (cls.rows, cls.classes))
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
        bases = tuple(choice_bases(members))
        run = group_program(engine, solver, bases, members[0].branches, input,
                       assign, proposals[k], limits, stored, drop)
        return run if not isinstance(run, Program) else engine.run(
            run, {INPUT: GridInput(input)}, outputs, limits)

    got: list[list[GroupRun]] = [[] for _ in inputs]
    for (k, members, _drop), result in zip(tasks, at_once(ran, tasks),
                                           strict=True):
        fields = () if fields_at is None or not isinstance(result, Tuples) \
            else tuple(fields_at.of(c, k, inputs[k][1], proposals[k])
                       for c in members)
        got[k].append(GroupRun(tuple(members), result, fields))
    return [GroupRuns(columns, tuple(g)) for g in got]


class _FieldsAt:
    """`solver.open_values.open_fields` of each case on each input, computed
    once, the derived values those the input's probe gives each
    `@derive` branch's proposer, as `group_program` fixes them."""

    def __init__(self, engine: Engine, solver: Solver) -> None:
        self.engine = engine
        self.solver = solver
        self.readings = field_readings(solver)
        self.got: dict[tuple[Case, int], FieldValues] = {}

    def of(self, case: Case, k: int, assign: Assignment,
           proposals: "Proposals | RunFailure | None") -> FieldValues:
        key = (case, k)
        got = self.got.get(key)
        if got is None:
            derived = {} if not isinstance(proposals, Proposals) else {
                b.parameter: proposals.values.get(b.proposer, ())
                for b in case.branches if isinstance(b, DeriveBranch)}
            got = self.got[key] = open_fields(self.engine, self.solver,
                                              self.readings, case, assign,
                                              derived)
        return got


def _unread_units(engine: Engine, solver: Solver,
                  groups: Sequence[tuple[Case, ...]]
                  ) -> list[frozenset[UnitId]]:
    """For each group, the units of the solver's own text that no case of
    the group depends on (`dependence`), and the facts an operation wrote
    of a relation that no case of the group reads or feeds, as a variation
    writes a parameter's value: its run leaves them out, so that the run's
    text, which keys its stored result, holds the units its cases depend
    on, and an edit to a unit, or a variation of a relation, reruns only
    the groups whose cases depend on it."""
    own_units = frozenset(u.id for u in solver.program.units if own(u.span))
    written = [u for u in solver.program.units
               if u.span is None and u.body is None]
    read = _read_units(engine, _enumerated(engine, solver),
                       [c.base for g in groups for c in g])
    out: list[frozenset[UnitId]] = []
    for g in groups:
        relations = frozenset[RelationName]().union(
            *(read[c.base].relations for c in g))
        out.append(own_units.difference(*(read[c.base].units for c in g))
                   | {u.id for u in written
                      if u.head.relation not in relations})
    return out


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


@dataclass(frozen=True)
class _Reads:
    """What a base's derivation of `out` depends on (`dependence`): the
    units of the solver's own text, and the relations those units read or
    feed."""

    units: frozenset[UnitId]
    relations: frozenset[RelationName]


_READ_UNITS: ByIdentity[Program, tuple[tuple[object, ...],
                                      dict[Base | None, _Reads]]] \
    = ByIdentity()
"""`_read_units`'s reads by base, for each program while it lives, with
the parts of the solver the result also reads."""


def _read_units(engine: Engine, solver: Solver,
                bases: Sequence[Base | None]
                ) -> dict[Base | None, _Reads]:
    """What each of `bases` depends on (`dependence`), computed once per
    base for the solver's program."""
    program = solver.program
    parts = (solver.choice, solver.annotations.markers, solver.params)
    memo = _READ_UNITS.guarded(program, parts, dict)
    missing = [b for b in dict.fromkeys(bases) if b not in memo]
    if missing:
        rd = dependence(engine, solver, missing)
        units = _by_base(rd.units, missing)
        relations = _by_base(rd.relations, missing)
        for b in missing:
            memo.setdefault(b, _Reads(units[b], relations[b]))
    return {b: memo[b] for b in bases}


def _by_base[K](read: Mapping[K, tuple[Base | None, ...]],
                bases: Sequence[Base | None]
                ) -> dict[Base | None, frozenset[K]]:
    """For each of `bases`, the keys of `read` whose bases include it."""
    return {b: frozenset(k for k, depending in read.items() if b in depending)
            for b in bases}


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
        or out_columns(solver.program).case is not None
    groups: dict[tuple[tuple[Branch, ...], Base | None], list[Case]] = {}
    for case in dict.fromkeys(cases):
        groups.setdefault((case.branches, None if shared else case.base),
                          []).append(case)
    return [tuple(g) for g in groups.values()]


def classed(engine: Engine, program: Program) -> Classed:
    """`program` with the rules that class a run's keys by equal `out`
    rows (`Engine.classify`), so that a run outputs `out` at each class's
    representative alone and the key-to-representative table, and the keys
    are compared in the run. A key is `out`'s case and open-value columns,
    those of them `out` has."""
    out = out_columns(program)
    key = tuple(c for c in (out.case, out.open) if c is not None)
    assert key
    return engine.classify(program, OUTPUT, key)


class _Read:
    """What one run's `out` gives: its rows by base, the margins of each
    position value (`_grid_of`), and the grids already read, by base.
    `classes` gives each key's representative (`classed`), whose rows
    `rows` holds, for a run of `classed`; where a key holds an open value,
    a case's grid at a combination of open values is read from the rows
    of the representatives of its keys that hold there, once for each set
    of representatives (`solver.out_grids.open_grids`)."""

    def __init__(self, rows: Rows, out: OutColumns,
                 classes: Mapping[Value, Value] | None = None) -> None:
        self.rows = rows
        self.out = out
        self.classes = classes
        self.by_base = rows_by_base(rows, out.case)
        self.margins: dict[int, Place | None] = {}
        self.read: dict[tuple[Value | None, FieldValues],
                        Grids | Undefined] = {}
        self.lock = threading.Lock()
        self.opens: dict[Value | None, list[tuple[Value, Value]]] = {}
        self.by_reps: dict[tuple[Value, ...], Grids | Undefined] = {}
        self.rep_rows: dict[Value, list[Row]] | None = None
        if classes is not None and out.open is not None:
            for k, rep in classes.items():
                base, value = _key_parts(out, k)
                self.opens.setdefault(base, []).append((value, rep))

    def grids(self, base: Base | None, fields: FieldValues
              ) -> Grids | Undefined:
        mine = base if self.out.case is not None else None
        with self.lock:
            got = self.read.get((mine, fields))
            if got is None:
                got = self.read[(mine, fields)] = self._grids(mine, fields)
            return got

    def _grids(self, mine: Value | None, fields: FieldValues
               ) -> Grids | Undefined:
        if self.classes is None:
            return case_grids(self.out, self.rows if mine is None
                              else self.by_base.get(mine, ()), self.margins,
                              fields)
        if self.out.open is None:
            rep = self.classes.get(mine) if mine is not None else None
            if rep is None:
                return Undefined(NoOutput())
            return case_grids(self.out, self.by_base.get(rep, ()),
                              self.margins, fields)
        reps = self.opens.get(mine)
        if not reps:
            return Undefined(NoOutput())
        if self.rep_rows is None:
            self.rep_rows = self._by_key()
        return open_grids(self.out.resolution, reps, self._rows_of, fields,
                          self.margins, self.by_reps)

    def _rows_of(self, rep: Value) -> Sequence[Row]:
        assert self.rep_rows is not None
        return self.rep_rows.get(rep, ())

    def _by_key(self) -> dict[Value, list[Row]]:
        """The rows of each representative key."""
        assert self.out.open is not None
        if self.out.case is None:
            return by_value(self.rows, self.out.open)
        out: dict[Value, list[Row]] = {}
        for base, rows in self.by_base.items():
            for value, mine in by_value(rows, self.out.open).items():
                out[RecordValue((base, value))] = mine
        return out


def _key_parts(out: OutColumns, key: Value) -> tuple[Value | None, Value]:
    """The base and the open value of a key of `classed`: a record of the
    two where `out` has a case column, the open value alone otherwise."""
    if out.case is None:
        return None, key
    assert isinstance(key, RecordValue)
    base, value = key.fields
    return base, value


_READS: ByIdentity[Tuples, dict[RunColumns, _Read]] = ByIdentity()


def _read_of(result: Tuples, columns: RunColumns) -> _Read:
    """The reading of `result`'s `out`, made once per result: the engine
    gives the same result for a run made again."""

    def make() -> _Read:
        rels = result.relations
        if columns.classed is not None:
            rows, classes = columns.classed
            return _Read(rels[rows], columns.out,
                         {r[0]: r[1] for r in rels[classes]})
        return _Read(rels[OUTPUT], columns.out)

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


def run_input(input: Grid | None) -> InputValue:
    """A grid as the run's `in`, the empty input where it is None."""
    return () if input is None else GridInput(input)


def group_program(engine: Engine, solver: Solver, bases: tuple[Base, ...],
             branches: tuple[Branch, ...], input: Grid | None,
             assign: Assignment,
             proposals: "Proposals | RunFailure | None", limits: Limits,
             stored: StoredValues, drop: frozenset[UnitId] = frozenset()
             ) -> Program | Undefined | RunFailure:
    """The program the cases of `bases` that take `branches` run on
    `input`, the empty input where it is None, at `assign` (`outcomes`),
    with `proposals` the proposer probe of the input, and without the
    units of `drop`."""
    held_program = restricted(engine, solver, bases)
    run = _without(engine, held_program, drop)
    derived = derived_parameters(branches)
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
            run = fixed_at_every_case(engine, solver, run, b.parameter,
                                      values)
        elif isinstance(b, StoreBranch):
            value = assigned.get(b.spelled)
            if value is None:
                got = stored.get((bases, b.relation), lambda b=b: stored_value(
                    engine, solver, held_program, b, limits))
                if not isinstance(got, StoredValue):
                    return got
                if got.keyed_by_case:
                    value = got.stored_rows()
                else:
                    here = engine.run(run, {INPUT: run_input(input)},
                                      [b.relation], limits)
                    if not isinstance(here, Tuples):
                        return here
                    value = got.on(here.relations[b.relation])
            run = engine.fix_relation(run, b.relation, value)
    return run


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
            written = _written_assign(solver, name, value.rows, where)
            if isinstance(written, Fault):
                return written
            out.append((name, written))
            continue
        param = params.get(name)
        grid, anchor = (value.grid, value.anchor) \
            if isinstance(value, AnchoredGrid) else (value, None)
        match param:
            case Parameter(stored=StoredGrid(grids=(call,))):
                pass
            case _:
                if anchor is None:
                    return Fault(ProblemKind.GRID_OFF_LAYOUT, where,
                                 GridOffLayout(name, None, grid_size(grid)))
                storage = Storage.STORED_RELATION if param is None \
                    else Storage.GRID_CALLS \
                    if isinstance(param.stored, StoredGrid) else Storage.FACTS
                return Fault(ProblemKind.ANCHOR_WITHOUT_STAMP, where,
                             AnchorWithoutStamp(name, storage))
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


@quotes("solver-file.md", "Witness file",
        "An `assign` of a relation in [Params](docs/handbook/solver-file.md#params) "
        "or of a `@store` line's relation gives its facts without their case "
        "part")
def _written_assign(solver: Solver, name: str,
                    facts: Sequence[tuple[AssignArg, ...]],
                    where: InWitnessFile) -> tuple[Row, ...] | Fault:
    """The facts an `assign` of rows on `name`, a parameter or a `@store`
    relation, writes: each row a fact without its case part
    (`PerCase.value`), a parameter's case part being its `Choice` columns
    (`parameter_reading`) and a `@store` relation's every column that
    carries the case (`case_reading`), written at every base of the `Choice`
    (`at_every_case`). Each argument is read as a value of its column's
    type, and a case column's record as the list of its fields outside the
    case, each read as a value of its field's type
    (`solver.columns.arg_value`). A row of another width than the columns
    outside the case part, a string that names nothing, and an argument
    of another type than its column's are the problem at `where`."""
    sb = store_branch(solver, name) \
        if solver.params.parameter(name) is None else None
    pc = case_reading(solver, sb.relation) if sb is not None \
        else parameter_reading(solver, name)
    rel = pc.relation
    types = pc.types
    names = column_names(solver.engine, solver.program, rel)
    mixed = pc.mixed
    given = tuple(sorted({len(f) for f in facts}))
    if given and given != (len(pc.given),):
        return Fault(ProblemKind.ASSIGN_ARITY, where,
                     AssignArity(name, given, len(pc.given), bool(pc.case)))
    rows: list[Row] = []
    for fact in facts:
        row: list[Value] = []
        for i, arg in zip(pc.given, fact, strict=True):
            want = pc.kept_types(solver, i) if i in mixed else types[i]
            off = Fault(ProblemKind.ASSIGN_TYPE, where, AssignType(
                name, names[i], want, json.dumps(arg)))
            if isinstance(want, tuple):
                if not isinstance(arg, tuple) or len(arg) != len(want):
                    return off
                parts = tuple(zip(arg, want, strict=True))
            else:
                parts = ((arg, want),)
            got: list[Value] = []
            for a, t in parts:
                match arg_value(solver, a, t):
                    case ArgUnknown(text=text):
                        return Fault(ProblemKind.ASSIGN_VALUE_UNKNOWN, where,
                                     Named(text))
                    case ArgOffType():
                        return off
                    case v:
                        got.append(v)
            row.append(RecordValue(tuple(got)) if i in mixed else got[0])
        rows.append(tuple(row))
    return at_every_case(solver, pc, rows)
