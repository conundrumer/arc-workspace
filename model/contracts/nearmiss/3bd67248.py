import json
from pathlib import Path


def _copy(g):
    return [row[:] for row in g]


def _diag_cells(out):
    return [(r, c) for r, row in enumerate(out) for c, v in enumerate(row) if v == 2]


def _floor_cells(out):
    return [(r, c) for r, row in enumerate(out) for c, v in enumerate(row) if v == 4]


def swap_colors(inp, out):
    g = _copy(out)
    for r, c in _diag_cells(out):
        g[r][c] = 4
    for r, c in _floor_cells(out):
        g[r][c] = 2
    return g


def floor_on_top(inp, out):
    return [row[:] for row in out[::-1]]


def transposed(inp, out):
    return [list(col) for col in zip(*out)]


def floor_over_wall(inp, out):
    g = _copy(out)
    g[-1][0] = 4
    return g


def diagonal_main_direction(inp, out):
    g = _copy(out)
    for r, c in _diag_cells(out):
        g[r][c] = inp[r][c]
    n, m = len(out), len(out[0])
    for r in range(1, n - 1):
        if r < m and inp[r][r] == 0:
            g[r][r] = 2
    return g


def diagonal_short(inp, out):
    g = _copy(out)
    cells = _diag_cells(out)
    r0 = min(r for r, c in cells)
    for r, c in cells:
        if r == r0:
            g[r][c] = inp[r][c]
    return g


def diagonal_shifted_left(inp, out):
    g = _copy(out)
    cells = _diag_cells(out)
    for r, c in cells:
        g[r][c] = inp[r][c]
    for r, c in cells:
        if c - 1 >= 1:
            g[r][c - 1] = 2
    return g


def floor_one_short(inp, out):
    g = _copy(out)
    g[-1][-1] = inp[-1][-1]
    return g


def no_diagonal(inp, out):
    g = _copy(out)
    for r, c in _diag_cells(out):
        g[r][c] = inp[r][c]
    return g


def no_floor(inp, out):
    g = _copy(out)
    for r, c in _floor_cells(out):
        g[r][c] = inp[r][c]
    return g


def diagonal_in_wall_color(inp, out):
    wall = inp[0][0]
    g = _copy(out)
    for r, c in _diag_cells(out):
        g[r][c] = wall
    return g


def floor_wall_color(inp, out):
    wall = inp[0][0]
    g = _copy(out)
    for r, c in _floor_cells(out):
        g[r][c] = wall
    return g


ALTERNATIVES = [
    ("floor and diagonal colors swapped (floor 2, diagonal 4)", swap_colors),
    ("floor line on the top edge instead of the bottom, diagonal mirrored to match", floor_on_top),
    ("rule applied transposed: floor line runs down the right edge, wall on top", transposed),
    ("floor line also paints the wall's bottom cell", floor_over_wall),
    ("diagonal runs along the main diagonal direction instead of the anti-diagonal", diagonal_main_direction),
    ("diagonal stops one cell short of the top edge", diagonal_short),
    ("diagonal shifted one column toward the wall, so it misses the floor corner", diagonal_shifted_left),
    ("floor line stops one cell short of the far edge", floor_one_short),
    ("only the floor line is drawn, no diagonal", no_diagonal),
    ("only the diagonal is drawn, no floor line", no_floor),
    ("diagonal drawn in the wall color", diagonal_in_wall_color),
    ("floor line drawn in the wall color", floor_wall_color),
]


def _valid(g):
    return (
        isinstance(g, list)
        and len(g) > 0
        and all(isinstance(r, list) and len(r) == len(g[0]) and len(r) > 0 for r in g)
        and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r)
    )


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/3bd67248.json").read_text())
    pairs = task["train"]
    print(f"pairs: {len(pairs)}")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
