import json
from collections import Counter
from pathlib import Path

FILL = 8


def _bg(inp):
    return Counter(v for r in inp for v in r).most_common(1)[0][0]


def _comps(inp):
    bg = _bg(inp)
    h, w = len(inp), len(inp[0])
    seen = set()
    res = []
    for i in range(h):
        for j in range(w):
            if inp[i][j] == bg or (i, j) in seen:
                continue
            stack = [(i, j)]
            seen.add((i, j))
            cells = []
            while stack:
                a, b = stack.pop()
                cells.append((a, b))
                for da, db in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    x, y = a + da, b + db
                    if 0 <= x < h and 0 <= y < w and (x, y) not in seen and inp[x][y] != bg:
                        seen.add((x, y))
                        stack.append((x, y))
            rs = [c[0] for c in cells]
            cs = [c[1] for c in cells]
            res.append({"cells": cells, "box": (min(rs), min(cs), max(rs), max(cs)),
                        "color": inp[cells[0][0]][cells[0][1]]})
    return res


def _copy(g):
    return [list(r) for r in g]


def _paint(inp, rects, color=FILL, base=None):
    g = _copy(base if base is not None else inp)
    h, w = len(g), len(g[0])
    for (r0, c0, r1, c1) in rects:
        for i in range(max(r0, 0), min(r1, h - 1) + 1):
            for j in range(max(c0, 0), min(c1, w - 1) + 1):
                g[i][j] = color
    return g


def _inner(box, k=1):
    r0, c0, r1, c1 = box
    return (r0 + k, c0 + k, r1 - k, c1 - k)


def wrong_color(inp, out):
    return [[5 if v == FILL else v for v in r] for r in out]


def fill_whole_box(inp, out):
    return _paint(inp, [c["box"] for c in _comps(inp)])


def largest_only(inp, out):
    cs = _comps(inp)
    big = max(cs, key=lambda c: len(c["cells"]))
    return _paint(inp, [_inner(big["box"])])


def skip_smallest(inp, out):
    cs = _comps(inp)
    small = min(cs, key=lambda c: len(c["cells"]))
    return _paint(inp, [_inner(c["box"]) for c in cs if c is not small])


def erode_two(inp, out):
    return _paint(inp, [_inner(c["box"], 2) for c in _comps(inp)])


def one_big_object(inp, out):
    cs = _comps(inp)
    r0 = min(c["box"][0] for c in cs)
    c0 = min(c["box"][1] for c in cs)
    r1 = max(c["box"][2] for c in cs)
    c1 = max(c["box"][3] for c in cs)
    return _paint(inp, [_inner((r0, c0, r1, c1))])


def horizontal_only(inp, out):
    rects = [(c["box"][0], c["box"][1] + 1, c["box"][2], c["box"][3] - 1) for c in _comps(inp)]
    return _paint(inp, rects)


def hollow_interior(inp, out):
    return _paint(inp, [_inner(c["box"]) for c in _comps(inp)], color=_bg(inp))


def shifted_interior(inp, out):
    rects = []
    for c in _comps(inp):
        r0, c0, r1, c1 = _inner(c["box"])
        rects.append((r0 + 1, c0 + 1, r1 + 1, c1 + 1))
    return _paint(inp, rects)


def outline_filled(inp, out):
    g = _copy(inp)
    for c in _comps(inp):
        r0, c0, r1, c1 = c["box"]
        for (i, j) in c["cells"]:
            if i in (r0, r1) or j in (c0, c1):
                g[i][j] = FILL
    return g


def only_color_two(inp, out):
    return _paint(inp, [_inner(c["box"]) for c in _comps(inp) if c["color"] == 2])


def unchanged(inp, out):
    return _copy(inp)


ALTERNATIVES = [
    ("fill color 5 instead of 8", wrong_color),
    ("fill whole bounding box including border", fill_whole_box),
    ("fill only the largest object", largest_only),
    ("leave the smallest object unfilled", skip_smallest),
    ("erode two cells instead of one", erode_two),
    ("treat all objects as one and fill the interior of their joint box", one_big_object),
    ("fill only horizontally inside, keeping top and bottom border rows too", horizontal_only),
    ("clear the interior to background", hollow_interior),
    ("interior box shifted one down and right", shifted_interior),
    ("paint the border instead of the interior", outline_filled),
    ("fill only color-2 objects", only_color_two),
    ("return the input unchanged", unchanged),
]


def _valid(g, out):
    return (isinstance(g, list) and g and all(isinstance(r, list) and len(r) == len(g[0]) for r in g)
            and all(type(v) is int and 0 <= v <= 9 for r in g for v in r) and g != out)


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/50cb2852.json'))
    pairs = task["train"]
    print("pairs", len(pairs))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g, p["output"]):
                n += 1
        print(n, desc)
