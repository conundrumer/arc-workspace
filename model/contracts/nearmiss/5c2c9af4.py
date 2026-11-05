import json
from pathlib import Path


def _info(inp):
    marks = [(r, c, v) for r, row in enumerate(inp) for c, v in enumerate(row) if v != 0]
    marks.sort()
    col = marks[0][2]
    cr, cc = marks[1][0], marks[1][1]
    k = abs(marks[0][0] - cr)
    return cr, cc, k, col


def _draw(inp, cr, cc, k, col, keep=lambda d, r, c: True, dist="cheb", start=0, color=None):
    h, w = len(inp), len(inp[0])
    color = col if color is None else color
    g = [[0] * w for _ in range(h)]
    for r in range(h):
        for c in range(w):
            dr, dc = abs(r - cr), abs(c - cc)
            d = max(dr, dc) if dist == "cheb" else dr + dc
            if k > 0 and d % k == 0 and d >= start and keep(d, r, c):
                g[r][c] = color
    return g


def _put_marks(g, inp):
    for r, row in enumerate(inp):
        for c, v in enumerate(row):
            if v:
                g[r][c] = v
    return g


def one_ring(inp, out):
    cr, cc, k, col = _info(inp)
    return _draw(inp, cr, cc, k, col, keep=lambda d, r, c: d <= k)


def double_spacing(inp, out):
    cr, cc, k, col = _info(inp)
    return _draw(inp, cr, cc, 2 * k, col)


def spacing_plus_one(inp, out):
    cr, cc, k, col = _info(inp)
    return _draw(inp, cr, cc, k + 1, col)


def no_center(inp, out):
    cr, cc, k, col = _info(inp)
    g = [row[:] for row in out]
    g[cr][cc] = 0
    return g


def diamonds(inp, out):
    cr, cc, k, col = _info(inp)
    return _put_marks(_draw(inp, cr, cc, k, col, dist="manh"), inp)


def center_shifted(inp, out):
    cr, cc, k, col = _info(inp)
    return _draw(inp, cr + 1, cc, k, col)


def skip_box_ring(inp, out):
    cr, cc, k, col = _info(inp)
    g = _draw(inp, cr, cc, k, col, keep=lambda d, r, c: d != k)
    return _put_marks(g, inp)


def wrong_color(inp, out):
    cr, cc, k, col = _info(inp)
    return _draw(inp, cr, cc, k, col, color=col % 9 + 1)


def horizontal_sides_only(inp, out):
    cr, cc, k, col = _info(inp)
    return _draw(inp, cr, cc, k, col, keep=lambda d, r, c: abs(r - cr) == d)


def diagonals(inp, out):
    cr, cc, k, col = _info(inp)
    h, w = len(inp), len(inp[0])
    g = [[0] * w for _ in range(h)]
    for r in range(h):
        for c in range(w):
            if abs(r - cr) == abs(c - cc):
                g[r][c] = col
    return g


def rings_inside_box_only(inp, out):
    cr, cc, k, col = _info(inp)
    g = [row[:] for row in out]
    h, w = len(inp), len(inp[0])
    for r in range(h):
        for c in range(w):
            if max(abs(r - cr), abs(c - cc)) > k:
                g[r][c] = 0
    return g


def unchanged(inp, out):
    return [row[:] for row in inp]


ALTERNATIVES = [
    ("draw only the innermost ring through the outer dots", one_ring),
    ("ring spacing is twice the dot offset", double_spacing),
    ("ring spacing is one more than the dot offset", spacing_plus_one),
    ("center dot is dropped from the output", no_center),
    ("rings are diamonds (Manhattan distance) not squares", diamonds),
    ("rings are centered one row below the middle dot", center_shifted),
    ("the innermost ring through the outer dots is left out", skip_box_ring),
    ("rings drawn in a different color than the dots", wrong_color),
    ("only the top and bottom sides of each ring are drawn", horizontal_sides_only),
    ("diagonal line through the dots extended instead of rings", diagonals),
    ("rings outside the dots' bounding box are left out", rings_inside_box_only),
    ("output equals the input", unchanged),
]


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/5c2c9af4.json").read_text())
    pairs = task["train"]
    print(len(ALTERNATIVES), "readings,", len(pairs), "pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is None:
                continue
            ok = (
                isinstance(g, list) and g and all(isinstance(r, list) for r in g)
                and len({len(r) for r in g}) == 1 and len(g[0]) > 0
                and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r)
                and g != p["output"]
            )
            n += ok
        print(n, desc)
