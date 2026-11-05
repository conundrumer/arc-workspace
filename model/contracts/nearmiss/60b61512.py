import json
from pathlib import Path

FILL = 7


def _copy(g):
    return [row[:] for row in g]


def _components(inp, diag=True):
    h, w = len(inp), len(inp[0])
    seen = set()
    comps = []
    if diag:
        steps = [(a, b) for a in (-1, 0, 1) for b in (-1, 0, 1) if (a, b) != (0, 0)]
    else:
        steps = [(-1, 0), (1, 0), (0, -1), (0, 1)]
    for r in range(h):
        for c in range(w):
            if inp[r][c] != 0 and (r, c) not in seen:
                stack = [(r, c)]
                seen.add((r, c))
                cells = []
                while stack:
                    y, x = stack.pop()
                    cells.append((y, x))
                    for dy, dx in steps:
                        ny, nx = y + dy, x + dx
                        if 0 <= ny < h and 0 <= nx < w and inp[ny][nx] != 0 and (ny, nx) not in seen:
                            seen.add((ny, nx))
                            stack.append((ny, nx))
                comps.append(cells)
    return comps


def _bbox(cells):
    ys = [p[0] for p in cells]
    xs = [p[1] for p in cells]
    return min(ys), min(xs), max(ys), max(xs)


def _fill_boxes(inp, boxes, color=FILL, grow=0):
    g = _copy(inp)
    h, w = len(g), len(g[0])
    for (r0, c0, r1, c1) in boxes:
        for r in range(max(0, r0 - grow), min(h - 1, r1 + grow) + 1):
            for c in range(max(0, c0 - grow), min(w - 1, c1 + grow) + 1):
                if g[r][c] == 0:
                    g[r][c] = color
    return g


def _boxes(inp, diag=True):
    return [_bbox(c) for c in _components(inp, diag)]


def wrong_color(inp, out):
    return [[8 if v == FILL else v for v in row] for row in out]


def object_color_fill(inp, out):
    return _fill_boxes(inp, _boxes(inp), color=4)


def only_first_object(inp, out):
    comps = sorted(_components(inp), key=lambda c: _bbox(c)[:2])
    return _fill_boxes(inp, [_bbox(comps[0])])


def only_largest_object(inp, out):
    comps = _components(inp)
    big = max(comps, key=lambda c: (len(c), -_bbox(c)[0]))
    return _fill_boxes(inp, [_bbox(big)])


def grown_box(inp, out):
    return _fill_boxes(inp, _boxes(inp), grow=1)


def row_span_only(inp, out):
    g = _copy(inp)
    for (r0, c0, r1, c1) in _boxes(inp):
        for r in range(r0, r1 + 1):
            xs = [c for c in range(c0, c1 + 1) if inp[r][c] != 0]
            if xs:
                for c in range(min(xs), max(xs) + 1):
                    if g[r][c] == 0:
                        g[r][c] = FILL
    return g


def col_span_only(inp, out):
    g = _copy(inp)
    for (r0, c0, r1, c1) in _boxes(inp):
        for c in range(c0, c1 + 1):
            ys = [r for r in range(r0, r1 + 1) if inp[r][c] != 0]
            if ys:
                for r in range(min(ys), max(ys) + 1):
                    if g[r][c] == 0:
                        g[r][c] = FILL
    return g


def one_global_box(inp, out):
    cells = [(r, c) for r, row in enumerate(inp) for c, v in enumerate(row) if v != 0]
    return _fill_boxes(inp, [_bbox(cells)])


def box_missing_last_row(inp, out):
    return _fill_boxes(inp, [(r0, c0, max(r0, r1 - 1), c1) for (r0, c0, r1, c1) in _boxes(inp)])


def recolor_objects(inp, out):
    return [[FILL if v == 4 else (0 if v == FILL else v) for v in row] for row in out]


def whole_box_filled(inp, out):
    g = _copy(inp)
    for (r0, c0, r1, c1) in _boxes(inp):
        for r in range(r0, r1 + 1):
            for c in range(c0, c1 + 1):
                g[r][c] = FILL
    return g


def skip_last_object(inp, out):
    comps = sorted(_components(inp), key=lambda c: _bbox(c)[:2])
    if len(comps) < 2:
        return None
    return _fill_boxes(inp, [_bbox(c) for c in comps[:-1]])


ALTERNATIVES = [
    ("fill color 8 instead of 7", wrong_color),
    ("fill the box gaps with the object color instead of a new color", object_color_fill),
    ("fill only the top-most object's box", only_first_object),
    ("fill only the largest object's box", only_largest_object),
    ("box grown by one cell on every side", grown_box),
    ("fill gaps only between the leftmost and rightmost object cell of each row", row_span_only),
    ("fill gaps only between the top and bottom object cell of each column", col_span_only),
    ("one box around all objects together", one_global_box),
    ("box one row short at the bottom", box_missing_last_row),
    ("recolor the object cells with the fill color and leave the gaps empty", recolor_objects),
    ("paint the whole box, object cells included, with the fill color", whole_box_filled),
    ("fill every object's box except the last object's", skip_last_object),
]


def _valid(g, out):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) for r in g):
        return False
    if len({len(r) for r in g}) != 1 or len(g[0]) == 0:
        return False
    if not all(type(v) is int and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/60b61512.json").read_text())
    train = task["train"]
    print(f"{len(ALTERNATIVES)} readings, {len(train)} train pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in train:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g, p["output"]):
                n += 1
        print(f"{n}/{len(train)}  {desc}")
