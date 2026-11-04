from pathlib import Path
import json


def _depth(h, w, i, j):
    return min(i, j, h - 1 - i, w - 1 - j)


def _colors(inp):
    h, w = len(inp), len(inp[0])
    n = (min(h, w) + 1) // 2
    return [inp[d][d] for d in range(n)]


def _paint(inp, f):
    """Paint each ring d with color f(d, colors)."""
    h, w = len(inp), len(inp[0])
    cs = _colors(inp)
    return [[f(_depth(h, w, i, j), cs) for j in range(w)] for i in range(h)]


def shift_one(inp, out):
    return _paint(inp, lambda d, c: c[(d + 1) % len(c)])


def shift_back(inp, out):
    return _paint(inp, lambda d, c: c[(d - 1) % len(c)])


def keep_outer(inp, out):
    return _paint(inp, lambda d, c: c[0] if d == 0 else c[len(c) - d])


def keep_inner(inp, out):
    n = len(_colors(inp))
    return _paint(inp, lambda d, c: c[d] if d == n - 1 else c[n - 1 - d])


def swap_ends_only(inp, out):
    n = len(_colors(inp))

    def f(d, c):
        if d == 0:
            return c[n - 1]
        if d == n - 1:
            return c[0]
        return c[d]
    return _paint(inp, f)


def swap_adjacent(inp, out):
    def f(d, c):
        k = d ^ 1
        return c[k] if k < len(c) else c[d]
    return _paint(inp, f)


def sorted_by_value(inp, out):
    def f(d, c):
        return sorted(c, reverse=True)[d]
    return _paint(inp, f)


def border_only(inp, out):
    n = len(_colors(inp))
    return _paint(inp, lambda d, c: c[n - 1] if d == 0 else c[d])


def fill_innermost(inp, out):
    return _paint(inp, lambda d, c: c[-1])


def diamond_rings(inp, out):
    # rings measured by Manhattan distance to the nearest edge cell corner-wise
    h, w = len(inp), len(inp[0])
    cs = _colors(inp)
    n = len(cs)
    res = []
    for i in range(h):
        row = []
        for j in range(w):
            d = min(min(i, h - 1 - i) + min(j, w - 1 - j), n - 1)
            row.append(cs[n - 1 - d])
        res.append(row)
    return res


def thick_border(inp, out):
    # border treated as 2 cells wide: ring depth halved, so rings are doubled in width
    h, w = len(inp), len(inp[0])
    cs = _colors(inp)
    n = len(cs)
    return [[cs[n - 1 - min(_depth(h, w, i, j) // 2, n - 1)] if _depth(h, w, i, j) // 2 < n else cs[0]
             for j in range(w)] for i in range(h)]


def true_but_outer_ring_unfilled(inp, out):
    h, w = len(out), len(out[0])
    res = [r[:] for r in out]
    for i in range(h):
        for j in range(w):
            if _depth(h, w, i, j) == 0:
                res[i][j] = inp[i][j]
    return res


ALTERNATIVES = [
    ("ring colors shifted by one ring inward instead of reversed", shift_one),
    ("ring colors shifted by one ring outward instead of reversed", shift_back),
    ("outermost ring keeps its color, inner rings reversed", keep_outer),
    ("innermost ring keeps its color, other rings reversed", keep_inner),
    ("only outermost and innermost ring colors swapped", swap_ends_only),
    ("adjacent rings swapped in pairs", swap_adjacent),
    ("ring colors reassigned by sorting color values descending", sorted_by_value),
    ("only the border ring is recolored with the innermost color", border_only),
    ("whole grid filled with the innermost color", fill_innermost),
    ("rings drawn as diamonds (Manhattan depth) with reversed colors", diamond_rings),
    ("rings two cells thick (depth halved) with reversed colors", thick_border),
    ("true output but the outer ring left at input color", true_but_outer_ring_unfilled),
]


def _valid(g, out):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9 for r in g for v in r)
            and g != out)


if __name__ == "__main__":
    task = json.load(open(str(Path(__file__).resolve().parents[3] / 'data/tasks/85c4e7cd.json')))
    pairs = task["train"]
    print("pairs", len(pairs))
    for desc, fn in ALTERNATIVES:
        cnt = 0
        for p in pairs:
            try:
                g = fn(p["input"], p["output"])
            except Exception as e:
                print("  error", fn.__name__, e)
                g = None
            if g is not None and _valid(g, p["output"]):
                cnt += 1
        print(cnt, desc)
