"""Near-miss readings for ARC task 06df4c85 (tile grid; join same-colour marks)."""
import json
from pathlib import Path


def _parse(inp):
    h, w = len(inp), len(inp[0])
    k = next(i for i, r in enumerate(inp) if len(set(r)) == 1)
    p = k + 1
    bg = inp[0][0]
    nr, nc = (h + 1) // p, (w + 1) // p
    marks = {}
    for i in range(nr):
        for j in range(nc):
            c = inp[i * p][j * p]
            if c != bg:
                marks[(i, j)] = c
    return k, p, bg, inp[k][0], nr, nc, marks


def _paint(grid, k, p, tile, color):
    i, j = tile
    for a in range(k):
        for b in range(k):
            grid[i * p + a][j * p + b] = color


def _paint_span(grid, k, p, a, b, color):
    """Paint tiles and the separator cells between the two tiles a, b (same row/col)."""
    r0, r1 = sorted((a[0] * p, b[0] * p + k - 1))
    c0, c1 = sorted((a[1] * p, b[1] * p + k - 1))
    for r in range(r0, r1 + 1):
        for c in range(c0, c1 + 1):
            grid[r][c] = color


def _links(marks, nr, nc, axes=("h", "v"), same=True):
    """Consecutive marks along a line (no mark between) that join; yields (a, b, colour)."""
    res = []
    if "h" in axes:
        for i in range(nr):
            row = [(j, marks[(i, j)]) for j in range(nc) if (i, j) in marks]
            for (j1, c1), (j2, c2) in zip(row, row[1:]):
                if (c1 == c2 or not same) and j2 - j1 > 1:
                    res.append(((i, j1), (i, j2), c1))
    if "v" in axes:
        for j in range(nc):
            col = [(i, marks[(i, j)]) for i in range(nr) if (i, j) in marks]
            for (i1, c1), (i2, c2) in zip(col, col[1:]):
                if (c1 == c2 or not same) and i2 - i1 > 1:
                    res.append(((i1, j), (i2, j), c1))
    return res


def _between(a, b):
    di = (b[0] > a[0]) - (b[0] < a[0])
    dj = (b[1] > a[1]) - (b[1] < a[1])
    t = (a[0] + di, a[1] + dj)
    while t != b:
        yield t
        t = (t[0] + di, t[1] + dj)


def _copy(g):
    return [list(r) for r in g]


def _fill(inp, axes=("h", "v"), same=True, color=None, trim=0, min_gap=0,
          max_gap=99, ends=False):
    k, p, bg, gap, nr, nc, marks = _parse(inp)
    g = _copy(inp)
    for a, b, c in _links(marks, nr, nc, axes, same):
        tiles = list(_between(a, b))
        if not (min_gap <= len(tiles) <= max_gap):
            continue
        if trim:
            tiles = tiles[:-trim]
        for t in tiles:
            _paint(g, k, p, t, c if color is None else color)
    return g


def horizontal_only(inp, out):
    return _fill(inp, axes=("h",))


def vertical_only(inp, out):
    return _fill(inp, axes=("v",))


def any_colour_pairs(inp, out):
    # joins consecutive marks of different colours too, painted in the first mark's colour
    return _fill(inp, same=False)


def bounding_box(inp, out):
    k, p, bg, gap, nr, nc, marks = _parse(inp)
    g = _copy(inp)
    for c in set(marks.values()):
        ts = [t for t, v in marks.items() if v == c]
        if len(ts) < 2:
            continue
        for i in range(min(t[0] for t in ts), max(t[0] for t in ts) + 1):
            for j in range(min(t[1] for t in ts), max(t[1] for t in ts) + 1):
                if (i, j) not in marks:
                    _paint(g, k, p, (i, j), c)
    return g


def fill_through_separators(inp, out):
    k, p, bg, gap, nr, nc, marks = _parse(inp)
    g = _copy(inp)
    for a, b, c in _links(marks, nr, nc):
        _paint_span(g, k, p, a, b, c)
    return g


def gap_colour_fill(inp, out):
    k, p, bg, gap, nr, nc, marks = _parse(inp)
    return _fill(inp, color=gap)


def single_colour_fill(inp, out):
    # every join is painted in the most common mark colour
    k, p, bg, gap, nr, nc, marks = _parse(inp)
    vals = list(marks.values())
    top = max(sorted(set(vals)), key=vals.count)
    return _fill(inp, color=top)


def stop_one_short(inp, out):
    return _fill(inp, trim=1)


def only_single_tile_gaps(inp, out):
    return _fill(inp, max_gap=1)


def only_long_gaps(inp, out):
    return _fill(inp, min_gap=2)


def extend_to_grid_edges(inp, out):
    k, p, bg, gap, nr, nc, marks = _parse(inp)
    g = _fill(inp)
    for a, b, c in _links(marks, nr, nc):
        if a[0] == b[0]:
            for j in range(nc):
                if (a[0], j) not in marks:
                    _paint(g, k, p, (a[0], j), c)
        else:
            for i in range(nr):
                if (i, a[1]) not in marks:
                    _paint(g, k, p, (i, a[1]), c)
    return g


def diagonal_links(inp, out):
    k, p, bg, gap, nr, nc, marks = _parse(inp)
    g = _copy(out)
    for (i, j), c in marks.items():
        for di, dj in ((1, 1), (1, -1)):
            t = (i + di, j + dj)
            while 0 <= t[0] < nr and 0 <= t[1] < nc:
                if t in marks:
                    if marks[t] == c:
                        for u in _between((i, j), t):
                            _paint(g, k, p, u, c)
                    break
                t = (t[0] + di, t[1] + dj)
    return g


def one_cell_per_tile(inp, out):
    k, p, bg, gap, nr, nc, marks = _parse(out)
    return [[out[i * p][j * p] for j in range(nc)] for i in range(nr)]


def marks_removed(inp, out):
    # joins drawn, but the original marks are erased back to the background
    k, p, bg, gap, nr, nc, marks = _parse(inp)
    g = _fill(inp)
    for t in marks:
        _paint(g, k, p, t, bg)
    return g


ALTERNATIVES = [
    ("join marks horizontally only", horizontal_only),
    ("join marks vertically only", vertical_only),
    ("join consecutive marks of any colour, in the first mark's colour", any_colour_pairs),
    ("fill the whole bounding box of each colour's marks", bounding_box),
    ("fill the separator lines between joined tiles too", fill_through_separators),
    ("paint joins in the separator-line colour", gap_colour_fill),
    ("paint all joins in the most common mark colour", single_colour_fill),
    ("leave the tile next to the second mark unfilled", stop_one_short),
    ("join only marks with exactly one tile between", only_single_tile_gaps),
    ("join only marks with two or more tiles between", only_long_gaps),
    ("extend each join to both grid edges", extend_to_grid_edges),
    ("output one cell per tile instead of the full grid", one_cell_per_tile),
]


def _valid(g, ref):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1
            and all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9
                    for r in g for v in r)
            and g != ref)


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/06df4c85.json").read_text())
    pairs = task["train"]
    k0 = _fill  # sanity: the correct rule reproduces the true output
    for pr in pairs:
        assert k0(pr["input"]) == pr["output"], "reference fill mismatch"
    print(len(ALTERNATIVES), "readings,", len(pairs), "pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for pr in pairs:
            g = fn(pr["input"], pr["output"])
            if g is not None and _valid(g, pr["output"]):
                n += 1
        print(n, desc)
