import json
from pathlib import Path


def pts(inp):
    return [(r, c, v) for r, row in enumerate(inp) for c, v in enumerate(row) if v != 0]


def draw(inp, rows=True, cols=True, row_over_col=True, cross=2, own=None,
         shift_r=0, shift_c=0, dr=(-1, 0, 1), dc=(-1, 0, 1), swap=False, only=None):
    h, w = len(inp), len(inp[0])
    ps = pts(inp)
    if only is not None:
        ps = ps[only:only + 1]
    colors = [p[2] for p in ps]
    g = [[0] * w for _ in range(h)]
    rcol = {}
    ccol = {}
    for i, (r, c, v) in enumerate(ps):
        if swap:
            v = colors[(i + 1) % len(colors)]
        rcol[(r + shift_r) % h] = v
        ccol[(c + shift_c) % w] = v
    for y in range(h):
        for x in range(w):
            a = rcol.get(y) if rows else None
            b = ccol.get(x) if cols else None
            if a is not None and b is not None:
                if a == b:
                    g[y][x] = a
                elif cross is None:
                    g[y][x] = a if row_over_col else b
                else:
                    g[y][x] = cross
            elif a is not None:
                g[y][x] = a
            elif b is not None:
                g[y][x] = b
    if own is not None:
        for r, c, v in pts(inp):
            g[r][c] = own
    return g


def half_lines(inp):
    # lines run only down and right from each point
    h, w = len(inp), len(inp[0])
    g = [[0] * w for _ in range(h)]
    for r, c, v in pts(inp):
        for x in range(c, w):
            g[r][x] = v if g[r][x] in (0, v) else 2
        for y in range(r, h):
            g[y][c] = v if g[y][c] in (0, v) else 2
    return g


def diagonals(inp):
    h, w = len(inp), len(inp[0])
    g = [[0] * w for _ in range(h)]
    for r, c, v in pts(inp):
        for y in range(h):
            for x in range(w):
                if abs(y - r) == abs(x - c):
                    g[y][x] = v if g[y][x] in (0, v) else 2
    return g


def line_between(inp):
    # lines drawn only between the two points' rows/cols extent (bounding box)
    h, w = len(inp), len(inp[0])
    ps = pts(inp)
    g = [[0] * w for _ in range(h)]
    r0, r1 = min(p[0] for p in ps), max(p[0] for p in ps)
    c0, c1 = min(p[1] for p in ps), max(p[1] for p in ps)
    for r, c, v in ps:
        for x in range(c0, c1 + 1):
            g[r][x] = v if g[r][x] in (0, v) else 2
        for y in range(r0, r1 + 1):
            g[y][c] = v if g[y][c] in (0, v) else 2
    return g


def cross_color_input_color(out, inp):
    # intersections take the color of the first point instead of 2
    first = pts(inp)[0][2]
    return [[first if v == 2 else v for v in row] for row in out]


ALTERNATIVES = [
    ("rows and columns both drawn, crossing cells stay the row's color instead of 2",
     lambda inp, out: draw(inp, row_over_col=True, cross=None)),
    ("rows and columns both drawn, crossing cells stay the column's color instead of 2",
     lambda inp, out: draw(inp, row_over_col=False, cross=None)),
    ("only horizontal lines drawn, no vertical lines",
     lambda inp, out: draw(inp, cols=False)),
    ("only vertical lines drawn, no horizontal lines",
     lambda inp, out: draw(inp, rows=False)),
    ("crossing cells of different colors are left background 0",
     lambda inp, out: draw(inp, cross=0)),
    ("crossing cells take color 3 instead of 2",
     lambda inp, out: draw(inp, cross=3)),
    ("the original points are also marked 2 as crossings",
     lambda inp, out: draw(inp, own=2)),
    ("each point's lines take the other point's color",
     lambda inp, out: draw(inp, swap=True)),
    ("lines run one row down and one column right of each point",
     lambda inp, out: draw(inp, shift_r=1, shift_c=1)),
    ("lines run only down and right from each point, not the full row and column",
     lambda inp, out: half_lines(inp)),
    ("lines are limited to the bounding box of the points",
     lambda inp, out: line_between(inp)),
    ("only the first point in reading order gets lines",
     lambda inp, out: draw(inp, only=0)),
]


def valid(g, out):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) for r in g):
        return False
    if len({len(r) for r in g}) != 1 or not g[0]:
        return False
    if not all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/23581191.json'))
    train = task["train"]
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in train:
            g = fn(p["input"], p["output"])
            if g is not None and valid(g, p["output"]):
                n += 1
        print(f"{n}/{len(train)}  {desc}")
