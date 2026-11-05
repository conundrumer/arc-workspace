"""Near-miss rules for ARC task 2204b7a8.

Rule: two opposite borders are uniform lines of two colors. Each scattered
mark (color 3) takes the color of the nearer line.
"""
import json
from pathlib import Path


def _lines(inp):
    """Return (axis, c1, c2): axis 'h' if the lines are the top/bottom rows."""
    h, w = len(inp), len(inp[0])
    if len(set(inp[0])) == 1 and len(set(inp[-1])) == 1 and inp[0][0] != 0:
        return "h", inp[0][0], inp[-1][0]
    return "v", inp[0][0], inp[0][-1]


def _marks(inp):
    """Mark cells with (r, c, pos along the line-to-line axis, size of that axis)."""
    axis, _, _ = _lines(inp)
    h, w = len(inp), len(inp[0])
    res = []
    for r in range(h):
        for c in range(w):
            if inp[r][c] == 0:
                continue
            if axis == "h" and r in (0, h - 1):
                continue
            if axis == "v" and c in (0, w - 1):
                continue
            res.append((r, c, r if axis == "h" else c, h if axis == "h" else w))
    return res


def _recolor(inp, fn):
    """fn(r, c, pos, n, c1, c2) -> new color for each mark."""
    axis, c1, c2 = _lines(inp)
    g = [row[:] for row in inp]
    for r, c, pos, n in _marks(inp):
        g[r][c] = fn(r, c, pos, n, c1, c2)
    return g


def unchanged(inp, out):
    return [row[:] for row in inp]


def all_first(inp, out):
    return _recolor(inp, lambda r, c, p, n, c1, c2: c1)


def all_second(inp, out):
    return _recolor(inp, lambda r, c, p, n, c1, c2: c2)


def farthest(inp, out):
    return _recolor(inp, lambda r, c, p, n, c1, c2: c2 if p < n / 2 else c1)


def erase(inp, out):
    return _recolor(inp, lambda r, c, p, n, c1, c2: 0)


def perpendicular_axis(inp, out):
    axis, c1, c2 = _lines(inp)
    h, w = len(inp), len(inp[0])

    def f(r, c, p, n, a, b):
        q, m = (c, w) if axis == "h" else (r, h)
        return a if q < m / 2 else b

    return _recolor(inp, f)


def only_near_second(inp, out):
    """Recolor only the marks nearer the second line; others stay unrecolored."""
    axis, c1, c2 = _lines(inp)
    g = [row[:] for row in inp]
    for r, c, p, n in _marks(inp):
        if p >= n / 2:
            g[r][c] = c2
    return g


def majority(inp, out):
    cnt = {}
    for r, c, p, n in _marks(inp):
        cnt[out[r][c]] = cnt.get(out[r][c], 0) + 1
    best = max(cnt, key=lambda k: (cnt[k], -k))
    return _recolor(inp, lambda r, c, p, n, c1, c2: best)


def shifted_threshold(inp, out):
    return _recolor(inp, lambda r, c, p, n, c1, c2: c1 if p < n / 2 + 2 else c2)


def path_filled(inp, out):
    """Also paint the cells between each mark and its nearer line."""
    axis, c1, c2 = _lines(inp)
    h, w = len(inp), len(inp[0])
    g = [row[:] for row in out]
    for r, c, p, n in _marks(inp):
        col = c1 if p < n / 2 else c2
        if axis == "h":
            rng = range(1, r) if p < n / 2 else range(r + 1, h - 1)
            for rr in rng:
                g[rr][c] = col
        else:
            rng = range(1, c) if p < n / 2 else range(c + 1, w - 1)
            for cc in rng:
                g[r][cc] = col
    return g


def line_extended(inp, out):
    """Marks recolored, and the nearer line's color also spills onto the adjacent interior cell."""
    axis, c1, c2 = _lines(inp)
    h, w = len(inp), len(inp[0])
    g = [row[:] for row in out]
    for r, c, p, n in _marks(inp):
        near_first = p < n / 2
        col = c1 if near_first else c2
        if axis == "h":
            rr = 1 if near_first else h - 2
            g[rr][c] = col
        else:
            cc = 1 if near_first else w - 2
            g[r][cc] = col
    return g


ALTERNATIVES = [
    ("marks left unchanged (input returned)", unchanged),
    ("every mark takes the first line's color (top/left)", all_first),
    ("every mark takes the second line's color (bottom/right)", all_second),
    ("each mark takes the farther line's color", farthest),
    ("marks erased to 0 instead of recolored", erase),
    ("nearest line judged along the wrong axis (parallel to the lines)", perpendicular_axis),
    ("only marks nearer the second line recolored; others stay", only_near_second),
    ("all marks take the color most marks received", majority),
    ("nearer-line threshold shifted by 2 cells toward the second line", shifted_threshold),
    ("marks recolored and the path to the nearer line also painted", path_filled),
    ("marks recolored and the interior cell next to the nearer line also painted", line_extended),
]


def _valid(g, out):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) for r in g):
        return False
    if len({len(r) for r in g}) != 1 or not g[0]:
        return False
    if not all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/2204b7a8.json").read_text())
    pairs = task["train"]
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g, p["output"]):
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
