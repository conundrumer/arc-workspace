import json
from collections import Counter
from pathlib import Path


def _info(inp):
    cells = Counter(v for r in inp for v in r)
    bg = cells.most_common(1)[0][0]
    cols = []  # (color, ink count, bbox side, first appearance)
    seen = {}
    for i, r in enumerate(inp):
        for j, v in enumerate(r):
            if v != bg and v not in seen:
                seen[v] = (i, j)
    for c, pos in seen.items():
        pts = [(i, j) for i, r in enumerate(inp) for j, v in enumerate(r) if v == c]
        h = max(p[0] for p in pts) - min(p[0] for p in pts) + 1
        w = max(p[1] for p in pts) - min(p[1] for p in pts) + 1
        n = len(pts)
        side = int(round(n ** 0.5))
        cols.append({"c": c, "n": n, "side": side, "bbox": max(h, w), "first": pos})
    return bg, cols


def _build(bg, items, gap=1, align="bottom", extra_rows=0):
    """items: list of (color, side) left to right."""
    h = max(s for _, s in items)
    w = sum(s for _, s in items) + gap * (len(items) - 1)
    g = [[bg] * w for _ in range(h)]
    x = 0
    for c, s in items:
        top = h - s if align == "bottom" else 0
        for i in range(top, top + s):
            for j in range(x, x + s):
                g[i][j] = c
        x += s + gap
    return [[bg] * w for _ in range(extra_rows)] + g


def _true_items(inp):
    bg, cols = _info(inp)
    cols = sorted(cols, key=lambda d: d["side"])
    return bg, cols


def descending(inp, out):
    bg, cols = _true_items(inp)
    return _build(bg, [(d["c"], d["side"]) for d in reversed(cols)])


def top_aligned(inp, out):
    bg, cols = _true_items(inp)
    return _build(bg, [(d["c"], d["side"]) for d in cols], align="top")


def no_gap(inp, out):
    bg, cols = _true_items(inp)
    return _build(bg, [(d["c"], d["side"]) for d in cols], gap=0)


def wide_gap(inp, out):
    bg, cols = _true_items(inp)
    return _build(bg, [(d["c"], d["side"]) for d in cols], gap=2)


def bbox_side(inp, out):
    bg, cols = _info(inp)
    cols = sorted(cols, key=lambda d: d["bbox"])
    return _build(bg, [(d["c"], d["bbox"]) for d in cols])


def side_off_by_one(inp, out):
    bg, cols = _true_items(inp)
    return _build(bg, [(d["c"], d["side"] - 1) for d in cols if d["side"] > 1] or None) \
        if any(d["side"] > 1 for d in cols) else None


def hollow(inp, out):
    bg, cols = _true_items(inp)
    g = _build(bg, [(d["c"], d["side"]) for d in cols])
    h = len(g)
    x = 0
    for d in cols:
        s = d["side"]
        top = h - s
        for i in range(top + 1, top + s - 1):
            for j in range(x + 1, x + s - 1):
                g[i][j] = bg
        x += s + 1
    return g


def input_order(inp, out):
    bg, cols = _info(inp)
    cols = sorted(cols, key=lambda d: d["first"])
    return _build(bg, [(d["c"], d["side"]) for d in cols])


def transposed(inp, out):
    return [list(r) for r in zip(*out)]


def colors_reversed(inp, out):
    bg, cols = _true_items(inp)
    cs = [d["c"] for d in reversed(cols)]
    return _build(bg, [(c, d["side"]) for c, d in zip(cs, cols)])


def extra_row(inp, out):
    bg, cols = _true_items(inp)
    return _build(bg, [(d["c"], d["side"]) for d in cols], extra_rows=1)


def drop_last_col(inp, out):
    return [list(r[:-1]) for r in out]


ALTERNATIVES = [
    ("squares ordered largest first instead of smallest first", descending),
    ("squares aligned to the top edge instead of the bottom edge", top_aligned),
    ("squares packed with no gap between them", no_gap),
    ("squares separated by a gap of two columns", wide_gap),
    ("square side taken from the bounding box of the color, not from its pixel count", bbox_side),
    ("square side one less than the root of the pixel count", side_off_by_one),
    ("squares drawn as hollow frames", hollow),
    ("squares ordered by first appearance in the input", input_order),
    ("squares stacked top to bottom instead of left to right", transposed),
    ("sizes in the right order but colors assigned in reverse order", colors_reversed),
    ("canvas has one extra background row on top", extra_row),
    ("output cropped one column short at the right edge", drop_last_col),
]


def _valid(g):
    return (
        isinstance(g, list) and len(g) > 0
        and all(isinstance(r, list) and len(r) == len(g[0]) and len(r) > 0 for r in g)
        and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r)
    )


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/8abad3cf.json").read_text())
    pairs = task["train"]
    print("pairs", len(pairs))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(n, desc)
