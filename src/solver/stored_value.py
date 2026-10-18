"""The value a `@store` branch stores."""

from dataclasses import dataclass
from itertools import combinations, product

from engine import (
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
from solver.model import StoreBranch
from solver.per_case import case_reading, joined
from solver.vocabulary import INPUT


@quotes("solver-file.md", "Program",
        "**`@store` directive.** The relation, or the instance's relation the "
        "line gives, has one value on every input, and the line is a branch "
        "of a choice point on it")
@dataclass(frozen=True)
class StoredValue:
    """The value a `@store` branch stores: the columns of the relation that
    hold one value on every input, and the rows of that value, each row over
    those columns alone, at each value of the columns that hold the case
    (`case_columns`). The other columns are the value's keys, which the
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


def stored_value(engine: Engine, solver: Solver, program: Program,
                 branch: StoreBranch, limits: Limits
                 ) -> StoredValue | RunFailure:
    """The value a `@store` branch stores (solver-file.md, under "Program"),
    from the relation's rows in `program` on each input of the task's pairs. A
    column that holds the case (`case_columns`) is a key, never a column of
    the value (solver-file.md, under "Program"). The value's columns are every
    other column where the rows are one set on every input. Else they are the
    most such columns, the first in column order among equals, whose rows are
    one set on every input and whose rows on each input are the same at each
    key, a key being the rows' part over the other columns: the relation is
    then its keys, which its clauses give on each input, with the value at
    each. Else every column that holds no case.
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
