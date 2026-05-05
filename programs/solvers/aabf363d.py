"""Recolor the input's shape with the corner marker's color, then clear the marker cell."""

from dataclasses import dataclass

from programs.lib import *


@dataclass(frozen=True)
class Consts:
    bg: Color
    marker_corner: DiagDir


CONSTS = Consts(bg=C0, marker_corner=DiagDir.BL)


def solve(grid: Grid, c: Consts) -> Grid:
    v_dir, h_dir = c.marker_corner.value
    # (marker_p, marker_color) :- in(P, col), dist(P, v_dir) = 0, dist(P, h_dir) = 0.
    ((marker_p, marker_color),) = {
        (p, col) for (p, col) in grid
        if dist(p, v_dir) == 0 and dist(p, h_dir) == 0
    }
    # out(marker_p, c.bg).
    cleared = {(marker_p, c.bg)}
    # out(p, marker_color) :- in(p, col), col != c.bg, p != marker_p.
    repainted = {(p, marker_color) for (p, col) in grid
                 if col != c.bg and p != marker_p}
    # out(p, c.bg) :- in(p, c.bg).
    bg_cells = {(p, c.bg) for (p, col) in grid if col == c.bg}
    return cleared | repainted | bg_cells
