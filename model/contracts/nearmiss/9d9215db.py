import json
from pathlib import Path


def _copy(g):
    return [r[:] for r in g]


def _rings(g):
    """Rings of site cells in g: list of (depth, lo, hi, corner color, side color)."""
    n = len(g)
    res = []
    d = 0
    while 1 + 2 * d <= n - 2 - 2 * d:
        lo, hi = 1 + 2 * d, n - 2 - 2 * d
        cc = g[lo][lo]
        sc = g[lo][lo + 2] if hi - lo >= 4 else 0
        res.append((d, lo, hi, cc, sc))
        d += 1
    return res


def _corners(lo, hi):
    return {(lo, lo), (lo, hi), (hi, lo), (hi, hi)}


def _cells(lo, hi, step=2):
    s = set()
    for k in range(lo, hi + 1, step):
        s |= {(lo, k), (hi, k), (k, lo), (k, hi)}
    return s


def _sides(lo, hi, step=2):
    return _cells(lo, hi, step) - _corners(lo, hi)


def _paint(g, cells, col):
    for r, c in cells:
        g[r][c] = col


def _clear_ring(g, lo, hi):
    _paint(g, _cells(lo, hi, 1), 0)


def _draw(n, specs):
    """specs: list of (lo, hi, corner color, side color, side step)."""
    g = [[0] * n for _ in range(n)]
    for lo, hi, cc, sc, st in specs:
        if sc:
            _paint(g, _sides(lo, hi, st), sc)
        if cc:
            _paint(g, _corners(lo, hi), cc)
    return g


def sides_only_next_to_corner(inp, out):
    g = _copy(out)
    for d, lo, hi, cc, sc in _rings(out):
        if hi - lo < 4:
            continue
        keep = {(lo, lo + 2), (lo, hi - 2), (hi, lo + 2), (hi, hi - 2),
                (lo + 2, lo), (hi - 2, lo), (lo + 2, hi), (hi - 2, hi)}
        _paint(g, _sides(lo, hi) - keep, 0)
    return g


def sides_in_corner_color(inp, out):
    g = _copy(out)
    for d, lo, hi, cc, sc in _rings(out):
        if sc:
            _paint(g, _sides(lo, hi), cc)
    return g


def corner_and_side_colors_swapped(inp, out):
    g = _copy(out)
    for d, lo, hi, cc, sc in _rings(out):
        if sc:
            _paint(g, _sides(lo, hi), cc)
            _paint(g, _corners(lo, hi), sc)
    return g


def rings_seated_one_deeper(inp, out):
    n = len(out)
    specs = []
    for d, lo, hi, cc, sc in _rings(out):
        if cc and lo + 2 <= hi - 2:
            specs.append((lo + 2, hi - 2, cc, sc, 2))
    if not specs:
        return None
    return _draw(n, specs)


def only_outermost_ring(inp, out):
    g = _copy(out)
    for d, lo, hi, cc, sc in _rings(out)[1:]:
        _clear_ring(g, lo, hi)
    return g


def rings_without_side_ink_dropped(inp, out):
    g = _copy(out)
    for d, lo, hi, cc, sc in _rings(out):
        if cc and not sc:
            _clear_ring(g, lo, hi)
    return g


def sides_on_horizontal_edges_only(inp, out):
    g = _copy(out)
    for d, lo, hi, cc, sc in _rings(out):
        if sc:
            for k in range(lo + 1, hi):
                g[k][lo] = 0
                g[k][hi] = 0
    return g


def sides_on_vertical_edges_only(inp, out):
    g = _copy(out)
    for d, lo, hi, cc, sc in _rings(out):
        if sc:
            for k in range(lo + 1, hi):
                g[lo][k] = 0
                g[hi][k] = 0
    return g


def sides_at_every_cell(inp, out):
    n = len(out)
    specs = [(lo, hi, cc, sc, 1) for d, lo, hi, cc, sc in _rings(out) if cc]
    return _draw(n, specs)


def all_corners_outermost_color(inp, out):
    g = _copy(out)
    rs = [r for r in _rings(out) if r[3]]
    first = rs[0][3]
    for d, lo, hi, cc, sc in rs:
        _paint(g, _corners(lo, hi), first)
    return g


def sides_not_mirrored_past_middle(inp, out):
    g = _copy(out)
    for d, lo, hi, cc, sc in _rings(out):
        if sc:
            mid = (lo + hi) // 2
            for k in range(mid + 1, hi):
                for r, c in ((lo, k), (hi, k), (k, lo), (k, hi)):
                    g[r][c] = 0
    return g


def top_half_only(inp, out):
    n = len(out)
    g = _copy(out)
    for r in range(n // 2 + 1, n):
        g[r] = [0] * n
    return g


ALTERNATIVES = [
    ("side ink fills only the cells next to the corners, not the whole side", sides_only_next_to_corner),
    ("sides take the corner color instead of the side ink color", sides_in_corner_color),
    ("corner color and side color swapped", corner_and_side_colors_swapped),
    ("every ring drawn one ring deeper than the ring it came from", rings_seated_one_deeper),
    ("only the outermost ring is drawn", only_outermost_ring),
    ("rings with no side ink are not drawn", rings_without_side_ink_dropped),
    ("sides drawn on the top and bottom edges only", sides_on_horizontal_edges_only),
    ("sides drawn on the left and right edges only", sides_on_vertical_edges_only),
    ("sides drawn on every cell, ignoring the one-cell site pitch", sides_at_every_cell),
    ("all rings take the corner color of the outermost ring", all_corners_outermost_color),
    ("side ink reaches only to the middle of each side, not mirrored", sides_not_mirrored_past_middle),
    ("only the upper half of the output is drawn", top_half_only),
]


def _valid(g, out):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) for r in g):
        return False
    if len({len(r) for r in g}) != 1 or not g[0]:
        return False
    if not all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / 'data/tasks/9d9215db.json').read_text())
    pairs = task["train"]
    print(len(ALTERNATIVES), "readings,", len(pairs), "pairs")
    for desc, fn in ALTERNATIVES:
        cnt = 0
        for p in pairs:
            g = fn(_copy(p["input"]), _copy(p["output"]))
            if g is not None and _valid(g, p["output"]):
                cnt += 1
        print(cnt, desc)
