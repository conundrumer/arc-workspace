"""The payloads of the relabeling check (`checker.relabeling`): a
relabeling of the stored parameters, and the relabeling no output
observes."""

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from checker.store.witness import D4


@dataclass(frozen=True)
class ColorSwap:
    """A stored color swapped for a free one, in every `Color` column and
    every colored grid cell of every stored parameter."""

    stored: int
    free: int


@dataclass(frozen=True)
class ColorCycle:
    """Each stored color, in ascending order, taken to the next, the last
    to the first."""

    colors: tuple[int, ...]


@dataclass(frozen=True)
class Complement:
    """A stored `GRID_MASK` parameter's cells complemented within its own
    grid."""

    parameter: str


@dataclass(frozen=True)
class D4Image:
    """A D4 element applied to every stored parameter at once."""

    element: "D4"


type Relabeling = ColorSwap | ColorCycle | Complement | D4Image


@dataclass(frozen=True)
class UnobservedPayload:
    """The payload of an `unobserved-relabeling` finding
    (`checker.finding.Kind.UNOBSERVED_RELABELING`): the relabeling, and the
    parameters it changes, in the order the solver declares them."""

    relabeling: Relabeling
    parameters: tuple[str, ...]
