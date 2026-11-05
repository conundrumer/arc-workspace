import json
from pathlib import Path


def _ink(inp):
    for r in inp:
        for v in r:
            if v != 0:
                return v
    return None


def _blank(h, w, v=0):
    return [[v] * w for _ in range(h)]


def _ring(h, w, c, inner=0):
    g = _blank(h, w, inner)
    for i in range(h):
        for j in range(w):
            if i in (0, h - 1) or j in (0, w - 1):
                g[i][j] = c
    return g


def solid_fill(inp, out):
    c = _ink(inp)
    return _blank(len(inp), len(inp[0]), c)


def inverted(inp, out):
    c = _ink(inp)
    return _ring(len(inp), len(inp[0]), 0, c)


def top_bottom_only(inp, out):
    h, w, c = len(inp), len(inp[0]), _ink(inp)
    g = _blank(h, w)
    for j in range(w):
        g[0][j] = c
        g[h - 1][j] = c
    return g


def left_right_only(inp, out):
    h, w, c = len(inp), len(inp[0]), _ink(inp)
    g = _blank(h, w)
    for i in range(h):
        g[i][0] = c
        g[i][w - 1] = c
    return g


def inset_ring(inp, out):
    h, w, c = len(inp), len(inp[0]), _ink(inp)
    g = _blank(h, w)
    for i in range(1, h - 1):
        for j in range(1, w - 1):
            if i in (1, h - 2) or j in (1, w - 2):
                g[i][j] = c
    return g


def one_smaller(inp, out):
    h, w, c = len(inp) - 1, len(inp[0]) - 1, _ink(inp)
    return _ring(h, w, c)


def one_larger(inp, out):
    h, w, c = len(inp) + 1, len(inp[0]) + 1, _ink(inp)
    return _ring(h, w, c)


def keep_center(inp, out):
    g = [r[:] for r in out]
    for i, r in enumerate(inp):
        for j, v in enumerate(r):
            if v != 0:
                g[i][j] = v
    return g


def corners_missing(inp, out):
    g = [r[:] for r in out]
    h, w = len(g), len(g[0])
    for i, j in ((0, 0), (0, w - 1), (h - 1, 0), (h - 1, w - 1)):
        g[i][j] = 0
    return g


def fixed_color(inp, out):
    return _ring(len(inp), len(inp[0]), 5)


def top_left_only(inp, out):
    h, w, c = len(inp), len(inp[0]), _ink(inp)
    g = _blank(h, w)
    for j in range(w):
        g[0][j] = c
    for i in range(h):
        g[i][0] = c
    return g


def transposed_size(inp, out):
    h, w, c = len(inp), len(inp[0]), _ink(inp)
    return _ring(w, h, c)


ALTERNATIVES = [
    ("fills the whole grid with the ink color instead of leaving the interior empty", solid_fill),
    ("swaps colors: ink fills the interior and the border is background", inverted),
    ("draws only the top and bottom rows", top_bottom_only),
    ("draws only the left and right columns", left_right_only),
    ("draws the ring one cell inside the grid edge", inset_ring),
    ("ring in a grid one row and one column smaller", one_smaller),
    ("ring in a grid one row and one column larger", one_larger),
    ("keeps the input's ink cell in the interior", keep_center),
    ("leaves the four corner cells empty", corners_missing),
    ("draws the ring in a fixed color 5 instead of the ink color", fixed_color),
    ("draws only the top row and left column", top_left_only),
    ("ring in a transposed (width by height) grid", transposed_size),
]


def _valid(g):
    return (
        isinstance(g, list) and g and all(isinstance(r, list) for r in g)
        and len({len(r) for r in g}) == 1 and len(g[0]) > 0
        and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r)
    )


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/fc754716.json'))
    train = task["train"]
    print(len(ALTERNATIVES), "readings,", len(train), "pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in train:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(n, desc)
