"""Near-miss rules for ARC task 8f2ea7aa.

True rule: crop the bounding box of the non-background cells (a 3x3 shape),
then build a grid of tiles; tile (i, j) holds a copy of the shape where the
shape's cell (i, j) is ink, and background elsewhere.
"""
import json
from collections import Counter
from pathlib import Path


def _bg(inp):
    return Counter(v for row in inp for v in row).most_common(1)[0][0]


def _box(inp, grow=0):
    bg = _bg(inp)
    cells = [(r, c) for r, row in enumerate(inp) for c, v in enumerate(row) if v != bg]
    r0 = min(r for r, _ in cells)
    r1 = max(r for r, _ in cells) + grow
    c0 = min(c for _, c in cells)
    c1 = max(c for _, c in cells) + grow
    r1 = min(r1, len(inp) - 1)
    c1 = min(c1, len(inp[0]) - 1)
    return [row[c0:c1 + 1] for row in inp[r0:r1 + 1]]


def _color(shape, bg):
    return next(v for row in shape for v in row if v != bg)


def _build(outer, inner, bg, color=None):
    """Tile (i, j) holds `inner` where outer[i][j] is not bg, else bg."""
    n, m = len(outer), len(outer[0])
    h, w = len(inner), len(inner[0])
    res = [[bg] * (m * w) for _ in range(n * h)]
    for i in range(n):
        for j in range(m):
            if outer[i][j] != bg:
                for a in range(h):
                    for b in range(w):
                        v = inner[a][b]
                        if color is not None and v != bg:
                            v = color
                        res[i * h + a][j * w + b] = v
    return res


def _transpose(g):
    return [list(r) for r in zip(*g)]


def _flip_h(g):
    return [row[::-1] for row in g]


def _flip_v(g):
    return [row[:] for row in g[::-1]]


def _rot90(g):
    return [list(r) for r in zip(*g[::-1])]


def _invert(g, bg, color):
    return [[color if v == bg else bg for v in row] for row in g]


def tile_all(inp, out):
    s = _box(inp)
    return _build([[1] * len(s[0]) for _ in s], s, _bg(inp))


def outer_inverted(inp, out):
    s = _box(inp)
    bg = _bg(inp)
    return _build(_invert(s, bg, 1), s, bg)


def inner_complement(inp, out):
    s = _box(inp)
    bg = _bg(inp)
    return _build(s, _invert(s, bg, _color(s, bg)), bg)


def inner_transposed(inp, out):
    s = _box(inp)
    return _build(s, _transpose(s), _bg(inp))


def inner_flipped_h(inp, out):
    s = _box(inp)
    return _build(s, _flip_h(s), _bg(inp))


def outer_flipped_v(inp, out):
    s = _box(inp)
    return _build(_flip_v(s), s, _bg(inp))


def outer_rotated(inp, out):
    s = _box(inp)
    return _build(_rot90(s), s, _bg(inp))


def crop_only(inp, out):
    return _box(inp)


def wrong_fill_color(inp, out):
    bg = _bg(inp)
    return [[5 if v != bg else v for v in row] for row in out]


def bbox_grown_by_one(inp, out):
    s = _box(inp, grow=1)
    return _build(s, s, _bg(inp))


def first_tile_row_only(inp, out):
    bg = _bg(inp)
    k = len(out) // 3
    return [row[:] if r < k else [bg] * len(row) for r, row in enumerate(out)]


def whole_input_as_shape(inp, out):
    bg = _bg(inp)
    return _build(inp, inp, bg)


ALTERNATIVES = [
    ("every tile gets the shape, with no gating by the shape's cells", tile_all),
    ("tiles are placed where the shape is background instead of where it is ink", outer_inverted),
    ("each tile holds the complement of the shape", inner_complement),
    ("each tile holds the transposed shape", inner_transposed),
    ("each tile holds the shape mirrored left-right", inner_flipped_h),
    ("tile placement follows the shape flipped top-bottom", outer_flipped_v),
    ("tile placement follows the shape rotated 90 degrees", outer_rotated),
    ("output is only the cropped shape, with no tiling", crop_only),
    ("stamps are drawn in color 5 instead of the shape's color", wrong_fill_color),
    ("bounding box is one cell too large in each direction, so tiles are 4x4", bbox_grown_by_one),
    ("only the first row of tiles is filled", first_tile_row_only),
    ("the whole input grid is used as the shape and the tile pattern", whole_input_as_shape),
]


def _valid(g):
    return (
        isinstance(g, list) and g and all(isinstance(r, list) for r in g)
        and len({len(r) for r in g}) == 1 and len(g[0]) > 0
        and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r)
    )


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/8f2ea7aa.json").read_text())
    pairs = task["train"]
    print("pairs:", len(pairs))
    for desc, fn in ALTERNATIVES:
        ok = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                ok += 1
        print(f"{ok}/{len(pairs)}  {fn.__name__}: {desc}")
