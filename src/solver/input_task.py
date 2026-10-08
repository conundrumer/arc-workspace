"""The task a probe runs on."""

from arc.task import Example, Task
from engine import Grid
from engine.program import grid_lists


def input_task(grid: Grid) -> Task:
    """A task whose one example is `grid`, with no output, for the probe of
    one input."""
    return Task(train=[], test=[Example(input=grid_lists(grid),
                                        output=[])])
