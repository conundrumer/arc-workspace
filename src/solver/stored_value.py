"""The value a `@store` branch stores."""

from collections.abc import Sequence
from dataclasses import dataclass
from itertools import combinations, product
from typing import TYPE_CHECKING

from engine import (
    CompileError,
    Engine,
    GridInput,
    Limits,
    Program,
    RelationName,
    Row,
    Rows,
    RunFailure,
    Tuples,
)
from engine.engine import resolved
from engine.program import RelationDecl, as_grid
from engine.quotes import quotes
from solver.aggregate import TOP, Solver
from solver.case_columns import holds_at
from solver.model import Base, StoreBranch
from solver.per_case import PerCase, case_reading, joined
from solver.vocabulary import INPUT

if TYPE_CHECKING:
    from solver.pair_runs import PairId


@quotes("solver-file.md", "Program",
        "**`@store` directive.** The relation, or the instance's relation the "
        "line gives, has one value on every input.")
@quotes("solver-file.md", "Cases",
        "A `@derive` or `@store` line is a branch of a choice point on "
        "its parameter or relation")
@dataclass(frozen=True)
class StoredValue:
    """The value a `@store` branch stores: the columns of the relation that
    hold one value on every input at the case values the group holds, and the
    rows of that value, each row over those columns alone, at each value of
    the columns that hold the case (`case_columns`). The other columns are the value's keys, which the
    relation's clauses give on each input."""

    arity: int
    columns: tuple[int, ...]
    case: tuple[int, ...]
    rows: tuple[tuple[Row, Rows], ...]
    """At each value of the case columns, the value's rows."""

    @property
    def keyed_by_case(self) -> bool:
        """Whether every column outside the value holds the case, so
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


@dataclass(frozen=True)
class NoStoredValue:
    """That a `@store` relation has no value to store at the case values
    its cases hold: no choice of its columns gives one value on every input.
    `pair` is the first input whose rows at those case values differ from
    the first input's."""

    relation: RelationName
    pair: "PairId"


@dataclass(frozen=True)
class NoValueError(CompileError):
    """The failure of the runs of the cases that take a `@store` branch
    whose relation has no value to store (`NoStoredValue`), placed at the
    branch's line."""

    relation: RelationName
    pair: "PairId"


def no_value_error(branch: StoreBranch, no: NoStoredValue) -> NoValueError:
    """`no` as the failure of the runs of the cases that take `branch`."""
    return NoValueError(
        None if branch.line is None else branch.line.line,
        f"`{no.relation.text}` is not one value on every input at the case "
        f"values the cases that take its `@store` branch hold; it differs "
        f"on {no.pair.text}", no.relation, no.pair)


def held_rows(solver: Solver, reading: PerCase, rows: Rows,
              bases: Sequence[Base | None]) -> Rows:
    """The rows of a relation on one input at the case values some base of
    `bases` holds (`solver.case_columns.holds_at`, at the case columns
    `reading` gives), all its rows where the relation has no case column or
    `bases` is empty."""
    if not reading.case or not bases:
        return rows
    held: dict[Row, bool] = {}

    def holds(values: Row) -> bool:
        if values not in held:
            held[values] = any(
                holds_at(solver, b, reading.types, reading.case, values)
                for b in bases)
        return held[values]

    return tuple(r for r in rows if holds(tuple(r[i] for i in reading.case)))


def value_columns(per_input: Sequence[Rows], arity: int,
                  case: tuple[int, ...]) -> tuple[int, ...] | None:
    """The columns of the value of a relation whose rows on each input are
    `per_input` (`stored_value`), or None where no choice of columns gives
    one value on every input."""

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
    if one_value(every):
        return every
    constant = [i for i in every if one_value((i,))]
    subsets = [c for n in range(len(constant), 0, -1)
               for c in combinations(constant, n)
               if one_value(c) and product(c)]
    return subsets[0] if subsets else None


def differs_on(solver: Solver, relation: RelationName,
               per_input: Sequence[Rows], pairs: "Sequence[PairId]",
               bases: Sequence[Base | None],
               program: Program | None = None) -> "PairId | None":
    """The first input of `pairs` on which a relation, whose rows on each
    input are `per_input`, differs from its rows on the first input, at the
    case values some base of `bases` holds, where no choice of its columns
    gives it one value on every input there (`value_columns`); None where
    some choice does."""
    reading = case_reading(solver, relation, program)
    held = [held_rows(solver, reading, rows, bases) for rows in per_input]
    if value_columns(held, len(reading.types), reading.case) is not None:
        return None
    return _first_differing(pairs, held)


def _first_differing(pairs: "Sequence[PairId]", held: Sequence[Rows]
                     ) -> "PairId":
    """The first of `pairs` whose rows in `held` are not the first's."""
    return next(p for p, h in zip(pairs, held, strict=True)
                if set(h) != set(held[0]))


def stored_value(engine: Engine, solver: Solver, program: Program,
                 branch: StoreBranch, bases: Sequence[Base | None],
                 limits: Limits) -> StoredValue | NoStoredValue | RunFailure:
    """The value a `@store` branch stores
    (docs/handbook/solver-file.md#program), from the relation's rows in
    `program` on each input of the task's pairs, at the case values some
    base of `bases`, the bases of the cases that take the branch, holds
    (`held_rows`); rows at any other case value are no part of the value. A
    column that holds the case (`case_columns`) is a key, never a column of
    the value (docs/handbook/solver-file.md#program). The value's columns
    are every other column where the held rows are one set on every input.
    Else they are the most such columns, the first in column order among
    equals, whose held rows are one set on every input and whose held rows on
    each input are the same at each key, a key being the rows' part over the
    other columns: the relation is then its keys, which its clauses give on
    each input, with the value at each. Else there is no value: the result is
    `NoStoredValue`, with the first input whose held rows differ from the
    first input's. The value's rows are the held rows over its columns on the
    first train input. The relation's arity is the one its declaration gives,
    a relation empty on every input included.
    `outcomes` passes the program with `impl_choice` holding the bases of
    the cases that take the branch, at the stored assignment."""
    from solver.pair_runs import examples

    if solver.task is None or not solver.task.train:
        raise ValueError(f"{solver.stem}: no train input to store "
                         f"`{branch.relation.text}` from")
    reading = case_reading(solver, branch.relation, program)
    arity = len(reading.types)
    case = reading.case
    per_input: list[Rows] = []
    pairs: list["PairId"] = []
    for pair, ex in examples(solver.task):
        got = engine.run(program, {INPUT: GridInput(as_grid(ex.input))},
                         [branch.relation], limits)
        if not isinstance(got, Tuples):
            return got
        per_input.append(held_rows(solver, reading,
                                   got.relations[branch.relation], bases))
        pairs.append(pair)
    cols = value_columns(per_input, arity, case)
    if cols is None:
        return NoStoredValue(branch.relation,
                             _first_differing(pairs, per_input))
    rows: dict[Row, dict[Row, None]] = {}
    for r in per_input[0]:
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
