"""The variations of a solver's program."""

from dataclasses import dataclass

from engine import (
    Engine,
    GridValue,
    Program,
    RelationName,
    RemovalTarget,
    Rows,
)
from solver.aggregate import Solver
from solver.model import Case, choice_bases
from solver.per_case import fixed_at_every_case
from solver.readers import parameter
from solver.restricted import holding


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
            return fixed_at_every_case(engine, solver, program, p, values)
        case Restrict(cases=cases):
            return holding(engine, program, choice_bases(cases))
        case Remove(target=target):
            return engine.remove(program, target)
