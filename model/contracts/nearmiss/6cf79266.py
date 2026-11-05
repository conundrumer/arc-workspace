import json
from collections import Counter
from pathlib import Path

FILL = 1


def _bg(inp):
    c = Counter(x for r in inp for x in r)
    return min(c, key=lambda k: (c[k], k))


def _windows(inp, k, color, maxbad=0):
    n, m = len(inp), len(inp[0])
    res = []
    for i in range(n - k + 1):
        for j in range(m - k + 1):
            bad = sum(inp[i + a][j + b] != color for a in range(k) for b in range(k))
            if bad <= maxbad:
                res.append((i, j))
    return res


def _paint(inp, cells, color=FILL):
    g = [r[:] for r in inp]
    for i, j in cells:
        if 0 <= i < len(g) and 0 <= j < len(g[0]):
            g[i][j] = color
    return g


def _square(i, j, k):
    return [(i + a, j + b) for a in range(k) for b in range(k)]


def _true_windows(inp):
    return _windows(inp, 3, _bg(inp))


def wrong_color(inp, out):
    # fill with the majority color instead of a new color
    bg = _bg(inp)
    maj = [c for c in set(x for r in inp for x in r) if c != bg][0]
    return [[maj if o != i else o for o, i in zip(ro, ri)] for ro, ri in zip(out, inp)]


def unchanged(inp, out):
    return [r[:] for r in inp]


def size2(inp, out):
    cells = [c for w in _windows(inp, 2, _bg(inp)) for c in _square(*w, 2)]
    return _paint(inp, cells)


def size4_grown(inp, out):
    cells = [c for w in _true_windows(inp) for c in _square(*w, 4)]
    return _paint(inp, cells)


def shifted_right(inp, out):
    cells = [c for w in _true_windows(inp) for c in _square(w[0], w[1] + 1, 3)]
    return _paint(inp, cells)


def first_only(inp, out):
    w = _true_windows(inp)
    if len(w) < 2:
        return None
    return _paint(inp, _square(*w[0], 3))


def majority_squares(inp, out):
    bg = _bg(inp)
    maj = [c for c in set(x for r in inp for x in r) if c != bg][0]
    cells = [c for w in _windows(inp, 3, maj) for c in _square(*w, 3)]
    return _paint(inp, cells)


def full_rows(inp, out):
    g = [r[:] for r in inp]
    for i, j in _true_windows(inp):
        for a in range(3):
            g[i + a] = [FILL] * len(g[0])
    return g


def border_only(inp, out):
    cells = []
    for i, j in _true_windows(inp):
        cells += [c for c in _square(i, j, 3) if c != (i + 1, j + 1)]
    return _paint(inp, cells)


def center_only(inp, out):
    return _paint(inp, [(i + 1, j + 1) for i, j in _true_windows(inp)])


def tolerant_one_bad(inp, out):
    cells = [c for w in _windows(inp, 3, _bg(inp), 2) for c in _square(*w, 3)]
    return _paint(inp, cells)


def mirrored_columns(inp, out):
    m = len(inp[0])
    cells = [c for i, j in _true_windows(inp) for c in _square(i, m - 3 - j, 3)]
    return _paint(inp, cells)


ALTERNATIVES = [
    ("fill the squares with the other input color instead of a new color", wrong_color),
    ("no squares filled, input returned", unchanged),
    ("fill all-background 2x2 windows instead of 3x3", size2),
    ("fill 4x4 blocks starting at each 3x3 window (off-by-one size)", size4_grown),
    ("fill each square shifted one column right", shifted_right),
    ("fill only the first all-background 3x3 square", first_only),
    ("fill 3x3 squares of the other input color instead of the rarest color", majority_squares),
    ("fill the full rows spanned by each square", full_rows),
    ("fill only the border cells of each square, centre left", border_only),
    ("fill only the centre cell of each square", center_only),
    ("accept 3x3 windows with up to two non-background cells", tolerant_one_bad),
    ("fill squares at horizontally mirrored positions", mirrored_columns),
]


def _valid(g, out):
    return (
        isinstance(g, list)
        and len(g) > 0
        and all(isinstance(r, list) and len(r) == len(g[0]) for r in g)
        and all(isinstance(x, int) and 0 <= x <= 9 for r in g for x in r)
        and g != out
    )


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/6cf79266.json"))
    train = task["train"]
    print(len(ALTERNATIVES), "readings,", len(train), "pairs")
    for desc, f in ALTERNATIVES:
        n = 0
        for p in train:
            g = f(p["input"], p["output"])
            if g is not None:
                assert _valid(g, p["output"]), (desc, "invalid grid")
                n += 1
        print(n, desc)
