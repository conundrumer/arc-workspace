"""Near-miss readings for ARC task 7e576d6e.

The grid has parallel divider lines, each with a gap, and two markers.  The
true output draws, in the marker color, a staircase path from the first marker
through the middle of each gap (painting it) (in progress order, left to right or top to
bottom) to the second marker.  Each gap is entered one cell before its divider.
"""
import json
from collections import Counter
from pathlib import Path


def _transpose(g):
    return [list(r) for r in zip(*g)]


def _analyze(g):
    """g has vertical dividers.  Returns bg, divider cols, gap mids, markers."""
    h, w = len(g), len(g[0])
    cnt = Counter(v for r in g for v in r)
    bg = cnt.most_common(1)[0][0]
    cols = [c for c in range(w)
            if sum(1 for r in range(h) if g[r][c] != bg) >= 0.8 * h]
    gaps = {}
    line_col = None
    gap_col = None
    for c in cols:
        col = [g[r][c] for r in range(h)]
        lc = Counter(col).most_common(1)[0][0]
        line_col = lc
        rows = [r for r in range(h) if col[r] != lc]
        if rows:
            gap_col = col[rows[0]]
            gaps[c] = (rows[0], rows[-1])
    markers = [(r, c) for r in range(h) for c in range(w)
               if g[r][c] != bg and c not in cols]
    markers.sort(key=lambda p: p[1])
    return bg, line_col, gap_col, gaps, markers


def _seg(h, w, cells, a, b, width=1):
    (r1, c1), (r2, c2) = a, b
    if r1 == r2:
        for c in range(min(c1, c2), max(c1, c2) + 1):
            cells.add((r1, c))
    else:
        for r in range(min(r1, r2), max(r1, r2) + 1):
            cells.add((r, c1))


def _path(g, off=1, reverse=False, order="progress", color=None,
          keep_mid=False, mid="mid", final_leg=True, first_only=False,
          vfirst=False):
    """Draw a path on a copy of g (vertical dividers)."""
    h, w = len(g), len(g[0])
    bg, line_col, gap_col, gaps, markers = _analyze(g)
    mcol = g[markers[0][0]][markers[0][1]]
    pc = mcol if color is None else color
    gl = []
    for c, (r0, r1) in gaps.items():
        if mid == "mid":
            r = (r0 + r1) // 2
        else:
            r = r0
        gl.append((r, c))
    if order == "progress":
        gl.sort(key=lambda p: p[1], reverse=reverse)
    else:
        gl.sort(key=lambda p: p[0], reverse=reverse)
    m1, m2 = markers[0], markers[-1]
    if reverse:
        m1, m2 = m2, m1
    sign = -1 if reverse else 1
    stops = [m1] + gl + [m2]
    xs = [stops[0][1]] + [c - sign * off for _, c in gl] + [stops[-1][1]]
    wp = [(stops[0][0], xs[0])]
    n = len(stops) - 1
    for i in range(1, n + 1):
        if vfirst:
            wp.append((stops[i][0], xs[i - 1]))
            wp.append((stops[i][0], xs[i]))
        else:
            wp.append((stops[i - 1][0], xs[i]))
            wp.append((stops[i][0], xs[i]))
    if not final_leg:
        wp = wp[:-3]
    if first_only:
        wp = wp[:4]
    cells = set()
    for a, b in zip(wp, wp[1:]):
        _seg(h, w, cells, a, b)
    out = [row[:] for row in g]
    for r, c in cells:
        if 0 <= r < h and 0 <= c < w:
            if keep_mid and (r, c) in set(gl):
                continue
            out[r][c] = pc
    return out


def _apply(fn, inp, **kw):
    """Run fn on the grid normalized to vertical dividers."""
    h, w = len(inp), len(inp[0])
    bg = Counter(v for r in inp for v in r).most_common(1)[0][0]
    vert = sum(1 for c in range(w)
               if sum(1 for r in range(h) if inp[r][c] != bg) >= 0.8 * h) > 0
    if vert:
        return fn(inp, **kw)
    return _transpose(fn(_transpose(inp), **kw))


def _make(**kw):
    def f(inp, out):
        return _apply(_path, inp, **kw)
    return f


def _color_of(which):
    def f(inp, out):
        def go(g):
            bg, lc, gc, gaps, markers = _analyze(g)
            return _path(g, color=lc if which == "line" else gc)
        return _apply(lambda g: go(g), inp)
    return f


def true_path(inp, out):
    return _apply(_path, inp)


ALTERNATIVES = [
    ("path drawn in the gap color instead of the marker color", _color_of("gap")),
    ("path drawn in the divider color instead of the marker color", _color_of("line")),
    ("path leaves the middle cell of each gap in the gap color", _make(keep_mid=True)),
    ("elbow legs run along the divider line (entry offset 0 instead of 1)", _make(off=0)),
    ("elbow legs sit two cells before each divider (entry offset 2)", _make(off=2)),
    ("path heads the opposite way along the progress axis", _make(reverse=True)),
    ("gaps visited in order along the divider axis instead of the progress axis", _make(order="divider")),
    ("path stops at the last gap and never reaches the second marker", _make(final_leg=False)),
    ("path passes through the first cell of each gap instead of its middle", _make(mid="edge")),
    ("path covers only the first marker and the first gap", _make(first_only=True)),
    ("vertical legs placed at the previous stop's column (turn before entering, not after)", _make(vfirst=True)),
]


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/7e576d6e.json"))
    pairs = task["train"]
    print("sanity: generator reproduces true output:",
          [true_path(p["input"], p["output"]) == p["output"] for p in pairs])
    for desc, fn in ALTERNATIVES:
        ok = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is None:
                continue
            rect = (isinstance(g, list) and len(g) > 0
                    and all(isinstance(r, list) and len(r) == len(g[0]) for r in g))
            vals = rect and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r)
            if vals and g != p["output"]:
                ok += 1
        print(f"{ok}/{len(pairs)}  {desc}")
