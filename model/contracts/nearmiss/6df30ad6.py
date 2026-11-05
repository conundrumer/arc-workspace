import json
from collections import Counter
from pathlib import Path


def _bg(inp):
    return Counter(v for r in inp for v in r).most_common(1)[0][0]


def _shape_color(inp):
    # the color that is a large block and vanishes: the one color whose cells form
    # the biggest count among non-background colors
    bg = _bg(inp)
    c = Counter(v for r in inp for v in r if v != bg)
    return c.most_common(1)[0][0]


def _shape(inp):
    sc = _shape_color(inp)
    return [(i, j) for i, r in enumerate(inp) for j, v in enumerate(r) if v == sc]


def _dots(inp):
    bg, sc = _bg(inp), _shape_color(inp)
    return [(i, j, v) for i, r in enumerate(inp) for j, v in enumerate(r) if v not in (bg, sc)]


def _true_color(inp, out):
    i, j = _shape(inp)[0]
    return out[i][j]


def _paint(inp, color, cells=None):
    bg = _bg(inp)
    g = [[bg] * len(inp[0]) for _ in inp]
    for i, j in (cells if cells is not None else _shape(inp)):
        g[i][j] = color
    return g


def _dist(cells, i, j, metric):
    if metric == "cheb":
        return min(max(abs(i - a), abs(j - b)) for a, b in cells)
    return min(abs(i - a) + abs(j - b) for a, b in cells)


def _nearest_color(inp, metric, pick):
    sh = _shape(inp)
    ds = [(_dist(sh, i, j, metric), k, v) for k, (i, j, v) in enumerate(_dots(inp))]
    d = min(x[0] for x in ds) if pick == "near" else max(x[0] for x in ds)
    cand = [x for x in ds if x[0] == d]
    return cand[0][2]  # first in scan order


def shape_stays(inp, out):
    sc = _shape_color(inp)
    return _paint(inp, sc)


def most_frequent_dot(inp, out):
    c = Counter(v for _, _, v in _dots(inp))
    m = max(c.values())
    return _paint(inp, max(k for k, n in c.items() if n == m))


def least_frequent_dot(inp, out):
    c = Counter(v for _, _, v in _dots(inp))
    m = min(c.values())
    return _paint(inp, min(k for k, n in c.items() if n == m))


def nearest_cheb_scan_tie(inp, out):
    return _paint(inp, _nearest_color(inp, "cheb", "near"))


def nearest_manhattan_scan_tie(inp, out):
    return _paint(inp, _nearest_color(inp, "manh", "near"))


def farthest_dot(inp, out):
    return _paint(inp, _nearest_color(inp, "cheb", "far"))


def keep_dots(inp, out):
    bg, sc = _bg(inp), _shape_color(inp)
    g = [r[:] for r in out]
    for i, j, v in _dots(inp):
        g[i][j] = v
    return g


def ring_also_filled(inp, out):
    c = _true_color(inp, out)
    sh = set(_shape(inp))
    cells = set(sh)
    h, w = len(inp), len(inp[0])
    for i, j in sh:
        for di in (-1, 0, 1):
            for dj in (-1, 0, 1):
                a, b = i + di, j + dj
                if 0 <= a < h and 0 <= b < w:
                    cells.add((a, b))
    return _paint(inp, c, cells)


def first_dot_in_scan(inp, out):
    return _paint(inp, _dots(inp)[0][2])


def crop_shape(inp, out):
    sh = _shape(inp)
    r0, r1 = min(i for i, _ in sh), max(i for i, _ in sh)
    c0, c1 = min(j for _, j in sh), max(j for _, j in sh)
    c = _true_color(inp, out)
    bg = _bg(inp)
    s = set(sh)
    return [[c if (i, j) in s else bg for j in range(c0, c1 + 1)] for i in range(r0, r1 + 1)]


def nearest_to_centroid(inp, out):
    sh = _shape(inp)
    ci = sum(i for i, _ in sh) / len(sh)
    cj = sum(j for _, j in sh) / len(sh)
    best = min(_dots(inp), key=lambda d: ((d[0] - ci) ** 2 + (d[1] - cj) ** 2))
    return _paint(inp, best[2])


def bbox_filled(inp, out):
    sh = _shape(inp)
    r0, r1 = min(i for i, _ in sh), max(i for i, _ in sh)
    c0, c1 = min(j for _, j in sh), max(j for _, j in sh)
    cells = [(i, j) for i in range(r0, r1 + 1) for j in range(c0, c1 + 1)]
    return _paint(inp, _true_color(inp, out), cells)


def _guard(f):
    def g(inp, out):
        r = f(inp, out)
        return None if r == out else r
    return g


ALTERNATIVES = [
    ("shape keeps its original color instead of being recolored", shape_stays),
    ("shape takes the most frequent dot color in the whole grid", most_frequent_dot),
    ("shape takes the least frequent dot color in the whole grid", least_frequent_dot),
    ("shape takes the color of the nearest dot by 8-neighbor distance, ties by scan order", nearest_cheb_scan_tie),
    ("shape takes the color of the nearest dot by 4-neighbor distance, ties by scan order", nearest_manhattan_scan_tie),
    ("shape takes the color of the farthest dot", farthest_dot),
    ("dots are kept in the output next to the recolored shape", keep_dots),
    ("shape and the ring of cells around it are all filled with the color", ring_also_filled),
    ("shape takes the color of the first dot in scan order", first_dot_in_scan),
    ("output is only the cropped bounding box of the recolored shape", crop_shape),
    ("shape takes the color of the dot nearest its centroid", nearest_to_centroid),
    ("shape is filled to its bounding box", bbox_filled),
]
ALTERNATIVES = [(d, _guard(f)) for d, f in ALTERNATIVES]


def _valid(g, out):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) and r for r in g):
        return False
    if len({len(r) for r in g}) != 1:
        return False
    if not all(type(v) is int and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/6df30ad6.json"))
    pairs = task["train"]
    print("pairs", len(pairs))
    for desc, f in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = f(p["input"], p["output"])
            if g is not None and _valid(g, p["output"]):
                n += 1
        print(n, desc)
