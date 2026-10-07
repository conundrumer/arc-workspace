"""The parts a run builds a program from: the limits of a variant run, the
program restricted to some bases, the value a `@store` branch stores, the
per-case reading of a relation or a parameter, the task a probe runs on,
and the order on values."""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from enum import Enum
from itertools import combinations, product
from typing import overload

from arc.task import Example, Task
from engine import (
    AdtValue,
    Engine,
    Grid,
    GridInput,
    Limits,
    Program,
    RecordValue,
    RelationName,
    Row,
    Rows,
    RunFailure,
    Tuples,
    Value,
)
from engine.engine import (
    resolved,
)
from engine.memo import ByIdentity
from engine.program import (
    RelationDecl,
    as_grid,
    grid_lists,
)
from engine.quotes import quotes
from solver.aggregate import (
    TOP,
    Solver,
    enumerates,
)
from solver.case_columns import case_columns, case_values, holds_at
from solver.case_types import case_types
from solver.columns import (
    ColumnTypes,
    column_reading,
    parameter_case_columns,
    parameter_columns,
)
from solver.model import (
    Base,
    Choice,
    StoreBranch,
    every_base,
)
from solver.readers import (
    based_choice,
    parameter,
)
from solver.vocabulary import (
    IMPL,
    INPUT,
)


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


VARIANT_CPU_FACTOR = 10
"""How many times the CPU seconds of the solver's own run a variant's run
of the same inputs may spend (`variant_limits`)."""
VARIANT_CPU_FLOOR_SECONDS = 2.0
"""The least CPU limit of a variant's run (`variant_limits`)."""


class VariantBound(Enum):
    """The rule that sets a variant's CPU limit (`variant_limits`)."""

    MULTIPLE = "multiple"
    """`VARIANT_CPU_FACTOR` times the CPU seconds of the solver's own run."""
    FLOOR = "floor"
    """`VARIANT_CPU_FLOOR_SECONDS`."""


def variant_bound(measured: float) -> VariantBound:
    """The rule that sets the CPU limit of a variant's run, where the
    solver's own run of the same inputs spent `measured` CPU seconds: the
    multiple, where it is over the floor."""
    return VariantBound.MULTIPLE \
        if VARIANT_CPU_FACTOR * measured > VARIANT_CPU_FLOOR_SECONDS \
        else VariantBound.FLOOR


def variant_limits(limits: Limits, measured: float) -> Limits:
    """The limits of a variant's run, where the solver's own run of the
    same inputs spent `measured` CPU seconds: the CPU limit
    `variant_bound` gives, and the wall limit of `limits`."""
    match variant_bound(measured):
        case VariantBound.MULTIPLE:
            cpu = VARIANT_CPU_FACTOR * measured
        case VariantBound.FLOOR:
            cpu = VARIANT_CPU_FLOOR_SECONDS
    return Limits(cpu_seconds=cpu, wall_seconds=limits.wall_seconds)


def restricted(engine: Engine, solver: Solver, bases: tuple[Base, ...]
               ) -> Program:
    """The solver's program with `impl_choice` holding `bases`, where the
    program enumerates its cases; as it stands where `bases` is empty."""
    program = solver.program
    if not bases or not enumerates(program):
        return program
    return _RESTRICTED.keyed(program, (engine, bases),
                             lambda: holding(engine, program, bases))


