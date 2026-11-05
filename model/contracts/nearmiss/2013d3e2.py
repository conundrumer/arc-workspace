import json
from collections import Counter
from pathlib import Path


def _bg(inp):
    return Counter(c for r in inp for c in r).most_common(1)[0][0]


def _bbox(inp):
    bg = _bg(inp)
    cells = [(i, j) for i, r in enumerate(inp) for j, c in enumerate(r) if c != bg]
    r0 = min(i for i, _ in cells)
    r1 = max(i for i, _ in cells)
    c0 = min(j for _, j in cells)
    c1 = max(j for _, j in cells)
    return r0, r1, c0, c1


def _crop(inp, r, c, h, w):
    bg = _bg(inp)
    H, W = len(inp), len(inp[0])
    return [[inp[i][j] if 0 <= i < H and 0 <= j < W else bg
             for j in range(c, c + w)] for i in range(r, r + h)]


def _quadrant(inp, which):
    r0, r1, c0, c1 = _bbox(inp)
    h, w = r1 - r0 + 1, c1 - c0 + 1
    hh, hw = h // 2, w // 2
    r = r0 if which in ("TL", "TR") else r0 + h - hh
    c = c0 if which in ("TL", "BL") else c0 + w - hw
    return _crop(inp, r, c, hh, hw)


def top_right(inp, out):
    return _quadrant(inp, "TR")


def bottom_left(inp, out):
    return _quadrant(inp, "BL")


def bottom_right(inp, out):
    return _quadrant(inp, "BR")


def centre_window(inp, out):
    r0, r1, c0, c1 = _bbox(inp)
    return _crop(inp, r0 + 1, c0 + 1, len(out), len(out[0]))


def whole_box(inp, out):
    r0, r1, c0, c1 = _bbox(inp)
    return _crop(inp, r0, c0, r1 - r0 + 1, c1 - c0 + 1)


def quadrant_plus_one(inp, out):
    r0, r1, c0, c1 = _bbox(inp)
    return _crop(inp, r0, c0, len(out) + 1, len(out[0]) + 1)


def quadrant_minus_one(inp, out):
    r0, r1, c0, c1 = _bbox(inp)
    return _crop(inp, r0, c0, len(out) - 1, len(out[0]) - 1)


def shifted_up_left(inp, out):
    r0, r1, c0, c1 = _bbox(inp)
    return _crop(inp, r0 - 1, c0 - 1, len(out), len(out[0]))


def vertical_flip(inp, out):
    return [list(r) for r in reversed(out)]


def centre_cell_blank(inp, out):
    g = [list(r) for r in out]
    g[-1][-1] = _bg(inp)
    return g


def grid_corner(inp, out):
    return _crop(inp, 0, 0, len(out), len(out[0]))


ALTERNATIVES = [
    ("take the top-right quadrant of the object box", top_right),
    ("take the bottom-left quadrant of the object box", bottom_left),
    ("take the bottom-right quadrant of the object box", bottom_right),
    ("take the 3x3 window one cell inside the object box corner", centre_window),
    ("output the whole object box without reducing it", whole_box),
    ("take a quadrant one row and column too large", quadrant_plus_one),
    ("take a quadrant one row and column too small", quadrant_minus_one),
    ("take the quadrant window one cell up and left of the object box", shifted_up_left),
    ("take the right quadrant but flip it top to bottom", vertical_flip),
    ("take the right quadrant but blank the innermost cell", centre_cell_blank),
    ("take the top-left corner of the input grid, not of the object box", grid_corner),
]


def _valid(g, out):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(c, int) and 0 <= c <= 9 for r in g for c in r)
            and g != out)


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/2013d3e2.json").read_text())
    pairs = task["train"]
    print("pairs", len(pairs))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g, p["output"]):
                n += 1
        print(n, desc)
