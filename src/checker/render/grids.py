"""The rows of a drawn grid, typed apart from the other lines of a
report."""

from engine import Grid


class GridRow(str):
    """A line that draws a row of a grid (`grid_lines`), so that an order
    of a section's lines reads what a line draws from its type."""


def grid_lines(grid: Grid) -> list[str]:
    """A grid drawn: one row per line, cells separated by spaces."""
    if not grid or not grid[0]:
        return ["(empty)"]
    return [GridRow(" ".join(str(c) for c in row)) for row in grid]


def shifted(line: str, by: str) -> str:
    """`line` indented by `by`, a grid's row still a row (`GridRow`)."""
    return GridRow(by + line) if isinstance(line, GridRow) else by + line
