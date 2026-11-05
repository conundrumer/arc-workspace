import json
from pathlib import Path

INK, FILL = 1, 2


def _copy(g):
    return [row[:] for row in g]


def _cells(g, c):
    return [(r, k) for r, row in enumerate(g) for k, v in enumerate(row) if v == c]


def _bbox(cells):
    rs = [r for r, _ in cells]
    ks = [k for _, k in cells]
    return min(rs), max(rs), min(ks), max(ks)


def _recolor_fill(out, color):
    g = _copy(out)
    for r, k in _cells(out, FILL):
        g[r][k] = color
    return g


def fill_with_ink_color(inp, out):
    return _recolor_fill(out, INK)


def recolor_whole_figure(inp, out):
    g = _copy(out)
    for r, k in _cells(out, INK):
        g[r][k] = FILL
    return g


def fill_first_row_only(inp, out):
    cells = _cells(out, FILL)
    top = min(r for r, _ in cells)
    g = _copy(out)
    for r, k in cells:
        if r != top:
            g[r][k] = 0
    return g


def fill_leftmost_column_only(inp, out):
    cells = _cells(out, FILL)
    left = min(k for _, k in cells)
    g = _copy(out)
    for r, k in cells:
        if k != left:
            g[r][k] = 0
    return g


def fill_bbox_of_fill(inp, out):
    r0, r1, k0, k1 = _bbox(_cells(out, FILL))
    g = _copy(out)
    for r in range(r0, r1 + 1):
        for k in range(k0, k1 + 1):
            if g[r][k] == 0:
                g[r][k] = FILL
    return g


def fill_bbox_of_ink(inp, out):
    r0, r1, k0, k1 = _bbox(_cells(inp, INK))
    g = _copy(inp)
    for r in range(r0, r1 + 1):
        for k in range(k0, k1 + 1):
            if g[r][k] == 0:
                g[r][k] = FILL
    return g


def _mirror_fill(inp, f):
    r0, r1, k0, k1 = _bbox(_cells(inp, INK))
    g = _copy(inp)
    for r, k in _cells(inp, INK):
        nr, nk = f(r, k, r0, r1, k0, k1)
        if 0 <= nr < len(g) and 0 <= nk < len(g[0]) and g[nr][nk] == 0:
            g[nr][nk] = FILL
    return g


def mirror_horizontal_only(inp, out):
    return _mirror_fill(inp, lambda r, k, r0, r1, k0, k1: (r, k0 + k1 - k))


def point_reflection_only(inp, out):
    return _mirror_fill(inp, lambda r, k, r0, r1, k0, k1: (r0 + r1 - r, k0 + k1 - k))


def transpose_only(inp, out):
    def f(r, k, r0, r1, k0, k1):
        return r0 + (k - k0), k0 + (r - r0)
    return _mirror_fill(inp, f)


def fill_shifted_right(inp, out):
    g = _copy(inp)
    for r, k in _cells(out, FILL):
        if k + 1 < len(g[0]) and g[r][k + 1] == 0:
            g[r][k + 1] = FILL
    return g


def crop_to_figure(inp, out):
    r0, r1, k0, k1 = _bbox(_cells(out, INK) + _cells(out, FILL))
    return [row[k0:k1 + 1] for row in out[r0:r1 + 1]]


ALTERNATIVES = [
    ("fill the missing cells with the ink color 1 instead of 2", fill_with_ink_color),
    ("recolor the whole figure to 2, not only the restored cells", recolor_whole_figure),
    ("restore only the top row of missing cells", fill_first_row_only),
    ("restore only the leftmost column of missing cells", fill_leftmost_column_only),
    ("fill every empty cell in the bounding box of the missing cells", fill_bbox_of_fill),
    ("fill every empty cell in the bounding box of the figure", fill_bbox_of_ink),
    ("complete the figure by a left-right mirror about its bounding box only", mirror_horizontal_only),
    ("complete the figure by a 180-degree turn about its bounding box center only", point_reflection_only),
    ("complete the figure by a main-diagonal reflection about its bounding box only", transpose_only),
    ("restored cells land one column to the right of the right place", fill_shifted_right),
    ("output is the figure's bounding box crop, not the full grid", crop_to_figure),
]


def _valid(g):
    return (
        isinstance(g, list) and g and all(isinstance(r, list) for r in g)
        and len({len(r) for r in g}) == 1 and len(g[0]) > 0
        and all(type(v) is int and 0 <= v <= 9 for r in g for v in r)
    )


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/1b60fb0c.json").read_text())
    train = task["train"]
    print("task 1b60fb0c, pairs:", len(train))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in train:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(f"{n}/{len(train)}  {desc}")
