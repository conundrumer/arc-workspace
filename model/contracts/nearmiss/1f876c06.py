import json
from collections import Counter
from itertools import combinations
from pathlib import Path


def _bg(inp):
    return Counter(v for r in inp for v in r).most_common(1)[0][0]


def _marks(inp):
    bg = _bg(inp)
    return [(i, j, v) for i, r in enumerate(inp) for j, v in enumerate(r) if v != bg]


def _spans(inp, same_color=True, diags=("main", "anti")):
    """List of (color, cells strictly between, endpoint a, endpoint b)."""
    res = []
    for (a, b) in combinations(_marks(inp), 2):
        if same_color and a[2] != b[2]:
            continue
        dr, dc = b[0] - a[0], b[1] - a[1]
        if dr == 0 or abs(dr) != abs(dc):
            continue
        kind = "main" if dr * dc > 0 else "anti"
        if kind not in diags:
            continue
        sr, sc = (dr > 0) - (dr < 0), (dc > 0) - (dc < 0)
        cells = [(a[0] + k * sr, a[1] + k * sc) for k in range(1, abs(dr))]
        res.append((a[2], cells, a, b, (sr, sc)))
    return res


def _paint(inp, spans, color=None):
    g = [r[:] for r in inp]
    for col, cells, *_ in spans:
        for (i, j) in cells:
            g[i][j] = col if color is None else color(col)
    return g


def only_main(inp, out):
    return _paint(inp, _spans(inp, diags=("main",)))


def only_anti(inp, out):
    return _paint(inp, _spans(inp, diags=("anti",)))


def to_edge(inp, out):
    g = [r[:] for r in inp]
    h, w = len(inp), len(inp[0])
    bg = _bg(inp)
    for col, cells, a, b, (sr, sc) in _spans(inp):
        for (p, d) in ((a, (-sr, -sc)), (b, (sr, sc))):
            i, j = p[0] + d[0], p[1] + d[1]
            while 0 <= i < h and 0 <= j < w:
                if g[i][j] == bg:
                    g[i][j] = col
                i, j = i + d[0], j + d[1]
        for (i, j) in cells:
            g[i][j] = col
    return g


def shorter_by_one(inp, out):
    g = [r[:] for r in inp]
    for col, cells, *_ in _spans(inp):
        for (i, j) in cells[:-1]:
            g[i][j] = col
    return g


def rotated_colors(inp, out):
    cols = sorted({v for _, _, v in _marks(inp)})
    if len(cols) < 2:
        return None
    nxt = {c: cols[(k + 1) % len(cols)] for k, c in enumerate(cols)}
    return _paint(inp, _spans(inp), color=lambda c: nxt[c])


def any_color_pairs(inp, out):
    g = [r[:] for r in inp]
    bg = _bg(inp)
    for col, cells, a, b, _ in _spans(inp, same_color=False):
        for (i, j) in cells:
            if g[i][j] == bg:
                g[i][j] = col
    return g if g != out else None


def only_longest(inp, out):
    sp = _spans(inp)
    if not sp:
        return None
    best = max(sp, key=lambda s: len(s[1]))
    return _paint(inp, [best])


def only_lowest_color(inp, out):
    sp = _spans(inp)
    if not sp:
        return None
    m = min(s[0] for s in sp)
    return _paint(inp, [s for s in sp if s[0] == m])


def endpoints_erased(inp, out):
    g = [r[:] for r in out]
    bg = _bg(inp)
    for col, cells, a, b, _ in _spans(inp):
        g[a[0]][a[1]] = bg
        g[b[0]][b[1]] = bg
    return g


def mirrored_fill(inp, out):
    g = [r[:] for r in inp]
    w = len(inp[0])
    for col, cells, *_ in _spans(inp):
        for (i, j) in cells:
            g[i][w - 1 - j] = col
    return g


def fill_with_dominant_mark_color(inp, out):
    cnt = Counter(v for _, _, v in _marks(inp))
    top = cnt.most_common(1)[0][0]
    g = _paint(inp, _spans(inp), color=lambda c: top)
    return g


ALTERNATIVES = [
    ("connect same-color marks along main diagonals only", only_main),
    ("connect same-color marks along anti-diagonals only", only_anti),
    ("extend each connecting diagonal to the grid edge", to_edge),
    ("span stops one cell short of one endpoint", shorter_by_one),
    ("span filled with the next color in sorted order", rotated_colors),
    ("connect any two diagonal marks regardless of color", any_color_pairs),
    ("draw only the longest span", only_longest),
    ("draw only spans of the lowest color value", only_lowest_color),
    ("erase the endpoint marks after drawing", endpoints_erased),
    ("fill cells reflected left-right", mirrored_fill),
    ("fill all spans with one color (the most common mark color)", fill_with_dominant_mark_color),
]


def _valid(g, out):
    if g is None or not isinstance(g, list) or not g:
        return False
    if not all(isinstance(r, list) and len(r) == len(g[0]) for r in g):
        return False
    if not all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/1f876c06.json").read_text())
    train = task["train"]
    # sanity: the reference span painting reproduces the truth
    for p in train:
        assert _paint(p["input"], _spans(p["input"])) == p["output"]
    print("pairs:", len(train))
    for desc, fn in ALTERNATIVES:
        n = sum(_valid(fn(p["input"], p["output"]), p["output"]) for p in train)
        print(n, desc)
