import json
from pathlib import Path

BG = 0
WALL = 5


def _copy(g):
    return [list(r) for r in g]


def _markers(inp):
    return [(r, c, v) for r, row in enumerate(inp) for c, v in enumerate(row)
            if v not in (BG, WALL)]


def one_step(inp, out):
    # Marker falls a single cell, swapping with the cell below.
    g = _copy(inp)
    for r, c, v in _markers(inp):
        if r + 1 < len(g):
            g[r][c], g[r + 1][c] = g[r + 1][c], g[r][c]
    return g


def not_cleared(inp, out):
    # Marker lands at the edge but its original cell keeps the marker.
    g = _copy(out)
    for r, c, v in _markers(inp):
        g[r][c] = v
    return g


def fall_up(inp, out):
    g = _copy(inp)
    for r, c, v in _markers(inp):
        g[r][c] = BG
    for r, c, v in _markers(inp):
        g[0][c] = v
    return g


def fall_right(inp, out):
    g = _copy(inp)
    for r, c, v in _markers(inp):
        g[r][c] = BG
    for r, c, v in _markers(inp):
        g[r][len(g[0]) - 1] = v
    return g


def fall_left(inp, out):
    g = _copy(inp)
    for r, c, v in _markers(inp):
        g[r][c] = BG
    for r, c, v in _markers(inp):
        g[r][0] = v
    return g


def stops_above_wall(inp, out):
    # Marker falls only until it meets the wall color, so it stays in place
    # except that the wall stays intact; the cleared cell is then wrongly filled.
    g = _copy(inp)
    for r, c, v in _markers(inp):
        g[r][c] = WALL
    return g


def lands_in_wall_row_only_cleared(inp, out):
    # Marker is removed but nothing lands.
    g = _copy(inp)
    for r, c, v in _markers(inp):
        g[r][c] = BG
    return g


def cleared_with_wall_color(inp, out):
    # Cleared cell takes the wall color instead of the background.
    g = _copy(out)
    for r, c, v in _markers(inp):
        g[r][c] = WALL
    return g


def column_offset(inp, out):
    # Marker lands one column to the right of its own column.
    g = _copy(inp)
    w = len(g[0])
    for r, c, v in _markers(inp):
        g[r][c] = BG
    for r, c, v in _markers(inp):
        g[-1][(c + 1) % w] = v
    return g


def fill_edge_row(inp, out):
    # Whole fall-edge row takes the marker color.
    g = _copy(out)
    for r, c, v in _markers(inp):
        g[-1] = [v] * len(g[-1])
    return g


def trail(inp, out):
    # Marker leaves a trail of its color down the column.
    g = _copy(out)
    for r, c, v in _markers(inp):
        for rr in range(r, len(g)):
            g[rr][c] = v
    return g


def wall_cell_also_removed(inp, out):
    # Marker lands at the edge and the wall cell it rested on disappears.
    g = _copy(out)
    for r, c, v in _markers(inp):
        if r + 1 < len(g) - 1:
            g[r + 1][c] = BG
    return g


ALTERNATIVES = [
    ("marker falls one cell only, swapping with the cell below", one_step),
    ("marker lands on the edge row but the original marker cell is not cleared", not_cleared),
    ("marker falls up to the top edge instead of down", fall_up),
    ("marker slides right to the right edge instead of falling down", fall_right),
    ("marker slides left to the left edge instead of falling down", fall_left),
    ("marker cell is replaced by the wall color and nothing lands", stops_above_wall),
    ("marker is removed (cleared to background) and nothing lands", lands_in_wall_row_only_cleared),
    ("true output but the cleared marker cell takes the wall color", cleared_with_wall_color),
    ("marker lands one column to the right of its column", column_offset),
    ("whole edge row is filled with the marker color", fill_edge_row),
    ("marker leaves a trail of its color down its column", trail),
    ("wall cell under the marker is removed as well as the marker landing", wall_cell_also_removed),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / 'data/tasks/3618c87e.json').read_text())
    train = task["train"]
    print("pairs:", len(train))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in train:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(f"{n}/{len(train)}  {desc}")
