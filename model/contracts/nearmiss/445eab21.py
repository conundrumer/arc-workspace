import json
from collections import Counter
from pathlib import Path


def _boxes(inp):
    bg = Counter(c for r in inp for c in r).most_common(1)[0][0]
    pos = {}
    for y, r in enumerate(inp):
        for x, c in enumerate(r):
            if c != bg:
                pos.setdefault(c, []).append((y, x))
    res = {}
    for c, ps in pos.items():
        y0 = min(p[0] for p in ps); y1 = max(p[0] for p in ps)
        x0 = min(p[1] for p in ps); x1 = max(p[1] for p in ps)
        h, w = y1 - y0 + 1, x1 - x0 + 1
        res[c] = dict(y0=y0, y1=y1, x0=x0, x1=x1, h=h, w=w,
                      inner=max(h - 2, 0) * max(w - 2, 0))
    return bg, res


def _winner(inp):
    bg, b = _boxes(inp)
    return max(b, key=lambda c: b[c]["inner"])


def _fill(h, w, c):
    return [[c] * w for _ in range(h)]


def smallest_box(inp, out):
    bg, b = _boxes(inp)
    return _fill(2, 2, min(b, key=lambda c: b[c]["inner"]))


def lowest_color(inp, out):
    bg, b = _boxes(inp)
    return _fill(2, 2, min(b))


def topmost_box(inp, out):
    bg, b = _boxes(inp)
    return _fill(2, 2, min(b, key=lambda c: b[c]["y0"]))


def one_by_one(inp, out):
    return _fill(1, 1, _winner(inp))


def three_by_three(inp, out):
    return _fill(3, 3, _winner(inp))


def two_by_one(inp, out):
    return _fill(2, 1, _winner(inp))


def one_by_two(inp, out):
    return _fill(1, 2, _winner(inp))


def background_fill(inp, out):
    bg, b = _boxes(inp)
    return _fill(2, 2, bg)


def winner_bbox_filled(inp, out):
    bg, b = _boxes(inp)
    c = _winner(inp)
    return _fill(b[c]["h"], b[c]["w"], c)


def winner_interior_filled(inp, out):
    bg, b = _boxes(inp)
    c = _winner(inp)
    return _fill(b[c]["h"] - 2, b[c]["w"] - 2, c)


def winner_crop(inp, out):
    bg, b = _boxes(inp)
    c = _winner(inp)
    d = b[c]
    return [r[d["x0"]:d["x1"] + 1] for r in inp[d["y0"]:d["y1"] + 1]]


ALTERNATIVES = [
    ("2x2 of the color of the box with the smallest interior", smallest_box),
    ("2x2 of the lowest-numbered non-background color", lowest_color),
    ("2x2 of the color of the topmost box", topmost_box),
    ("1x1 of the winning color", one_by_one),
    ("3x3 of the winning color", three_by_three),
    ("2 rows by 1 column of the winning color", two_by_one),
    ("1 row by 2 columns of the winning color", one_by_two),
    ("2x2 of the background color", background_fill),
    ("winning box's full bounding box filled with its color", winner_bbox_filled),
    ("winning box's interior size filled with its color", winner_interior_filled),
    ("crop of the winning box from the input", winner_crop),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/445eab21.json").read_text())
    train = task["train"]
    print("pairs", len(train))
    for desc, f in ALTERNATIVES:
        n = 0
        for p in train:
            g = f(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(n, desc)
