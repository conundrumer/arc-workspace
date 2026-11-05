import json
from pathlib import Path


def tiled(inp, pred, content=None):
    """3x3 tiling of the input: tile (r,c) holds `content` (default inp) where pred(r,c,v) holds."""
    n = len(inp)
    m = len(inp[0])
    tile = inp if content is None else content
    out = [[0] * (m * m) for _ in range(n * n)]
    for r in range(n):
        for c in range(m):
            if pred(r, c, inp[r][c]):
                for i in range(n):
                    for j in range(m):
                        out[r * n + i][c * m + j] = tile[i][j]
    return out


def any_nonzero(inp, out):
    return tiled(inp, lambda r, c, v: v != 0)


def only_color_1(inp, out):
    return tiled(inp, lambda r, c, v: v == 1)


def background_cells(inp, out):
    return tiled(inp, lambda r, c, v: v == 0)


def mirrored_positions(inp, out):
    m = len(inp[0])
    return tiled(inp, lambda r, c, v: inp[r][m - 1 - c] == 2)


def flipped_vertically_positions(inp, out):
    n = len(inp)
    return tiled(inp, lambda r, c, v: inp[n - 1 - r][c] == 2)


def stamp_only_2_cells(inp, out):
    masked = [[v if v == 2 else 0 for v in row] for row in inp]
    return tiled(inp, lambda r, c, v: v == 2, masked)


def stamp_without_2_cells(inp, out):
    masked = [[v if v != 2 else 0 for v in row] for row in inp]
    return tiled(inp, lambda r, c, v: v == 2, masked)


def stamp_flipped_horizontally(inp, out):
    flipped = [row[::-1] for row in inp]
    return tiled(inp, lambda r, c, v: v == 2, flipped)


def stamp_transposed(inp, out):
    n = len(inp)
    m = len(inp[0])
    t = [[inp[i][j] for i in range(n)] for j in range(m)]
    return tiled(inp, lambda r, c, v: v == 2, t)


def first_marker_only(inp, out):
    n = len(inp)
    m = len(inp[0])
    first = next(((r, c) for r in range(n) for c in range(m) if inp[r][c] == 2), None)
    return tiled(inp, lambda r, c, v: (r, c) == first)


def whole_row_of_tiles(inp, out):
    rows = {r for r, row in enumerate(inp) if 2 in row}
    return tiled(inp, lambda r, c, v: r in rows)


def solid_marker_tiles(inp, out):
    solid = [[2] * len(inp[0]) for _ in inp]
    return tiled(inp, lambda r, c, v: v == 2, solid)


def marker_map_only(inp, out):
    return [[2 if v == 2 else 0 for v in row] for row in inp]


ALTERNATIVES = [
    ("stamp the input at every nonzero cell, not only color 2", any_nonzero),
    ("stamp the input only at color 1 cells", only_color_1),
    ("stamp the input at the 0 cells instead of the 2 cells", background_cells),
    ("tile positions of the 2 cells mirrored left-right", mirrored_positions),
    ("tile positions of the 2 cells mirrored top-bottom", flipped_vertically_positions),
    ("stamp keeps only the 2 cells of the input", stamp_only_2_cells),
    ("stamp keeps everything of the input except the 2 cells", stamp_without_2_cells),
    ("stamp is the input flipped left-right", stamp_flipped_horizontally),
    ("stamp is the input transposed", stamp_transposed),
    ("only the first 2 cell in reading order gets a stamp", first_marker_only),
    ("every tile in a tile row that holds a 2 gets a stamp", whole_row_of_tiles),
    ("stamp tiles are solid 2 instead of the input", solid_marker_tiles),
    ("answer is the 3x3 map of 2 cells, no tiling", marker_map_only),
]


def valid(g):
    return (
        isinstance(g, list)
        and g
        and all(isinstance(r, list) and len(r) == len(g[0]) and r for r in g)
        and all(type(v) is int and 0 <= v <= 9 for r in g for v in r)
    )


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/cce03e0d.json"))
    pairs = task["train"]
    print(len(ALTERNATIVES), "readings,", len(pairs), "pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and valid(g) and g != p["output"]:
                n += 1
        print(n, "/", len(pairs), desc)
