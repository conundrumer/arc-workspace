import json
from collections import Counter
from pathlib import Path


def _bg(inp):
    return Counter(c for r in inp for c in r).most_common(1)[0][0]


def _box(inp, ignore=None):
    bg = _bg(inp)
    cells = [(i, j) for i, r in enumerate(inp) for j, c in enumerate(r)
             if c != bg and (ignore is None or c not in ignore)]
    if not cells:
        return None
    rs = [i for i, _ in cells]
    cs = [j for _, j in cells]
    return min(rs), max(rs), min(cs), max(cs)


def _crop(inp, r0, r1, c0, c1, hole=0, keep_bg=False):
    bg = _bg(inp)
    h, w = len(inp), len(inp[0])
    g = []
    for i in range(r0, r1 + 1):
        row = []
        for j in range(c0, c1 + 1):
            if 0 <= i < h and 0 <= j < w:
                c = inp[i][j]
            else:
                c = bg
            row.append(c if (c != bg or keep_bg) else hole)
        g.append(row)
    return g


def keep_bg_in_crop(inp, out):
    r0, r1, c0, c1 = _box(inp)
    return _crop(inp, r0, r1, c0, c1, keep_bg=True)


def hole_color_8(inp, out):
    r0, r1, c0, c1 = _box(inp)
    return _crop(inp, r0, r1, c0, c1, hole=8)


def first_ink_color_only(inp, out):
    bg = _bg(inp)
    cnt = Counter(c for r in inp for c in r if c != bg)
    col = cnt.most_common(1)[0][0]
    ignore = set(cnt) - {col}
    b = _box(inp, ignore)
    return _crop(inp, *b)


def margin_one(inp, out):
    r0, r1, c0, c1 = _box(inp)
    return _crop(inp, r0 - 1, r1 + 1, c0 - 1, c1 + 1)


def drop_last_row(inp, out):
    r0, r1, c0, c1 = _box(inp)
    return _crop(inp, r0, r1 - 1, c0, c1)


def drop_first_col(inp, out):
    r0, r1, c0, c1 = _box(inp)
    return _crop(inp, r0, r1, c0 + 1, c1)


def transposed(inp, out):
    return [list(r) for r in zip(*out)]


def rotated_cw(inp, out):
    return [list(r) for r in zip(*out[::-1])]


def whole_grid_bg_zero(inp, out):
    bg = _bg(inp)
    return [[0 if c == bg else c for c in r] for r in inp]


def single_ink_color(inp, out):
    bg = _bg(inp)
    cnt = Counter(c for r in inp for c in r if c != bg)
    col = cnt.most_common(1)[0][0]
    return [[col if c != 0 else 0 for c in r] for r in out]


def row_span_full_width(inp, out):
    r0, r1, _, _ = _box(inp)
    return _crop(inp, r0, r1, 0, len(inp[0]) - 1)


def col_span_full_height(inp, out):
    _, _, c0, c1 = _box(inp)
    return _crop(inp, 0, len(inp) - 1, c0, c1)


def _differs(f):
    def g(inp, out):
        r = f(inp, out)
        return None if r == out else r
    return g


ALTERNATIVES = [
    ("crop the ink bounding box but leave the background color inside it", keep_bg_in_crop),
    ("crop the bounding box and fill the holes with 8 instead of 0", hole_color_8),
    ("bounding box covers only the most common ink color", first_ink_color_only),
    ("bounding box grown by one cell on every side", margin_one),
    ("bounding box loses its last row", drop_last_row),
    ("bounding box loses its first column", drop_first_col),
    ("correct crop, output transposed", transposed),
    ("correct crop, output rotated 90 degrees clockwise", rotated_cw),
    ("no crop: whole grid with background replaced by 0", whole_grid_bg_zero),
    ("all ink cells recolored to the most common ink color", single_ink_color),
    ("crop only the rows of the ink, keep full grid width", row_span_full_width),
    ("crop only the columns of the ink, keep full grid height", col_span_full_height),
]
ALTERNATIVES = [(d, _differs(f)) for d, f in ALTERNATIVES]


def _valid(g, out):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) for r in g):
        return False
    if len({len(r) for r in g}) != 1 or not g[0]:
        return False
    if not all(isinstance(c, int) and not isinstance(c, bool) and 0 <= c <= 9 for r in g for c in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/a740d043.json'))
    pairs = task["train"]
    print("pairs", len(pairs))
    for desc, f in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = f(p["input"], p["output"])
            if g is not None and _valid(g, p["output"]):
                n += 1
        print(n, desc)
