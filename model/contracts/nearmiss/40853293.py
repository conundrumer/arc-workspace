"""Near-miss readings for ARC task 40853293.

Rule: same-colored marks come in pairs that share a row or a column. Each pair
is joined by a straight line of its color. Where a vertical and a horizontal
line cross, the vertical line is on top.
"""
import json
from pathlib import Path


def _pairs(inp):
    """Return a list of (color, orientation, fixed, lo, hi, first_pos).

    orientation 'v' means the marks share a column (fixed = column, lo/hi are rows).
    """
    h, w = len(inp), len(inp[0])
    pos = {}
    for r in range(h):
        for c in range(w):
            if inp[r][c] != 0:
                pos.setdefault(inp[r][c], []).append((r, c))
    res = []
    for col, ps in pos.items():
        if len(ps) < 2:
            continue
        (r1, c1), (r2, c2) = ps[0], ps[-1]
        if c1 == c2:
            res.append((col, "v", c1, min(r1, r2), max(r1, r2), ps[0]))
        elif r1 == r2:
            res.append((col, "h", r1, min(c1, c2), max(c1, c2), ps[0]))
    return res


def _draw(inp, top="v", lo_pad=0, hi_pad=0, edge=False, only=None,
          cross=None, order=None, keep_ends=True):
    h, w = len(inp), len(inp[0])
    g = [[0] * w for _ in range(h)]
    ps = _pairs(inp)
    if only is not None:
        ps = [p for p in ps if only(p)]
    if order is not None:
        ps = order(ps)
    horiz = [p for p in ps if p[1] == "h"]
    vert = [p for p in ps if p[1] == "v"]
    layers = horiz + vert if top == "v" else vert + horiz
    for col, o, fixed, lo, hi, _ in layers:
        a, b = lo - lo_pad, hi + hi_pad
        n = h if o == "v" else w
        if edge:
            a, b = 0, n - 1
        a, b = max(a, 0), min(b, n - 1)
        for i in range(a, b + 1):
            if not keep_ends and (i == lo or i == hi):
                continue
            r, c = (i, fixed) if o == "v" else (fixed, i)
            if cross is not None and g[r][c] != 0 and g[r][c] != col:
                g[r][c] = cross
            else:
                g[r][c] = col
    return g


def _ok(g, out):
    return g if g != out else None


def horizontal_on_top(inp, out):
    return _ok(_draw(inp, top="h"), out)


def crossings_blank(inp, out):
    return _ok(_fix_blank(_draw(inp, cross=-1)), out)


def _fix_blank(g):
    return [[0 if v == -1 else v for v in row] for row in g]


def lines_to_edges(inp, out):
    return _ok(_draw(inp, edge=True), out)


def endpoints_left_empty(inp, out):
    return _ok(_draw(inp, keep_ends=False), out)


def only_vertical(inp, out):
    return _ok(_draw(inp, only=lambda p: p[1] == "v"), out)


def only_horizontal(inp, out):
    return _ok(_draw(inp, only=lambda p: p[1] == "h"), out)


def overshoot_by_one(inp, out):
    return _ok(_draw(inp, lo_pad=1, hi_pad=1), out)


def horizontal_blocked_by_vertical(inp, out):
    """A horizontal line stops at the first vertical line it meets."""
    h, w = len(inp), len(inp[0])
    g = _draw(inp)
    ps = _pairs(inp)
    verts = [p for p in ps if p[1] == "v"]
    for col, o, fixed, lo, hi, _ in ps:
        if o != "h":
            continue
        cols = sorted(v[2] for v in verts if v[3] <= fixed <= v[4] and lo < v[2] < hi)
        if not cols:
            continue
        for c in range(cols[0] + 1, hi + 1):
            if g[fixed][c] == col:
                g[fixed][c] = 0
    return _ok(g, out)


def first_color_only(inp, out):
    ps = _pairs(inp)
    if not ps:
        return None
    first = min(ps, key=lambda p: p[5])[0]
    return _ok(_draw(inp, only=lambda p: p[0] == first), out)


def line_ends_at_first_mark_to_edge(inp, out):
    """Ray from the later mark away from the pair to the grid edge instead of the segment."""
    h, w = len(inp), len(inp[0])
    g = [[0] * w for _ in range(h)]
    ps = _pairs(inp)
    ps = [p for p in ps if p[1] == "h"] + [p for p in ps if p[1] == "v"]
    for col, o, fixed, lo, hi, _ in ps:
        n = h if o == "v" else w
        for i in range(lo, n):
            r, c = (i, fixed) if o == "v" else (fixed, i)
            g[r][c] = col
    return _ok(g, out)


def true_output_without_crossing_overrides(inp, out):
    """Start from the true output; the second pair's line is left unfilled."""
    ps = _pairs(inp)
    if len(ps) < 2:
        return None
    ps.sort(key=lambda p: p[5])
    col, o, fixed, lo, hi, _ = ps[1]
    g = [row[:] for row in out]
    for i in range(lo + 1, hi):
        r, c = (i, fixed) if o == "v" else (fixed, i)
        if g[r][c] == col:
            g[r][c] = 0
    return _ok(g, out)


ALTERNATIVES = [
    ("horizontal lines are drawn over vertical lines at crossings", horizontal_on_top),
    ("crossing cells are left empty", crossings_blank),
    ("each line runs the full width or height of the grid", lines_to_edges),
    ("lines run strictly between the marks, so the marks themselves are erased", endpoints_left_empty),
    ("only vertical pairs are joined", only_vertical),
    ("only horizontal pairs are joined", only_horizontal),
    ("each line overshoots both marks by one cell", overshoot_by_one),
    ("a horizontal line stops at the first vertical line it meets", horizontal_blocked_by_vertical),
    ("only the pair that appears first in reading order is joined", first_color_only),
    ("each line runs from its first mark to the grid edge past the second mark", line_ends_at_first_mark_to_edge),
    ("one pair's line is left unfilled between its marks", true_output_without_crossing_overrides),
]


def _valid(g, out):
    return (
        isinstance(g, list) and g and all(isinstance(r, list) and r for r in g)
        and len({len(r) for r in g}) == 1
        and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r)
        and g != out
    )


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/40853293.json").read_text())
    train = task["train"]
    # sanity: the correct reading matches
    print("correct reading matches:", [_draw(p["input"]) == p["output"] for p in train])
    print(len(ALTERNATIVES), "readings,", len(train), "pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in train:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g, p["output"]):
                n += 1
        print(n, desc)
