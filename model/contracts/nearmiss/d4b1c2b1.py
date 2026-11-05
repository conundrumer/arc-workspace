import json
from collections import Counter
from pathlib import Path


def _scale(g, n):
    n = max(1, n)
    return [[v for v in row for _ in range(n)] for row in g for _ in range(n)]


def _ncol(g):
    return len({v for r in g for v in r})


def _guard(f):
    def w(inp, out):
        r = f(inp, out)
        if r is None or r == out:
            return None
        return r
    return w


@_guard
def scale_colors_plus_one(inp, out):
    return _scale(inp, _ncol(inp) + 1)


@_guard
def scale_colors_minus_one(inp, out):
    return _scale(inp, _ncol(inp) - 1)


@_guard
def scale_by_width(inp, out):
    return _scale(inp, len(inp[0]))


@_guard
def scale_by_max_row_colors(inp, out):
    return _scale(inp, max(len(set(r)) for r in inp))


@_guard
def transposed_tiles(inp, out):
    t = [list(r) for r in zip(*inp)]
    return _scale(t, _ncol(inp))


@_guard
def mirrored_tiles(inp, out):
    return _scale([r[::-1] for r in inp], _ncol(inp))


@_guard
def rotated_tiles(inp, out):
    r = [list(x) for x in zip(*inp[::-1])]
    return _scale(r, _ncol(inp))


@_guard
def tile_instead_of_scale(inp, out):
    n = _ncol(inp)
    return [list(row) * n for _ in range(n) for row in inp]


@_guard
def crop_last_row_col(inp, out):
    return [r[:-1] for r in out[:-1]]


@_guard
def swap_extreme_colors(inp, out):
    c = Counter(v for r in out for v in r).most_common()
    if len(c) < 2:
        return None
    a, b = c[0][0], c[-1][0]
    m = {a: b, b: a}
    return [[m.get(v, v) for v in r] for r in out]


@_guard
def kronecker_with_input(inp, out):
    bg = Counter(v for r in inp for v in r).most_common(1)[0][0]
    h, w = len(inp), len(inp[0])
    return [[inp[k][l] if inp[i][j] != bg else bg
             for j in range(w) for l in range(w)]
            for i in range(h) for k in range(h)]


@_guard
def scale_by_least_color_count(inp, out):
    c = Counter(v for r in inp for v in r)
    return _scale(inp, min(c.values()))


@_guard
def scale_by_colors_in_first_row(inp, out):
    return _scale(inp, len(set(inp[0])))


ALTERNATIVES = [
    ("scale factor is distinct colors plus one", scale_colors_plus_one),
    ("scale factor is distinct colors minus one", scale_colors_minus_one),
    ("scale factor is the grid width instead of the color count", scale_by_width),
    ("scale factor is the most distinct colors in any one row", scale_by_max_row_colors),
    ("input is transposed before scaling", transposed_tiles),
    ("input is mirrored left-right before scaling", mirrored_tiles),
    ("input is rotated 90 degrees before scaling", rotated_tiles),
    ("input is repeated as a whole (tiled) instead of each cell scaled", tile_instead_of_scale),
    ("output is cropped by one row and one column", crop_last_row_col),
    ("most and least frequent colors are swapped in the output", swap_extreme_colors),
    ("each non-background cell is replaced by a copy of the input (fractal)", kronecker_with_input),
    ("scale factor is the count of the rarest color", scale_by_least_color_count),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/d4b1c2b1.json").read_text())
    pairs = task["train"]
    for desc, f in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = f(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
