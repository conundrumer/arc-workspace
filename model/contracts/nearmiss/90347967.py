"""Near-miss rules for ARC task 90347967.

True rule: the colored shape is rotated 180 degrees about its 5 cell, which
stays in place; everything else is background 0.
"""
import json
from pathlib import Path


def cells(g):
    return [(r, c, v) for r, row in enumerate(g) for c, v in enumerate(row) if v]


def find(g, color):
    for r, c, v in cells(g):
        if v == color:
            return r, c
    return None


def blank(g):
    return [[0] * len(g[0]) for _ in g]


def put(g, r, c, v):
    if 0 <= r < len(g) and 0 <= c < len(g[0]):
        g[r][c] = v


def about_pivot(inp, pivot, f, keep_original=False, drop_pivot=False):
    """Map each cell offset (dr, dc) from the pivot through f, clipping to the grid."""
    pr, pc = pivot
    res = [row[:] for row in inp] if keep_original else blank(inp)
    for r, c, v in cells(inp):
        if drop_pivot and (r, c) == pivot:
            continue
        dr, dc = f(r - pr, c - pc)
        put(res, pr + dr, pc + dc, v)
    return res


def rot180_bbox_center(inp, out):
    cs = cells(inp)
    r0, r1 = min(r for r, _, _ in cs), max(r for r, _, _ in cs)
    c0, c1 = min(c for _, c, _ in cs), max(c for _, c, _ in cs)
    res = blank(inp)
    for r, c, v in cs:
        put(res, r0 + r1 - r, c0 + c1 - c, v)
    return res


def mirror_h(inp, out):
    return about_pivot(inp, find(inp, 5), lambda dr, dc: (dr, -dc))


def mirror_v(inp, out):
    return about_pivot(inp, find(inp, 5), lambda dr, dc: (-dr, dc))


def transpose(inp, out):
    return about_pivot(inp, find(inp, 5), lambda dr, dc: (dc, dr))


def rot90_cw(inp, out):
    return about_pivot(inp, find(inp, 5), lambda dr, dc: (dc, -dr))


def rot90_ccw(inp, out):
    return about_pivot(inp, find(inp, 5), lambda dr, dc: (-dc, dr))


def rot180_about_one(inp, out):
    return about_pivot(inp, find(inp, 1), lambda dr, dc: (-dr, -dc))


def rot180_no_pivot_cell(inp, out):
    res = [row[:] for row in out]
    r, c = find(inp, 5)
    res[r][c] = 0
    return res


def rot180_keep_original(inp, out):
    return about_pivot(inp, find(inp, 5), lambda dr, dc: (-dr, -dc), keep_original=True)


def rot180_whole_grid(inp, out):
    return [row[::-1] for row in inp[::-1]]


def out_shifted_down_right(inp, out):
    res = blank(out)
    for r, c, v in cells(out):
        put(res, r + 1, c + 1, v)
    return res


ALTERNATIVES = [
    ("rotate 180 about the center of the shape's bounding box, so it stays put", rot180_bbox_center),
    ("mirror the shape left-right about the 5 cell", mirror_h),
    ("mirror the shape top-bottom about the 5 cell", mirror_v),
    ("transpose the shape about the 5 cell", transpose),
    ("rotate 90 degrees clockwise about the 5 cell", rot90_cw),
    ("rotate 90 degrees counter-clockwise about the 5 cell", rot90_ccw),
    ("rotate 180 about the 1 cell instead of the 5 cell", rot180_about_one),
    ("correct rotation but the 5 cell is erased", rot180_no_pivot_cell),
    ("rotate 180 about the 5 cell but leave the original shape in place too", rot180_keep_original),
    ("rotate the whole grid 180 about the grid center", rot180_whole_grid),
    ("correct output shifted one row down and one column right", out_shifted_down_right),
]


def valid(g, out):
    return (
        isinstance(g, list)
        and len(g) > 0
        and all(isinstance(r, list) and len(r) == len(g[0]) for r in g)
        and all(type(v) is int and 0 <= v <= 9 for r in g for v in r)
        and g != out
    )


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/90347967.json"))
    pairs = task["train"]
    print(f"{len(ALTERNATIVES)} readings, {len(pairs)} train pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and valid(g, p["output"]):
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
