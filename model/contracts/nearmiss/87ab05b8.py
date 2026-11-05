"""Near-miss readings for ARC task 87ab05b8.

Rule: the grid is background 6 with scattered marker cells. The output is all
background, except the quadrant (half-size block) that contains the cell of
colour 2, which is filled with 2.
"""
import json
from pathlib import Path

FILL = 2


def _bg(g):
    counts = {}
    for r in g:
        for v in r:
            counts[v] = counts.get(v, 0) + 1
    return max(counts, key=counts.get)


def _find(g, color):
    for i, r in enumerate(g):
        for j, v in enumerate(r):
            if v == color:
                return i, j
    return None


def _blank(g, bg):
    return [[bg] * len(g[0]) for _ in g]


def _quad(g, qi, qj, color, bg, size=None, base=None):
    h, w = len(g), len(g[0])
    sh, sw = h // 2, w // 2
    res = [r[:] for r in base] if base else _blank(g, bg)
    for i in range(qi * sh, qi * sh + (size or sh)):
        for j in range(qj * sw, qj * sw + (size or sw)):
            if 0 <= i < h and 0 <= j < w:
                res[i][j] = color
    return res


def _true_quad(inp):
    h, w = len(inp), len(inp[0])
    p = _find(inp, FILL)
    return p[0] // (h // 2), p[1] // (w // 2)


def wrong_fill_color(inp, out):
    bg = _bg(inp)
    qi, qj = _true_quad(inp)
    other = next(v for r in inp for v in r if v not in (bg, FILL))
    return _quad(inp, qi, qj, other, bg)


def opposite_quadrant(inp, out):
    bg = _bg(inp)
    qi, qj = _true_quad(inp)
    return _quad(inp, 1 - qi, 1 - qj, FILL, bg)


def horizontal_mirror_quadrant(inp, out):
    bg = _bg(inp)
    qi, qj = _true_quad(inp)
    return _quad(inp, qi, 1 - qj, FILL, bg)


def vertical_mirror_quadrant(inp, out):
    bg = _bg(inp)
    qi, qj = _true_quad(inp)
    return _quad(inp, 1 - qi, qj, FILL, bg)


def block_anchored_at_marker(inp, out):
    bg = _bg(inp)
    h, w = len(inp), len(inp[0])
    i, j = _find(inp, FILL)
    res = _blank(inp, bg)
    for di in range(h // 2):
        for dj in range(w // 2):
            if i + di < h and j + dj < w:
                res[i + di][j + dj] = FILL
    return res


def first_marker_in_reading_order(inp, out):
    bg = _bg(inp)
    h, w = len(inp), len(inp[0])
    i, j = next((i, j) for i, r in enumerate(inp) for j, v in enumerate(r)
                if v not in (bg, FILL))
    return _quad(inp, i // (h // 2), j // (w // 2), FILL, bg)


def row_band(inp, out):
    bg = _bg(inp)
    h, w = len(inp), len(inp[0])
    qi, _ = _true_quad(inp)
    res = _blank(inp, bg)
    for i in range(qi * (h // 2), (qi + 1) * (h // 2)):
        res[i] = [FILL] * w
    return res


def column_band(inp, out):
    bg = _bg(inp)
    h, w = len(inp), len(inp[0])
    _, qj = _true_quad(inp)
    res = _blank(inp, bg)
    for i in range(h):
        for j in range(qj * (w // 2), (qj + 1) * (w // 2)):
            res[i][j] = FILL
    return res


def cropped_block_only(inp, out):
    h, w = len(inp), len(inp[0])
    return [[FILL] * (w // 2) for _ in range(h // 2)]


def markers_left_in_place(inp, out):
    bg = _bg(inp)
    qi, qj = _true_quad(inp)
    return _quad(inp, qi, qj, FILL, bg, base=inp)


def oversized_block(inp, out):
    bg = _bg(inp)
    h, w = len(inp), len(inp[0])
    qi, qj = _true_quad(inp)
    n = h // 2 + 1
    res = _blank(inp, bg)
    i0 = 0 if qi == 0 else h - n
    j0 = 0 if qj == 0 else w - n
    for i in range(i0, i0 + n):
        for j in range(j0, j0 + n):
            res[i][j] = FILL
    return res


ALTERNATIVES = [
    ("fill the right quadrant with a non-2 marker colour", wrong_fill_color),
    ("fill the diagonally opposite quadrant", opposite_quadrant),
    ("fill the horizontally mirrored quadrant", horizontal_mirror_quadrant),
    ("fill the vertically mirrored quadrant", vertical_mirror_quadrant),
    ("fill a half-size block with its corner at the 2 cell, clipped", block_anchored_at_marker),
    ("use the first non-background cell in reading order as the marker", first_marker_in_reading_order),
    ("fill the full-width row band instead of the quadrant", row_band),
    ("fill the full-height column band instead of the quadrant", column_band),
    ("output only the cropped quadrant", cropped_block_only),
    ("fill the quadrant but leave the other marker cells in place", markers_left_in_place),
    ("fill an oversized block one cell larger than the quadrant", oversized_block),
]


def _valid(g, out):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r)
            and g != out)


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/87ab05b8.json'))
    pairs = task["train"]
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g, p["output"]):
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
