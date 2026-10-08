"""The program restricted to some bases."""

from collections.abc import Sequence

from engine import Engine, Program
from engine.memo import ByIdentity
from solver.aggregate import Solver, enumerates
from solver.model import Base
from solver.vocabulary import IMPL


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