def holding(engine: Engine, program: Program, bases: Sequence[Base]
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
                out[joined(self.arity, (self.case, key),
                           (self.columns, row))] = None
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
                out[joined(self.arity, (keys, key),
                           (self.columns, row))] = None
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
    each. Else every column that carries no case.
    The value's rows are the relation's rows over its columns on the first
    train input. The relation's arity is the one its declaration gives, a
    relation empty on every input included.
    `outcomes` passes the program with `impl_choice` holding the bases of
    the cases that take the branch, at the stored assignment."""
    from solver.pair_runs import examples

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
    reading = case_reading(solver, branch.relation, program)
    arity = len(reading.types)
    case = reading.case

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
    columns' types are `solver.columns.column_types`. Raises `ValueError`
    where it resolves to no declaration."""
    return program.declared_relation(
        resolved(engine.index(program), relation, TOP).declaration)


@quotes("solver-file.md", "Params",
        "**Case column.** Where the cases that read a relation in Params "
        "store different values of it, the relation takes a case column in "
        "the form of `out`'s, and each fact's case column is the `Choice` "
        "value of the case that stores the fact.")
@dataclass(frozen=True)
class PerCase:
    """A relation's case reading: its column types as the model resolves
    them and as written (`column_reading`), its case columns (`case_columns`;
    a parameter's, `solver.columns.parameter_case_columns`), and each case
    column of a record type with fields outside the case, with the places
    of those fields (`CaseTypes.kept`). A fact holds at each base that
    holds its case values (`solver.case_columns.holds_at`), and the relation's
    value at a base is the facts that hold there, each without its case
    part (`value`). Every reading of a parameter's value, the runs, the
    sweep, the determination, `derive`, `store` and the lint, reads each
    case at its own rows."""

    relation: RelationName
    types: tuple[str, ...]
    as_written: tuple[str, ...]
    case: tuple[int, ...]
    kept: tuple[tuple[int, tuple[int, ...]], ...] = ()

    @property
    def mixed(self) -> dict[int, tuple[int, ...]]:
        """`kept` by column: each case column of a record type with fields
        outside the case, with the places of those fields."""
        return dict(self.kept)

    def field_types(self, solver: Solver, column: int) -> tuple[str, ...]:
        """The types of the fields of the case column `column`, of a record
        type (`solver.case_types.CaseTypes.records`), in order."""
        return tuple(case_types(solver).records[self.types[column]])

    def kept_types(self, solver: Solver, column: int) -> tuple[str, ...]:
        """The types of the fields outside the case of the case column
        `column` (`mixed`), in order."""
        fields = self.field_types(solver, column)
        return tuple(fields[f] for f in self.mixed[column])

    @property
    def given(self) -> tuple[int, ...]:
        """The columns outside the case part: each column that is not a
        case column, and each case column with fields outside the case."""
        mixed = self.mixed
        return tuple(i for i in range(len(self.types))
                     if i not in self.case or i in mixed)

    @property
    def value_types(self) -> tuple[str, ...]:
        """The types of the columns outside the case part (`given`), a
        case column with fields outside the case at its record type."""
        return self.outside(self.types)

    @property
    def columns(self) -> ColumnTypes:
        """The column types, resolved and as written."""
        return ColumnTypes(self.as_written, self.types)

    @property
    def value_columns(self) -> ColumnTypes:
        """The column types of `value_types`, resolved and as written."""
        return ColumnTypes(self.outside(self.as_written), self.value_types)

    def outside[T](self, row: Sequence[T]) -> tuple[T, ...]:
        """The parts of `row`, a fact or its column types, at the columns
        outside the case part (`given`)."""
        return tuple(row[i] for i in self.given)

    def value(self, row: Row) -> Row:
        """A fact without its case part: each column outside it
        (`given`), a case column of a record type as the record of its
        fields outside the case, in order. Raises `ValueError` where such a
        column holds no record, which no value of its type is."""
        mixed = self.mixed
        out: list[Value] = []
        for i in self.given:
            v = row[i]
            if i in mixed:
                if not isinstance(v, RecordValue):
                    raise ValueError(f"`{v}` is no record of `{self.types[i]}`")
                v = RecordValue(tuple(v.fields[f] for f in mixed[i]))
            out.append(v)
        return tuple(out)

    def values(self, rows: Iterable[Row]) -> tuple[Row, ...]:
        """Each of `rows` without its case part (`value`), once, in
        order."""
        return tuple(dict.fromkeys(self.value(r) for r in rows))

    def key(self, row: Row) -> Row:
        """A fact's values at the case columns."""
        return tuple(row[i] for i in self.case)

    def holds(self, solver: Solver, base: Base | None, row: Row) -> bool:
        """Whether `base` holds the fact's case values
        (`solver.case_columns.holds_at`)."""
        return holds_at(solver, base, self.types, self.case, self.key(row))

    def written(self, solver: Solver, choice: Choice, base: Base,
                value: Row) -> list[Row]:
        """The facts that give `value`, a fact without its case part
        (`value`), at `base`: each case column and each case field holds
        what the base holds at its type (`solver.case_columns.case_values`).
        Raises `ValueError` where a case column with fields outside the
        case holds no record of those fields, which `value` never
        gives."""
        mixed = self.mixed
        at = dict(zip(self.given, value, strict=True))
        cols: list[list[Value]] = []
        for i, t in enumerate(self.types):
            if i not in self.case:
                cols.append([at[i]])
                continue
            if i not in mixed:
                cols.append(case_values(solver, choice, base, t))
                continue
            given = at[i]
            if not isinstance(given, RecordValue) \
                    or len(given.fields) != len(mixed[i]):
                raise ValueError(f"`{given}` is no record of the fields of "
                                 f"`{t}` outside the case")
            by = dict(zip(mixed[i], given.fields, strict=True))
            parts = [[by[f]] if f in by
                     else case_values(solver, choice, base, ft)
                     for f, ft in enumerate(self.field_types(solver, i))]
            cols.append([RecordValue(tuple(c)) for c in product(*parts)])
        return [tuple(r) for r in product(*cols)]


def joined(arity: int, *parts: tuple[Sequence[int], Row]) -> Row:
    """The row of `arity` columns that each part's values fill at the
    part's columns."""
    at: dict[int, Value] = {}
    for cols, values in parts:
        at |= dict(zip(cols, values, strict=True))
    return tuple(at[i] for i in range(arity))


def case_reading(solver: Solver, relation: RelationName,
                 program: Program | None = None) -> PerCase:
    """The case reading of `relation` in `program`, the solver's program
    where it is None: its column types (`column_reading`) and its case
    columns (`case_columns`)."""
    columns = column_reading(
        solver.engine, solver.program if program is None else program,
        relation)
    types = columns.types
    case = case_columns(solver, types)
    reading = case_types(solver)
    return PerCase(relation, types, columns.written, case, tuple(
        (i, k) for i in case if (k := reading.kept(types[i])) is not None))


def parameter_reading(solver: Solver, name: str) -> PerCase:
    """The case reading of the parameter `name`: its column types
    (`column_reading`) and its case columns, its columns of type `Choice`
    (`solver.columns.parameter_case_columns`)."""
    columns = parameter_columns(solver, name)
    return PerCase(parameter(solver, name), columns.types, columns.written,
                   parameter_case_columns(columns.types))


def per_case(solver: Solver, name: str) -> PerCase | None:
    """The parameter `name` as it stores a value per case; None where it
    has no case column."""
    pc = parameter_reading(solver, name)
    return pc if pc.case else None


def held_at(solver: Solver, pc: PerCase, rows: Sequence[Row],
            bases: Iterable[Base]) -> tuple[Row, ...]:
    """Each of `rows` that holds at one of `bases` (`PerCase.holds`), in
    order."""
    at = tuple(bases)
    return tuple(r for r in rows if any(pc.holds(solver, b, r) for b in at))


def rows_at(solver: Solver, pc: PerCase, rows: Sequence[Row], base: Base
            ) -> tuple[Row, ...]:
    """The parameter's value at `base`: each of `rows` that holds there
    (`held_at`), without its case columns (`PerCase.values`)."""
    return pc.values(held_at(solver, pc, rows, (base,)))


@overload
def by_base(solver: Solver, pc: PerCase, rows: Sequence[Row],
            bases: Sequence[Base]
            ) -> list[tuple[Base | None, tuple[Row, ...]]]: ...


@overload
def by_base(solver: Solver, pc: PerCase, rows: Sequence[Row],
            bases: Sequence[Base] | RunFailure
            ) -> list[tuple[Base | None, tuple[Row, ...]]] | RunFailure: ...


def by_base(solver: Solver, pc: PerCase, rows: Sequence[Row],
            bases: Sequence[Base] | RunFailure
            ) -> list[tuple[Base | None, tuple[Row, ...]]] | RunFailure:
    """A parameter's facts `rows` as its cases read them: where it has no
    case column, every fact, under None; else each of `bases` in order,
    whose base case (`solver.model.base_case`) reads its values, with the
    facts that hold there (`held_at`), or the failure of the run that
    enumerates the bases where it fails."""
    if not pc.case:
        return [(None, tuple(rows))]
    got = at_bases(solver, pc, rows, bases)
    return got if not isinstance(got, list) else [(b, at) for b, at in got]


def at_bases(solver: Solver, pc: PerCase, rows: Sequence[Row],
             bases: Sequence[Base] | RunFailure
             ) -> list[tuple[Base, tuple[Row, ...]]] | RunFailure:
    """The facts `rows` of a parameter that stores a value per case
    (`per_case`) at each of `bases` in order, with the facts that hold
    there (`held_at`), or the failure of the run that enumerates the bases
    where it fails."""
    if not isinstance(bases, Sequence):
        return bases
    return [(b, held_at(solver, pc, rows, (b,))) for b in bases]


def written_at(solver: Solver, choice: Choice, pc: PerCase,
               values: Sequence[Row], bases: Sequence[Base]
               ) -> tuple[Row, ...]:
    """The facts that give each of `values`, a fact without its case part
    (`PerCase.value`), at each of `bases` of `choice` (`PerCase.written`),
    so that a base that reaches no point of a column's type holds no fact
    and gets no row."""
    out: dict[Row, None] = {}
    for base in bases:
        for v in values:
            out |= dict.fromkeys(pc.written(solver, choice, base, v))
    return tuple(out)


def at_every_case(solver: Solver, pc: PerCase, values: Sequence[Row]
                  ) -> tuple[Row, ...]:
    """The facts that give `values`, facts without their case part
    (`PerCase.value`), at every base of the `Choice` (`written_at`), for a
    relation with a case column; `values` as they stand for any other,
    and where the `Choice` has no bases to enumerate, which `load` reports
    (`UndecidedForm.CHOICE_NOT_ENUMERABLE`)."""
    choice = solver.choice
    if not pc.case or choice is None:
        return tuple(values)
    bases = every_base(choice)
    return tuple(values) if bases is None \
        else written_at(solver, choice, pc, values, bases)


def fixed_at_every_case(engine: Engine, solver: Solver, program: Program,
                        name: str, values: Sequence[Row]) -> Program:
    """`program` with the parameter `name` holding `values`, rows without
    its case columns, at every case (`at_every_case`)."""
    return engine.fix_relation(
        program, parameter(solver, name),
        at_every_case(solver, parameter_reading(solver, name), values))


def with_rows_at(solver: Solver, pc: PerCase, rows: Sequence[Row],
                 base: Base, values: Sequence[Row]) -> tuple[Row, ...]:
    """`rows` with the parameter's value at `base` replaced by `values`
    (`rows_at`, `written_at`): the rows that hold at another base stay.
    Raises `ValueError` for a solver with no `Choice`, which has no
    base."""
    here = written_at(solver, based_choice(solver), pc, values, (base,))
    kept = [r for r in rows if not pc.holds(solver, base, r)]
    return tuple(dict.fromkeys((*kept, *here)))


def value_key(value: Value) -> tuple[object, ...]:
    """An order on values built from their parts: numbers, then symbols,
    then records by their fields, then ADT values by constructor and
    arguments. An ordering of values that reaches output is by a key built
    from their parts, never by `repr`."""
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
