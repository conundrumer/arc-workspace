import json
from collections import Counter
from pathlib import Path


def _box(inp):
    cnt = Counter(v for r in inp for v in r if v)
    corner = min(cnt, key=lambda c: (cnt[c], c))
    pts = [(i, j) for i, r in enumerate(inp) for j, v in enumerate(r) if v == corner]
    r0 = min(p[0] for p in pts); r1 = max(p[0] for p in pts)
    c0 = min(p[1] for p in pts); c1 = max(p[1] for p in pts)
    return r0, r1, c0, c1


def _shape(inp):
    r0, r1, c0, c1 = _box(inp)
    pts = [(i, j) for i, r in enumerate(inp) for j, v in enumerate(r)
           if v and not (r0 <= i <= r1 and c0 <= j <= c1)]
    a = min(p[0] for p in pts); b = max(p[0] for p in pts)
    c = min(p[1] for p in pts); d = max(p[1] for p in pts)
    return [row[c:d + 1] for row in inp[a:b + 1]]


def _interior(out):
    return [r[1:-1] for r in out[1:-1]]


def _with_interior(out, inter):
    g = [list(r) for r in out]
    for i, row in enumerate(inter):
        for j, v in enumerate(row):
            g[i + 1][j + 1] = v
    return g


def _hflip(g):
    return [r[::-1] for r in g]


def _same_shape(a, b):
    return len(a) == len(b) and len(a[0]) == len(b[0])


def raw_shape(inp, out):
    s = _shape(inp)
    if not _same_shape(s, _interior(out)):
        return None
    return _with_interior(out, s)


def always_flip(inp, out):
    s = _shape(inp)
    if not _same_shape(s, _interior(out)):
        return None
    return _with_interior(out, _hflip(s))


def vflip_interior(inp, out):
    return _with_interior(out, _interior(out)[::-1])


def rot180_interior(inp, out):
    return _with_interior(out, [r[::-1] for r in _interior(out)[::-1]])


def interior_only(inp, out):
    return _interior(out)


def blank_interior(inp, out):
    h, w = len(out) - 2, len(out[0]) - 2
    return _with_interior(out, [[0] * w for _ in range(h)])


def no_corners(inp, out):
    g = [list(r) for r in out]
    for i in (0, -1):
        for j in (0, -1):
            g[i][j] = 0
    return g


def swap_bars(inp, out):
    g = [list(r) for r in out]
    h, w = len(g), len(g[0])
    for i in range(1, h - 1):
        g[i][0], g[i][w - 1] = g[i][w - 1], g[i][0]
    return g


def swap_shape_colors(inp, out):
    inter = _interior(out)
    cols = sorted({v for r in inter for v in r if v})
    if len(cols) != 2:
        return None
    m = {cols[0]: cols[1], cols[1]: cols[0], 0: 0}
    return _with_interior(out, [[m[v] for v in r] for r in inter])


def crop_margin(inp, out):
    r0, r1, c0, c1 = _box(inp)
    r0 = max(r0 - 1, 0); c0 = max(c0 - 1, 0)
    r1 = min(r1 + 1, len(inp) - 1); c1 = min(c1 + 1, len(inp[0]) - 1)
    return [row[c0:c1 + 1] for row in inp[r0:r1 + 1]]


def shape_only(inp, out):
    return _shape(inp)


def shift_interior(inp, out):
    inter = _interior(out)
    return _with_interior(out, [[0] + r[:-1] for r in inter])


ALTERNATIVES = [
    ("shape pasted into the box without reflecting it", raw_shape),
    ("shape always reflected left-right, even when its colors already match the bars", always_flip),
    ("shape reflected top-bottom instead of left-right", vflip_interior),
    ("shape rotated 180 degrees instead of reflected", rot180_interior),
    ("output is only the box interior, without the border bars and corners", interior_only),
    ("box emitted with an empty interior", blank_interior),
    ("corner markers dropped from the box", no_corners),
    ("bar colors on the left and right edges swapped", swap_bars),
    ("shape colors swapped instead of the shape being reflected", swap_shape_colors),
    ("crop taken one cell larger than the box, with the shape left outside", crop_margin),
    ("output is the loose shape cropped, without the box", shape_only),
    ("shape placed one column right of its correct position in the box", shift_interior),
]


def _valid(g, out):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) for r in g):
        return False
    if len({len(r) for r in g}) != 1 or not g[0]:
        return False
    if not all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / 'data/tasks/846bdb03.json').read_text())
    pairs = task["train"]
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g, p["output"]):
                n += 1
        print(n, len(pairs), desc)
