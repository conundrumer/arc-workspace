"""Near-miss rules for 363442ee.

The input holds a 3x3 key at the left, a divider column of 5, and a canvas
of 3x3 tiles. Each 1 in the canvas sits at a tile center; the output stamps
the key onto that tile.
"""
import json
from pathlib import Path


def _key(inp):
    return [row[0:3] for row in inp[0:3]]


def _marks(inp):
    return [(r, c) for r, row in enumerate(inp) for c, v in enumerate(row)
            if v == 1 and c >= 4]


def _blank(inp):
    g = [row[:] for row in inp]
    for r, c in _marks(inp):
        g[r][c] = 0
    return g


def _stamp(g, key, top, left):
    for i in range(3):
        for j in range(3):
            r, c = top + i, left + j
            if 0 <= r < len(g) and 0 <= c < len(g[0]):
                g[r][c] = key[i][j]


def _paint(inp, key=None, dr=-1, dc=-1, marks=None):
    key = key if key is not None else _key(inp)
    g = _blank(inp)
    for r, c in (marks if marks is not None else _marks(inp)):
        _stamp(g, key, r + dr, c + dc)
    return g


def only_first_mark(inp, out):
    ms = sorted(_marks(inp))
    return _paint(inp, marks=ms[:1])


def only_last_mark(inp, out):
    ms = sorted(_marks(inp))
    return _paint(inp, marks=ms[-1:])


def key_top_left_at_mark(inp, out):
    return _paint(inp, dr=0, dc=0)


def key_mirrored(inp, out):
    return _paint(inp, key=[row[::-1] for row in _key(inp)])


def key_flipped_vertically(inp, out):
    return _paint(inp, key=_key(inp)[::-1])


def key_rotated(inp, out):
    k = _key(inp)
    return _paint(inp, key=[[k[2 - j][i] for j in range(3)] for i in range(3)])


def marks_left_in_place(inp, out):
    g = _paint(inp)
    for r, c in _marks(inp):
        g[r][c] = 1
    return g


def every_tile_filled(inp, out):
    g = _blank(inp)
    k = _key(inp)
    for top in range(0, len(g), 3):
        for left in range(4, len(g[0]), 3):
            _stamp(g, k, top, left)
    return g


def marks_to_center_color_only(inp, out):
    k = _key(inp)
    g = _blank(inp)
    for r, c in _marks(inp):
        g[r][c] = k[1][1]
    return g


def stamp_in_transposed_tile(inp, out):
    g = _blank(inp)
    k = _key(inp)
    for r, c in _marks(inp):
        tr, tc = r // 3, (c - 4) // 3
        _stamp(g, k, tc * 3, 4 + tr * 3)
    return g


def stamp_one_row_down(inp, out):
    return _paint(inp, dr=0, dc=-1)


def stamp_with_ones_color(inp, out):
    g = _blank(inp)
    for r, c in _marks(inp):
        _stamp(g, [[1] * 3 for _ in range(3)], r - 1, c - 1)
    return g


ALTERNATIVES = [
    ("stamp the key only at the first mark in reading order", only_first_mark),
    ("stamp the key only at the last mark in reading order", only_last_mark),
    ("key placed with its top-left corner on the mark instead of its center", key_top_left_at_mark),
    ("key stamped mirrored left to right", key_mirrored),
    ("key stamped flipped top to bottom", key_flipped_vertically),
    ("key stamped rotated a quarter turn", key_rotated),
    ("marks stay as 1 at the stamp centers", marks_left_in_place),
    ("every tile of the canvas receives the key, marks ignored", every_tile_filled),
    ("stamp drawn in color 1 instead of the key colors", stamp_with_ones_color),
    ("each mark only takes the key's center color, no stamp", marks_to_center_color_only),
    ("stamp tile row and column swapped (transposed tile position)", stamp_in_transposed_tile),
    ("key stamped one row below the mark's tile", stamp_one_row_down),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / 'data/tasks/363442ee.json').read_text())
    pairs = task["train"]
    print("pairs", len(pairs), "readings", len(ALTERNATIVES))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(n, desc)
