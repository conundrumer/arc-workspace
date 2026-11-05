import json
from pathlib import Path


def _box(inp):
    cells = [(r, c) for r, row in enumerate(inp) for c, v in enumerate(row) if v == 3]
    r0 = min(r for r, c in cells)
    r1 = max(r for r, c in cells)
    c0 = min(c for r, c in cells)
    c1 = max(c for r, c in cells)
    return r0, r1, c0, c1


def _dot(inp):
    r0, r1, c0, c1 = _box(inp)
    for r in range(r0 + 1, r1):
        for c in range(c0 + 1, c1):
            if inp[r][c] == 3:
                return r, c
    return None


def _paint(inp, dist, odd=4, even=2, region=None, maxd=None):
    """Copy inp; background cells in region take odd/even color by dist(r, c)."""
    r0, r1, c0, c1 = region if region else _box(inp)
    g = [row[:] for row in inp]
    for r in range(r0, r1 + 1):
        for c in range(c0, c1 + 1):
            if inp[r][c] != 0:
                continue
            d = dist(r, c)
            if maxd is not None and d > maxd:
                continue
            g[r][c] = odd if d % 2 else even
    return g


def swapped_colors(inp, out):
    d = _dot(inp)
    return _paint(inp, lambda r, c: max(abs(r - d[0]), abs(c - d[1])), odd=2, even=4,
                  region=(_box(inp)[0] + 1, _box(inp)[1] - 1, _box(inp)[2] + 1, _box(inp)[3] - 1))


def _interior(inp):
    r0, r1, c0, c1 = _box(inp)
    return (r0 + 1, r1 - 1, c0 + 1, c1 - 1)


def manhattan(inp, out):
    d = _dot(inp)
    return _paint(inp, lambda r, c: abs(r - d[0]) + abs(c - d[1]), region=_interior(inp))


def whole_grid(inp, out):
    d = _dot(inp)
    h, w = len(inp), len(inp[0])
    return _paint(inp, lambda r, c: max(abs(r - d[0]), abs(c - d[1])), region=(0, h - 1, 0, w - 1))


def dot_overpainted(inp, out):
    g = [row[:] for row in out]
    d = _dot(inp)
    g[d[0]][d[1]] = 2
    return g


def from_corner(inp, out):
    r0, r1, c0, c1 = _interior(inp)
    return _paint(inp, lambda r, c: max(abs(r - r0), abs(c - c0)), region=(r0, r1, c0, c1))


def two_rings_only(inp, out):
    d = _dot(inp)
    return _paint(inp, lambda r, c: max(abs(r - d[0]), abs(c - d[1])), region=_interior(inp), maxd=2)


def concentric_with_box(inp, out):
    r0, r1, c0, c1 = _interior(inp)
    return _paint(inp, lambda r, c: min(r - r0, r1 - r, c - c0, c1 - c) + 1, region=(r0, r1, c0, c1))


def row_stripes(inp, out):
    d = _dot(inp)
    return _paint(inp, lambda r, c: abs(r - d[0]), region=_interior(inp))


def single_color(inp, out):
    g = [[4 if v == 2 else v for v in row] for row in out]
    return g


def shrunk_interior(inp, out):
    r0, r1, c0, c1 = _interior(inp)
    d = _dot(inp)
    return _paint(inp, lambda r, c: max(abs(r - d[0]), abs(c - d[1])), region=(r0 + 1, r1 - 1, c0 + 1, c1 - 1))


def rings_over_outline(inp, out):
    d = _dot(inp)
    g = [row[:] for row in out]
    r0, r1, c0, c1 = _box(inp)
    for r in range(r0, r1 + 1):
        for c in range(c0, c1 + 1):
            if inp[r][c] == 3 and (r, c) != d:
                k = max(abs(r - d[0]), abs(c - d[1]))
                g[r][c] = 4 if k % 2 else 2
    return g


def cross_only(inp, out):
    d = _dot(inp)
    g = [row[:] for row in out]
    for r, c in ((r, c) for r in range(len(g)) for c in range(len(g[0]))):
        if inp[r][c] == 0 and r != d[0] and c != d[1] and g[r][c] != 0:
            g[r][c] = 0
    return g


ALTERNATIVES = [
    ("odd and even ring colors swapped (2 at odd distance, 4 at even)", swapped_colors),
    ("ring distance is Manhattan instead of Chebyshev (diamond rings)", manhattan),
    ("rings fill the whole grid, not only the box interior", whole_grid),
    ("the dot cell is repainted with the even ring color", dot_overpainted),
    ("rings grow from the interior's top-left corner instead of the dot", from_corner),
    ("only the first two rings around the dot are painted", two_rings_only),
    ("rings are concentric with the box edges instead of the dot", concentric_with_box),
    ("distance is row distance only, giving horizontal stripes", row_stripes),
    ("all ring cells use one color (4), no alternation", single_color),
    ("interior shrunk by one cell: the interior's edge cells stay background", shrunk_interior),
    ("rings also overwrite the outline cells", rings_over_outline),
    ("rings painted only along the dot's row and column", cross_only),
]


def _valid(g, out):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r)
            and g != out)


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/b7fb29bc.json'))
    pairs = task["train"]
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g, p["output"]):
                n += 1
        print(n, "/", len(pairs), desc)
