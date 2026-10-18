"""The undefined output, and why a run gives no grid
(docs/handbook/principles.md#models-and-tasks)."""

from dataclasses import dataclass, field

from engine.quotes import quotes


@quotes("principles.md", "Models and tasks",
        "A model is defined at an assignment and input when its output is "
        "nonempty and contains only total grids.")
@dataclass(frozen=True)
class NoOutput:
    """`out` holds no cell at the case: the output is empty."""


type Cell = tuple[int, int]
"""A cell of a grid, by row and column."""


@quotes("principles.md", "Models and tasks",
        "A model is defined at an assignment and input when its output is "
        "nonempty and contains only total grids.")
@dataclass(frozen=True)
class MissingCells:
    """`out`'s cells at the case leave cells of their frame without a color:
    the grid is not total."""

    cells: tuple[Cell, ...]
    """The cells without a color, in row order."""


@dataclass(frozen=True)
class ConflictingCells:
    """`out`'s cells at the case give cells two colors, so they describe
    no grid."""

    cells: tuple[Cell, ...]
    """The cells with two colors, in row order."""


@dataclass(frozen=True)
class NegativeEdges:
    """`out`'s cells at the case give a cell a negative distance to an
    edge of its frame, so they describe no grid."""

    edges: tuple[tuple[int, int, int, int], ...]
    """Each such cell's distances to the top, bottom, left and right
    edges, in order."""


@dataclass(frozen=True)
class InconsistentBounds:
    """`out`'s cells at the case give more than one frame size, so they
    describe no grid."""

    bounds: tuple[Cell, ...]
    """The frame sizes, as height and width, in order."""


@dataclass(frozen=True)
class NoDerivedValue:
    """A `@derive` branch of the case derives its parameter, and the
    proposer gives it no value on the input
    (docs/handbook/principles.md#stored-or-derived)."""

    parameter: str
    proposer: str


type UndefinedReason = (NoOutput | MissingCells | ConflictingCells
                        | NegativeEdges | InconsistentBounds | NoDerivedValue)


@quotes("solver-file.md", "Witness file",
        "\"grid\": Grid | Grid[] | null } // null for undefined")
@dataclass(frozen=True)
class Undefined:
    """`null`: the cases are undefined on the input. Two values are equal
    whatever their reasons, as a witness file's `null` states none, and are
    one output (`solver.witness_groups.same_output`)."""

    reason: UndefinedReason | None = field(default=None, compare=False)
    """Why a run gives no grid; None for a witness file's `null`, which
    states no reason."""
