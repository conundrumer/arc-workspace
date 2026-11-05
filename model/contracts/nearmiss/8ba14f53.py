"""Near-miss readings for ARC task 8ba14f53.

True rule: the input holds a few hollow shapes of different colors on a 0
background. Each shape contributes as many cells as it encloses (0 cells that
the grid edge cannot reach). The 3x3 output is filled in row-major order from
the top-left, shapes taken left to right; each shape starts on a fresh row.
"""
import json
from pathlib import Path


def _shapes(inp):
    """List of dicts (color, cells, minc, enclosed, bbox_bg), left to right."""
    h, w = len(inp), len(inp[0])
    by = {}
    for r in range(h):
        for c in range(w):
            if inp[r][c]:
                by.setdefault(inp[r][c], []).append((r, c))
    res = []
    for col, cells in by.items():
        # flood bg-or-other cells from the border
        seen = set()
        stack = [(r, c) for r in range(h) for c in range(w)
                 if (r in (0, h - 1) or c in (0, w - 1)) and inp[r][c] != col]
        while stack:
            r, c = stack.pop()
            if (r, c) in seen or inp[r][c] == col:
                continue
            seen.add((r, c))
            for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nr, nc = r + dr, c + dc
                if 0 <= nr < h and 0 <= nc < w and (nr, nc) not in seen:
                    stack.append((nr, nc))
        enclosed = sum(1 for r in range(h) for c in range(w)
                       if inp[r][c] != col and (r, c) not in seen)
        r0 = min(r for r, _ in cells); r1 = max(r for r, _ in cells)
        c0 = min(c for _, c in cells); c1 = max(c for _, c in cells)
        bbox_bg = sum(1 for r in range(r0, r1 + 1) for c in range(c0, c1 + 1)
                      if inp[r][c] == 0)
        res.append(dict(color=col, area=len(cells), minc=c0, enclosed=enclosed,
                        bbox_bg=bbox_bg))
    res.sort(key=lambda s: s["minc"])
    return res


def _render(items, size=3, pad_rows=True, order="row"):
    """items: list of (color, count). Row-major fill, each item on a fresh row."""
    g = [[0] * size for _ in range(size)]
    pos = 0
    for col, n in items:
        if pad_rows and pos % size:
            pos += size - pos % size
        for k in range(n):
            p = pos + k
            if p >= size * size:
                break
            r, c = divmod(p, size)
            if order == "col":
                r, c = c, r
            g[r][c] = col
        pos += n
    return g


def _true(inp):
    return _render([(s["color"], s["enclosed"]) for s in _shapes(inp)])


def packed(inp, out):
    return _render([(s["color"], s["enclosed"]) for s in _shapes(inp)], pad_rows=False)


def right_first(inp, out):
    sh = _shapes(inp)[::-1]
    return _render([(s["color"], s["enclosed"]) for s in sh])


def by_count(inp, out):
    sh = sorted(_shapes(inp), key=lambda s: -s["enclosed"])
    return _render([(s["color"], s["enclosed"]) for s in sh])


def column_major(inp, out):
    return _render([(s["color"], s["enclosed"]) for s in _shapes(inp)], order="col")


def flip_rows(inp, out):
    return [row[:] for row in out[::-1]]


def flip_cols(inp, out):
    return [row[::-1] for row in out]


def area_count(inp, out):
    return _render([(s["color"], s["area"]) for s in _shapes(inp)])


def bbox_bg_count(inp, out):
    return _render([(s["color"], s["bbox_bg"]) for s in _shapes(inp)])


def plus_one(inp, out):
    return _render([(s["color"], s["enclosed"] + 1) for s in _shapes(inp)])


def minus_one(inp, out):
    return _render([(s["color"], max(s["enclosed"] - 1, 0)) for s in _shapes(inp)])


def first_shape_only(inp, out):
    return _render([(s["color"], s["enclosed"]) for s in _shapes(inp)[:1]])


def swap_colors(inp, out):
    cols = sorted({v for row in out for v in row if v})
    if len(cols) != 2:
        return None
    a, b = cols
    return [[b if v == a else a if v == b else v for v in row] for row in out]


def whole_rows(inp, out):
    items = [(s["color"], -(-s["enclosed"] // 3) * 3) for s in _shapes(inp)]
    return _render(items)


def single_color(inp, out):
    sh = _shapes(inp)
    return _render([(sh[0]["color"], s["enclosed"]) for s in sh], pad_rows=False)


ALTERNATIVES = [
    ("shapes packed back to back, the next shape does not start on a fresh row", packed),
    ("shapes taken right to left instead of left to right", right_first),
    ("shapes ordered by enclosed count, largest first, instead of by position", by_count),
    ("fill goes down columns instead of along rows", column_major),
    ("fill starts at the bottom-left corner (output flipped vertically)", flip_rows),
    ("fill starts at the top-right corner (output flipped horizontally)", flip_cols),
    ("cell count is the shape's total area, not its enclosed cells", area_count),
    ("cell count is the 0 cells inside the bounding box, including notches open to the edge", bbox_bg_count),
    ("each shape gets one cell more than it encloses", plus_one),
    ("each shape gets one cell fewer than it encloses", minus_one),
    ("only the leftmost shape is drawn", first_shape_only),
    ("the two shape colors are swapped", swap_colors),
    ("each shape fills whole rows, rounding its count up to a multiple of 3", whole_rows),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9
                    for r in g for v in r))


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/8ba14f53.json"))
    train = task["train"]
    # sanity: the model of the true rule reproduces every train output
    assert all(_true(p["input"]) == p["output"] for p in train), "true rule mismatch"
    print(f"{len(ALTERNATIVES)} readings, {len(train)} train pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in train:
            try:
                g = fn(p["input"], p["output"])
            except Exception as e:
                print("  error:", desc, e)
                g = None
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(f"{n}/{len(train)}  {desc}")
