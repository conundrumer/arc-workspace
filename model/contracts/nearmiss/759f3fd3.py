"""Near-miss rules for ARC task 759f3fd3.

True rule: the input has a full row and a full column of 3 (a cross). Square
rings (Chebyshev distance K from the crossing cell) grow out from the crossing.
Rings with even K are 4, rings with odd K are 0. Cross cells stay 3.
"""
import json
from pathlib import Path

CROSS = 3
FILL = 4


def _cross_pos(inp):
    h, w = len(inp), len(inp[0])
    r = next(i for i in range(h) if all(v == CROSS for v in inp[i]))
    c = next(j for j in range(w) if all(inp[i][j] == CROSS for i in range(h)))
    return r, c


def _render(inp, center, dist, filled, color=FILL, keep_cross=True):
    h, w = len(inp), len(inp[0])
    r0, c0 = center
    g = []
    for i in range(h):
        row = []
        for j in range(w):
            if keep_cross and inp[i][j] == CROSS:
                row.append(CROSS)
            else:
                row.append(color if filled(dist(i - r0, j - c0)) else 0)
        g.append(row)
    return g


def _cheb(dr, dc):
    return max(abs(dr), abs(dc))


def odd_rings(inp, out):
    r, c = _cross_pos(inp)
    return _render(inp, (r, c), _cheb, lambda k: k % 2 == 1)


def diamond_rings(inp, out):
    r, c = _cross_pos(inp)
    return _render(inp, (r, c), lambda a, b: abs(a) + abs(b), lambda k: k % 2 == 0)


def grid_center_rings(inp, out):
    h, w = len(inp), len(inp[0])
    return _render(inp, (h // 2, w // 2), _cheb, lambda k: k % 2 == 0)


def double_width_rings(inp, out):
    r, c = _cross_pos(inp)
    return _render(inp, (r, c), _cheb, lambda k: (k // 2) % 2 == 0)


def center_shifted(inp, out):
    r, c = _cross_pos(inp)
    return _render(inp, (r + 1, c + 1), _cheb, lambda k: k % 2 == 0)


def cross_recolored(inp, out):
    r, c = _cross_pos(inp)
    return _render(inp, (r, c), _cheb, lambda k: k % 2 == 0, keep_cross=False)


def horizontal_bands(inp, out):
    r, c = _cross_pos(inp)
    return _render(inp, (r, c), lambda a, b: abs(a), lambda k: k % 2 == 0)


def ring_color_is_cross_color(inp, out):
    r, c = _cross_pos(inp)
    return _render(inp, (r, c), _cheb, lambda k: k % 2 == 0, color=CROSS)


def outer_ring_unfilled(inp, out):
    r, c = _cross_pos(inp)
    h, w = len(inp), len(inp[0])
    ks = [_cheb(i - r, j - c) for i in range(h) for j in range(w)
          if out[i][j] == FILL]
    top = max(ks)
    g = [row[:] for row in out]
    for i in range(h):
        for j in range(w):
            if out[i][j] == FILL and _cheb(i - r, j - c) == top:
                g[i][j] = 0
    return g


def distance_to_nearest_arm(inp, out):
    r, c = _cross_pos(inp)
    return _render(inp, (r, c), lambda a, b: min(abs(a), abs(b)),
                   lambda k: k % 2 == 0)


def center_row_col_swapped(inp, out):
    r, c = _cross_pos(inp)
    h, w = len(inp), len(inp[0])
    return _render(inp, (c, r), _cheb, lambda k: k % 2 == 0)


ALTERNATIVES = [
    ("fill odd-distance rings instead of even-distance rings", odd_rings),
    ("distance is Manhattan, so rings are diamonds", diamond_rings),
    ("rings are centered on the grid center, not the crossing", grid_center_rings),
    ("each ring is two cells wide", double_width_rings),
    ("ring center is one cell down and right of the crossing", center_shifted),
    ("cross cells are recolored by ring parity too", cross_recolored),
    ("only the distance from the crossing's row counts, giving horizontal bands", horizontal_bands),
    ("filled rings use the cross color 3 instead of 4", ring_color_is_cross_color),
    ("the outermost filled ring is left unfilled", outer_ring_unfilled),
    ("distance is to the nearest cross arm, not to the crossing", distance_to_nearest_arm),
    ("crossing row and column are swapped when centering the rings", center_row_col_swapped),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(type(v) is int and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/759f3fd3.json'))
    pairs = task["train"]
    print(len(ALTERNATIVES), "readings,", len(pairs), "train pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
