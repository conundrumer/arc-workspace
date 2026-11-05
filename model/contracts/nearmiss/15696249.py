import json
from pathlib import Path


def _line(inp):
    """Return (axis, index, color) of the uniform row/column; axis 'r' or 'c'."""
    n = len(inp)
    for i in range(n):
        if len(set(inp[i])) == 1:
            return "r", i, inp[i][0]
    for j in range(len(inp[0])):
        col = {inp[i][j] for i in range(n)}
        if len(col) == 1:
            return "c", j, inp[0][j]
    return None


def _render(inp, tiles, bg=0, tile_fn=None):
    n = len(inp)
    m = len(inp[0])
    grid = [[bg] * (m * m) for _ in range(n * n)]
    for (ti, tj) in tiles:
        t = tile_fn(inp) if tile_fn else inp
        for i in range(n):
            for j in range(m):
                grid[ti * n + i][tj * m + j] = t[i][j]
    return grid


def _strip(axis, idx, n=3, m=3):
    if axis == "r":
        return [(idx, j) for j in range(m)]
    return [(i, idx) for i in range(n)]


def full_tiling(inp, out):
    return _render(inp, [(i, j) for i in range(3) for j in range(3)])


def transposed_axis(inp, out):
    ax, idx, _ = _line(inp)
    return _render(inp, _strip("c" if ax == "r" else "r", idx))


def single_tile(inp, out):
    ax, idx, _ = _line(inp)
    return _render(inp, [(idx, idx)])


def line_color_bg(inp, out):
    _, _, col = _line(inp)
    return [[col if v == 0 else v for v in row] for row in out]


def index_off_by_one(inp, out):
    ax, idx, _ = _line(inp)
    return _render(inp, _strip(ax, (idx + 1) % 3))


def index_mirrored(inp, out):
    ax, idx, _ = _line(inp)
    return _render(inp, _strip(ax, 2 - idx))


def solid_line_color_tiles(inp, out):
    ax, idx, col = _line(inp)
    solid = [[col] * 3 for _ in range(3)]
    return _render(inp, _strip(ax, idx), tile_fn=lambda g: solid)


def flipped_tiles(inp, out):
    ax, idx, _ = _line(inp)
    return _render(inp, _strip(ax, idx), tile_fn=lambda g: [r[::-1] for r in g])


def transposed_tiles(inp, out):
    ax, idx, _ = _line(inp)
    return _render(
        inp, _strip(ax, idx), tile_fn=lambda g: [list(r) for r in zip(*g)]
    )


def cross_tiles(inp, out):
    ax, idx, _ = _line(inp)
    tiles = set(_strip("r", idx)) | set(_strip("c", idx))
    return _render(inp, sorted(tiles))


def strip_only_crop(inp, out):
    ax, idx, _ = _line(inp)
    if ax == "r":
        return [list(out[3 * idx + i]) for i in range(3)]
    return [[out[i][3 * idx + j] for j in range(3)] for i in range(9)]


def line_only_copied(inp, out):
    # only the uniform line's cells are copied into each strip tile
    ax, idx, _ = _line(inp)
    g = [list(r) for r in out]
    for (ti, tj) in _strip(ax, idx):
        for i in range(3):
            for j in range(3):
                on_line = (i == idx) if ax == "r" else (j == idx)
                if not on_line:
                    g[ti * 3 + i][tj * 3 + j] = 0
    return g


ALTERNATIVES = [
    ("copy the input into all nine tiles (no gating by the uniform line)", full_tiling),
    ("apply the line index to the other tile axis (row line selects a tile column)", transposed_axis),
    ("copy the input only into the one tile at (line index, line index)", single_tile),
    ("fill the background with the uniform line's color instead of 0", line_color_bg),
    ("select the tile row/column one past the uniform line's index", index_off_by_one),
    ("select the tile row/column at the mirrored index (2 - index)", index_mirrored),
    ("fill the selected strip tiles solid with the line color", solid_line_color_tiles),
    ("copy the input horizontally flipped into the selected strip", flipped_tiles),
    ("copy the input transposed into the selected strip", transposed_tiles),
    ("select both the tile row and the tile column of the line index (cross)", cross_tiles),
    ("answer is only the selected strip, not the full 9x9 canvas", strip_only_crop),
    ("copy only the uniform line's cells into the selected strip tiles", line_only_copied),
]


def _valid(g):
    return (
        isinstance(g, list)
        and len(g) > 0
        and all(isinstance(r, list) and len(r) == len(g[0]) and len(r) > 0 for r in g)
        and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r)
    )


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/15696249.json"))
    pairs = task["train"]
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(n, len(pairs), desc)
