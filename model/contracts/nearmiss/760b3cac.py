"""Near-miss readings for ARC task 760b3cac.

Grid is 2x3 tiles of 3x3 cells. The 8 pattern sits in the top middle tile,
the 4 marker in the bottom middle tile. The marker's corner cell points left
or right, and the horizontally mirrored pattern fills the top tile on that side.
"""
import json
from pathlib import Path

T = 3


def _tile(g, tr, tc):
    return [row[tc * T:(tc + 1) * T] for row in g[tr * T:(tr + 1) * T]]


def _put(g, tr, tc, t):
    g = [r[:] for r in g]
    for i in range(T):
        for j in range(T):
            g[tr * T + i][tc * T + j] = t[i][j]
    return g


def _hflip(t):
    return [r[::-1] for r in t]


def _vflip(t):
    return t[::-1]


def _rot180(t):
    return [r[::-1] for r in t[::-1]]


def _transpose(t):
    return [list(r) for r in zip(*t)]


def _blank():
    return [[0] * T for _ in range(T)]


def _side(inp, out):
    """Tile column (0 or 2) that the true output fills in the top row."""
    for tc in (0, 2):
        if _tile(out, 0, tc) != _tile(inp, 0, tc):
            return tc
    return None


def _base(inp):
    return [r[:] for r in inp]


def wrong_side(inp, out):
    s = _side(inp, out)
    g = _base(inp)
    return _put(g, 0, 2 - s, _hflip(_tile(inp, 0, 1)))


def no_mirror(inp, out):
    s = _side(inp, out)
    return _put(_base(inp), 0, s, _tile(inp, 0, 1))


def vertical_flip(inp, out):
    s = _side(inp, out)
    return _put(_base(inp), 0, s, _vflip(_tile(inp, 0, 1)))


def rotate_180(inp, out):
    s = _side(inp, out)
    return _put(_base(inp), 0, s, _rot180(_tile(inp, 0, 1)))


def transpose(inp, out):
    s = _side(inp, out)
    return _put(_base(inp), 0, s, _transpose(_tile(inp, 0, 1)))


def both_sides(inp, out):
    g = _put(_base(inp), 0, 0, _hflip(_tile(inp, 0, 1)))
    return _put(g, 0, 2, _hflip(_tile(inp, 0, 1)))


def also_marker_row(inp, out):
    s = _side(inp, out)
    g = [r[:] for r in out]
    return _put(g, 1, s, _hflip(_tile(inp, 1, 1)))


def marker_color(inp, out):
    s = _side(inp, out)
    t = [[4 if v else 0 for v in r] for r in _hflip(_tile(inp, 0, 1))]
    return _put(_base(inp), 0, s, t)


def bottom_row_instead(inp, out):
    s = _side(inp, out)
    return _put(_base(inp), 1, s, _hflip(_tile(inp, 0, 1)))


def shifted_one_column(inp, out):
    s = _side(inp, out)
    t = _hflip(_tile(inp, 0, 1))
    g = _base(inp)
    d = -1 if s == 0 else 1
    for i in range(T):
        for j in range(T):
            c = s * T + j + d
            if 0 <= c < len(g[0]):
                g[i][c] = t[i][j]
    return g


def crop_filled_tile(inp, out):
    s = _side(inp, out)
    return _hflip(_tile(inp, 0, 1))


def overwrite_pattern_tile(inp, out):
    """Mirror fills the side, and the original pattern tile is erased."""
    s = _side(inp, out)
    g = [r[:] for r in out]
    return _put(g, 0, 1, _blank())


ALTERNATIVES = [
    ("mirror goes to the tile on the opposite side of the marker's pointing side", wrong_side),
    ("pattern is copied to the pointed side without mirroring", no_mirror),
    ("pattern is flipped top to bottom instead of left to right", vertical_flip),
    ("pattern is rotated 180 degrees instead of mirrored", rotate_180),
    ("pattern is transposed instead of mirrored", transpose),
    ("mirrored pattern fills both side tiles", both_sides),
    ("marker row side tile is also filled with the mirrored marker", also_marker_row),
    ("mirrored shape is drawn in the marker color 4", marker_color),
    ("mirrored pattern is placed in the marker row instead of the pattern row", bottom_row_instead),
    ("mirrored pattern is placed one column off from the tile boundary", shifted_one_column),
    ("output is only the mirrored tile, cropped", crop_filled_tile),
    ("original pattern tile is erased after mirroring", overwrite_pattern_tile),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/760b3cac.json'))
    pairs = task["train"]
    print(len(ALTERNATIVES), "readings,", len(pairs), "pairs")
    for desc, f in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = f(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(n, f.__name__, "-", desc)
