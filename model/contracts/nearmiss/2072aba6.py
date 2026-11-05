import json
from pathlib import Path

TILE = [[1, 2], [2, 1]]


def _render(inp, tile, scale=2, mask=None, bg=0):
    h, w = len(inp), len(inp[0])
    res = [[bg] * (w * scale) for _ in range(h * scale)]
    for r in range(h):
        for c in range(w):
            on = inp[r][c] != 0 if mask is None else mask(inp, r, c)
            if on:
                for i in range(scale):
                    for j in range(scale):
                        res[r * scale + i][c * scale + j] = tile(i, j, r, c)
    return res


def swapped_tile(inp, out):
    return _render(inp, lambda i, j, r, c: 3 - TILE[i][j])


def stripe_tile(inp, out):
    return _render(inp, lambda i, j, r, c: 1 if j == 0 else 2)


def scale_three(inp, out):
    return _render(inp, lambda i, j, r, c: 1 + (i + j) % 2, scale=3)


def inverted_mask(inp, out):
    return _render(inp, lambda i, j, r, c: TILE[i][j], mask=lambda g, r, c: g[r][c] == 0)


def flipped_input(inp, out):
    return _render(inp[::-1], lambda i, j, r, c: TILE[i][j])


def mirrored_input(inp, out):
    return _render([row[::-1] for row in inp], lambda i, j, r, c: TILE[i][j])


def cell_level_checker(inp, out):
    return _render(inp, lambda i, j, r, c: 1 + (r + c) % 2)


def only_color_one(inp, out):
    return [[1 if v == 2 else v for v in row] for row in out]


def background_five(inp, out):
    return [[5 if v == 0 else v for v in row] for row in out]


def fill_everywhere(inp, out):
    return _render(inp, lambda i, j, r, c: TILE[i][j], mask=lambda g, r, c: True)


def shift_right_one(inp, out):
    return [[0] + row[:-1] for row in out]


def one_cell_unfilled(inp, out):
    res = [row[:] for row in out]
    for r in range(0, len(out), 2):
        for c in range(0, len(out[0]), 2):
            if out[r][c] != 0:
                for i in range(2):
                    for j in range(2):
                        res[r + i][c + j] = 0
                return res
    return None


def input_unchanged(inp, out):
    return [row[:] for row in inp]


ALTERNATIVES = [
    ("tile colors swapped: 2 1 / 1 2 instead of 1 2 / 2 1", swapped_tile),
    ("tile is vertical stripes 1 2 / 1 2 instead of a checker", stripe_tile),
    ("scale factor 3 instead of 2, with a 3x3 checker tile", scale_three),
    ("silhouette inverted: tiles drawn on the 0 cells", inverted_mask),
    ("input flipped vertically before expansion", flipped_input),
    ("input mirrored horizontally before expansion", mirrored_input),
    ("checker phase applied per input cell: solid 2x2 blocks of 1 or 2", cell_level_checker),
    ("only color 1 used for the tile", only_color_one),
    ("background painted 5 instead of 0", background_five),
    ("tile drawn in every cell, ignoring the silhouette", fill_everywhere),
    ("output shifted right by one column", shift_right_one),
    ("one silhouette cell left unfilled", one_cell_unfilled),
    ("input returned unchanged", input_unchanged),
][:12]


def _valid(g):
    return (
        isinstance(g, list) and g and all(isinstance(r, list) for r in g)
        and len({len(r) for r in g}) == 1 and len(g[0]) > 0
        and all(type(v) is int and 0 <= v <= 9 for r in g for v in r)
    )


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/2072aba6.json").read_text())
    pairs = task["train"]
    print(len(ALTERNATIVES), "readings,", len(pairs), "pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(n, desc)
