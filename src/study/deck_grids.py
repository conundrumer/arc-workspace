"""Grids drawn as SVG for a concept-decision deck, and the cells on which
outputs of one size differ, outlined on each."""

from collections.abc import Sequence
from itertools import groupby

from engine import Grid
from study.cards import ARC

type Cell = tuple[int, int]


def size(grid: Grid) -> tuple[int, int]:
    """(rows, columns)."""
    return len(grid), len(grid[0]) if grid else 0


def contested(grids: Sequence[Grid]) -> frozenset[Cell] | None:
    """The cells at which `grids`, all of one size, do not all hold one
    color; None where they are not all of one size."""
    sizes = {size(g) for g in grids}
    if len(sizes) != 1:
        return None
    h, w = next(iter(sizes))
    return frozenset((r, c) for r in range(h) for c in range(w)
                     if len({g[r][c] for g in grids}) > 1)


def svg(grid: Grid, marked: frozenset[Cell] = frozenset()) -> str:
    """`grid` as an SVG of unit cells, one path per color, its lines one
    pixel at any size, with the boundary of `marked` outlined."""
    h, w = size(grid)
    parts = [f'<svg class="g" viewBox="0 0 {w} {h}" '
             f'style="width:calc(var(--cell) * {w})" '
             f'role="img" aria-label="{h} by {w} grid">']
    by_color: dict[int, list[str]] = {}
    for r, row in enumerate(grid):
        c = 0
        for color, run in groupby(row):
            n = len(list(run))
            by_color.setdefault(color, []).append(f"M{c} {r}h{n}v1h-{n}z")
            c += n
    for color, d in by_color.items():
        parts.append(f'<path fill="{ARC[color]}" d="{"".join(d)}"/>')
    lines = [f"M{x} 0v{h}" for x in range(1, w)] \
        + [f"M0 {y}h{w}" for y in range(1, h)]
    if lines:
        parts.append(f'<path class="gl" d="{"".join(lines)}"/>')
    if marked:
        d = _boundary(marked)
        parts.append(f'<path class="dk" d="{d}"/><path class="dw" d="{d}"/>')
    parts.append("</svg>")
    return "".join(parts)


def _boundary(cells: frozenset[Cell]) -> str:
    """The edges between a cell of `cells` and one outside it, or the
    frame."""
    d = []
    for r, c in sorted(cells):
        if (r - 1, c) not in cells:
            d.append(f"M{c} {r}h1")
        if (r + 1, c) not in cells:
            d.append(f"M{c} {r + 1}h1")
        if (r, c - 1) not in cells:
            d.append(f"M{c} {r}v1")
        if (r, c + 1) not in cells:
            d.append(f"M{c + 1} {r}v1")
    return "".join(d)
