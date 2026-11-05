import json
from collections import Counter
from pathlib import Path


def _info(inp):
    h, w = len(inp), len(inp[0])
    bg = Counter(c for r in inp for c in r).most_common(1)[0][0]
    cells = [(i, j) for i in range(h) for j in range(w) if inp[i][j] != bg]
    if len(cells) != 1:
        return None
    r, c = cells[0]
    return h, w, bg, r, c, inp[r][c]


def _span(p, n, near=True):
    """Rows (or cols) from p to the nearer (or farther) edge, inclusive."""
    to_lo, to_hi = p, n - 1 - p
    go_lo = (to_lo < to_hi) if near else (to_lo > to_hi)
    if to_lo == to_hi:
        go_lo = True
    return range(0, p + 1) if go_lo else range(p, n)


def _paint(inp, rows, cols, color, keep_mark=True):
    g = [row[:] for row in inp]
    for i in rows:
        for j in cols:
            g[i][j] = color
    return g


def farthest_corner(inp, out):
    h, w, bg, r, c, col = _info(inp)
    return _paint(inp, _span(r, h, False), _span(c, w, False), col)


def wrong_vertical(inp, out):
    h, w, bg, r, c, col = _info(inp)
    return _paint(inp, _span(r, h, False), _span(c, w, True), col)


def wrong_horizontal(inp, out):
    h, w, bg, r, c, col = _info(inp)
    return _paint(inp, _span(r, h, True), _span(c, w, False), col)


def always_top_left(inp, out):
    h, w, bg, r, c, col = _info(inp)
    return _paint(inp, range(0, r + 1), range(0, c + 1), col)


def exclusive_column_side(inp, out):
    h, w, bg, r, c, col = _info(inp)
    cols = [j for j in _span(c, w) if j != c]
    g = _paint(inp, _span(r, h), cols, col)
    return g


def exclusive_row_side(inp, out):
    h, w, bg, r, c, col = _info(inp)
    rows = [i for i in _span(r, h) if i != r]
    return _paint(inp, rows, _span(c, w), col)


def wrong_color(inp, out):
    h, w, bg, r, c, col = _info(inp)
    fill = 1 if col != 1 else 2
    g = _paint(inp, _span(r, h), _span(c, w), fill)
    g[r][c] = col
    return g


def half_plane(inp, out):
    h, w, bg, r, c, col = _info(inp)
    return _paint(inp, _span(r, h), range(w), col)


def l_shape_only(inp, out):
    h, w, bg, r, c, col = _info(inp)
    g = _paint(inp, _span(r, h), [c], col)
    return _paint(g, [r], _span(c, w), col)


def hollow_box(inp, out):
    h, w, bg, r, c, col = _info(inp)
    rows, cols = list(_span(r, h)), list(_span(c, w))
    g = [row[:] for row in inp]
    for i in rows:
        for j in cols:
            if i in (rows[0], rows[-1]) or j in (cols[0], cols[-1]):
                g[i][j] = col
    return g


def mark_erased(inp, out):
    h, w, bg, r, c, col = _info(inp)
    g = [row[:] for row in out]
    g[r][c] = bg
    return g


def unchanged(inp, out):
    return [row[:] for row in inp]


ALTERNATIVES = [
    ("fill toward the farthest corner instead of the nearest", farthest_corner),
    ("pick the farther edge vertically, nearer edge horizontally", wrong_vertical),
    ("pick the nearer edge vertically, farther edge horizontally", wrong_horizontal),
    ("always fill toward the top-left corner", always_top_left),
    ("box leaves out the mark's column", exclusive_column_side),
    ("box leaves out the mark's row", exclusive_row_side),
    ("box filled with a fixed wrong color, mark kept", wrong_color),
    ("fill the full-width band from the mark to the nearer top/bottom edge", half_plane),
    ("fill only the row and column segments from the mark to the corner", l_shape_only),
    ("fill only the outline of the box", hollow_box),
    ("correct box but the mark cell is erased to background", mark_erased),
    ("output equals input", unchanged),
]


def _valid(g, out):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) for r in g):
        return False
    if len({len(r) for r in g}) != 1:
        return False
    if not all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/4a1cacc2.json"))
    pairs = task["train"]
    print(len(ALTERNATIVES), "readings,", len(pairs), "pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g, p["output"]):
                n += 1
        print(n, desc)
