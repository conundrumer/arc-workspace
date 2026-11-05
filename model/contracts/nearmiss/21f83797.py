import json
from pathlib import Path


def _marks(inp):
    return [(r, c) for r, row in enumerate(inp) for c, v in enumerate(row) if v != 0]


def _geom(inp):
    m = _marks(inp)
    rs = sorted({r for r, _ in m})
    cs = sorted({c for _, c in m})
    return m, rs, cs, min(rs), max(rs), min(cs), max(cs)


def _build(inp, rows, cols, region, line=2, fill=1, seg=None):
    h, w = len(inp), len(inp[0])
    g = [[0] * w for _ in range(h)]
    for r in range(h):
        for c in range(w):
            if region(r, c):
                g[r][c] = fill
    for r in range(h):
        for c in range(w):
            if r in rows or c in cols:
                if seg is None or seg(r, c):
                    g[r][c] = line
    return g


def no_fill(inp, out):
    return [[2 if v == 2 else 0 for v in row] for row in out]


def fill_grown(inp, out):
    m, rs, cs, r0, r1, c0, c1 = _geom(inp)
    return _build(inp, rs, cs, lambda r, c: r0 - 1 <= r <= r1 + 1 and c0 - 1 <= c <= c1 + 1)


def fill_shrunk(inp, out):
    m, rs, cs, r0, r1, c0, c1 = _geom(inp)
    return _build(inp, rs, cs, lambda r, c: r0 + 2 <= r <= r1 - 2 and c0 + 2 <= c <= c1 - 2)


def fill_shifted(inp, out):
    m, rs, cs, r0, r1, c0, c1 = _geom(inp)
    return _build(inp, rs, cs, lambda r, c: r0 + 2 <= r <= r1 and c0 + 2 <= c <= c1)


def fill_color_mark(inp, out):
    m, rs, cs, r0, r1, c0, c1 = _geom(inp)
    return _build(inp, rs, cs, lambda r, c: r0 < r < r1 and c0 < c < c1, fill=2)


def swapped_colors(inp, out):
    m, rs, cs, r0, r1, c0, c1 = _geom(inp)
    return _build(inp, rs, cs, lambda r, c: r0 < r < r1 and c0 < c < c1, line=1, fill=2)


def only_rows(inp, out):
    m, rs, cs, r0, r1, c0, c1 = _geom(inp)
    return _build(inp, rs, [], lambda r, c: r0 < r < r1 and c0 < c < c1)


def only_cols(inp, out):
    m, rs, cs, r0, r1, c0, c1 = _geom(inp)
    return _build(inp, [], cs, lambda r, c: r0 < r < r1 and c0 < c < c1)


def segments_in_bbox(inp, out):
    m, rs, cs, r0, r1, c0, c1 = _geom(inp)
    return _build(inp, rs, cs, lambda r, c: r0 < r < r1 and c0 < c < c1,
                  seg=lambda r, c: r0 <= r <= r1 and c0 <= c <= c1)


def fill_outside(inp, out):
    m, rs, cs, r0, r1, c0, c1 = _geom(inp)
    return _build(inp, rs, cs, lambda r, c: not (r0 <= r <= r1 and c0 <= c <= c1))


def fill_whole_grid(inp, out):
    m, rs, cs, r0, r1, c0, c1 = _geom(inp)
    return _build(inp, rs, cs, lambda r, c: True)


def fill_band_full_width(inp, out):
    m, rs, cs, r0, r1, c0, c1 = _geom(inp)
    return _build(inp, rs, cs, lambda r, c: r0 < r < r1)


ALTERNATIVES = [
    ("lines drawn but the rectangle between them is left unfilled", no_fill),
    ("fill grows one cell beyond the lines' bounding box", fill_grown),
    ("fill is inset one extra cell from the lines", fill_shrunk),
    ("fill box is offset by one cell from the lines on the near side", fill_shifted),
    ("interior filled with the mark color instead of the new color", fill_color_mark),
    ("line and fill colors swapped", swapped_colors),
    ("only horizontal lines drawn", only_rows),
    ("only vertical lines drawn", only_cols),
    ("lines stop at the bounding box instead of spanning the grid", segments_in_bbox),
    ("fill applied outside the bounding box instead of inside", fill_outside),
    ("every non-line cell of the grid is filled", fill_whole_grid),
    ("fill spans the full grid width between the horizontal lines", fill_band_full_width),
]


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/21f83797.json'))
    for desc, f in ALTERNATIVES:
        n = 0
        for p in task['train']:
            g = f(p['input'], p['output'])
            ok = (g is not None and len(g) > 0 and all(len(r) == len(g[0]) for r in g)
                  and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r)
                  and g != p['output'])
            n += ok
        print(n, len(task['train']), desc)
