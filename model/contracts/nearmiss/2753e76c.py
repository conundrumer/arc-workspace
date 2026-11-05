"""Near-miss readings for 2753e76c.

True rule: count the rectangles of each non-background color. The output is a
staircase with one row per color; rows descend by rectangle count; a row of
count k has k cells of its color, right-aligned (anchored at the top-right
corner), and 0 elsewhere.
"""
import json
from collections import Counter
from pathlib import Path


def _stats(inp):
    h, w = len(inp), len(inp[0])
    bg = Counter(v for r in inp for v in r).most_common(1)[0][0]
    seen = set()
    comps = []  # (color, area)
    for i in range(h):
        for j in range(w):
            if inp[i][j] == bg or (i, j) in seen:
                continue
            c = inp[i][j]
            st = [(i, j)]
            seen.add((i, j))
            area = 0
            while st:
                y, x = st.pop()
                area += 1
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < h and 0 <= nx < w and (ny, nx) not in seen and inp[ny][nx] == c:
                        seen.add((ny, nx))
                        st.append((ny, nx))
            comps.append((c, area))
    colors = {}
    for c, a in comps:
        d = colors.setdefault(c, {"n": 0, "cells": 0, "max": 0})
        d["n"] += 1
        d["cells"] += a
        d["max"] = max(d["max"], a)
    return bg, colors


def _rows(out):
    """(color, count) per output row, from the true output."""
    n = len(out)
    res = []
    for r in out:
        cells = [v for v in r if v != 0]
        res.append((cells[0], len(cells)))
    return res


def _stair(rows, n, align="right", width=None):
    width = width or n
    g = []
    for c, k in rows:
        k = max(0, min(k, width))
        if align == "right":
            g.append([0] * (width - k) + [c] * k)
        else:
            g.append([c] * k + [0] * (width - k))
    return g


def left_aligned(inp, out):
    return _stair(_rows(out), len(out), "left")


def ascending(inp, out):
    return _stair(_rows(out)[::-1], len(out))


def by_cell_area(inp, out):
    bg, cs = _stats(inp)
    order = sorted(cs, key=lambda c: (-cs[c]["cells"], c))
    return _stair([(c, cs[c]["n"]) for c in order], len(out))


def bar_one_shorter(inp, out):
    rows = [(c, k - 1) for c, k in _rows(out)]
    return _stair(rows, len(out))


def bar_one_longer(inp, out):
    n = len(out)
    return _stair([(c, k + 1) for c, k in _rows(out)], n, width=n + 1)


def with_background_row(inp, out):
    bg, cs = _stats(inp)
    g = _stair(_rows(out), len(out) + 1)
    g.append([0] * (len(out) + 1))
    return g


def transposed(inp, out):
    return [list(r) for r in zip(*out)]


def flipped_vertical(inp, out):
    return [r[:] for r in out[::-1]]


def rotated_180(inp, out):
    return [r[::-1] for r in out[::-1]]


def full_width_bars(inp, out):
    n = len(out)
    return [[c] * n for c, k in _rows(out)]


def rank_by_largest_rect(inp, out):
    bg, cs = _stats(inp)
    order = sorted(cs, key=lambda c: (-cs[c]["max"], c))
    return _stair([(c, cs[c]["n"]) for c in order], len(out))


def rank_by_color_value(inp, out):
    bg, cs = _stats(inp)
    order = sorted(cs)
    return _stair([(c, cs[c]["n"]) for c in order], len(out))


ALTERNATIVES = [
    ("bars are left-aligned instead of right-aligned", left_aligned),
    ("rows ordered by ascending rectangle count", ascending),
    ("rows ranked by total cell area of each color", by_cell_area),
    ("every bar one cell too short", bar_one_shorter),
    ("every bar one cell too long, with an extra column", bar_one_longer),
    ("background counted as an extra color row (output one size too big)", with_background_row),
    ("output transposed: one column per color", transposed),
    ("staircase flipped vertically (top-ranked row at bottom)", flipped_vertical),
    ("staircase rotated 180 degrees (corner at bottom-left)", rotated_180),
    ("every bar spans the full row width", full_width_bars),
    ("rows ranked by the largest single rectangle area", rank_by_largest_rect),
    ("rows ordered by color value", rank_by_color_value),
]


def _valid(g):
    return (
        isinstance(g, list) and g and all(isinstance(r, list) for r in g)
        and len({len(r) for r in g}) == 1 and len(g[0]) > 0
        and all(type(v) is int and 0 <= v <= 9 for r in g for v in r)
    )


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/2753e76c.json"))
    pairs = task["train"]
    for desc, f in ALTERNATIVES:
        ok = 0
        for p in pairs:
            g = f(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                ok += 1
        print(f"{ok}/{len(pairs)}  {desc}")
