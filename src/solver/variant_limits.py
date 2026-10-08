"""The limits of a variant run."""

from enum import Enum

from arc.task import Task
from engine import Limits


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
