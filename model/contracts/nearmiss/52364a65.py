import json
from collections import Counter
from pathlib import Path


def _bg(g):
    return Counter(v for r in g for v in r).most_common(1)[0][0]


def _boxes(g, bg):
    box = {}
    for r, row in enumerate(g):
        for c, v in enumerate(row):
            if v == bg:
                continue
            b = box.setdefault(v, [r, r, c, c])
            b[0] = min(b[0], r)
            b[1] = max(b[1], r)
            b[2] = min(b[2], c)
            b[3] = max(b[3], c)
    return box


def _peel(g, side, depth, fill=None, only=None, bbox=None):
    bg = _bg(g)
    fill = bg if fill is None else fill
    boxes = _boxes(g, bg)
    res = [row[:] for row in g]
    for r, row in enumerate(g):
        for c, v in enumerate(row):
            if v == bg:
                continue
            if only is not None and not only(v, boxes):
                continue
            r0, r1, c0, c1 = bbox if bbox else boxes[v]
            if side == "left":
                hit = c - c0 < depth
            elif side == "right":
                hit = c1 - c < depth
            elif side == "top":
                hit = r - r0 < depth
            else:
                hit = r1 - r < depth
            if hit:
                res[r][c] = fill
    return res


def peel_right(inp, out):
    return _peel(inp, "right", 2)


def peel_one(inp, out):
    return _peel(inp, "left", 1)


def peel_three(inp, out):
    return _peel(inp, "left", 3)


def peel_top(inp, out):
    return _peel(inp, "top", 2)


def peel_grid_edge(inp, out):
    bg = _bg(inp)
    return [[bg if c < 2 else v for c, v in enumerate(row)] for row in inp]


def peel_union_box(inp, out):
    bg = _bg(inp)
    boxes = _boxes(inp, bg).values()
    u = (min(b[0] for b in boxes), max(b[1] for b in boxes),
         min(b[2] for b in boxes), max(b[3] for b in boxes))
    return _peel(inp, "left", 2, bbox=u)


def peel_zero_fill(inp, out):
    bg = _bg(inp)
    return _peel(inp, "left", 2, fill=0 if bg != 0 else 1)


def peel_per_row(inp, out):
    bg = _bg(inp)
    res = [row[:] for row in inp]
    for row in res:
        idx = [c for c, v in enumerate(row) if v != bg]
        for c in idx[:2]:
            row[c] = bg
    return res


def peel_count_depth(inp, out):
    bg = _bg(inp)
    n = len(_boxes(inp, bg))
    return _peel(inp, "left", n)


def peel_wide_only(inp, out):
    return _peel(inp, "left", 2, only=lambda v, b: b[v][3] - b[v][2] + 1 > 2)


def peel_first_object(inp, out):
    first = min(_boxes(inp, _bg(inp)).items(), key=lambda kv: (kv[1][0], kv[1][2]))[0]
    return _peel(inp, "left", 2, only=lambda v, b: v == first)


def out_unfilled(inp, out):
    """True output with the topmost object left unpeeled."""
    bg = _bg(inp)
    boxes = _boxes(inp, bg)
    first = min(boxes.items(), key=lambda kv: (kv[1][0], kv[1][2]))[0]
    res = [row[:] for row in out]
    for r, row in enumerate(inp):
        for c, v in enumerate(row):
            if v == first:
                res[r][c] = v
    return res


ALTERNATIVES = [
    ("peel the rightmost two columns of each object instead of the leftmost", peel_right),
    ("peel only one column from the left of each object", peel_one),
    ("peel three columns from the left of each object", peel_three),
    ("peel the top two rows of each object instead of left columns", peel_top),
    ("peel the two leftmost grid columns, not each object's own leftmost columns", peel_grid_edge),
    ("peel two columns from the left of the union box of all objects", peel_union_box),
    ("peeled cells filled with a non-background color", peel_zero_fill),
    ("remove the first two object cells of every row, not whole bbox columns", peel_per_row),
    ("peel depth equals the number of objects instead of the tile count", peel_count_depth),
    ("objects not wider than the depth are left untouched", peel_wide_only),
    ("only the topmost object is peeled", peel_first_object),
    ("topmost object is skipped, all others peeled", out_unfilled),
]


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/52364a65.json").read_text())
    train = task["train"]
    for desc, fn in ALTERNATIVES:
        ok = 0
        for p in train:
            g = fn(p["input"], p["output"])
            if g is None:
                continue
            if (g and all(isinstance(r, list) and len(r) == len(g[0]) for r in g)
                    and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r)
                    and g != p["output"]):
                ok += 1
        print(f"{ok}/{len(train)}  {desc}")
