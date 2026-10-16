"""What a case gives on an input: the assignment it runs at, its grids, and
its outcome, which is those grids, undefined, or the failure of its run."""

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Annotated

from engine import Grid, RelationValue, RunFailure, Value
from engine.quotes import quotes
from solver.problems import Fault
from solver.undefined import Undefined
from solver.witness import GroupGrid, Resolution, Resolutions

if TYPE_CHECKING:
    from typing_extensions import TypeIs


@dataclass(frozen=True)
class Assignment:
    """A value for each parameter or stored relation it names; the others
    keep their stored values."""

    values: tuple[tuple[str, RelationValue], ...]


@quotes("solver-file.md", "Cases",
        "A case's model reads from `out` at that case one grid per "
        "combination of a value the case reads in each `out` column of a "
        "type whose lines give the values a case reads in it, its output "
        "is the distinct grids it reads")
@quotes("solver-file.md", "Alt outputs",
        "The solver enumerates a tiebreak's resolutions through a trailing "
        "`out` column of type `TiebreakResolution`.")
@dataclass(frozen=True)
class Grids:
    """The distinct grids a case gives (`solver.out_grids.case_grids`),
    and the resolution value each first stands at where `out` has
    resolution columns and the case has one combination of open values
    and rules (`solver.out_grids.open_union`), the grid's identity."""

    grids: tuple[Grid, ...]
    resolutions: tuple[Resolution, ...] = field(default=(), compare=False)


type Outcome = Annotated[Grids | Undefined | RunFailure,
    quotes("principles.md", "Models and tasks",
           "A model is defined at an assignment and input when its output is "
           "nonempty and contains only total grids."),
    quotes("solver-file.md", "Cases",
           "and it is undefined on an input where some combination reads no "
           "grid, or facts that describe no total grid.")]
"""What a case gives on an input: its grids, undefined, or the failure of
its run."""


def is_result(outcome: Outcome | Fault) -> "TypeIs[Grids | Undefined]":
    """Whether a run gave a result: grids, or undefined; not a run's
    failure, nor the fault that stopped the run."""
    return isinstance(outcome, Grids | Undefined)


def first_failure(outcomes: Iterable[Outcome]) -> RunFailure | None:
    """The first of `outcomes` that is no result (`is_result`), or None
    where each is one."""
    return next((o for o in outcomes if not is_result(o)), None)


def group_grid(outcome: Grids | Undefined) -> GroupGrid:
    """An outcome as a witness file's group holds it: one grid as a grid,
    more than one as its distinct grids, each with its resolution value
    (history 1119), undefined as
    it is."""
    if isinstance(outcome, Undefined):
        return outcome
    if len(outcome.grids) == 1:
        return outcome.grids[0]
    return Resolutions(outcome.grids, outcome.resolutions)
